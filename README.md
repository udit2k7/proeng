# ProEng — Prompt Engineer

A small floating desktop tool for Windows. You talk (or type) in your own rambling
words; it hands back a clean, well-structured prompt ready to paste into Claude Code,
ChatGPT, or Gemini.

Built so that rewriting your prompt **never costs you Claude or ChatGPT tokens.**

---

## The idea in one picture

```
  You click the little character (or press Ctrl+Shift+Space)
                     |
                     v
  A small translucent box slides in from the side
                     |
                     v
  You speak  ---->  live text appears as you talk
                     |
        (you press Enter, OR you go quiet for 7 seconds)
                     |
                     v
  The raw ramble is rewritten into a proper prompt
                     |
                     v
  You click the result --> copied to clipboard --> paste anywhere
```

---

## Quick start

**No API keys are included anywhere in this repository.** You bring your own —
both providers below are free and need no card.

### Just the Claude Code hook (easiest — no install, no dependencies)

Type `++` before a rambling prompt and Claude receives a structured version.

```
/plugin marketplace add udit2k7/proeng
/plugin install proeng
```

Then set your own key:

```bash
setx PROENG_GROQ_KEY "gsk_your_key_here"      # Windows
export PROENG_GROQ_KEY="gsk_your_key_here"    # Mac / Linux
```

Get one free at [console.groq.com/keys](https://console.groq.com/keys). Needs
Python 3 and nothing else — the hook uses only the standard library.

### The full desktop widget (voice dictation)

```bash
git clone https://github.com/udit2k7/proeng.git
cd proeng
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-phase1.txt -r requirements-phase2.txt -r requirements-phase3.txt
```

Then add your key — either run this, which prompts without the key touching
your shell history:

```bash
.venv\Scripts\python.exe scripts\set_key.py groq
```

…or copy `config.example.toml` to `config.toml` and paste it into the
`api_key = ""` line yourself.

```bash
.venv\Scripts\python.exe -m proeng
```

A small circle appears at the screen edge. Click it, or press
`Ctrl+Shift+Space`, and speak.

### Where your key lives

| | |
|---|---|
| `config.toml` | Your keys. **Gitignored** — cannot be committed |
| `config.example.toml` | The template. Committed, always blank |
| Environment variables | `PROENG_GROQ_KEY`, `PROENG_GEMINI_KEY` — override the file |

A pre-commit hook blocks any commit containing an API-key-shaped string, and
`scripts/audit_keys.py` checks your files, your git history, and whether the
keys still work. See [docs/11-key-security.md](docs/11-key-security.md).

---

## Documentation

Read these in order. They were written before any code, on purpose.

| Doc | What's in it |
|---|---|
| [docs/01-requirements.md](docs/01-requirements.md) | What you asked for, in plain language. The source of truth. |
| [docs/02-architecture.md](docs/02-architecture.md) | How the pieces fit together, technically. |
| [docs/03-decisions.md](docs/03-decisions.md) | Every technology choice and *why*, including the ones rejected. |
| [docs/04-rewrite-engine.md](docs/04-rewrite-engine.md) | The heart of it: how rambling becomes a good prompt. |
| [docs/05-ui-spec.md](docs/05-ui-spec.md) | Exactly what the widget looks like and how it behaves. |
| [docs/06-setup.md](docs/06-setup.md) | Install steps, for a fresh machine. |
| [docs/07-roadmap.md](docs/07-roadmap.md) | Build order, in phases. What ships first. |
| [docs/08-glossary.md](docs/08-glossary.md) | Non-technical explanations of every term used here. |
| [docs/09-integrations.md](docs/09-integrations.md) | Hooks for Claude Code and Codex; the browser extension. |
| [docs/10-claude-code-hook.md](docs/10-claude-code-hook.md) | How to install the Claude Code hook. |
| [docs/11-key-security.md](docs/11-key-security.md) | Keeping API keys safe, and what to do if one leaks. |

---

## Status

**Phases 1-2 complete, plus the Claude Code hook.**

| Phase | State |
|---|---|
| 1 - voice capture, silence detection, transcription | done, measured at 0.05x realtime |
| 2 - the rewriter (rules + Groq + Gemini tiers) | done; needs an API key to use the cloud tiers |
| 3.5 - Claude Code hook | done, 9/9 tests passing |
| 3 - the floating widget | next |

Add a free API key to `config.toml` to enable the cloud tiers - see
[docs/06-setup.md](docs/06-setup.md).

## Scope

Private tool, built for one user on one laptop. Possibly open-sourced later —
so the code is kept clean and the secrets stay out of the repository, but no
effort is spent on multi-user features, installers for other people, or cloud sync.
