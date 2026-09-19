# ProEng

Turns rambling prompts into clear, structured ones — before Claude reads them.

Prefix a prompt with `++` and it gets restructured by a **free** model (Groq, or
Gemini as backup). Your Claude tokens are never spent on the messy version.

```
You type:
  ++ uh so the login thing is broken on mobile it works fine on desktop
     but nothing happens when I tap it maybe the click handler

Claude also receives:
  Goal
  Fix the login button, which does not respond to taps on mobile.

  Context
  Works correctly on desktop. No response when tapped on a phone.

  Open questions
  - Is the click handler the cause?
```

Without the `++` prefix, nothing happens at all. "yes", "run the tests" and
"commit this" pass through untouched.

## Install

```
/plugin marketplace add uditt/proeng
/plugin install proeng
```

Then set a free API key:

```bash
setx PROENG_GROQ_KEY "gsk_..."     # Windows
export PROENG_GROQ_KEY="gsk_..."   # macOS / Linux
```

Get one free, no card, at [console.groq.com](https://console.groq.com).
Optionally add `PROENG_GEMINI_KEY` from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) as a backup, so
a rate limit on one provider costs you nothing.

Restart Claude Code, then try `++ ` followed by something rambling.

## Requirements

**Python 3.** That is all — no pip install, no dependencies. The hook uses only
the standard library.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PROENG_GROQ_KEY` | — | Groq key, tried first (~1.5s) |
| `PROENG_GEMINI_KEY` | — | Gemini key, the backup |
| `PROENG_PREFIX` | `++` | Change the trigger |

`GROQ_API_KEY` and `GEMINI_API_KEY` are also read, if you already have them set.

Or put them in `~/.claude/proeng.toml`:

```toml
[groq]
api_key = "gsk_..."

[gemini]
api_key = "AIza..."

[hooks]
trigger_prefix = "++"
```

## What it will not do

**It cannot remove your original wording.** Claude Code ignores the field that
would replace a prompt, so the structured version arrives *alongside* your words
rather than instead of them. This buys accuracy, not token savings.

**It never loses a prompt.** No key, no network, a bug in the hook — your words
reach Claude regardless. A prompt-rewriting hook that eats prompts is worse than
no hook at all.

## The desktop widget

This plugin is the hook only. The full [ProEng project](https://github.com/uditt/proeng)
also has a floating desktop widget that does voice dictation — speak, and it
transcribes locally with Whisper, rewrites, and copies to your clipboard.

That is the route that genuinely saves tokens, since you paste only the clean
version. It needs Python, Qt and a speech model, which is why it is not bundled
here.

## Licence

MIT
