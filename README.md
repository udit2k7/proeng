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
