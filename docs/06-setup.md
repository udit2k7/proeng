# 06 — Setup

What needs installing, and in what order. Nothing here has been done yet — this is
the plan.

Steps 1 and 2 are required. Step 3 is optional and can be done later.

---

## Step 1 — Python environment

Already installed: Python 3.12 at
`C:\Users\uditt\AppData\Local\Programs\Python\Python312`.

We create an isolated environment so this project's libraries never interfere with
anything else on your machine:

```bash
py -3.12 -m venv .venv
```

Then activate it (needed in each new terminal):

```bash
.venv\Scripts\activate
```

---

## Step 2 — Libraries

```bash
pip install -r requirements.txt
```

What gets installed and why:

| Library | Size | Purpose |
|---|---|---|
| `PySide6` | ~100 MB | The floating widget |
| `faster-whisper` | ~40 MB | Speech to text |
| `sounddevice` | small | Microphone capture |
| `webrtcvad` | small | The 7-second silence detector |
| `pyperclip` | tiny | Clipboard |
| `keyboard` | tiny | The global hotkey |
| `httpx` | small | Talking to Groq and Ollama |
| `psutil` | tiny | Checking free RAM before loading Ollama |

Roughly 150 MB total. Plus the Whisper model, which downloads itself on first run
(~150 MB for `base.en`).

**Windows note:** `webrtcvad` sometimes fails to install because it needs a C++
compiler. If that happens, the fix is `pip install webrtcvad-wheels`, which ships
prebuilt. I'll handle this when we get there.

---

## Step 3 — Pick your rewrite engine

You can do **either, both, or neither**. With neither, the tool still works on
Tier 3 rules.

### Option A — Groq (recommended first; 5 minutes, free)

1. Go to https://console.groq.com and sign up (free, no card)
2. Create an API key
3. Copy `config.example.toml` to `config.toml`
4. Paste the key into the `groq_api_key` line

That's it. You now have sub-second, high-quality rewrites that cost nothing and
don't touch your Claude or ChatGPT tokens.

### Option B — Ollama (offline capability; ~2 GB download)

1. Download from https://ollama.com/download/windows and install
2. Pull the model:

```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
```

That's about 2 GB, comfortably inside your stated 2.5 GB budget.

**If it feels too slow or your RAM is tight**, use the smaller one instead:

```bash
ollama pull qwen2.5:1.5b-instruct-q4_K_M
```

About 1 GB, roughly twice as fast, somewhat lower quality.

**RAM reminder:** you had 1.7 GB free when I checked. The 3B model wants about
2.5 GB to itself. Either close some browser tabs before using offline mode, or use
the 1.5B model. The tool will check and tell you rather than freezing.

---

## Step 4 — Run it

```bash
python -m proeng
```

The character appears on screen. Press `Ctrl+Shift+Space` to test.

---

## Step 5 — Start with Windows (optional)

Once you're happy with it, a shortcut in the Startup folder makes it always
available. I'll provide the exact command when we get there.

---

## Uninstalling

Delete the `ProEng` folder. That's it.

Everything the tool uses lives inside that one folder: the downloaded speech
models (`ProEng/models/`), the Python environment (`ProEng/.venv/`), the config,
and the prompt history. Nothing is written to the registry, and nothing is
installed system-wide.

The only exception is Ollama, if you choose to install it in Phase 4. That
uninstalls normally through Windows Settings.

---

## If something goes wrong

A troubleshooting guide will be written once we know what actually breaks. Guessing
at problems in advance produces documentation nobody reads. The likely candidates,
noted now so we watch for them:

- Microphone not detected, or Windows blocking microphone access
- `webrtcvad` install failing (see Step 2)
- Ollama running out of RAM
- The global hotkey clashing with another application
