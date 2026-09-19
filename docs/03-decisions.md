# 03 — Decisions

Every significant technology choice, with the reasoning and the rejected
alternatives. Written so that in six months you (or anyone else) can see *why*
rather than guessing.

---

## D1 — Language: Python 3.12

**Chosen:** Python 3.12 (already installed at
`C:\Users\uditt\AppData\Local\Programs\Python\Python312`).

**Why:** every library this project needs — Whisper, audio capture, voice activity
detection, Qt — has first-class Python support and nothing else comes close for
this particular combination.

**Why 3.12 and not the 3.14 you also have installed:** 3.14 is newer than several
of the audio and AI libraries we depend on. Some do not yet publish prebuilt
packages for it, which means failed installs and hunting for compilers. 3.12 is the
sweet spot: modern, and everything works on the first try.

**Rejected:** Electron/JavaScript — would ship a 200 MB browser to draw a small box,
and would still have to shell out to Python for the AI parts anyway.

---

## D2 — Interface toolkit: PySide6 (Qt)

**Chosen:** PySide6.

**Why:** the requirements ask for a frameless, translucent, always-on-top,
animated floating widget. Qt does all four natively on Windows and is the only
Python toolkit that does.

**Rejected:**
- *Tkinter* (built into Python) — its transparency support on Windows is a crude
  colour-key hack. You get a hole in the window, not genuine see-through. Fails R11.
- *Electron* — works, but a 200 MB runtime for this is absurd.
- *customtkinter* — prettier Tkinter, same transparency limitation.

**Cost:** PySide6 is a ~100 MB install. Acceptable given 157 GB free.

---

## D3 — Speech to text: faster-whisper, model `base.en`

**Chosen:** `faster-whisper` with the `base.en` model, int8 quantised.

**Why faster-whisper over plain Whisper:** it is the same model re-implemented on
CTranslate2. On a CPU it is roughly **4x faster and uses about half the RAM** for
identical output. On a laptop with no GPU and little free RAM, that is decisive.

**Why `base.en` and not something bigger:**

| Model | Disk | RAM when loaded | Speed on your CPU | Accuracy |
|---|---|---|---|---|
| `tiny.en` | 75 MB | ~250 MB | very fast | noticeably error-prone |
| **`base.en`** | **150 MB** | **~400 MB** | **fast** | **good — our default** |
| `small.en` | 500 MB | ~1 GB | moderate | very good |
| `medium.en` | 1.5 GB | ~2.5 GB | slow | excellent |

`base.en` is the default because of your RAM situation (see D7). `small.en` is a
one-line config change if you free up memory and want better accuracy — and
honestly, once you've used it a while, I expect you'll want `small.en`.

**Why `.en` (English-only) variants:** they are smaller and more accurate than the
multilingual versions *at the same size*, because they aren't spending capacity on
other languages. If you ever want to dictate in Hindi, we switch to `base` (no
`.en`) — same size, slightly lower English accuracy.

**Rejected:**
- *Windows built-in dictation* — not controllable from code; can't do the 7-second rule.
- *Cloud speech APIs* — would send your voice off the machine and break R3 (offline).

---

## D4 — The rewriting engine: three tiers

This is the decision you asked me to make, so here is the full reasoning.

### The candidates

**Ollama (local LLM)**
- Free forever, fully offline, private.
- On *your* machine: no GPU, so it runs on CPU only. A 3B model produces roughly
  10–20 tokens per second. A typical rewrite is ~200 tokens. **So: 10–20 seconds
  of waiting, every time.**
- Needs ~2.5 GB RAM while running.

**Groq (cloud API)**
- Genuinely free tier, generous limits for personal use.
- Absurdly fast — it runs on custom hardware. **Under 1 second**, typically ~300ms.
- Does **not** touch your Claude or ChatGPT quota, which satisfies R2 fully.
- Needs internet. Your text goes to their servers.

**Rule-based (plain code)**
- Instant, free, offline, no dependencies, no RAM.
- But it can only reorganise and clean — it cannot genuinely rewrite. It removes
  "uh", fixes punctuation, and slots your sentences into a template. That is
  useful, but it is not the same as a model understanding your intent.

### The decision

**Build all three with automatic fallback.** Not a compromise — the right answer.

The reason is that ~80% of the work in this project is shared no matter which
engine you use: the widget, the microphone, the silence detection, the clipboard.
The engines themselves are each a small, self-contained file. Adding the second and
third costs maybe a day, and buys:

- **Speed when you're online.** You get sub-second rewrites almost always, because
  you almost always have internet.
- **True offline capability.** R3 is satisfied for real, not on paper.
- **It never breaks.** No API key, no internet, Ollama not running, Groq changed
  their free tier — it still works. Tier 3 has no dependencies whatsoever.

