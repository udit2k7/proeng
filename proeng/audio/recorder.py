"""Microphone capture with voice-activity-based auto-stop.

The job here is narrow: open the mic, collect audio, and decide when the user
has stopped talking. Deciding *what was said* is someone else's problem
(see proeng/stt/transcribe.py).

The auto-stop rule (requirement R6): stop after SILENCE_TIMEOUT seconds of
continuous non-speech. We use webrtcvad rather than a volume threshold because
fan noise and typing defeat a volume threshold - see docs/03-decisions.md D5.
"""

from __future__ import annotations

import collections
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import sounddevice as sd
import webrtcvad

# webrtcvad only accepts 8/16/32/48 kHz, and frames of exactly 10, 20 or 30 ms.
# Whisper wants 16 kHz mono, so 16 kHz suits both and avoids a resample.
SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples
BYTES_PER_SAMPLE = 2  # int16

# The longest we will ever wait between live previews. Past this, previews are
# too expensive to be worth scheduling at all and are switched off for the rest
# of the recording - see the reasoning in record().
MAX_PARTIAL_GAP = 8.0


@dataclass
class RecorderConfig:
    silence_timeout: float = 7.0
    vad_aggressiveness: int = 2  # 0-3; see docs/03-decisions.md D5
    max_duration: float = 300.0  # hard stop after 5 minutes, as a safety net
    # Require this much speech before the silence timer is allowed to fire, so
    # that a pause while you gather your thoughts at the very start doesn't
    # immediately end the recording.
    min_speech_before_timeout: float = 0.5
    device: int | None = None  # None = system default microphone
    # How often to hand the audio-so-far to a partial-transcription callback,
    # so the user sees words appear while still speaking (R4). 0 disables it.
    #
    # 1.5s is a compromise: shorter feels more live but re-transcribes the whole
    # clip more often, and Whisper needs a second or so of context before it
    # stops guessing.
    partial_interval: float = 1.5
    # Stop previewing once the clip passes this many seconds.
    #
    # Each preview re-transcribes the WHOLE clip, so its cost grows without
    # bound while the interval cannot. Past a point the loop would spend all
    # its time re-reading itself. By 45s you can already see plenty of your own
    # words, and the full transcript arrives when you stop regardless - so
    # previews simply stop earning their cost.
    partial_max_seconds: float = 45.0

    # Minimum loudness (RMS, 0-32768) for speech to count as YOURS.
    #
    # webrtcvad answers "is this speech?", not "is this the person at the
    # microphone?". A colleague talking behind you is speech, so the silence
    # timer never fires and it sits on "listening" forever.
    #
    # Distance is the one signal that separates them: you are close to the mic
    # and loud, they are not. 300 is low enough not to clip a quiet speaker,
    # high enough to ignore a conversation across a room. Raise it in a noisy
    # office, lower it if you get cut off mid-sentence.
    speech_level_threshold: float = 300.0

    # Previews transcribe only the LAST this-many seconds, not the whole clip.
    #
    # Re-reading everything made preview cost grow without limit: measured at
    # 4.3s for a 12s clip with the `small` model, after which previews had to
    # be switched off entirely. A fixed window makes the cost constant however
    # long you talk.
    #
    # The trade: a preview shows recent words rather than everything said so
    # far. That is fine - it is a preview. The final transcript is separate and
    # covers the whole recording.
    partial_window_seconds: float = 8.0


@dataclass
class RecordingResult:
    audio: np.ndarray               # float32, mono, 16 kHz, range -1..1
    duration: float
    stop_reason: str                # "silence" | "manual" | "max_duration"
    speech_detected: bool


