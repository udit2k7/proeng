# 11 — Key security

Your API keys are free, but a leaked key is still someone else spending your
quota under your name. This document covers what the tool does about that,
and - just as importantly - what it cannot do.

---

## What this tool can and cannot detect

**It CANNOT tell you that a key has leaked.**

No provider offers an API that reports "this key appeared publicly". Only they
know, and they would email you. Any tool claiming to detect a leak from the
inside is guessing.

**It CAN do these things, which cover the real risk:**

| | How |
|---|---|
| Make leaking hard | `.gitignore`, a repo scanner, a pre-commit block |
| Detect a **revoked** key | A rejected key returns HTTP 401/403 - loudly surfaced |
| Make replacement trivial | One command, hidden input |

The middle row is the practical detection point. When a key leaks, you revoke
it - and from that moment the old key returns 401. The tool now treats that as
a security event rather than a routine fallback.

---

## The four defences

### 1. Keys live in one gitignored file

`config.toml` holds every key and is line 2 of `.gitignore`. `config.example.toml`
is the committed template, with the keys blank.

### 2. Keys are never printed whole

Anywhere a key appears - error messages, logs, status output - it is redacted to
`gsk_...cE0I`. Never enough to use.

The Gemini key is sent as an `x-goog-api-key` header rather than a URL query
parameter, specifically so it cannot end up in a server log or a browser history.

### 3. A rejected key stops being silent

This was the important change. Previously a 401 just rotated to the next key and
then quietly fell through to the next tier - so a revoked key looked like
"the tool got a bit worse today".

Now, when **every** key for a provider is rejected, the tier raises `KeyRevoked`,
which the router promotes to an alert:

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  API KEY PROBLEM
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  Groq: all 1 key(s) REJECTED. The key is invalid or has been
  revoked. If you did not revoke it, treat it as compromised
  and replace it now.

  If you did not revoke this key yourself, assume it leaked:
    1. Revoke it at the provider's console NOW
    2. Create a new one
    3. .venv\Scripts\python.exe scripts\set_key.py <provider>
```

Shown even in `--quiet` mode, and surfaced through the Claude Code hook's
`systemMessage` so you see it there too.

**Note the distinction:** a 429 (rate limit) rotates quietly, because that is
normal. A 401 does not, because it never is.

### 4. A pre-commit hook blocks keys

`.gitignore` protects `config.toml`. It does nothing about a key pasted into a
script or a note while debugging - which is how keys usually escape.

```bash
.venv\Scripts\python.exe scripts\install_git_guard.py
```

Any commit containing an API-key-shaped string is refused, with the offending
file named. Bypassable with `git commit --no-verify` if it ever misfires.

Requires `git init` first. Run it again after.

---

## The commands

### Check everything

```bash
.venv\Scripts\python.exe scripts\audit_keys.py
```

Four checks:

1. Is `config.toml` gitignored?
2. Does a key appear in any other file?
3. Does a key appear in **git history**? (removing a file does not remove it
   from history - the key must be revoked)
4. Are the configured keys still accepted by their providers?

Exits 1 on anything critical, so it works in CI or a hook.

### See what is configured

```bash
.venv\Scripts\python.exe scripts\set_key.py --status
```

Redacted. Never prints a usable key.

### Replace a key

```bash
.venv\Scripts\python.exe scripts\set_key.py groq
```

Hidden prompt - the key never reaches your shell history, scrollback, or logs.

### Remove a key

```bash
.venv\Scripts\python.exe scripts\set_key.py groq --clear
```

---

## If a key leaks

In this order. Step 1 is the one that matters.

1. **Revoke it at the provider.** Everything else is housekeeping; until you do
   this, the key still works for whoever has it.
   - Groq: https://console.groq.com/keys
   - Gemini: https://aistudio.google.com/apikey
2. **Create a replacement** and install it:
   `.venv\Scripts\python.exe scripts\set_key.py <provider>`
3. **Find out how it escaped:**
   `.venv\Scripts\python.exe scripts\audit_keys.py`
4. **If it was ever in git history**, revoking is the only real fix. Rewriting
   history does not help - assume anyone who cloned the repo has it.

---

## Several keys per provider

Each provider accepts a list. Rotation spreads load and survives a rate limit:

```toml
[groq]
api_keys = ["gsk_first...", "gsk_second..."]
```

**A note on blast radius:** more keys means more to revoke if your `config.toml`
is exposed, since they all sit in the same file. The rotation is there for rate
limits, not for security. Two keys is a reasonable maximum.

---

## What is deliberately not done

- **No encryption of config.toml.** The tool would need the decryption key
  anyway, stored next to it - which protects against nothing. File permissions
  and gitignore are the honest defences.
- **No key vault or OS keychain.** Real security value, but it adds a dependency
  and a failure mode to a personal tool whose keys are free and revocable in
  thirty seconds. Worth revisiting if this ever handles paid keys.
- **No telemetry.** Nothing about your keys or usage leaves the machine, other
  than the keys themselves going to their own providers.