**Default order:** Groq → Ollama → Rules.
**With "Offline Only" toggled on:** Ollama → Rules.

### Which Groq model
`llama-3.3-70b-versatile` was the original choice. **Groq has since retired it** -
superseded by D19.

### Which Ollama model
`qwen2.5:3b-instruct-q4_K_M` — about 2 GB on disk, ~2.5 GB RAM when running.
Chosen because Qwen 2.5 at 3B is unusually strong at instruction-following for its
size, which is exactly the skill a rewriter needs. Fits your 2.5 GB download budget.

*Fallback if RAM is too tight:* `qwen2.5:1.5b-instruct-q4_K_M` (~1 GB, ~1.2 GB RAM).
Faster and lighter, meaningfully worse quality.

---

## D5 — Silence detection: webrtcvad

**Chosen:** `webrtcvad`.

**Why:** R6 needs a reliable 7-second silence trigger. The naive approach — check
if the microphone volume is below some number — fails badly in the real world.
Your laptop fan, keyboard, air conditioner, and street noise all register as
"sound", so the timer either never fires or fires while you're mid-thought.

`webrtcvad` is Google's voice-activity detector, extracted from the code that
powers browser video calls. It distinguishes *human speech* from *noise*, which is
precisely the question we need answered.

**Setting:** aggressiveness level 2 of 0–3. Level 3 is the most aggressive at
rejecting noise, but it can also clip quiet speech — cutting you off mid-sentence,
which would be maddening. Level 2 is the practical balance. Tunable in config.

---

## D6 — Configuration: a plain TOML file

**Chosen:** a `config.toml` file you can open in Notepad.

**Why:** R13 says keep it simple. Building a settings screen is real work and you'd
open it perhaps twice a year. A text file with comments is faster to build, easier
to change, and easy to back up.

**Important:** `config.toml` holds your Groq API key, so it is listed in
`.gitignore` and never committed. A `config.example.toml` with the key blanked out
*is* committed, so the repo is usable if this ever goes public.

---

## D7 — RAM budget (the tight constraint)

Your laptop has 15.7 GB, but only **1.7 GB was free** when measured. The rest is
held by your browser, Claude Code, and whatever else is open.

Here is what the tool actually needs at peak:

| Component | RAM |
|---|---|
| Python + PySide6 widget | ~180 MB |
| Whisper `base.en` | ~400 MB |
| Audio buffers | ~20 MB |
| **Subtotal (Tier 1 or 3 — Groq or Rules)** | **~600 MB** |
| Ollama `qwen2.5:3b` (Tier 2 only) | +2,500 MB |
| **Total with local LLM** | **~3,100 MB** |

**What this means:**

- Using Groq or Rules, ~600 MB — **fits comfortably in your 1.7 GB free.** Good.
- Using Ollama, ~3.1 GB — **does not fit right now.** Windows would start swapping
  to disk, and the already-slow 10–20s rewrite could stretch past a minute.

**How we handle it:**

1. Groq is the default tier precisely because it is the light one.
2. Ollama is the offline fallback, used rarely — and when you're offline you're
   probably not running twelve browser tabs anyway.
3. The tool will **check free RAM before loading Ollama** and, if there isn't
   enough, tell you plainly rather than grinding to a halt.
4. If you want Ollama to be comfortable day-to-day, closing browser tabs is the
   real fix — or we drop to the 1.5B model.

---

## D8 — Global hotkey: yes

**Chosen:** a system-wide hotkey (default `Ctrl+Shift+Space`) in addition to
clicking the character.

**Why:** your hands are already on the keyboard while you code. Reaching for the
mouse to click a small character breaks flow every single time. This is a handful
of lines of code for a disproportionate gain.

---

## D9 — Auto-paste: not in version 1

**Considered:** having the tool paste directly into whatever window you were last
using, rather than just copying.

**Deferred.** It requires simulating keystrokes into another application, which is
fiddly, occasionally triggers antivirus heuristics, and misbehaves against
terminals and Electron apps — which is exactly where you'd use it. Copy-then-paste
is one extra keystroke and is completely reliable.

Revisit after the core tool has been in daily use for a while.

---

## D10 — Prompt history: yes, small and local

**Chosen:** the last 50 prompts, stored in a local SQLite file.

**Why:** cheap to build, and genuinely useful — you will want to re-copy something
from ten minutes ago, and you will want to reuse a prompt shape that worked well.

**Not synced anywhere. Not uploaded. Clearable with one button.**

---

## D11 — Target-specific prompt styles: yes

**Chosen:** a three-way toggle — Claude Code / ChatGPT / Gemini.

**Why:** R14. The three differ enough to matter:

- **Claude Code** wants file paths, concrete constraints, and a clear statement of
  done. It responds well to explicit structure and dislikes vagueness.
- **ChatGPT** responds well to a stated role and a specified output format.
- **Gemini** responds well to explicit context boundaries and numbered steps.

