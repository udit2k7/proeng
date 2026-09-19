"""Check that no API key is exposed anywhere it shouldn't be.

Run this any time you are about to publish the project, and after any change
to .gitignore.

    .venv\\Scripts\\python.exe scripts\\audit_keys.py

Checks:
  1. config.toml is in .gitignore
  2. No key appears in any file other than config.toml
  3. No key is in git history (if this is a git repository)
  4. Every configured key is still accepted by its provider

Exit code 1 if anything critical is found, so it can be used in a pre-commit
hook or CI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from proeng import config as cfgmod  # noqa: E402
from proeng import security as sec  # noqa: E402
from proeng.rewrite.keys import KeyRing  # noqa: E402

critical = 0


def report(f: sec.Finding) -> None:
    global critical
    tag = {"critical": "CRITICAL", "warning": "WARN", "ok": "ok"}[f.level]
    print(f"  [{tag:8}] {f.message}")
    if f.fix:
        print(f"             fix: {f.fix}")
    if f.level == "critical":
        critical += 1


def check_git_history() -> None:
    """A key removed from a file still lives in git history forever."""
    if not (ROOT / ".git").exists():
        print("  [ok      ] not a git repository - nothing in history")
        return

    try:
        blob = subprocess.run(
            ["git", "log", "-p", "--all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=60,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN    ] could not read git history: {exc}")
        return

    found = sec.find_keys(blob)
    if not found:
        print("  [ok      ] no keys found in git history")
        return

    global critical
    seen = set()
    for provider, key in found:
        if key in seen:
            continue
        seen.add(key)
        critical += 1
        print(f"  [CRITICAL] {provider} key {sec.redact(key)} is in GIT HISTORY")
        print("             fix: REVOKE that key at the provider immediately.")
        print("             Removing the file does not remove it from history.")


def check_live_keys() -> None:
    """Ask each provider whether the key is still accepted."""
    import httpx

    cfg = cfgmod.load()
    checks = [
        (
            "groq",
            cfg.groq_api_key,
            "https://api.groq.com/openai/v1/models",
            lambda k: {"Authorization": f"Bearer {k}"},
        ),
        (
            "gemini",
            cfg.gemini_api_key,
            "https://generativelanguage.googleapis.com/v1beta/models",
            lambda k: {"x-goog-api-key": k},
        ),
    ]

    global critical
    for name, raw, url, headers in checks:
        ring = KeyRing(raw)
        if not ring:
            print(f"  [ok      ] {name}: no key configured")
            continue
        for key in ring.rotation():
            try:
                r = httpx.get(url, headers=headers(key), timeout=15)
            except Exception as exc:  # noqa: BLE001
                print(f"  [WARN    ] {name} {sec.redact(key)}: no connection ({exc.__class__.__name__})")
                continue
            if r.status_code == 200:
                print(f"  [ok      ] {name} {sec.redact(key)}: accepted")
            elif r.status_code in (401, 403):
                critical += 1
                print(f"  [CRITICAL] {name} {sec.redact(key)}: REJECTED (revoked or invalid)")
                print(f"             fix: .venv\\Scripts\\python.exe scripts\\set_key.py {name}")
            else:
                print(f"  [WARN    ] {name} {sec.redact(key)}: HTTP {r.status_code}")


def main() -> int:
    print("\nKey exposure audit")
    print("=" * 62)

    print("\n1. .gitignore")
    report(sec.check_gitignore(ROOT))

    print("\n2. Keys in project files")
    findings = sec.scan_tree(ROOT)
    if not findings:
        print("  [ok      ] no keys found outside config.toml")
    for f in findings:
        report(f)

    print("\n3. Git history")
    check_git_history()

    print("\n4. Are the configured keys still valid?")
    check_live_keys()

    print("\n" + "=" * 62)
    if critical:
        print(f"{critical} CRITICAL issue(s). Fix before publishing.\n")
        return 1
    print("No key exposure found.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
