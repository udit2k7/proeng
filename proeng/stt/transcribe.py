"""Speech to text, running entirely on this machine.

Uses faster-whisper: the same Whisper model as OpenAI's, rebuilt on CTranslate2,
which on a CPU is roughly 4x faster and uses about half the RAM. That matters a
lot here - see docs/03-decisions.md D3.

Nothing in this file touches the network except the one-time model download.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from dataclasses import dataclass, replace

import numpy as np

SAMPLE_RATE = 16_000

# Keep downloaded models inside the project rather than in the user's home
# directory, so the whole tool is self-contained: delete this folder and
# nothing is left behind elsewhere on the machine.
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
os.environ.setdefault("HF_HOME", str(MODEL_DIR))
os.environ.setdefault("HF_HUB_CACHE", str(MODEL_DIR / "hub"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


@dataclass
class TranscribeConfig:
    model: str = "base.en"
    # int8 quantisation: ~2x faster on CPU, with accuracy loss small enough
    # that it is not noticeable for dictation.
    compute_type: str = "int8"
    # 0 lets CTranslate2 pick based on the machine. On the i7-1355U that lands
    # around 4 threads, which is about right - it has 2 performance cores and
    # 8 efficiency cores, and piling threads onto the efficiency cores does
    # not help.
    cpu_threads: int = 0

    # "en", "hi" (Hindi), any Whisper language code, or "auto" to detect.
    #
    # IMPORTANT: the ".en" models are English-ONLY. Asking them for Hindi
    # produces silence or nonsense, not an error. `resolve()` below handles
    # that automatically rather than letting it fail silently.
    language: str = "en"

    # Whisper is known to hallucinate text during silence. beam_size 1 (greedy)
    # is faster and, in practice, less prone to inventing words than a wider beam.
    beam_size: int = 1

    # Words Whisper would otherwise mangle, passed as `initial_prompt` to bias
    # decoding towards them - it is how you stop "Groq" coming back as "Grog".
    #
    # KEEP THIS SHORT. `initial_prompt` does not only correct spellings: on
    # unclear audio Whisper will happily INSERT words from it that were never
    # spoken. A long list of exotic terms makes that worse. An earlier version
    # listed "Ollama", and it duly turned up in a transcript where nobody had
    # said it.
    #
    # So: only words that are both frequently spoken here AND reliably
    # mis-heard. If something appears in transcripts unbidden, take it out.
    vocabulary: str = "Groq, Gemini, Claude Code, ChatGPT, Codex, API key, prompt"

    def resolve(self) -> TranscribeConfig:
        """Return a config whose model can actually serve the language asked for.

        An English-only model with language="hi" fails quietly - it emits
        nothing, or invented English. Catching it here turns a baffling bug
        into an automatic correction.
        """
        if self.language in ("en", "english"):
            return self

        if self.model.endswith(".en"):
            multilingual = self.model[:-3]
            return replace(self, model=multilingual)
        return self


@dataclass
class TranscriptResult:
    text: str
    duration: float        # seconds of audio
    elapsed: float         # seconds spent transcribing
    realtime_factor: float # elapsed / duration; below 1.0 is faster than real time


class Transcriber:
    """Wraps a Whisper model. Load once, reuse - loading is the slow part."""

    def __init__(self, config: TranscribeConfig | None = None) -> None:
        # resolve() swaps an English-only model for its multilingual twin when
        # a non-English language is requested.
        self.config = (config or TranscribeConfig()).resolve()
        self._model = None
        # With language="auto", Whisper re-detects on every call. During live
        # previews that is the same work repeated every 1.5 seconds on audio
        # whose language obviously has not changed. Detect once, then pin it.
        self._detected: str | None = None

    def forget_language(self) -> None:
        """Drop the pinned language. Call between recordings.

        Pinning is only safe within one recording - across recordings the user
        may well switch language, which is the whole point of "auto".
        """
        self._detected = None

    def load(self) -> float:
        """Load the model into memory. Returns seconds taken.

        Called explicitly rather than lazily so the caller can show a
        "loading..." message instead of appearing to freeze.
        """
        from faster_whisper import WhisperModel

        start = time.monotonic()
        self._model = WhisperModel(
            self.config.model,
            device="cpu",
            compute_type=self.config.compute_type,
            cpu_threads=self.config.cpu_threads,
            download_root=str(MODEL_DIR / "hub"),
        )
        return time.monotonic() - start

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def transcribe(self, audio: np.ndarray, partial: bool = False) -> TranscriptResult:
        """Transcribe float32 mono 16 kHz audio.

        `partial=True` is for the live-preview pass while the user is still
        speaking. It skips Whisper's VAD filter, because a clip that ends
        mid-sentence often gets trimmed to nothing by it - which is exactly the
        case we want to show text for.
        """
        if self._model is None:
            raise RuntimeError("call load() before transcribe()")

        duration = len(audio) / SAMPLE_RATE
        if duration < 0.3:
            return TranscriptResult("", duration, 0.0, 0.0)

        # "auto" means detect - but only the first time. After that reuse what
        # was found, because re-detecting identical audio every 1.5s is pure
        # waste during live previews.
        if self.config.language == "auto":
            language = self._detected  # None on the first call = detect
        else:
            language = self.config.language

        start = time.monotonic()
        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=self.config.beam_size,
            initial_prompt=self.config.vocabulary or None,
            # Whisper's own VAD, as a second line of defence against it
            # inventing text during the silence at the end of a recording.
            vad_filter=not partial,
            vad_parameters=None if partial else {"min_silence_duration_ms": 500},
            condition_on_previous_text=False,  # stops it looping on repeats
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.monotonic() - start

        # Pin what was detected, but only on a confident result. A doubtful
        # guess from a half-second of audio is worse than detecting again.
        if (
            self.config.language == "auto"
            and self._detected is None
            and getattr(info, "language", None)
            and getattr(info, "language_probability", 0) >= 0.7
        ):
            self._detected = info.language

        return TranscriptResult(
            text=text,
            duration=duration,
            elapsed=elapsed,
            realtime_factor=elapsed / duration if duration > 0 else 0.0,
        )