The differences live entirely in the instruction templates under
`rewrite/prompts/`. Adding a fourth target later means adding one text file.

---

## D15 — Ollama dropped; Gemini becomes tier 2

**Supersedes the Ollama parts of D4.**

**Decision:** the tier chain is now **Groq -> Gemini -> rules**. No local LLM.

**Why:** the user works exclusively with online tools - Claude Code and Codex.
A prompt rewriter that works offline is solving a problem they do not have. The
offline requirement (R3) was stated before that became clear.

What dropping it buys:

- No 2.5 GB model download, no 3 GB RAM spike, no RAM guard logic
- No 15-60 second rewrites; every path is now sub-second
- Phase 4 disappears entirely
- Quality goes up: a 3B local model was always going to be the weakest tier

**What replaces it:** Google's Gemini free API as tier 2. A second, independent
cloud provider means a Groq rate limit or outage degrades nothing - it fails over
in under a second instead of dropping to a 3B model or to rules.

**The remaining offline story:** the rules tier. It needs no network, no key and
no model, so the tool still produces structured output on a plane. Lower quality,
but never a dead end.

**Reversible.** The tier interface is unchanged, so `ollama.py` can be added later
as a third tier if the need ever appears. Nothing about this decision blocks it.

---

## D16 — Rewrite trigger: an explicit prefix

**Chosen:** in the Claude Code and Codex hooks, only prompts beginning with `++`
are rewritten. Everything else passes through untouched.

**Why:** short prompts - "yes", "run the tests", "commit this" - are already fine.
Rewriting them adds latency and risks mangling a perfectly good instruction.

**Rejected:** automatic rewriting above a word count. It would work most of the
time and then surprise the user at the worst possible moment, which is the wrong
failure mode for something sitting in the path of every prompt.

---

## D17 — The rewriter must be domain-neutral

**Chosen:** nothing in the instructions or the rules tier assumes the request is
about software.

**Why:** an earlier version of `instructions.py` opened with "prompts for AI
coding assistants", and the Claude template told the model to look for file paths.
That quietly biased every rewrite towards technical structure.

The user dictates software work, but also stories, scripts, research, planning
and business writing. A rewriter that strains to find file paths in a story idea
is worse than useless - it distorts the request.

**What changed:**

- The system prompt now states explicitly that the request may be about anything,
  and to use the vocabulary of the user's domain rather than a software one.
- Rule 4 (copy specifics exactly) was widened from "file paths, library names,
  error messages" to also cover character names, place names, titles, dates and
  quotes.
- A new rule 9: preserve the register of the request. A creative brief must not
  come back sounding like a technical specification.