class Recorder:
    """Records from the microphone until silence, or until stop() is called.

    Usage:
        rec = Recorder(RecorderConfig())
        result = rec.record(on_level=print_meter, on_countdown=print_countdown)
    """

    def __init__(self, config: RecorderConfig | None = None) -> None:
        self.config = config or RecorderConfig()
        self._vad = webrtcvad.Vad(self.config.vad_aggressiveness)
        self._stop_event = threading.Event()
        self._frames: queue.Queue[bytes] = queue.Queue()

    # -- public ----------------------------------------------------------

    def stop(self) -> None:
        """Request that recording end now (the Enter-key path)."""
        self._stop_event.set()

    def record(
        self,
        on_level: Callable[[float], None] | None = None,
        on_countdown: Callable[[float], None] | None = None,
        on_partial: Callable[[np.ndarray], None] | None = None,
    ) -> RecordingResult:
        """Block until the recording finishes, then return the audio.

        on_level      called with 0.0-1.0 loudness, for a level meter
        on_countdown  called with seconds remaining before auto-stop; called
                      with the full timeout value when speech resumes
        on_partial    called every `partial_interval` seconds with the audio
                      captured so far, so the caller can transcribe it and show
                      words appearing live (R4)

        A note on on_partial: it is called on this thread, so it briefly stalls
        this loop. That is safe - `sounddevice` keeps filling the queue from its
        own thread, so no audio is lost, it is only buffered. But the callback
        must stay well under `partial_interval` or the queue grows without bound.
        """
        self._stop_event.clear()
        while not self._frames.empty():           # drop anything stale
            self._frames.get_nowait()

        collected: list[bytes] = []
        started = time.monotonic()
        last_speech_at: float | None = None
        speech_seconds = 0.0
        stop_reason = "manual"
        last_partial_at = started
        # Grows if previews start costing too much - see the backoff below.
        partial_every = self.config.partial_interval
        partials_affordable = True

        # A short ring buffer of recent VAD verdicts. Judging silence on a
        # single 30 ms frame is far too twitchy - a brief gap between words
        # would register as silence. Smoothing over ~300 ms tracks the way
        # people actually speak.
        recent = collections.deque(maxlen=10)

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            device=self.config.device,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        ):
            while True:
                if self._stop_event.is_set():
                    stop_reason = "manual"
                    break

                elapsed = time.monotonic() - started
                if elapsed > self.config.max_duration:
                    stop_reason = "max_duration"
                    break

                try:
                    frame = self._frames.get(timeout=0.1)
                except queue.Empty:
                    continue

                collected.append(frame)

                samples = np.frombuffer(frame, dtype=np.int16)
                # RMS, scaled so ordinary speech lands near the top of the
                # meter rather than as a barely visible wiggle.
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
                if on_level is not None:
                    on_level(min(1.0, rms / 3000.0))

                # Both tests must pass: it has to sound like speech AND be
                # close enough to be the person at the microphone. Either alone
                # is insufficient - VAD alone hears the room, loudness alone
                # hears a door slam.
                is_speech = (
                    rms >= self.config.speech_level_threshold
                    and self._is_speech(frame)
                )
                recent.append(is_speech)
                # Any speech at all in the recent window counts as "still talking".
                talking = any(recent)

                now = time.monotonic()
                if talking:
                    speech_seconds += FRAME_MS / 1000.0
                    last_speech_at = now
                    if on_countdown is not None:
                        on_countdown(self.config.silence_timeout)
                elif last_speech_at is not None:
                    quiet_for = now - last_speech_at
                    remaining = self.config.silence_timeout - quiet_for
                    if on_countdown is not None:
                        on_countdown(max(0.0, remaining))
                    if (
                        remaining <= 0
                        and speech_seconds >= self.config.min_speech_before_timeout
                    ):
                        stop_reason = "silence"
                        break

                # Live transcription (R4): hand the audio so far to the caller
                # periodically, so words appear while the user is still talking.
                # Only once there is something worth transcribing - running
                # Whisper on half a second of audio produces confident nonsense.
                clip_seconds = (
                    len(collected) * FRAME_SAMPLES / SAMPLE_RATE
                )
                if (
                    on_partial is not None
                    and self.config.partial_interval > 0
                    and partials_affordable
                    and speech_seconds >= 0.8
                    and clip_seconds <= self.config.partial_max_seconds
                    and now - last_partial_at >= partial_every
                ):
                    partial_started = time.monotonic()
                    # Only the tail, so cost does not grow with the recording.
                    window = self.config.partial_window_seconds
                    frames_needed = int(
                        window * SAMPLE_RATE / FRAME_SAMPLES
                    ) if window > 0 else len(collected)
                    tail = collected[-frames_needed:] if frames_needed else collected
                    on_partial(self._to_float32(b"".join(tail)))
                    took = time.monotonic() - partial_started
                    last_partial_at = time.monotonic()

                    # Each preview re-transcribes the WHOLE clip, so its cost
                    # grows as you keep talking. Left alone, a long dictation
                    # would spend most of its time re-reading itself.
                    #
                    # Rather than react after an overshoot, predict the next
                    # cost. We know what this one cost for this much audio, so
                    # we know roughly the machine's speed, and we know the clip
                    # will be one interval longer next time. Schedule so that
                    # previews never take more than a third of the gap.
                    measured = min(clip_seconds, self.config.partial_window_seconds)                         if self.config.partial_window_seconds > 0 else clip_seconds
                    if measured > 0:
                        speed = took / measured  # work per second of audio
                        # With a window, the next preview reads the same amount
                        # again - the cost is flat, not growing.
                        predicted = measured * speed
                        # Previews may take up to half the gap.
                        #
                        # This was a third, back when cost grew with the clip
                        # and headroom was the only defence against a runaway.
                        # A fixed window removes that risk, and a third made
                        # previews appear every ~7s - technically working,
                        # but too slow to feel live. Half gives ~2s.
                        wanted = predicted * 2

                        if wanted > MAX_PARTIAL_GAP:
                            # We cannot schedule this cheaply enough any more.
                            #
                            # Capping the gap here instead would be the trap:
                            # cost keeps growing while the gap cannot, so
                            # previews would eventually take longer than the
                            # space between them and the audio queue would grow
                            # without bound. On a slow machine that is a
                            # runaway, not a slowdown.
                            #
                            # Stopping is the honest response. You keep every
                            # word - the full transcript still arrives when you
                            # stop speaking - you simply stop seeing it early.
                            partials_affordable = False
                        else:
                            partial_every = max(
                                self.config.partial_interval, wanted
                            )

        audio = self._to_float32(b"".join(collected))
        return RecordingResult(
            audio=audio,
            duration=len(audio) / SAMPLE_RATE,
            stop_reason=stop_reason,
            speech_detected=speech_seconds >= self.config.min_speech_before_timeout,
        )

    # -- internals -------------------------------------------------------

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        # Runs on the audio thread. Do nothing slow here: blocking this
        # callback drops audio. Copy the bytes out and leave.
        self._frames.put(bytes(indata))

    def _is_speech(self, frame: bytes) -> bool:
        if len(frame) != FRAME_SAMPLES * BYTES_PER_SAMPLE:
            return False  # a partial frame at the tail; webrtcvad would reject it
        try:
            return self._vad.is_speech(frame, SAMPLE_RATE)
        except Exception:
            return False

    @staticmethod
    def _to_float32(raw: bytes) -> np.ndarray:
        if not raw:
            return np.zeros(0, dtype=np.float32)
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def list_microphones() -> list[tuple[int, str, int]]:
    """Return (index, name, channels) for every input device."""
    out = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            out.append((i, dev["name"], dev["max_input_channels"]))
    return out


def default_microphone() -> tuple[int, str] | None:
    try:
        idx = sd.default.device[0]
        if idx is None or idx < 0:
            return None
        return idx, sd.query_devices(idx)["name"]
    except Exception:
        return None
