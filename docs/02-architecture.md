# 02 — Architecture

How the pieces fit together.

---

## The five parts

```
┌──────────────────────────────────────────────────────────┐
│  1. THE WIDGET                                           │
│     The animated character + translucent panel.          │
│     Everything you see and click.                        │
└────────────────────┬─────────────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      v              v              v
┌───────────┐  ┌───────────┐  ┌──────────────┐
│ 2. AUDIO  │  │ 3. SPEECH │  │ 5. CLIPBOARD │
│  Captures │->│  Turns    │  │  Copies the  │
│  the mic. │  │  sound    │  │  result out. │
│  Detects  │  │  into     │  └──────────────┘
│  silence. │  │  text.    │         ^
└───────────┘  └─────┬─────┘         │
                     │ raw text      │
                     v               │
            ┌────────────────────────┴───┐
            │  4. THE REWRITER           │
            │  Raw ramble -> good prompt │
            │  (three tiers, see below)  │
            └────────────────────────────┘
```

---

## Part 1 — The Widget

The visible tool. A small always-on-top character that expands into a translucent
panel when clicked.

**Built with:** Python + PySide6 (the Qt toolkit).

**Why Qt:** it is the only mature option that gives us, on Windows, all at once:
a frameless window, real per-pixel transparency, always-on-top, a click-through
background, and smooth animation — without shipping a whole web browser.

See [05-ui-spec.md](05-ui-spec.md) for the exact look and behaviour.

---

## Part 2 — Audio capture

Listens to your microphone and writes the sound into a rolling buffer.

Its second job is **silence detection**. It continuously measures whether you are
speaking. When it has heard nothing but silence for 7 continuous seconds, it fires
a "stop" signal, which ends the recording exactly as if you had pressed Enter.

**Built with:** `sounddevice` for the microphone, `webrtcvad` for deciding
speech-vs-silence.

**Why not just measure loudness:** a simple volume threshold gets fooled by fan
noise, typing, and room hum — it would either never trigger or trigger constantly.
`webrtcvad` is Google's voice-activity detector, purpose-built to tell human speech
apart from background noise.

---

## Part 3 — Speech to text

Converts the captured audio into raw text, and streams partial results back to the
widget so you can watch your words appear while you're still talking.

**Built with:** `faster-whisper` running OpenAI's Whisper model locally.

**Why local:** this is the part that makes offline possible at all, and it means
your voice never leaves the laptop.

**Which model size:** `base.en` by default (~150 MB, quick, English-only). Upgrade
to `small.en` (~500 MB, noticeably more accurate) if your RAM allows. See
[03-decisions.md](03-decisions.md) for the RAM maths.

---

## Part 4 — The Rewriter

The heart of the tool. Takes the raw ramble and produces a structured prompt.

**Three tiers, tried in order:**

```
   Raw text
      |
      v
  ┌─────────────────────────────────────────────┐
  │ TIER 1 — Groq (cloud)                       │
  │ Free API. Under 1 second. Best quality.     │
  │ Used whenever you have internet.            │
  └─────────────────┬───────────────────────────┘
                    │ no internet, or no API key
                    v
  ┌─────────────────────────────────────────────┐
  │ TIER 2 — Ollama (local)                     │
  │ Fully offline. 10-20 seconds on your CPU.   │
  │ Good quality.                               │
  └─────────────────┬───────────────────────────┘
                    │ Ollama not installed / not running
                    v
  ┌─────────────────────────────────────────────┐
  │ TIER 3 — Rules (built in)                   │
  │ Always works. Instant. Basic quality.       │
  │ Strips filler, fixes punctuation, applies   │
  │ a structure template.                       │
  └─────────────────────────────────────────────┘
```

The fallback is automatic and silent. The widget shows a tiny dot telling you which
tier answered, so you always know what you got — but you are never asked to choose
mid-flow.

Full detail in [04-rewrite-engine.md](04-rewrite-engine.md).

---

## Part 5 — Clipboard

Puts the final text on the Windows clipboard when you click the result.

**Built with:** `pyperclip`.

---

## How it all runs: threads

This matters, because getting it wrong makes the widget freeze while you talk.

| Thread | Does what | Why separate |
|---|---|---|
| **Main** | Draws the widget, handles clicks | Qt requires all drawing on one thread |
| **Audio** | Reads the microphone, detects silence | Must never be interrupted, or audio drops out |
| **Transcribe** | Runs Whisper | Slow and CPU-heavy; would freeze the UI |
| **Rewrite** | Calls Groq / Ollama / rules | Network waits and model waits must not freeze the UI |

They talk to each other by passing messages, never by sharing memory directly.
This is the single most common source of bugs in tools like this, so it is being
designed in from the start rather than patched in later.

---

## Folder layout (planned)

```
ProEng/
├── README.md
├── docs/                    <- you are here
├── proeng/
│   ├── __main__.py          <- entry point; starts the app
│   ├── ui/
│   │   ├── character.py     <- the animated character
│   │   ├── panel.py         <- the translucent box
│   │   └── theme.py         <- colours, sizes, fonts in one place
│   ├── audio/
│   │   ├── recorder.py      <- microphone capture
│   │   └── vad.py           <- the 7-second silence detector
│   ├── stt/
│   │   └── whisper.py       <- speech to text
│   ├── rewrite/
│   │   ├── router.py        <- picks a tier, handles fallback
│   │   ├── groq.py          <- tier 1
│   │   ├── ollama.py        <- tier 2
│   │   ├── rules.py         <- tier 3
│   │   └── prompts/         <- the instruction templates per target
│   ├── clipboard.py
│   ├── hotkey.py            <- global Ctrl+Shift+Space
│   └── config.py            <- settings, read from a simple file
├── config.example.toml      <- committed; a template
├── config.toml              <- NOT committed; holds your API key
└── requirements.txt
```

---

## Where your data goes

Worth being explicit, since it's your voice.

| Tier | Where your words go |
|---|---|
| Speech-to-text | **Never leaves your laptop.** Always local, every tier. |
| Tier 1 (Groq) | Text is sent to Groq's servers to be rewritten. |
| Tier 2 (Ollama) | **Never leaves your laptop.** |
| Tier 3 (Rules) | **Never leaves your laptop.** |

If you ever dictate something you would not want on someone else's server, there
will be an **Offline Only** toggle that skips Tier 1 entirely for that session.