- The rules-tier cue lists gained non-technical entries ("write me", "the tone
  should", "set in", "the audience", "as a list").
- The Claude template now says: if the request is not about code, do not invent
  technical framing for it.

**Verified** on a creative sample (a short story brief) and a technical one, both
through the rules tier. The structure - Goal, Context, Requirements, Output, Open
questions - turns out to be genuinely domain-neutral; only the wording around it
needed fixing.

---

## D18 — Several API keys per provider

**Chosen:** each cloud tier accepts a list of keys and rotates between them.

**Why:** free tiers are rate-limited per key. With one key, a heavy session drops
to the next provider and eventually to the rules tier - a quality cliff. With
several, a rate limit costs nothing.

**How:** round-robin with an advancing start offset, so load spreads across keys
instead of hammering the first until it dies. A 401 or 429 moves to the next key;
a timeout or connection error does not, because those are about the network and
another key would fail identically.

**Safety:** keys are never logged whole. Error notes show `gsk_...abcd`.

Config takes either form:

```toml
api_key  = "one-key"
api_keys = ["first", "second"]   # a list wins over the single value
```

---

## D19 — Groq model: openai/gpt-oss-120b

**Supersedes the model choice in D4.**

`llama-3.3-70b-versatile` no longer exists. The first real API call returned
HTTP 404; querying the models endpoint confirmed it had been withdrawn.

Measured on the live free tier, 2026-09-19, rewriting the 109-word project pitch:

| Model | Time | Result |
|---|---|---|
| **`openai/gpt-oss-120b`** | **1.92s** | **Accurate, well structured - chosen** |
| `qwen/qwen3.8-27b` | 1.02s | Good, slightly more verbose |
| `openai/gpt-oss-20b` | 1.77s | **Returned empty output** - unusable |

**Chosen: `openai/gpt-oss-120b`.** It is the largest available and the most
reliable at following the instruction rules. `qwen3.8-27b` is nearly twice as
fast and a reasonable alternative if 1.9s ever feels slow.

**Timeout raised 3s -> 8s.** The original 3s was set assuming sub-second
responses; at 1.9s typical it left no margin for a slow network.

**Lesson worth keeping:** hosted model names are not stable. `scripts/list_models.py`
now exists to answer "what can my key actually use?" whenever a 404 appears.

---

## D20 — Normalise model output to ASCII

**Chosen:** fold typographic characters to ASCII in `rewrite/clean.py`, applied
centrally in the router so every tier benefits.

**Why:** the first live Groq call crashed on a non-breaking hyphen (U+2011) -
`'charmap' codec can't encode`. Windows consoles default to cp1252 and cannot
render much of what models emit.

Beyond the crash, the output gets pasted into terminals, JSON and code, where a
curly quote is noise at best and a syntax error at worst. Worse, a non-breaking
hyphen looks identical to a hyphen but is not one, so a copied `--verbose` flag
silently fails to match.

Also: the CLI now forces UTF-8 on stdout, as a second line of defence.

---

## D21 — Gemini model: gemini-3.5-flash-lite

`gemini-2.5-flash` returned HTTP 404: *"no longer available to new users"* -
retired for new keys, exactly as the Groq model had been. Two providers, same
lesson in one session.

Measured on the live free tier, 2026-09-19:

| Model | Time | Result |
|---|---|---|
| **`gemini-3.5-flash-lite`** | **1.75s** | **Clean, correct - chosen** |
| `gemini-3-flash-preview` | 7.72s | Best quality, too slow for a fallback |
| `gemini-3.6-flash` | 9.52s | **Emitted a "style check:" preamble** - broke rule 6 |
| `gemini-3.8-flash` | - | HTTP 503, persistently overloaded |
| `gemini-2.5-flash` | - | HTTP 404, retired |

**Chosen: `gemini-3.5-flash-lite`.** Gemini is the *backup* tier - it only runs
when Groq has already failed, so the user is waiting twice over. 1.75s and clean
beats 7.7s and marginally better.

`gemini-3.6-flash` is worth noting: newer did not mean better. It ignored the
"output the prompt and nothing else" rule and would have put a `style check:`
preamble straight onto the clipboard.

**Timeout raised 5s -> 10s**, matching the Groq change in D19.

---

## D22 — Key security: detect revocation, not leakage

**The honest framing first.** The tool cannot detect that a key has leaked. No
provider exposes an API for it. What it *can* detect is a key that has been
**revoked** - which is the state a key enters the moment you rotate it because
it leaked. That is the practical detection point, and the design targets it.

**The important change:** a rejected key used to be silent. HTTP 401 rotated to
the next key, then fell through to the next tier. A revoked key therefore looked
like "the tool got a bit worse today" - precisely the failure mode to avoid.

Now, when every key for a provider is rejected, the tier raises `KeyRevoked`
(a subclass of `TierUnavailable`, so careless callers still degrade gracefully).
The router promotes it to an `alert` on the result, which the CLI prints as a
banner - even under `--quiet` - and the Claude Code hook surfaces via
`systemMessage`.

**The distinction that matters:** HTTP 429 (rate limit) rotates quietly, because
that is normal. HTTP 401 never is.

**The other defences:**

| | |
|---|---|
| `scripts/audit_keys.py` | Scans files, **git history**, and asks each provider if the key still works |
| `scripts/install_git_guard.py` | Pre-commit hook refusing any commit containing a key |
| `scripts/set_key.py` | Hidden-input replacement; `--status`, `--clear` |
| Redaction | Keys are never printed whole - `gsk_...cE0I` |

Git history is checked specifically because deleting a key from a file does not
delete it from history. Only revocation fixes that.

**Verified** by planting a fake key in the tree and confirming the scanner
flagged it, and by calling Groq with an invalid key and confirming `KeyRevoked`
was raised with a usable message.

**Deliberately not done:** encrypting `config.toml` (the tool would need the
decryption key stored beside it, protecting nothing) and OS keychain integration
(real value, but a dependency and a failure mode for a personal tool whose keys
are free and revocable in thirty seconds). Revisit if paid keys are ever used.

---

## D23 — updatedPrompt does not work; use additionalContext

**Superseded twice before landing here.** Recorded in full because the sequence
is more instructive than the answer.

### What was tried

| Attempt | Shape | Result |
|---|---|---|
| 1 | `updatedPrompt` nested inside `hookSpecificOutput` | Prompt unchanged |
| 2 | `updatedPrompt` top-level, sibling of `hookSpecificOutput` | Prompt unchanged |
| 3 | Both placements + an `additionalContext` marker | **Marker arrived; prompt still unchanged** |

Attempt 3 settled it. This build of Claude Code **consumes hook output but
ignores `updatedPrompt` entirely**. `additionalContext` works.

Two documentation reads gave two different placements for `updatedPrompt`, and
neither took effect. The experiment gave an answer that did not depend on
interpreting anything.

### What the hook does now

Sends the rewrite through `additionalContext`, framed so the model knows to
prefer it over the raw wording. `updatedPrompt` is still emitted, harmlessly, so
a future build that supports it upgrades this hook with no code change.

### The cost, stated plainly

**The original rambling words still reach Claude.** Replacement would have
removed them; context injection cannot. So this does **not** save input tokens
the way the plan assumed - it buys clarity, not brevity.

R2 still holds: the *rewriting* runs on Groq's free tier and never touches Claude
quota. But the token-saving argument for the hook specifically is weaker than
claimed in D16, and the honest benefit is that the model stops misreading
rambling requests.

For genuine token saving, the desktop widget route - dictate, copy, paste only
the clean version - remains strictly better. The hook wins on convenience.

### Why three attempts were needed

Every signal said attempts 1 and 2 worked. The hook was invoked, reached Groq,
rewrote in ~1.5s, exited 0, emitted valid JSON, and all nine tests passed. Claude
Code raised no error. It silently ignored an unrecognised field.

**The tests were the real failure.** `test_hook.py` checked for `updatedPrompt`
in whichever place the hook was putting it - so it asserted our own assumption
rather than any real contract, and passed while the feature did nothing. Twice.

A test written from the same misreading as the code cannot catch that
misreading. What caught it was the `++` still being visible in the prompt Claude
received - end-to-end observation, not unit testing.

`test_hook.py` now asserts `additionalContext` is present and framed, which is
the behaviour actually observed to work.

### Carry forward

1. **A hook that runs, succeeds and logs cleanly is not a hook whose output is
   being used.** Verify the effect, not the exit code.
2. **When docs and behaviour disagree, measure.** Emitting every candidate shape
   at once, plus a marker on a known-good channel, answered in one round-trip
   what two doc reads got wrong.
3. **`hook.log` earned its place.** It turned "is it even running?" from
   speculation into a one-line answer, three times.

---

## D24 — Live transcription, and what it costs

**The gap:** R4 promised text appearing while you speak. Phase 3 shipped without
it - audio was recorded, then transcribed only after you stopped. The listening
indicator was correct and the silence was correct-as-built, but it was not what
had been promised. Found by the user, not by any test.

**How it works now:** every `partial_interval` seconds the recorder hands the
audio-so-far to a callback, which transcribes it and shows the text. Cheap here
because transcription runs at 0.05x realtime (D13) - a 10s clip costs ~0.5s.

Partial passes skip Whisper's VAD filter. A clip that stops mid-sentence often
gets trimmed to nothing by it, which is precisely the case we want text for.

### The scheduling problem, and two wrong answers

Each preview re-transcribes the **whole** clip, so cost grows as you talk.

*First attempt:* react after an expensive call - if it took too long, widen the
gap. Wrong: it reacts one step late, so it overshoots every time the cost climbs.

*Second attempt:* predict the next cost from the observed speed, and cap the gap
at 8s. Better on this laptop, but the cap is a trap - cost keeps growing while
the gap cannot, so on a slower machine previews eventually take longer than the
space between them and the audio queue grows without bound. A runaway, not a
slowdown.

*What it does now:* predict the cost, and if previews cannot be scheduled at a
third of the gap without exceeding 8s, **stop previewing for the rest of the
recording**. Also stop unconditionally past 45s of audio.

Stopping is the honest response. No words are lost - the full transcript still
arrives when you stop speaking. You simply stop seeing it early.

Simulated over time in `scripts/test_partials.py`:

| Machine | Result |
|---|---|
| This laptop (0.05x) | Previews to the 45s cutoff, 31% of time, worst ratio 0.34 |
| 5x slower (0.25x) | Previews stop at ~8s, worst ratio 0.46 |
| 1.0x realtime | One preview, then stops |

**The test earned its place twice.** Its first version paired fixed clip lengths
with intervals that would have changed those lengths - incoherent, and it flagged
a false failure. Rewritten as a proper time-stepped simulation, it then found the
real 8s-ceiling runaway, which no amount of reading the code had surfaced.

---

## D25 — Hindi, and words Whisper has never heard

Two transcription problems, same root: the defaults assumed English technical
dictation and nothing else.

### English-only models fail silently

`base.en` and its siblings are English-**only**. Ask one for Hindi and it
returns silence or invented English - no error, no warning. A baffling bug.

`TranscribeConfig.resolve()` now catches it: any non-English language
automatically switches to the multilingual model of the same size
(`base.en` -> `base`). Slightly weaker at English, handles everything else.

Set `language = "hi"` for Hindi, or `"auto"` to detect - which is the setting
that handles switching between Hindi and English mid-sentence.

**Worth knowing:** `base` is noticeably weaker at Hindi than at English. If
Hindi dictation matters, `small` or `medium` are a large step up, and this
laptop has the speed headroom for either (D13).

### "Groq" comes back as "Grog"

Whisper has never heard most of our vocabulary. A small model guesses at
whatever is phonetically nearest: Groq, Grok, Grog, rock.

Whisper accepts an `initial_prompt` that biases decoding towards a supplied
vocabulary. `TranscribeConfig.vocabulary` now lists the words this project
actually uses - Groq, Gemini, Ollama, PySide, venv, TOML and so on.

It costs nothing and is editable in one place. Add your own project's jargon to
that list and it stops being mangled.

---

## D26 — Panel geometry: two bugs found by using it

Both reported from a screenshot, neither caught by any test that existed.

### The copy button fell off the screen

`_fit_height` grew the panel to fit a long result, but grew it **downward from a
Y chosen for the old, shorter height**. A long enough result pushed the bottom -
including the copy button - past the bottom of the display, where it could not be
clicked or scrolled to.

Growing now re-clamps both height and position: the height is capped at the
usable screen height, and the panel is pulled up if it would overflow.

**Also added: Ctrl+Shift+C** copies the result from anywhere in the panel. A
button can end up out of reach; a keystroke cannot. Belt and braces for a bug
whose whole nature was "the thing you need is unreachable".

### The panel did not follow the character

The character could be dragged anywhere, but the panel stayed where it was -
so the two drifted apart and the connection between them looked accidental.

`Character` now emits `moved` during a drag and throughout the edge-snap
animation, and the panel repositions immediately. Deliberately not animated:
an animation would lag behind the mouse and feel broken.

### Worth carrying forward

Both are geometry bugs, and geometry is exactly what a smoke test that only
checks "does it construct?" will never catch. `smoke_ui.py` now renders a
deliberately over-long result and asserts the panel is still entirely within the
screen, and that dragging the character moves the panel.

The general lesson matches D23: a test that only exercises the happy path
confirms the code runs, not that it works.

---

## D27 — Defaults changed for Hindi: small, auto

The user dictates in **both Hindi and English**, sometimes in the same sentence.
`base.en` could serve neither - English-only, and small enough that Hindi would
be poor even if it were multilingual.

**Defaults are now `model = "small"`, `language = "auto"`.**

- `small` is multilingual and markedly better at Hindi than `base`.
- `auto` detects per utterance, so switching language mid-session needs no
  setting change.

**What it costs:**

| | `base.en` | `small` |
|---|---|---|
| Disk | 150 MB | 460 MB |
| RAM | ~400 MB | ~1 GB |
| Speed | 0.05x realtime | ~0.15x realtime |
| Languages | English only | ~99, including Hindi |

A 30-second dictation goes from ~1.5s to ~4.5s. Still far faster than speaking,
and the RAM is affordable now that ~6 GB is free (D14).

**Honest limits:** `auto` occasionally mis-detects on very short clips, and
heavy Hindi-English code-switching within one sentence is hard for any Whisper
model. `medium` would be better again at ~2.5 GB RAM and ~0.4x realtime, if
`small` proves insufficient - this laptop can afford it.

---

## D28 — A Stop button, and why "listening" got stuck

**Reported:** it kept saying "listening" after the user had stopped talking.

### The cause

`webrtcvad` answers "is this speech?" - not "is this the person at the
microphone?". Someone talking nearby is speech, so the silence timer kept
resetting and the recording never ended on its own.

Enter already stopped it, but Enter only works while the panel holds keyboard
focus. Click anywhere else mid-dictation and the key goes nowhere, leaving no
visible way out.

### Two fixes, because one is not enough

**1. A visible Stop button.** The only solid button in the panel while
recording, so it is findable without reading anything. It disables itself on
click - stopping takes a moment, and a second click in that window would be
confusing. Enter still works; they emit the same signal.

**2. A loudness gate.** Speech must now clear an RMS threshold *and* pass the
voice detector before it counts as yours. Distance is the one signal that
separates you from the room: you are close to the microphone, other people are
not.

`speech_level_threshold` defaults to 300 of 32768 - low enough not to clip a
quiet speaker, high enough to ignore a conversation across a room.

| Symptom | Fix |
|---|---|
| Still "listening" after you stop | Raise it (600-900 in a noisy office) |
| Cut off mid-sentence | Lower it (150 if soft spoken or far from the mic) |

**Why both.** The gate is the real fix and will handle most cases, but it is a
heuristic with a threshold that depends on the room, the microphone and the
voice. A manual stop is certainty. A tool that can hang with no visible way out
is worse than one that occasionally needs a click.

**Rejected:** raising `vad_aggressiveness` to 3. It rejects more *noise*, but
background speech is still speech - it would not have touched this, and it
clips quiet speakers.

---

## D29 — The vocabulary hint invented a word

**Reported:** "Ollama" appeared in a transcript. We removed Ollama from this
project in D15 and it is not in the config or the tier chain.

**Cause:** it was in `TranscribeConfig.vocabulary`, passed to Whisper as
`initial_prompt`. That parameter does not only correct spellings - on unclear
audio Whisper will **insert** words from the prompt that were never spoken.
A long list of exotic terms makes it worse, and mine had 28 of them including
one we no longer use.

**Fixed:** trimmed to seven words that are both frequently spoken here and
reliably mis-heard - Groq, Gemini, Claude Code, ChatGPT, Codex, API key, prompt.

**The rule now written into the code:** only add a word if it is both common in
your dictation AND actually mis-transcribed. If something starts appearing
unbidden, take it out.

An uncomfortable irony: the hint existed to stop "Groq" becoming "Grog", and it
introduced a worse failure than the one it fixed. Biasing a model towards
vocabulary is not free.

---

## D30 — A settings dialog, reversing part of D6

**D6 chose a plain TOML file over a settings screen**, reasoning that it would be
opened twice a year. That held for sizes and timeouts. It did not hold for API
keys.

Keys get rotated, revoked and replaced - D22 is entirely about making that easy.
Answering "how do I change my key?" with "run this CLI script" is a poor answer
when the tool is already on screen.

**In the dialog** (gear button beside the close button, and both menus):

- Both API keys, masked by default with a reveal
- Dictation language, as a dropdown rather than a code to look up
- Microphone sensitivity, the one setting that needs tuning by feel (D28)

**Everything else stays in the file.** Sizes, timeouts, tier order and the hotkey
are still config.toml only - D6's reasoning is intact for those.

**How it saves:** by editing the matching lines in place, not by re-serialising
the file. config.toml is mostly comments explaining what each setting does, and
a round-trip through a TOML writer would discard all of them. Verified: 52
comment lines before, 52 after.

**What applies immediately:** keys, language, sensitivity - the next dictation
picks them up, and the loaded speech model is dropped so a language change gets
the right one. Sizes and the hotkey still need a restart, because widgets read
them at construction.

---

## D31 — The Stop button did nothing (Qt cross-thread delivery)

**Reported:** clicking Stop showed "stopping..." and then kept listening.

### Cause

`panel.stop_recording` was connected to `worker.stop_recording` with a default
connection. The worker lives on another thread, so Qt chose a **queued**
connection - it posts the call to that thread's event loop.

But during a recording the worker is inside `Recorder.record()`, a loop that
never returns to its event loop. So the queued "stop" sat in the queue until
recording ended on its own, which is precisely the thing it was meant to cause.

**The tell we had all along:** Esc worked. `hide_panel()` calls
`self.worker.stop_recording()` as a plain Python call from the UI thread, which
bypasses Qt's delivery entirely. Same method, two call paths, only one working.

### Fix

Connect that one signal with `Qt.ConnectionType.DirectConnection`, so it runs
on the UI thread.

**Safe here and only here.** `Recorder.stop()` does exactly one thing - set a
`threading.Event`, which exists for cross-thread signalling. Nothing is read,
nothing is mutated, no Qt object is touched. Using DirectConnection for
anything that touches worker state would be a data race.

### Why no test caught it

`smoke_ui.py` checked that clicking Stop **emitted the signal**. It always did.
What failed was **delivery**, and delivery only fails when the receiving thread
is blocked - which a smoke test running everything on one thread never
reproduces.

`scripts/test_stop.py` now does reproduce it: a fake worker blocks its own
thread exactly as a recording does, Stop is pressed 0.4s in, and the test
asserts it lands. It runs **both** connection types and expects the queued one
to fail - so if Qt's behaviour ever changes, the test says so rather than
silently passing.

Measured: DirectConnection stops in **16ms**; QueuedConnection **never stopped**
and ran the full 3 seconds.

### Carry forward

Third time this project has hit the same shape of problem (D23, D26, now this):
**a test that exercises the mechanism on the happy path proves the code runs,
not that it works.** Emitting a signal is not delivering it. Returning valid
JSON is not having it honoured. Constructing a widget is not placing it on
screen.

---

## D32 — Any OpenAI-compatible provider

**Why:** Groq and Gemini are free and fast, but not universally reachable. Some
countries block them, some workplaces forbid them, and plenty of people already
pay for something else. Tying the tool to two providers limited who could use it
at all.

**Chosen:** one adapter speaking the OpenAI chat-completions shape, plus
`[[custom]]` entries in config.toml. That one format covers OpenRouter,
DeepSeek, Together, Mistral, Cerebras, Fireworks, OpenAI itself - and, notably,
**local servers**: Ollama, LM Studio, vLLM, llama.cpp, LocalAI.

So the local-model option cut in D15 is back, without any of its complexity:
point `base_url` at `http://localhost:11434/v1`, set `requires_key = false`,
and the tool runs entirely offline again. `offline_only` keeps localhost tiers
and skips remote ones automatically.

**Error messages name the likely cause**, because a misconfigured endpoint is
the normal case here: a 404 says to check base_url and the model name, and a
non-OpenAI response says so rather than reporting a parse error.

---

## D33 — Themes: light, dark, follow-Windows, eight accents

**Chosen:** `scheme` (dark / light / system) and `accent` in `[ui]`, both in the
settings dialog with colour swatches. `system` reads `AppsUseLightTheme` from
the registry.

**The light scheme is not an inverted dark scheme.** A translucent panel over a
light desktop is a harder problem: pale text on pale wallpaper disappears. So
light has its own opacity floor of 0.80 against dark's 0.50, and
`effective_opacity()` silently raises a too-low setting rather than letting
someone configure an unreadable panel and conclude the tool is broken.

Hover tints also invert - a white overlay is invisible on a light panel - which
is why the stylesheet takes a `tint` rather than hardcoding white.

**Custom hex accepted:** `accent = "#7FBF6A"` works, and the dialog keeps a
hand-typed hex rather than resetting it to amber.

**Verified:** all 27 scheme x accent combinations render with no unresolved
template tokens, and a round-trip through the dialog preserved all 119 config
comments and both API keys.

---

## D34 — No advertising

**Requested:** a small ad in the panel, to monetise the tool.

**Declined, with the reasoning, because it would damage the project:**

1. **It contradicts the privacy promise.** Ad networks require an identifier -
   IP, user agent, often a device ID - sent on every impression. The tool
   currently sends nothing anywhere except the user's own text to the user's
   own API key. An ad slot would make "we share no data" untrue, and that claim
   is one of the genuinely good things about this tool.
2. **Ad networks do not serve desktop apps.** AdSense terms cover websites;
   desktop inventory means a specialised SDK, and those are aimed at mobile
   games.
3. **The revenue would be pennies.** Display advertising pays roughly $1-5 per
   thousand impressions. A few hundred developer users would generate cents a
   month - far less than the effort, and far less than the goodwill it costs.
4. **Developers react badly to ads in developer tools.** For a new project with
   no reputation yet, this is the kind of thing that ends adoption rather than
   funding it.

**Offered instead:** GitHub Sponsors, plus optionally a single static line in
the About area reading "Supported by <name>", served from the project's own
repository. No third party, no tracking, no request leaving the machine that
the user did not initiate. Sponsors pay the author directly.

This is the same conclusion as the monetisation analysis: the tool is worth more
as a credential than as a revenue source, and the multilingual dictation angle
is the part with actual commercial potential.

---

## D12 — Unload the speech model when idle

**Chosen:** drop the Whisper model out of memory after 10 minutes of no use, and
reload it on the next activation.

**Why:** the tool sits on screen all day but is used in short bursts. Holding
~400 MB permanently for something used a few times an hour is wasteful on a 16 GB
machine. Measured on this laptop, a cached reload takes **1.2 seconds** — fast
enough that it happens while the panel is still sliding open.

**Effect:** idle cost drops from ~600 MB to ~180 MB.

**Cost:** the first dictation after a long gap has a ~1.2s delay before text starts
appearing. Acceptable. If it turns out to be annoying in daily use, the timeout is
one line in config.

---

## D13 — Measured results from Phase 1

Recorded here because these numbers settled several open questions.

Measured 2026-09-19 on the i7-1355U, `base.en`, int8, CPU only:

| Metric | Result |
|---|---|
| 20.6s of speech transcribed in | **0.9s** |
| Realtime factor | **0.05x** (20x faster than talking) |
| Model load, cached | 1.2s |
| Auto-stop on silence | worked correctly |

**What this changed:**

1. **Speed is a non-issue.** We budgeted for transcription being a bottleneck. It
   is not, by a wide margin.
2. **That headroom should be spent on accuracy.** At 0.05x we can afford `small.en`
   (roughly 3x slower, ~0.15x realtime) for noticeably better handling of technical
   vocabulary — which is most of what gets dictated here.
3. **D12 became worth doing**, because a 1.2s reload is cheap enough to make
   unloading painless.

**Still unverified:** transcription *accuracy* on technical words. Speed was
measurable without a human; accuracy needs real dictation. Pending a `small.en`
comparison run.

---

## D14 — Memory environment (context for D7)

The original D7 RAM budget assumed 1.4 GB available, which made Ollama unusable.
That has been fixed at the source rather than designed around.

Disabled permanently at startup: Microsoft Teams, new Outlook, Adobe Acrobat
Synchronizer, Samsung Bixby (service set to Disabled). Android Studio and its
Gradle daemons are closed when not in use.

**Result: 1.44 GB → 5.96 GB available.** Ollama's ~3 GB now fits comfortably, so
the RAM guard in `config.toml` (`min_free_ram_mb`) becomes a safety net rather than
a constant obstacle.
