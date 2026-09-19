# 09 — Integrations

The desktop widget is one way to reach the rewriter. It is not the only one, and
arguably not the most useful one.

This document covers the others: hooks that sit inside Claude Code and Codex, and
a browser extension. Researched and verified 2026-09-19.

---

## The core idea

All delivery forms call the same engine. Nothing is duplicated.

```
            ┌──────────────────────────────────┐
            │  proeng rewrite                  │
            │  stdin -> stdout, ~0.3s via Groq │
            └───────────────┬──────────────────┘
                            │
     ┌──────────────┬───────┴───────┬──────────────┐
     v              v               v              v
  Desktop      Claude Code       Codex          Chrome
  widget       hook              hook           extension
  (Phase 3)    (Phase 3.5)       (partial)      (later)
```

A single command-line entry point means a fix to the rewriter improves every
surface at once, and each integration is a few lines of config rather than a
reimplementation.

---

## 1. Claude Code hook — context injection (not replacement)

Claude Code fires a `UserPromptSubmit` hook when you submit a prompt, **before**
the model sees it.

The documentation describes an `updatedPrompt` field that replaces the prompt
entirely. **In practice it does not work** - tested in both documented placements,
neither had any effect. `additionalContext` does work. See D23 for the experiment.

So the hook **adds** the structured version alongside your original words, rather
than replacing them. Same mechanism as the Codex hook below.

### What it looks like in use

```
You type:   ++ uh so the login thing is broken on mobile it works fine on
            desktop but nothing happens when I tap it maybe the click handler

Claude sees:
            Goal
            Fix the login button, which does not respond to taps on mobile.

            Context
            Works correctly on desktop. No response when tapped on a phone.

            Open questions
            - Is the click handler the cause?
```

You never see the rewriting happen. It takes about 0.3 seconds.

### What this costs

**Your original words still reach Claude.** Replacement would have removed them;
context injection cannot. So the hook does **not** reduce input tokens.

R2 still holds - the rewriting itself runs on Groq's free tier and never touches
Claude quota. But the benefit here is accuracy, not brevity: the model stops
misreading a rambling request because the structured version is sitting right
next to it.

For real token saving, the desktop widget is better: you paste only the clean
version, and the ramble never leaves your machine. The hook wins on convenience,
the widget on economy.

### Available output fields

For `UserPromptSubmit`:

| Field | Documented effect | Observed |
|---|---|---|
| `updatedPrompt` | Replaces the prompt text | **Ignored** (both placements) |
| `additionalContext` | Adds context, keeps the original | **Works - what we use** |
| `systemMessage` | Shows a message to the user | Works |
| plain stdout | Added as context | Works |

---

## 2. Codex CLI hook — partial support

Codex CLI gained `UserPromptSubmit` hooks around v0.117.0 (PR #14626, March 2026).
Hooks register in `~/.codex/hooks.json` or `~/.codex/config.toml`.

**The limitation: Codex has no `updatedPrompt` equivalent.** Its hook can block a
prompt or add context, but cannot replace the text. It is a gatekeeper, not a
rewriter.

### The workaround

Use `additionalContext` to append the structured version while the original stays:

```
[your original rambling prompt]

--- structured interpretation ---
Goal
Fix the login button, which does not respond to taps on mobile.
...
```

The model then sees both. In practice this works well - the structure does most
of the steering - but it is strictly worse than Claude Code's version, because
the messy text is still sent and still costs tokens.

### If that proves unsatisfying

Fall back to the desktop widget for Codex: dictate, click to copy, paste. Slightly
more friction, full quality.

---

## 3. Browser extension — later

For chatgpt.com, claude.ai, and gemini.google.com, a Chrome extension can
intercept the input box before send and swap in the rewritten text.

Deferred, because:

- It is effectively a second product with its own build and packaging
- Chrome extensions cannot call a local service without extra setup
- The desktop widget already covers these sites via copy-paste

Revisit once the widget and hooks have been in daily use.

---

## When should rewriting trigger?

Not every prompt should be rewritten. "yes", "run the tests", "commit this" are
already fine, and rewriting them adds latency and risks mangling them.

**Chosen: an explicit prefix.** A prompt starting with `++` gets rewritten;
everything else passes through untouched.

| Approach | Verdict |
|---|---|
| **Prefix (`++`)** | **Chosen.** Predictable. You stay in control |
| Auto if over ~25 words | Rejected. Will surprise you at the worst moment |
| Rewrite everything | Rejected. Latency on every "yes" |

The prefix is configurable, and an auto-by-length mode can be added later if the
prefix turns out to be tedious in practice.

---

## Failure behaviour

A hook that breaks must never block you from working.

- If the rewriter fails for any reason, the hook returns the **original prompt
  unchanged**. You lose the improvement, not your prompt.
- A hard timeout of 5 seconds, after which the original is used.
- The rules tier means there is almost always *something* to return.

This is non-negotiable: a prompt-rewriting hook that eats prompts is worse than
no hook at all.
