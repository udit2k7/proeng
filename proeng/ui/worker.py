"""Background work, kept off the interface thread.

Qt requires all drawing on the main thread. Recording, transcribing and calling
an API are all slow or blocking, so every one of them happens here instead -
otherwise the widget freezes mid-sentence while you are still talking, which is
the single most common way tools like this go wrong (see docs/02-architecture.md).

Communication is by Qt signals only. Nothing here touches a widget directly.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ..audio.recorder import Recorder, RecorderConfig
from ..config import Config, build_router
from ..rewrite.base import Target
from ..stt.transcribe import TranscribeConfig, Transcriber


class DictationWorker(QObject):
    """Runs the whole dictate -> transcribe -> rewrite pipeline."""

    # recording
    level = Signal(float)           # 0.0-1.0 microphone loudness
    countdown = Signal(float)       # seconds left before auto-stop
    recording_started = Signal()
    recording_stopped = Signal(str)  # reason: silence | manual | max_duration

    # transcription
    model_loading = Signal()
    model_loaded = Signal(float)    # seconds taken
    partial = Signal(str)           # live text, while still speaking
    transcribed = Signal(str)       # the final raw text

    # rewriting
    rewriting = Signal()
    rewritten = Signal(str, str, float, str)  # text, tier, elapsed, alert

    failed = Signal(str)
    finished = Signal()

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self._recorder: Recorder | None = None
        self._transcriber: Transcriber | None = None
        # A second, smaller model purely for live previews.
        #
        # The accurate model (`small`, multilingual) runs at ~0.36x realtime on
        # this CPU, which made previews cost more than the gap between them -
        # measured 4.3s for a 12s clip, after which they switched off entirely.
        # `base` is roughly 3x faster and quite good enough for text that is
        # only on screen while you keep talking. The accurate model still
        # produces the final transcript.
        self._preview: Transcriber | None = None
        self._target = Target(cfg.default_target)

    # -- control (safe to call from the UI thread) ----------------------

    def set_target(self, target: Target) -> None:
        self._target = target

    def stop_recording(self) -> None:
        """The Enter-key path. Thread-safe: Recorder.stop() sets an Event."""
        if self._recorder is not None:
            self._recorder.stop()

    def release_model(self) -> None:
        """Drop Whisper from memory - see docs/03-decisions.md D12."""
        self._transcriber = None
        self._preview = None

    @property
    def model_loaded_already(self) -> bool:
        return self._transcriber is not None and self._transcriber.loaded

    # -- the pipeline ---------------------------------------------------

    @Slot()
    def run_dictation(self) -> None:
        """Record, transcribe, rewrite. Runs on the worker thread."""
        try:
            self._ensure_model()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"could not load the speech model: {exc}")
            self.finished.emit()
            return

        try:
            text = self._record_and_transcribe()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"recording failed: {exc}")
            self.finished.emit()
            return

        if not text:
            self.finished.emit()
            return

        self.transcribed.emit(text)
        self.rewrite_text(text)

    @Slot(str)
    def rewrite_text(self, raw: str) -> None:
        """Rewrite text that is already typed or transcribed."""
        if not raw.strip():
            self.finished.emit()
            return

        self.rewriting.emit()
        try:
            router = build_router(self.cfg)
            result = router.rewrite(raw, self._target)
        except Exception as exc:  # noqa: BLE001
            # Never leave the user with nothing: hand back their own words.
            self.rewritten.emit(raw, "none", 0.0, f"rewrite failed: {exc}")
            self.finished.emit()
            return

        self.rewritten.emit(
            result.text or raw, result.tier, result.elapsed, result.alert
        )
        self.finished.emit()

    # -- internals ------------------------------------------------------

    def _ensure_model(self) -> None:
        if self._transcriber is not None and self._transcriber.loaded:
            return
        self.model_loading.emit()
        self._transcriber = Transcriber(
            TranscribeConfig(
                model=self.cfg.speech_model,
                language=self.cfg.speech_language,
            )
        )
        self.model_loaded.emit(self._transcriber.load())

        # Only load a separate preview model if it differs from the main one.
        if self.cfg.preview_model and self.cfg.preview_model != self.cfg.speech_model:
            try:
                self._preview = Transcriber(
                    TranscribeConfig(
                        model=self.cfg.preview_model,
                        language=self.cfg.speech_language,
                    )
                )
                self._preview.load()
            except Exception:
                # A preview model is a nicety. If it will not load, previews
                # fall back to the main model and simply appear less often.
                self._preview = None

    def _emit_partial(self, audio) -> None:
        """Transcribe the audio so far and show it (R4).

        Runs on the recorder's loop, so it must be quick. At the measured
        0.05x realtime a 10s clip costs ~0.5s, which is fine; audio keeps
        buffering meanwhile and nothing is lost.

        Failures are swallowed deliberately - a live preview is a convenience,
        and it must never be the reason a recording dies.
        """
        model = self._preview or self._transcriber
        if model is None:
            return
        try:
            text = model.transcribe(audio, partial=True).text
        except Exception:
            return
        if text:
            self.partial.emit(text)

    def _record_and_transcribe(self) -> str:
        self._recorder = Recorder(
            RecorderConfig(
                silence_timeout=self.cfg.silence_timeout,
                vad_aggressiveness=self.cfg.vad_aggressiveness,
                partial_interval=self.cfg.partial_interval,
                speech_level_threshold=self.cfg.speech_level_threshold,
                partial_window_seconds=self.cfg.partial_window_seconds,
            )
        )
        # Each recording may be in a different language, so a language pinned
        # during the last one must not carry over.
        for model in (self._transcriber, self._preview):
            if model is not None:
                model.forget_language()

        self.recording_started.emit()
        result = self._recorder.record(
            on_level=self.level.emit,
            on_countdown=self.countdown.emit,
            on_partial=self._emit_partial,
        )
        self.recording_stopped.emit(result.stop_reason)

        if not result.speech_detected:
            self.failed.emit("no speech detected - is the microphone muted?")
            return ""

        assert self._transcriber is not None
        return self._transcriber.transcribe(result.audio).text
