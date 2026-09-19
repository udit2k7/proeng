"""Show the context around a scanner hit, so it can be judged rather than feared.

A pattern match is a question, not a verdict. "YOUR_API_KEY_HERE" matches the
same regex as a real credential. This prints the surrounding code and the
commit it came from, with the secret itself redacted, so you can tell which
you are looking at.

Usage:
    triage_finding.py owner/repo <4-char-prefix> <4-char-suffix>
    triage_finding.py myorg/myrepo AIza wXyZ
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def redact(s: str) -> str:
    return re.sub(
        r"\b([A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]{12,}([A-Za-z0-9_\-]{4})\b",
        r"\1...\2",
        s,
    )


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    slug, prefix, suffix = sys.argv[1], sys.argv[2], sys.argv[3]

    work = Path(tempfile.mkdtemp(prefix="triage_"))
    dest = work / "r"
    print(f"cloning {slug}...", flush=True)
    subprocess.run(
        ["git", "clone", "--quiet", "--filter=blob:limit=1m",
         f"https://github.com/{slug}.git", str(dest)],
        capture_output=True, timeout=900,
    )
    if not dest.exists():
        print("clone failed")
        return 1

    pattern = re.compile(
        re.escape(prefix) + r"[A-Za-z0-9_\-\.]*" + re.escape(suffix)
    )

    print(f"\nlooking for {prefix}...{suffix}\n")
    log = subprocess.run(
        ["git", "log", "--all", "-p", "--no-color"],
        cwd=dest, capture_output=True, text=True, errors="ignore", timeout=900,
    ).stdout

    shown = 0
    commit = ""
    filename = ""
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line.split()[1][:8]
        elif line.startswith("+++ b/"):
            filename = line[6:]
        elif pattern.search(line):
            shown += 1
            print(f"  commit {commit}  {filename}")
            print(f"    {redact(line.strip())[:190]}")
            print()
            if shown >= 6:
                break

    if not shown:
        print("  not found in history diffs (may be in a skipped large blob)")

    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
