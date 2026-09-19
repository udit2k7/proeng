"""Phase 1 check: does voice capture, silence detection and transcription
actually work on this laptop?

No interface. The point is to prove the risky parts before building anything
around them - see docs/07-roadmap.md.

Run:  python scripts/phase1_test.py
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

# Windows without Developer Mode can't make symlinks, so the HuggingFace cache
# prints a warning on every run. The fallback it uses works fine; silence it.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proeng.audio.recorder import (  # noqa: E402
    Recorder,
    RecorderConfig,
    default_microphone,
    list_microphones,
)
from proeng.stt.transcribe import TranscribeConfig, Transcriber  # noqa: E402

BAR_WIDTH = 24


def draw_status(level: float, countdown: float, timeout: float) -> None:
    filled = int(level * BAR_WIDTH)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    if countdown >= timeout - 0.01:
        tail = "speaking    "
    else:
        tail = f"silence {countdown:4.1f}s"
    print(f"\r  [{bar}] {tail}", end="", flush=True)


def main() -> int:
    # Optional: pick a model / mic from the command line, so different
    # settings can be compared without editing code.
    #   python scripts/phase1_test.py small.en
    #   python scripts/phase1_test.py small.en 5
    model = sys.argv[1] if len(sys.argv) > 1 else "base.en"
    device = int(sys.argv[2]) if len(sys.argv) > 2 else None

    print()
    print("ProEng - Phase 1 check")
    print("=" * 52)

    mics = list_microphones()
    if not mics:
        print("\n  No microphone found.")
        print("  Check Settings > Privacy & security > Microphone.")
        return 1

    print("\nInput devices:")
    for idx, name, ch in mics:
        print(f"  [{idx}] {name} ({ch} ch)")

    default = default_microphone()
    print(f"\nUsing: {default[1] if default else 'system default'}")

    cfg = TranscribeConfig(model=model)
    print(f"\nLoading Whisper '{cfg.model}' ...")
    print("  (first run downloads ~150 MB; later runs are instant)")
    transcriber = Transcriber(cfg)
    try:
        load_time = transcriber.load()
    except Exception as exc:
        print(f"\n  Failed to load the model: {exc}")
        return 1
    print(f"  loaded in {load_time:.1f}s")

    rec_cfg = RecorderConfig(device=device)
    recorder = Recorder(rec_cfg)

    print("\n" + "=" * 52)
    print("Speak when ready.")
    print(f"Stops automatically after {rec_cfg.silence_timeout:.0f}s of silence,")
    print("or press Enter to stop now.")
    print("=" * 52 + "\n")

    # Watch for Enter on a background thread so it can interrupt the recording.
    def wait_for_enter() -> None:
        try:
            input()
            recorder.stop()
        except (EOFError, KeyboardInterrupt):
            pass

    threading.Thread(target=wait_for_enter, daemon=True).start()

    state = {"level": 0.0, "countdown": rec_cfg.silence_timeout}

    def on_level(v: float) -> None:
        state["level"] = v
        draw_status(v, state["countdown"], rec_cfg.silence_timeout)

    def on_countdown(v: float) -> None:
        state["countdown"] = v

    try:
        result = recorder.record(on_level=on_level, on_countdown=on_countdown)
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        return 0
    except Exception as exc:
        print(f"\n\n  Recording failed: {exc}")
        return 1

    print("\r" + " " * 60 + "\r", end="")
    print(f"  Stopped: {result.stop_reason} after {result.duration:.1f}s\n")

    if not result.speech_detected:
        print("  No speech detected. Is the right microphone selected,")
        print("  and is it unmuted?")
        return 1

    print("  Transcribing ...")
    tr = transcriber.transcribe(result.audio)

    print("\n" + "=" * 52)
    print("TRANSCRIPT")
    print("=" * 52)
    print(tr.text if tr.text else "  (nothing recognised)")
    print("=" * 52)

    print(f"\n  audio     : {tr.duration:.1f}s")
    print(f"  transcribe: {tr.elapsed:.1f}s")
    print(f"  speed     : {tr.realtime_factor:.2f}x realtime", end="")
    print("  (under 1.00 is faster than real time)")

    print("\n  Phase 1 verdict:")
    ok_stop = result.stop_reason in ("silence", "manual")
    ok_text = bool(tr.text)
    ok_speed = tr.realtime_factor < 1.0
    print(f"    capture + auto-stop : {'PASS' if ok_stop else 'FAIL'}")
    print(f"    transcription       : {'PASS' if ok_text else 'FAIL'}")
    print(f"    speed usable        : {'PASS' if ok_speed else 'SLOW'}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
