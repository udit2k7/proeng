"""Add the ProEng UserPromptSubmit hook to Claude Code's settings.

Merges into the existing settings.json rather than replacing it, so your theme,
permissions and anything else you have configured survive untouched.

    .venv\\Scripts\\python.exe scripts\\install_hook.py           # user-wide
    .venv\\Scripts\\python.exe scripts\\install_hook.py --project # this project only
    .venv\\Scripts\\python.exe scripts\\install_hook.py --remove

A backup is written next to the file before anything changes.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
HOOK_SCRIPT = ROOT / "hooks" / "claude_code_hook.py"
COMMAND = f'"{PYTHON}" "{HOOK_SCRIPT}"'

USER_SETTINGS = Path.home() / ".claude" / "settings.json"
PROJECT_SETTINGS = ROOT / ".claude" / "settings.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: {path} is not valid JSON ({exc}).")
        print("Fix or delete it first - refusing to overwrite something unreadable.")
        sys.exit(1)


def is_ours(entry: dict) -> bool:
    return "claude_code_hook.py" in json.dumps(entry)


def install(path: Path) -> int:
    if not PYTHON.exists():
        print(f"ERROR: {PYTHON} not found. Has the venv been created?")
        return 1
    if not HOOK_SCRIPT.exists():
        print(f"ERROR: {HOOK_SCRIPT} not found.")
        return 1

    settings = load(path)

    if path.exists():
        backup = path.with_suffix(".json.backup")
        shutil.copy2(path, backup)
        print(f"backed up  -> {backup}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"creating   -> {path}")

    hooks = settings.setdefault("hooks", {})
    submit = hooks.setdefault("UserPromptSubmit", [])

    # Drop any previous ProEng entry so re-running never duplicates it.
    before = len(submit)
    submit[:] = [e for e in submit if not is_ours(e)]
    if len(submit) < before:
        print("removed an earlier ProEng hook entry")

    submit.append({
        "hooks": [{
            "type": "command",
            "command": COMMAND,
            "timeout": 15,
        }]
    })

    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"installed  -> {path}")
    print(f"command    -> {COMMAND}")
    print(f"\nOther settings preserved: {', '.join(k for k in settings if k != 'hooks') or '(none)'}")
    return 0


def remove(path: Path) -> int:
    if not path.exists():
        print(f"{path} does not exist - nothing to remove")
        return 0

    settings = load(path)
    submit = settings.get("hooks", {}).get("UserPromptSubmit", [])
    kept = [e for e in submit if not is_ours(e)]

    if len(kept) == len(submit):
        print("no ProEng hook found in that file")
        return 0

    backup = path.with_suffix(".json.backup")
    shutil.copy2(path, backup)
    print(f"backed up  -> {backup}")

    if kept:
        settings["hooks"]["UserPromptSubmit"] = kept
    else:
        settings["hooks"].pop("UserPromptSubmit", None)
        if not settings["hooks"]:
            settings.pop("hooks", None)

    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"removed    -> {path}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    path = PROJECT_SETTINGS if "--project" in args else USER_SETTINGS

    if "--remove" in args:
        return remove(path)

    code = install(path)
    if code == 0:
        print("\nRestart Claude Code, then try:")
        print("  ++ uh I want a dark mode toggle that remembers my choice")
        print("\nWithout the ++ prefix, nothing is changed.")
    return code


if __name__ == "__main__":
    sys.exit(main())
