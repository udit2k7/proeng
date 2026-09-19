"""Command-line entry point: text in, rewritten prompt out.

This is the single engine every surface calls - the desktop widget, the Claude
Code hook, the Codex hook, and any future browser extension. One implementation,
so a fix improves all of them at once. See docs/09-integrations.md.

Usage:
    echo "my rambling text" | python -m proeng.cli
    python -m proeng.cli --target chatgpt < input.txt
    python -m proeng.cli --json            # machine-readable, for hooks

Exit codes:
    0  success (or a graceful fallback - check stderr for which tier answered)
    1  nothing to rewrite
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config as cfgmod
from .rewrite.base import Target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proeng",
        description="Turn rambling dictation into a well-structured prompt.",
    )
    parser.add_argument(
        "--target",
        choices=[t.value for t in Target],
        default=None,
        help="which AI the prompt is for (default: from config.toml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON with the tier and timing, for hooks and scripts",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the tier note on stderr",
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="text to rewrite; if omitted, read from stdin",
    )
    args = parser.parse_args(argv)

    raw = " ".join(args.text) if args.text else sys.stdin.read()
    if not raw.strip():
        print("nothing to rewrite", file=sys.stderr)
        return 1

    cfg = cfgmod.load()
    target = Target(args.target or cfg.default_target)
    router = cfgmod.build_router(cfg)
    result = router.rewrite(raw, target)

    if args.json:
        json.dump(
            {
                "text": result.text,
                "tier": result.tier,
                "elapsed": round(result.elapsed, 3),
                "note": result.note,
                "target": target.value,
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        # Only the prompt goes to stdout, so it can be piped cleanly.
        sys.stdout.write(result.text + "\n")
        if not args.quiet:
            print(
                f"[{result.tier}, {result.elapsed:.2f}s]",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
