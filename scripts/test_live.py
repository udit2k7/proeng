"""Does live transcription actually fire? Speak and watch.

The preview path has several gates - enough speech, loud enough, clip short
enough, previews still affordable. This prints what each one decided, so a
silent preview can be diagnosed rather than guessed at.

Records until you go quiet (the configured silence timeout) or Ctrl+C.

Run:  .venv\\Scripts\\python.exe scripts\\test_live.py
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def say(*args) -> None:
    # Unbuffered: a crash must not swallow the last thing printed.
    print(*args, flush=True)


def main() -> int:
    from proeng.audio.recorder import Recorder, RecorderConfig
    from proeng.config import load
    from proeng.stt.transcribe import TranscribeConfig, Transcriber

    cfg = load()
    say("")
    say("Live transcription check")
    say("=" * 60)
    say(f"  model             : {cfg.speech_model}")
    say(f"  language          : {cfg.speech_language}")
    say(f"  preview model     : {cfg.preview_model}")
    say(f"  preview every     : {cfg.partial_interval}s")
    say(f"  preview window    : {cfg.partial_window_seconds}s")
    say(f"  loudness threshold: {cfg.speech_level_threshold}")
    say(f"  silence timeout   : {cfg.silence_timeout}s")

    tcfg = TranscribeConfig(model=cfg.speech_model, language=cfg.speech_language)
    resolved = tcfg.resolve()
    if resolved.model != tcfg.model:
        say(f"  resolved model    : {resolved.model} (multilingual)")

    say("\nLoading the accurate model (used for the final transcript)...")
    tr = Transcriber(tcfg)
    say(f"  loaded in {tr.load():.1f}s")

    # A second, faster model for previews. The accurate one is too slow to
    # re-run every 1.5s on a laptop CPU - measured 4.3s for a 12s clip.
    preview = tr
    if cfg.preview_model and cfg.preview_model != cfg.speech_model:
        say(f"Loading the fast preview model ({cfg.preview_model})...")
        preview = Transcriber(
            TranscribeConfig(
                model=cfg.preview_model, language=cfg.speech_language
            )
        )
        say(f"  loaded in {preview.load():.1f}s")

    rec = Recorder(
        RecorderConfig(
            silence_timeout=cfg.silence_timeout,
            vad_aggressiveness=cfg.vad_aggressiveness,
            partial_interval=cfg.partial_interval,
            speech_level_threshold=cfg.speech_level_threshold,
            partial_window_seconds=cfg.partial_window_seconds,
        )
    )

    say("\n" + "=" * 60)
    say("SPEAK NOW. Keep talking for 15 seconds or so.")
    say("Previews should appear every ~1.5s WITHOUT you stopping.")
    say(f"It stops on its own after {cfg.silence_timeout:.0f}s of quiet.")
    say("Ctrl+C to give up.")
    say("=" * 60 + "\n")

    started = time.monotonic()
    previews: list[float] = []
    peak = {"level": 0.0, "any_sound": False}
    heartbeat = {"last": 0.0}

    def on_level(v: float) -> None:
        peak["level"] = max(peak["level"], v)
        if v > 0.01:
            peak["any_sound"] = True
        # Prove it is alive even when nothing else is happening.
        now = time.monotonic() - started
        if now - heartbeat["last"] >= 2.0:
            heartbeat["last"] = now
            bar = "|" * int(v * 20) + "." * (20 - int(v * 20))
            say(f"  [{now:5.1f}s] mic [{bar}] {v:.2f}   previews so far: {len(previews)}")

    def on_partial(audio) -> None:
        at = time.monotonic() - started
        previews.append(at)
        t0 = time.monotonic()
        try:
            text = preview.transcribe(audio, partial=True).text
        except Exception as exc:  # noqa: BLE001
            say(f"  [{at:5.1f}s] PREVIEW FAILED: {exc}")
            return
        took = time.monotonic() - t0
        clip = len(audio) / 16_000
        say(f"  [{at:5.1f}s] PREVIEW  clip={clip:4.1f}s  cost={took:4.2f}s")
        say(f"           -> {text[:110] or '(nothing recognised yet)'}")

    try:
        result = rec.record(on_level=on_level, on_partial=on_partial)
    except KeyboardInterrupt:
        say("\n  cancelled")
        return 0
    except Exception:
        say("\n  RECORDING CRASHED:")
        traceback.print_exc()
        return 1

    say("\n" + "=" * 60)
    say(f"  stopped after {result.duration:.1f}s ({result.stop_reason})")
    say(f"  previews fired : {len(previews)}")
    say(f"  peak mic level : {peak['level']:.2f} of 1.00")
    say(f"  speech detected: {result.speech_detected}")

    if result.speech_detected:
        final = tr.transcribe(result.audio)
        say(f"\nFinal transcript ({final.elapsed:.1f}s):")
        say(f"  {final.text or '(nothing)'}")

    say("\nVerdict:")
    if result.duration < 1.0:
        say("  INCONCLUSIVE - the recording lasted under a second.")
        say("  Something stopped it immediately. Run it again and speak.")
    elif not peak["any_sound"]:
        say("  FAIL - the microphone produced no sound at all.")
        say("  Check Windows Settings > Privacy > Microphone, and that the")
        say("  right input device is the default.")
    elif not result.speech_detected:
        say(f"  FAIL - sound was heard (peak {peak['level']:.2f}) but none of it")
        say("  counted as speech.")
        say(f"  The loudness threshold is {cfg.speech_level_threshold:.0f}.")
        say("  Your peak of "
            f"{peak['level']:.2f} maps to roughly {peak['level'] * 3000:.0f} RMS.")
        if peak["level"] * 3000 < cfg.speech_level_threshold:
            say("  -> That is BELOW the threshold. Lower speech_level_threshold")
            say("     in config.toml, or use the gear button in the widget.")
        else:
            say("  -> Loud enough, so the voice detector rejected it as noise.")
            say("     Try vad_aggressiveness = 1 in config.toml.")
    elif len(previews) == 0:
        say("  FAIL - speech was heard, but no previews fired.")
        say("  Either you spoke for under ~2s, or partial_interval is 0.")
    elif len(previews) == 1 and result.duration > 6:
        say("  PARTIAL - only one preview in a long recording.")
        say("  Previews became unaffordable. Set a faster preview_model")
        say("  (tiny) or a shorter partial_window_seconds in config.toml.")
    else:
        rate = result.duration / len(previews)
        say(f"  PASS - {len(previews)} previews in {result.duration:.0f}s "
            f"(one every {rate:.1f}s).")
        say("  Live transcription is working.")
    say("")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\ncancelled")
        sys.exit(0)
