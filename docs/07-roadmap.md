# 07 — Roadmap

Build order. The principle: get something you can actually use as early as
possible, then improve it. Not: build every part perfectly and assemble at the end.

---

## Phase 1 — Prove the hard part works

**Goal:** confirm speech-to-text and the 7-second rule work on *your* machine
before building anything pretty around them.

- Capture microphone audio
- Transcribe with Whisper `base.en`
- Detect silence, stop after 7 seconds
- Print the result to the terminal

**No interface at all.** Just a script.

**Why first:** this is the only part that could genuinely fail on your hardware.
If Whisper is too slow on your CPU, or the microphone misbehaves, we need to know
on day one — not after a week spent on animations.

**Done when:** you speak into a terminal and your words come out correctly, and it
stops on its own after seven seconds of quiet.

---

## Phase 2 — Make it useful

**Goal:** a working rewriter, still with no interface.

- Tier 3 (rules) — filler removal, punctuation, slot sorting, templates
- Tier 1 (Groq) — API call, instruction template, fallback logic
- The Claude Code target template
- Copy the result to the clipboard

**Done when:** you run a script, speak, and a properly structured prompt is sitting
on your clipboard ready to paste.

**At the end of Phase 2 the tool is genuinely usable.** Ugly, but usable. Everything
after this is making it pleasant.

---

## Phase 3 — The widget

**Goal:** the floating character and translucent panel from
[05-ui-spec.md](05-ui-spec.md).

- Frameless, translucent, always-on-top panel
- The animated character, draggable, edge-snapping
- Live text appearing while you speak
- The voice level meter and silence countdown
- The global hotkey
- Click-to-copy
- System tray icon

**Done when:** you never need to open a terminal again.

---

## Phase 3.5 — Claude Code hook

**Goal:** rewriting happens inside Claude Code, with no copy-paste at all.

- `proeng rewrite` command-line entry point: stdin in, prompt out
- A `UserPromptSubmit` hook using `updatedPrompt` to replace the prompt
- The `++` prefix trigger
- Fail-safe: on any error, return the original prompt unchanged

**Why this early:** it is small - the engine already exists - and it is probably
the highest-value surface of the whole project. Claude Code is where the user
spends their time, and this removes every manual step.

See [09-integrations.md](09-integrations.md).

---

## Phase 4 — Gemini tier and smarter routing

**Goal:** the rewriter never has a bad day.

- Gemini free API as tier 2
- Health memory: after a tier fails, skip it for a few minutes rather than
  paying its timeout on every prompt
- The tier indicator in the panel
- Codex hook (context injection - see the limitation in 09-integrations.md)

## Phase 5 — Polish

- ChatGPT and Gemini target templates
- The three-way target toggle
- Prompt history (SQLite, last 50, searchable)
- Edit-before-rewrite
- `Ctrl+Z` to see the raw text
- The test file of real examples from your first week of use
- Tuning the rewriter against those real examples

---

## Phase 6 — Live with it

Use it daily for a couple of weeks. Collect what annoys you. Fix those things
specifically.

This phase matters more than it looks. Every tool like this has three or four small
frictions that are invisible during development and maddening in daily use. They
can only be found by using it.

Candidates already deferred to here:
- Auto-paste (see D9)
- Light theme
- Auto target detection
- Hindi / multilingual dictation

---

## What I need from you, and when

| When | What |
|---|---|
| Before Phase 1 | Nothing — I can start now |
| Before Phase 2 | A Groq API key (5 minutes, free, see [06-setup.md](06-setup.md)) |
| End of Phase 2 | Try it, tell me if the rewrites are actually good |
| Before Phase 4 | A Gemini API key (free, optional) |
| Phase 3 onward | Opinions on how it looks and feels |
| Phase 6 | The list of things that annoy you |

---

## Deliberately not planned

Ideas that might sound appealing but would work against R13 (keep it simple):

- Sending the prompt straight to the AI — you'd lose the chance to review it
- Browser extension — a whole second product
- Team or sharing features — this is your tool
- A prompt template library — the rewriter *is* the template
- Analytics on your prompting habits — interesting once, noise thereafter
