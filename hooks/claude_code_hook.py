"""UserPromptSubmit hook for Claude Code.

Claude Code pipes the submitted prompt in as JSON on stdin. If we return
`updatedPrompt`, that REPLACES what Claude sees. So a rambling prompt can be
turned into a structured one before the model ever reads it - and the messy
version never costs any Claude tokens.

Only prompts starting with the trigger prefix (default "++") are touched.
Everything else passes through untouched, because rewriting "yes" or
"run the tests" would add latency and risk mangling a perfectly good
instruction. See docs/03-decisions.md D16.

THE ONE RULE THIS FILE MUST OBEY: never eat a prompt. Any failure - no key,
no network, a bug in our own code, a timeout - results in the user's own words
being used. A prompt-rewriting hook that loses prompts is far worse than no
hook at all.

Install: see docs/10-claude-code-hook.md
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

# The project root, so this works wherever Claude Code is invoked from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_PREFIX = "++"

# A breadcrumb trail, so "did the hook even run?" is answerable with evidence
# rather than inference. Kept inside the project and gitignored.
LOG = ROOT / "hook.log"


def log(message: str) -> None:
    """Never let logging break the hook - that would defeat the purpose."""
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {message}\n")
    except Exception:
        pass


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(0)


def passthrough(why: str = "") -> None:
    """Emit nothing. Claude Code then uses the original prompt unchanged."""
    log(f"passthrough ({why})" if why else "passthrough")
    emit({})


def use(text: str, note: str = "") -> None:
    """Deliver the rewritten prompt to Claude.

    We use `additionalContext`, NOT `updatedPrompt`.

    Why, established by experiment rather than by reading docs (see D23):
    `updatedPrompt` was emitted both nested inside `hookSpecificOutput` and as a
    top-level sibling. Neither took effect - the prompt reached Claude unchanged
    while the hook reported success. A marker sent through `additionalContext`
    in the same payload DID arrive. So this build consumes hook output, but
    ignores `updatedPrompt`.

    The consequence is worth stating plainly: the user's original words still
    reach Claude, so this does not save input tokens the way replacement would.
    What it does deliver is the structure - which is what actually stops the
    model misreading a rambling request.

    `updatedPrompt` is still emitted, harmlessly, so that a future build which
    supports it upgrades this hook to true replacement with no code change.
    """
    framed = (
        "The user's message was dictated and may be unstructured. A local "
        "rewriter has reorganised it into the structured form below. Treat this "
        "as the authoritative statement of what they want, and prefer it over "
        "the raw wording above where the two differ. Nothing here was invented: "
        "it is a restructuring of their own words.\n\n"
        "--- structured prompt ---\n"
        f"{text}"
    )

    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": framed,
        },
        # Ignored by current builds; forward-compatible if that changes.
        "updatedPrompt": text,
    }
    if note:
        out["systemMessage"] = note
    emit(out)


def main() -> None:
    # --- read what Claude Code gave us ---------------------------------
    log("invoked")

    try:
        payload = json.load(sys.stdin)
    except Exception:
        passthrough("stdin was not valid JSON")

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        passthrough("no prompt field")

    # --- load our own machinery ----------------------------------------
    # If any of this fails the tool is broken, but the user's prompt is not
    # our property to lose - hand it straight back.
    try:
        from proeng import config as cfgmod
        from proeng.rewrite.base import Target
    except Exception as exc:
        passthrough(f"could not import proeng: {exc}")
        return  # unreachable; keeps type checkers happy

    try:
        cfg = cfgmod.load()
        prefix = cfg.trigger_prefix or DEFAULT_PREFIX
    except Exception:
        cfg, prefix = None, DEFAULT_PREFIX

    # --- should we touch this prompt at all? ---------------------------
    if not prompt.startswith(prefix):
        passthrough(f"no '{prefix}' prefix - left untouched")

    raw = prompt[len(prefix):].strip()
    if not raw:
        passthrough("prefix with nothing after it")

    if cfg is None:
        # Config was unreadable but the prefix was used, so the user clearly
        # wants a rewrite. Strip the prefix at minimum.
        use(raw)

    # --- rewrite -------------------------------------------------------
    try:
        router = cfgmod.build_router(cfg)
        result = router.rewrite(raw, Target.CLAUDE)
    except Exception:
        # Our bug must not become the user's problem.
        use(raw)
        return

    text = (result.text or "").strip() or raw
    log(f"REWROTE via {result.tier} in {result.elapsed:.2f}s "
        f"({len(raw.split())} words -> {len(text.split())} words)")

    note = f"prompt rewritten [{result.tier}, {result.elapsed:.2f}s]"
    if result.alert:
        # Claude Code shows systemMessage to the user, not to the model, so
        # this warns without polluting the prompt.
        note = (
            f"!! API KEY PROBLEM: {result.alert} "
            f"Run: python scripts/set_key.py <provider> to replace it. "
            f"(fell back to {result.tier})"
        )
    use(text, note)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Absolute last resort. Never crash, never block the user.
        passthrough()
