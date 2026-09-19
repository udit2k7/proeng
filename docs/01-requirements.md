# 01 — Requirements

This document captures what the tool must do, written in plain language.
It is the source of truth. If code and this document disagree, this document wins
until we deliberately change it.

---

## 1. The problem being solved

You are building several projects across Claude Code, ChatGPT, and Gemini. You are
not a prompt-engineering expert. When you speak or type your request, it comes out
long and unstructured — full of "uh", repeated thoughts, and details scattered out
of order.

Two things go wrong as a result:

1. **The AI misunderstands.** A long, unstructured prompt gives the model too many
   places to go wrong, so it returns something that isn't what you wanted.
2. **Tokens get wasted.** Long prompts cost more, and wrong answers cost a second
   round of prompting to fix.

The fix is a layer that sits *before* the AI: it turns your natural speech into a
tight, well-organised prompt.

---

## 2. Hard requirements

These are non-negotiable.

### R1 — It runs on your own machine
Installed locally on your Windows 11 laptop. Not a website you have to visit.

### R2 — Rewriting must not consume Claude/ChatGPT tokens
The whole point is to *save* money and tokens. The rewriting step uses either a
free local model or a free API tier — never your paid Claude or ChatGPT quota.

### R3 — It must never be a dead end
*Revised 2026-09-19. Originally "it must work offline".*

The user works exclusively with online tools (Claude Code, Codex), so full offline
operation solves a problem they do not have. Carrying a local LLM for it was cut -
see [03-decisions.md](03-decisions.md) D15.

What remains required: the tool must always return *something* usable. If both
cloud providers are unreachable, the built-in rules tier still produces structured
output with no network, no key and no model. Lower quality, never a dead end.

### R4 — Voice input
You speak. The words appear as text, live, while you are still talking — the same
way dictation works.

### R5 — Typed input
Sometimes you would rather type. The same box accepts typing, and typed input goes
through the same rewriting.

### R6 — Automatic stop
Recording stops when **either**:
- you press Enter, **or**
- you stay silent for **7 seconds**.

You should never have to hunt for a stop button.

### R7 — Rewritten prompt is returned in place
After stopping, the cleaned-up prompt replaces (or appears beneath) the raw text in
the same little box.

### R8 — One click to copy
Clicking the result copies it to the clipboard. You then paste it wherever you want.
No "select all, right click, copy" dance.

---

## 3. Interface requirements

### R9 — A small animated character
The tool sits on screen as a small, unobtrusive animated character — not a full
window, not a taskbar app you have to hunt for.

### R10 — Click opens a side panel
Clicking the character opens a small box at the side of the screen.

### R11 — Translucent
The box is see-through enough that you can still read what is behind it. You are
usually looking at code or a chat window while you dictate; the box must not hide it.

### R12 — Always on top
It floats above other windows. It does not disappear when you click elsewhere unless
you close it.

### R13 — Simple
This is explicitly *not* meant to be a big application. No settings maze, no
accounts, no dashboards. Open, speak, copy, done.

---

## 4. Quality requirements

### R14 — Three target formats
Claude Code, ChatGPT, and Gemini each respond best to slightly different prompt
shapes. The tool should be able to aim at whichever one you are about to use.

### R15 — Meaning must be preserved
The rewriter cleans up and restructures. It must **not** invent requirements you
did not state, or drop ones you did. If something is genuinely ambiguous, it should
be surfaced as an open question rather than silently guessed.

### R16 — Fast enough to not be annoying
Target: the rewrite comes back in under 2 seconds when online. Offline it will be
slower; that tradeoff is accepted and documented.

---

## 5. Explicitly out of scope

Listed so we do not accidentally build them:

- Multi-user support, accounts, login
- Sending the prompt directly to Claude/ChatGPT/Gemini (you paste it yourself)
- Mobile, Mac, or Linux versions
- Cloud sync of your prompt history
- Any kind of telemetry or analytics
- A polished installer for strangers to download

---

## 6. Constraints discovered on your machine

Checked directly on 2026-09-19:

| Thing | Value | What it means for us |
|---|---|---|
| CPU | Intel i7-1355U, 10 cores | Capable, but it's a low-power laptop chip |
| RAM | 15.7 GB total, **1.7 GB free** | **The tight one.** Models must stay small |
| GPU | Intel Iris Xe (integrated) | Cannot meaningfully speed up AI models |
| Disk | 157 GB free | No concern at all |
| Python | 3.12 and 3.14 installed | We use 3.12 (better library support) |
| Node | v24 | Available, but we won't need it |

The RAM figure is the important one and shapes several decisions in
[03-decisions.md](03-decisions.md).
