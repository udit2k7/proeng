"""Register the ProEng rewriter with Codex.

    .venv\\Scripts\\python.exe scripts\\install_codex_hook.py
    .venv\\Scripts\\python.exe scripts\\install_codex_hook.py --remove

WHAT IS UNCERTAIN HERE
----------------------
The documented hook system belongs to the Codex **CLI**, which registers hooks
in ~/.codex/hooks.json. This machine has the Codex **desktop app**, and whether
that reads the same file is not documented anywhere I could find.

Rather than assert it works, this installs it with logging switched on, so a
single test answers the question. If ~/.codex/proeng-hook.log gains entries
when you type `++`, it works. If the file never appears, the desktop app does
not read hooks.json, and the answer is the desktop widget instead.

That is the same approach that found the Claude Code problem (D23): measure,
do not assume.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CODEX_HOME = Path.home() / ".codex"
HOOKS_FILE = CODEX_HOME / "hooks.json"
LOG_FILE = CODEX_HOME / "proeng-hook.log"

# The zero-dependency hook, so it runs under whatever Python Codex can see -
# not the project's venv, which Codex knows nothing about.
HOOK_SCRIPT = ROOT / "plugin" / "scripts" / "rewrite_hook.py"


def entry() -> dict:
    return {
        "hooks": [
            {
                "type": "command",
                "command": f'python "{HOOK_SCRIPT}"',
                "timeout": 20,
                # Logging on by default here, because the whole point of this
                # installation is to find out whether it runs at all.
                "env": {
                    "PROENG_LOG": str(LOG_FILE),
                    # The same checkout Claude Code uses, so both share one
                    # config.toml and one set of keys. The script can find it
                    # unaided, but being explicit costs nothing and survives
                    # the folder being moved.
                    "PROENG_HOME": str(ROOT),
                },
            }
        ]
    }


def is_ours(obj) -> bool:
    return "rewrite_hook.py" in json.dumps(obj)


def load() -> dict:
    if not HOOKS_FILE.exists():
        return {}
    try:
        return json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: {HOOKS_FILE} is not valid JSON ({exc}).")
        print("Fix or delete it first - refusing to overwrite something unreadable.")
        sys.exit(1)


def install() -> int:
    if not CODEX_HOME.exists():
        print(f"{CODEX_HOME} does not exist - is Codex installed?")
        return 1
    if not HOOK_SCRIPT.exists():
        print(f"ERROR: {HOOK_SCRIPT} not found.")
        return 1

    data = load()
    if HOOKS_FILE.exists():
        backup = HOOKS_FILE.with_suffix(".json.backup")
        shutil.copy2(HOOKS_FILE, backup)
        print(f"backed up  -> {backup}")

    hooks = data.setdefault("hooks", {})
    submit = hooks.setdefault("UserPromptSubmit", [])
    before = len(submit)
    submit[:] = [e for e in submit if not is_ours(e)]
    if len(submit) < before:
        print("removed an earlier ProEng entry")
    submit.append(entry())

    HOOKS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"installed  -> {HOOKS_FILE}")
    print(f"log        -> {LOG_FILE}")

    print("\nNow RESTART Codex, then type a prompt starting with ++")
    print("\nThen check whether it ran:")
    print(f"  type \"{LOG_FILE}\"")
    print("\n  entries appear  -> it works")
    print("  file is missing -> the desktop app does not read hooks.json;")
    print("                     use the ProEng widget instead and paste")
    return 0


def remove() -> int:
    if not HOOKS_FILE.exists():
        print(f"{HOOKS_FILE} does not exist - nothing to remove")
        return 0

    data = load()
    submit = data.get("hooks", {}).get("UserPromptSubmit", [])
    kept = [e for e in submit if not is_ours(e)]
    if len(kept) == len(submit):
        print("no ProEng hook found")
        return 0

    shutil.copy2(HOOKS_FILE, HOOKS_FILE.with_suffix(".json.backup"))
    if kept:
        data["hooks"]["UserPromptSubmit"] = kept
    else:
        data["hooks"].pop("UserPromptSubmit", None)
        if not data["hooks"]:
            data.pop("hooks", None)

    HOOKS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"removed    -> {HOOKS_FILE}")
    return 0


def main() -> int:
    if "--remove" in sys.argv[1:]:
        return remove()
    return install()


if __name__ == "__main__":
    sys.exit(main())
