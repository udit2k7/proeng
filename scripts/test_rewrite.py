"""Exercise the rewriter on text, with no microphone involved.

Lets the rewrite logic be checked quickly and repeatably. Samples are real
dictation, not invented examples - see docs/04-rewrite-engine.md.

Run:  .venv\\Scripts\\python.exe scripts\\test_rewrite.py
      .venv\\Scripts\\python.exe scripts\\test_rewrite.py chatgpt
      .venv\\Scripts\\python.exe scripts\\test_rewrite.py claude "my own text here"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proeng import config as cfgmod  # noqa: E402
from proeng.rewrite.base import Target  # noqa: E402

# Real dictation collected during this project.
SAMPLES: list[tuple[str, str]] = [
    (
        "the original project pitch",
        "uh so I want to make an offline tool which can be installed on my system "
        "and can uh as I do voice to text and write text as well so sometimes that "
        "is not as much as a good prompt so I want an offline tool which can take "
        "uh my word as I talk or maybe as I write and convert it into a good prompt "
        "for you Claude Code ChatGPT and Gemini I use all three uh so that I can "
        "save tokens because I can think uh that when I give long prompts it "
        "hallucinates and give something that is not as per my requirement",
    ),
    (
        "a short feature request",
        "uh I want to add a dark mode toggle to the settings page it should "
        "remember what I picked last time and don't make it flash white when the "
        "page loads because that is really annoying maybe we can use local storage "
        "I am not sure",
    ),
    (
        "a bug report",
        "so basically the login button is not working on mobile right now it works "
        "fine on desktop but on my phone nothing happens when I tap it I think it "
        "might be the click handler or something give me a fix",
    ),
]


def show(title: str, raw: str, target: Target) -> None:
    cfg = cfgmod.load()
    router = cfgmod.build_router(cfg)
    result = router.rewrite(raw, target)

    print("=" * 66)
    print(f"{title}   ->   {target.label}")
    print("=" * 66)
    print("\nRAW:")
    print(f"  {raw[:300]}{'...' if len(raw) > 300 else ''}")
    print(f"\n  {len(raw.split())} words")

    print(f"\nREWRITTEN  [{result.tier}, {result.elapsed:.2f}s]:")
    print("-" * 66)
    print(result.text if result.text else "  (empty)")
    print("-" * 66)
    print(f"  {len(result.text.split())} words", end="")
    if raw.split():
        delta = len(result.text.split()) / len(raw.split())
        print(f"  ({delta:.0%} of the original)")
    else:
        print()
    if result.note:
        print(f"  note: {result.note}")
    print()


def main() -> int:
    args = sys.argv[1:]
    target = Target.CLAUDE
    if args and args[0] in ("claude", "chatgpt", "gemini"):
        target = Target(args[0])
        args = args[1:]

    if args:
        show("your text", " ".join(args), target)
        return 0

    for title, raw in SAMPLES:
        show(title, raw, target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
