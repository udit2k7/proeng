"""Download the Whisper model and measure how fast it runs on this CPU.

Uses synthetic audio, so it says nothing about accuracy - only about speed.
Accuracy gets checked by actually speaking into scripts/phase1_test.py.

Run:  .venv\\Scripts\\python.exe scripts\\bench_whisper.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proeng.stt.transcribe import SAMPLE_RATE, TranscribeConfig, Transcriber  # noqa: E402

MODELS = ["base.en"]  # add "small.en" here to compare


def fake_speech(seconds: float) -> np.ndarray:
    """Noise roughly shaped like speech: a few formant-ish tones, amplitude
    modulated at syllable rate. Enough to give the model real work to do."""
    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    sig = np.zeros_like(t)
    for f in (120, 400, 900, 1800, 2600):
        sig += np.sin(2 * np.pi * f * t) / f**0.5
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t)  # ~4 syllables/sec
    sig *= envelope
    sig += np.random.normal(0, 0.01, sig.shape)
    peak = np.max(np.abs(sig))
    return (sig / peak * 0.3).astype(np.float32)


def main() -> int:
    print()
    for name in MODELS:
        print(f"Model: {name}")
        print("-" * 46)
        tr = Transcriber(TranscribeConfig(model=name))

        print("  downloading / loading ...", flush=True)
        t0 = time.monotonic()
        try:
            load_s = tr.load()
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            return 1
        print(f"  load: {load_s:.1f}s  (first run includes the download)")

        for seconds in (5.0, 15.0, 30.0):
            audio = fake_speech(seconds)
            r = tr.transcribe(audio)
            verdict = "faster than realtime" if r.realtime_factor < 1 else "SLOWER than realtime"
            print(
                f"  {seconds:4.0f}s audio -> {r.elapsed:5.1f}s  "
                f"({r.realtime_factor:.2f}x, {verdict})"
            )

        del tr
        print(f"  total: {time.monotonic() - t0:.1f}s\n")

    print("What this means:")
    print("  A 30s dictation is a long prompt. If that transcribes in a")
    print("  few seconds, Phase 1 is comfortably viable on this laptop.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
