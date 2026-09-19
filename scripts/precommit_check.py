"""Pre-commit check: refuse to commit an API key.

Invoked by .git/hooks/pre-commit. Exits 1 to abort the commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from proeng import security as sec  # noqa: E402


def main() -> int:
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        ).stdout.split()
    except Exception:
        return 0  # never block a commit because our own check broke

    problems = []
    for name in staged:
        path = ROOT / name
        if not path.is_file():
            continue
        if path.name == "config.toml":
            # Should be gitignored; if it is staged, that alone is the problem.
            problems.append((name, "config.toml", "this file holds your keys"))
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for provider, key in sec.find_keys(content):
            if path.name == "config.example.toml" and "..." in key:
                continue
            problems.append((name, provider, sec.redact(key)))

    if not problems:
        return 0

    print("")
    print("=" * 62)
    print("  COMMIT BLOCKED - an API key is staged")
    print("=" * 62)
    for name, provider, detail in problems:
        print(f"  {name}: {provider} {detail}")
    print("")
    print("  Remove it, then commit again.")
    print("  If it was ever pushed, REVOKE the key - assume it is compromised.")
    print("")
    print("  To bypass (only if this is a false positive):")
    print("    git commit --no-verify")
    print("=" * 62)
    print("")
    return 1


if __name__ == "__main__":
    sys.exit(main())
