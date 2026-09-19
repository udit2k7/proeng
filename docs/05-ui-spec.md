# 05 — Interface Specification

Exactly what you see, and exactly what it does.

---

## State 1 — Resting (the character)

A small animated character sits on your screen, by default near the right edge,
vertically centred.

- **Size:** 64 × 64 pixels. Small enough to ignore, big enough to hit with a mouse.
- **Always on top**, over every other window.
- **Draggable** — pick it up and put it wherever suits you. Position is remembered.
- **Snaps to the nearest screen edge** when released, so it never floats awkwardly
  in the middle of your work.
- **Idle animation:** a slow, gentle breathing pulse. Deliberately subtle — anything
  bouncy becomes irritating within a day.
- **Fades to 40% opacity** after 10 seconds of no interaction, so it stops competing
  for attention. Returns to full opacity the moment your cursor comes near.

### Its states

| State | Look |
|---|---|
| Idle | Slow breathing pulse, muted colour |
| Listening | Ring around the character pulses **in time with your voice** |
| Thinking | Ring rotates slowly |
| Done | Brief green flash |
| Error | Brief amber flash |

The listening animation reacting to your actual voice level is important — it's how
you know the microphone is genuinely picking you up, without needing to read
anything.

---

## State 2 — Active (the panel)

Clicking the character, or pressing `Ctrl+Shift+Space`, slides a panel out from the
screen edge.

### Dimensions
- **Width:** 380 px
- **Height:** starts at 220 px, grows with content, caps at 600 px then scrolls
- **Position:** attached to the character's edge
- **Animation:** slides out over 180 ms with an ease-out curve. Fast enough to feel
  instant, slow enough to see where it came from.

### Translucency (R11)
- Background: **75% opaque** — you can read what's behind it
- A subtle blur behind the panel so text stays legible over a busy background
- Text itself is **fully opaque** — never make the words you need to read see-through
- Opacity adjustable in config, 50–100%

### Layout

```
┌────────────────────────────────────────┐
│  ● Claude Code  ○ ChatGPT  ○ Gemini  ✕ │   <- target toggle + close
├────────────────────────────────────────┤
│                                        │
│  so I want to build a tool that takes  │   <- live text, appears
│  my voice and turns it into a prop...  │      as you speak
│                                        │
│  ▁▂▃▅▇▅▃▂▁▂▃▅  ● listening   7s        │   <- level meter + silence countdown
│                                        │
├────────────────────────────────────────┤
│                                        │
│  Goal                                  │   <- the rewritten prompt
│  Build a desktop tool that converts    │      appears here
│  voice input into structured prompts.  │
│                                        │
│  Context                               │
│  ...                                   │
│                                        │
├────────────────────────────────────────┤
│  ⚡ groq · 0.3s      [ Click to copy ]  │   <- which tier answered
└────────────────────────────────────────┘
```

### The silence countdown
While you are recording, a small number counts down from 7 whenever you go quiet.
It resets the instant you speak again.

This is there because a silent auto-stop is unnerving — you need to see it coming.
It's also your cue: if you're thinking mid-sentence, you can see you have three
seconds left and keep going.

### The tier indicator
A small line at the bottom showing which engine answered and how long it took:

- `⚡ groq · 0.3s` — Tier 1
- `💻 local · 14s` — Tier 2
- `📝 rules` — Tier 3, with a short note explaining why it fell back

Never a popup, never a dialog you have to dismiss. Just information, quietly present.

---

## Interactions

| You do | It does |
|---|---|
| Click the character | Opens the panel and **starts recording immediately** |
| Press `Ctrl+Shift+Space` | Same — from anywhere, any app |
| Speak | Text appears live; level meter moves |
| Press `Enter` | Stops recording, starts rewriting |
| Stay silent 7 seconds | Same as pressing Enter |
| Start typing instead | Recording stops; typed input is used instead |
| Click the result | Copies to clipboard; brief green flash confirms |
| Press `Esc` | Closes the panel, discards everything |
| Press `Ctrl+Z` after a rewrite | Shows the raw text again, so you can compare |
| Drag the character | Moves it; snaps to nearest edge on release |
| Right-click the character | Small menu: History, Offline Only, Settings, Quit |

**Note on clicking the character:** it starts recording straight away rather than
just opening an empty box. One action, not two. If you wanted to type instead, just
start typing — that cancels the recording.

---

## Typing mode

The text area is always editable. You can:

- Type instead of speaking (recording stops the moment you type)
- **Edit the transcription** before it gets rewritten — useful when Whisper
  mishears a technical term
- Press `Enter` to rewrite, `Shift+Enter` for a new line

---

## The history panel

Right-click → History, or `Ctrl+H`.

A simple list of your last 50 prompts, newest first. Each row shows the first line
and a timestamp. Click one to copy it again. There's a search box, and a
"Clear all" button.

Stored locally in a SQLite file. Never uploaded.

---

## Visual design

Deliberately quiet. This tool sits on top of your work all day; it must not shout.

| | |
|---|---|
| Panel background | Near-black `#16181D` at 75% opacity |
| Text | Off-white `#E8EAED` — softer than pure white, easier on the eyes |
| Muted text | `#8B919B` for timestamps and the tier line |
| Accent | Warm amber `#E0A458` for the recording ring and buttons |
| Success | Muted green `#6FAF7F` |
| Error | Muted red `#C97A7A` |
| Font | Segoe UI Variable (Windows 11's own), 13px body |
| Corners | 12 px radius |
| Border | 1 px `#FFFFFF` at 8% opacity — just enough edge definition |

A light theme is planned but not for version 1. A translucent panel over a light
background is a harder design problem and isn't worth solving before the tool
actually works.

---

## Accessibility and comfort

- Every mouse action has a keyboard equivalent
- The panel can be resized and its position is remembered
- Animations respect the Windows "reduce motion" setting
- Minimum text size 13px; scale factor adjustable in config
- The character can be hidden entirely, leaving only the hotkey

---

## What it deliberately does not have

- A taskbar window (it lives in the system tray only)
- A splash screen
- Notifications
- A settings dialog — config is a text file (see D6)
- An update checker
- Any kind of onboarding tour
