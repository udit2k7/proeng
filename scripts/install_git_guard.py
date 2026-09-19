"""Install a git pre-commit hook that refuses to commit an API key.

.gitignore protects config.toml. It does nothing about a key pasted into a
script, a note, or a README while debugging - which is how keys usually escape.
This hook blocks the commit itself.

    .venv\\Scripts\\python.exe scripts\\install_git_guard.py

Only useful once this project is a git repository. Safe to run before that -
it will say so and do nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HOOK = r'''#!/bin/sh
# ProEng: block commits containing an API key.
# Installed by scripts/install_git_guard.py
python "$(git rev-parse --show-toplevel)/scripts/precommit_check.py"
'''

CHECKER = '''"""Pre-commit check: refuse to commit an API key.

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
'''


def main() -> int:
    checker = ROOT / "scripts" / "precommit_check.py"
    checker.write_text(CHECKER, encoding="utf-8")
    print(f"wrote {checker.relative_to(ROOT)}")

    git_dir = ROOT / ".git"
    if not git_dir.exists():
        print("\nThis is not a git repository yet, so the hook cannot be installed.")
        print("Run 'git init' first, then run this script again.")
        print("The checker script above is ready for when you do.")
        return 0

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8", errors="ignore")
        if "precommit_check.py" in existing:
            print("pre-commit hook already installed")
            return 0
        backup = hooks_dir / "pre-commit.backup"
        backup.write_text(existing, encoding="utf-8")
        print(f"existing pre-commit hook backed up to {backup.name}")

    hook_path.write_text(HOOK, encoding="utf-8", newline="\n")
    try:
        hook_path.chmod(0o755)
    except Exception:
        pass  # Windows ignores the mode; git for Windows runs it regardless

    print(f"installed {hook_path.relative_to(ROOT)}")
    print("\nCommits containing an API key will now be blocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
