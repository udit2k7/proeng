"""Check the live-transcription scheduling without needing a microphone.

Previews read a fixed WINDOW of recent audio, so their cost stays constant
however long you talk. (They used to read the whole clip, which made the cost
grow without bound - measured at 4.3s for a 12s clip, after which previews had
to switch themselves off. See D24.)

The schedule still has to adapt: a slower machine or a heavier model makes each
preview dearer, and past a point they are not worth running at all.

This simulates the policy in Recorder.record over simulated time, so the
behaviour can be checked before asking a human to talk at it.

Run:  .venv\\Scripts\\python.exe scripts\\test_partials.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from proeng.audio.recorder import RecorderConfig  # noqa: E402

CFG = RecorderConfig()
CEILING = 8.0  # the min(..., 8.0) in the recorder


@dataclass
class Preview:
    at: float        # when it happened, seconds into the recording
    clip: float      # how much audio existed then
    cost: float      # how long transcribing it took
    interval: float  # the gap that preceded it

    @property
    def ratio(self) -> float:
        return self.cost / self.interval


def simulate(speed: float, total: float = 120.0) -> list[Preview]:
    """Step through a recording, applying the recorder's own scheduling rule.

    `speed` is seconds of transcription work per second of audio - 0.05 on this
    laptop, measured in Phase 1.
    """
    previews: list[Preview] = []
    partial_every = CFG.partial_interval
    affordable = True
    now = 0.0

    while now < total:
        now += partial_every
        clip = now
        if clip > CFG.partial_max_seconds or not affordable:
            break

        window = min(clip, CFG.partial_window_seconds) if CFG.partial_window_seconds else clip
        cost = window * speed
        previews.append(Preview(now, clip, cost, partial_every))

        # The rule from Recorder.record: previews read a fixed window, so the
        # next one costs the same again. Keep them to half the gap; if that gap
        # would exceed the ceiling, previews stop for good.
        observed = cost / window          # work per second of audio read
        predicted = window * observed     # i.e. the same cost again
        wanted = predicted * 2
        if wanted > CEILING:
            affordable = False
        else:
            partial_every = max(CFG.partial_interval, wanted)

    return previews


def report(name: str, speed: float) -> tuple[bool, str]:
    previews = simulate(speed)
    print(f"\n{name} ({speed:.2f}x realtime):")
    print(f"  {'at':>6}  {'clip':>6}  {'cost':>6}  {'gap':>6}  {'ratio':>6}")
    for p in previews:
        print(
            f"  {p.at:>5.1f}s  {p.clip:>5.1f}s  {p.cost:>5.2f}s  "
            f"{p.interval:>5.2f}s  {p.ratio:>5.2f}"
        )

    if not previews:
        return False, "no previews at all"

    worst = max(p.ratio for p in previews)
    busy = sum(p.cost for p in previews) / previews[-1].at
    print(f"  worst ratio: {worst:.2f}   overall time spent previewing: {busy:.0%}")
    return worst, busy


def main() -> int:
    print("\nLive-transcription scheduling")
    print("=" * 62)
    print(f"  interval {CFG.partial_interval}s, stop previewing after "
          f"{CFG.partial_max_seconds:.0f}s of audio")

    ok = True

    worst, busy = report("This laptop", 0.05)
    if worst > 0.55:
        print("  FAIL - a preview took over half its interval")
        ok = False
    elif busy > 0.35:
        print("  FAIL - too much of the recording spent previewing")
        ok = False
    else:
        print("  PASS - previews stay comfortably affordable")

    worst, busy = report("A 5x slower machine", 0.25)
    if busy > 0.6:
        print("  FAIL - previews would dominate the recording")
        ok = False
    else:
        print("  PASS - backoff keeps it survivable")

    worst, busy = report("An absurdly slow machine", 1.0)
    print("  (here each preview costs as much as the audio it reads)")
    if worst > 4.0:
        print("  FAIL - runaway; the queue would grow unbounded")
        ok = False
    else:
        print("  PASS - the 8s ceiling and 45s cutoff contain it")

    print("\n" + "=" * 62)
    if ok:
        print("scheduling policy OK\n")
    else:
        print("PROBLEMS FOUND\n")
    print("This tests the schedule, not the transcription. For that, speak into:")
    print("  .venv\\Scripts\\python.exe -m proeng\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
