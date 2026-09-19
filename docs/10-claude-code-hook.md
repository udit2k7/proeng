# 10 — Installing the Claude Code hook

This makes rewriting happen *inside* Claude Code. You type a rambling prompt with
`++` in front, and Claude receives a clean structured version of it alongside
your words. No copy-paste needed.

**One honest limitation:** the hook cannot remove your original wording - Claude
Code ignores the field that would do that (see D23). Your ramble still reaches
Claude, so this buys accuracy rather than token savings. If saving input tokens
matters more, use the desktop widget and paste only the clean version.

---

## What it does

```
You type:
    ++ uh so the login thing is broken on mobile it works fine on desktop
       but nothing happens when I tap it maybe the click handler

Claude receives your words, plus this alongside them:
    Goal
    Fix the login button, which does not respond to taps on mobile.

    Context
    Works correctly on desktop. No response when tapped on a phone.

    Open questions
    - Is the click handler the cause?
```

Takes about 1.5-2 seconds. You see a small note saying which tier answered.

**Without the `++` prefix, nothing happens at all.** "yes", "run the tests" and
"commit this" pass through untouched. See D16 in [03-decisions.md](03-decisions.md).

---

## Prerequisites

1. Phase 2 installed (`requirements-phase1.txt` and `requirements-phase2.txt`)
2. At least one API key in `config.toml` - Groq or Gemini, both free

Without a key it still works, falling back to the rules tier. Quality is lower
but it never fails.

---

## Install

One command. It merges into your existing settings rather than replacing them,
and backs the file up first:

```bash
.venv\Scripts\python.exe scripts\install_hook.py
```

That writes to `~/.claude/settings.json` — on Windows,
`C:\Users\<you>\.claude\settings.json` — so the hook works in every project.

For this project only, add `--project`. It writes to `ProEng\.claude\settings.json`
and touches nothing outside the folder.

Then **restart Claude Code**.

### Removing it

```bash
.venv\Scripts\python.exe scripts\install_hook.py --remove
```

Or restore the `settings.json.backup` the installer wrote.

### Why a script rather than "edit this file"

Your settings file almost certainly already has content — a theme, permissions,
other hooks. Pasting a fresh JSON object over it silently destroys all of that.
The installer merges, backs up first, and refuses to run if the existing file is
malformed rather than overwriting something it cannot read.

It also removes any previous ProEng entry before adding a new one, so running it
twice never leaves you with the hook firing twice.

### Doing it by hand

If you would rather edit it yourself, **merge** this into the existing JSON —
do not replace the file:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"<ABSOLUTE PATH>\\.venv\\Scripts\\python.exe\" \"<ABSOLUTE PATH>\\hooks\\claude_code_hook.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Three things people get wrong here: both paths must be **absolute**; every
backslash must be **doubled** (JSON escaping); and each path needs **quotes
around it**, escaped as `\"`, because the path may contain spaces.

That is three ways to get it subtly wrong, which is exactly why the installer
exists.

Restart Claude Code, then type `++ ` followed by anything rambling.

**Restarting matters.** `settings.json` is read at startup, so a running session
will not pick up a newly installed hook. The hook *script* itself is re-read on
every invocation, so editing that needs no restart.

---

## Checking it works

Before wiring it into Claude Code, test it standalone:

```bash
.venv\Scripts\python.exe scripts\test_hook.py
```

Nine cases, covering the happy path and every failure path. All should pass.

To see a real rewrite:

```bash
echo {"prompt":"++ I want a dark mode toggle that remembers my choice"} | .venv\Scripts\python.exe hooks\claude_code_hook.py
```

---

## The safety guarantee

The hook sits in front of every prompt you type, so the one thing it must never
do is lose one.

Every failure path returns your own words:

| What goes wrong | What you get |
|---|---|
| No API key | Rules-tier rewrite |
| No internet | Rules-tier rewrite |
| Groq and Gemini both down | Rules-tier rewrite |
| Malformed input from Claude Code | Your prompt, untouched |
| A bug in our code | Your prompt, no added context |
| Python itself fails to start | Your prompt, untouched |

This is tested, not asserted - see the failure cases in `scripts/test_hook.py`.

Because the hook only *adds* context rather than replacing your prompt, the worst
case is that nothing is added. Your words always reach Claude either way - which
makes this considerably safer than a replacing hook would have been.

**Diagnosing:** every invocation is logged to `hook.log` in the project root -
whether it ran, whether it rewrote, which tier answered, and how long it took.
That file is what turned three separate "is it even working?" questions into
one-line answers.

---

## Turning it off

Delete the `hooks` block from `settings.json` and restart Claude Code.

To disable it temporarily without editing anything, just stop typing `++`.

---

## Codex CLI

Codex has `UserPromptSubmit` hooks too, with the same limitation: it can block a
prompt or add context, but not replace the text.

That turns out to be **identical to how Claude Code behaves in practice** - see
D23. The plan assumed Claude Code could replace the prompt and Codex could not;
testing showed neither can. So the same context-injection approach serves both,
and `hooks/claude_code_hook.py` works for Codex with only its registration path
differing (`~/.codex/hooks.json` or `~/.codex/config.toml`).

Covered in [09-integrations.md](09-integrations.md).
