"""Test the Claude Code hook, including every failure path.

The failure paths matter more than the happy path: the hook sits in front of
every prompt the user types, so it must never eat one.

Run:  .venv\\Scripts\\python.exe scripts\\test_hook.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "claude_code_hook.py"
PY = ROOT / ".venv" / "Scripts" / "python.exe"


def run(stdin_text: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(PY), str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


CASES: list[tuple[str, str, str]] = [
    (
        "no prefix - must pass through untouched",
        json.dumps({"prompt": "run the tests"}),
        "passthrough",
    ),
    (
        "short confirmation - must pass through",
        json.dumps({"prompt": "yes"}),
        "passthrough",
    ),
    (
        "with prefix - must rewrite",
        json.dumps({"prompt": "++ uh I want to add a dark mode toggle to the "
                              "settings page it should remember what I picked "
                              "last time and don't make it flash white"}),
        "rewritten",
    ),
    (
        "non-technical request - must rewrite without technical framing",
        json.dumps({"prompt": "++ uh I want to write a short story about a "
                              "lighthouse keeper set in Scotland in the 1890s "
                              "and the tone should be melancholy"}),
        "rewritten",
    ),
    (
        "prefix with nothing after it - must pass through",
        json.dumps({"prompt": "++"}),
        "passthrough",
    ),
    (
        "empty prompt - must pass through",
        json.dumps({"prompt": ""}),
        "passthrough",
    ),
    (
        "malformed JSON - must pass through, not crash",
        "this is not json at all {{{",
        "passthrough",
    ),
    (
        "missing prompt field - must pass through",
        json.dumps({"session_id": "abc"}),
        "passthrough",
    ),
    (
        "empty stdin - must pass through",
        "",
        "passthrough",
    ),
]


def main() -> int:
    failures = 0
    for name, stdin_text, expect in CASES:
        code, out, err = run(stdin_text)

        ok = code == 0
        why = ""
        if not ok:
            why = f"exit {code}"
        else:
            try:
                data = json.loads(out) if out else {}
            except Exception:
                data = None
                ok, why = False, "stdout was not valid JSON"

            if ok:
                # Test the channel that ACTUALLY works, established by
                # experiment (D23): additionalContext. Two earlier versions of
                # this test checked updatedPrompt - first nested, then
                # top-level - and passed both times while the hook had no
                # effect whatsoever on the prompt Claude received.
                #
                # The lesson: a test written from the same assumption as the
                # code cannot catch that assumption being wrong. This one now
                # asserts the observed behaviour instead.
                hso = data.get("hookSpecificOutput", {}) if data else {}
                context = hso.get("additionalContext")

                if expect == "passthrough" and context is not None:
                    ok, why = False, "injected context when it should not have"
                elif expect == "rewritten" and not context:
                    ok, why = False, "no additionalContext - Claude sees nothing"
                elif expect == "rewritten":
                    if hso.get("hookEventName") != "UserPromptSubmit":
                        ok, why = False, "hookEventName missing or wrong"
                    elif "structured prompt" not in context:
                        ok, why = False, "context is missing its framing"

        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{status}] {name}")
        if not ok:
            print(f"         {why}")
            print(f"         stdout: {out[:200]}")
            if err:
                print(f"         stderr: {err[:200]}")

    print()
    if failures:
        print(f"{failures} of {len(CASES)} cases FAILED")
    else:
        print(f"all {len(CASES)} cases passed - the hook never eats a prompt")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
