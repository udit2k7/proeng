# 04 — The Rewrite Engine

This is the part that actually solves your problem. Everything else is plumbing.

---

## What "a good prompt" means here

A good prompt is not a longer prompt. It is a prompt where the AI cannot easily
misunderstand you. Concretely, it answers five questions:

1. **What do you want?** — one clear sentence, up front.
2. **What's the situation?** — the background the AI needs and nothing more.
3. **What are the rules?** — constraints, things to avoid, technologies to use.
4. **What should come back?** — code? a plan? a file? how long?
5. **What's unclear?** — anything you left ambiguous, surfaced instead of guessed.

The rewriter's whole job is to take your ramble and fill in those five slots.

---

## Worked example

This is roughly what you said to me at the start of this project, and what the tool
should produce from it.

### Raw input (what you say)

> uh so I want to make an offline tool which can be installed on my system and can
> uh as I do voice to text and write text as well so sometimes that is not as much
> as a good prompt so I want an offline tool which can take uh my word as I talk or
> maybe as I write and convert it into a good prompt for you Claude Code ChatGPT and
> Gemini I use all three uh so that I can save tokens because I can think uh that
> when I give long prompts it hallucinates and give something that is not as per my
> requirement

### Rewritten output, targeting Claude Code

> **Goal**
> Build an offline desktop tool for Windows that converts spoken or typed input
> into a well-structured prompt.
>
> **Context**
> I work across Claude Code, ChatGPT, and Gemini. My natural speech and typing
> produce long, unstructured prompts, which lead to misunderstood requirements and
> wasted tokens.
>
> **Requirements**
> - Accepts voice input (live speech-to-text) and typed input
> - Runs offline, installed locally
> - Outputs a prompt optimised for Claude Code, ChatGPT, or Gemini
>
> **Output**
> A working tool, plus a short explanation of the approach.
>
> **Open questions**
> - Preferred programming language?
> - Should the rewriting run fully locally, or is a free cloud API acceptable?

Notice what happened: the filler is gone, the repetition is merged, the order is
fixed, and — crucially — the two things you left genuinely open have been raised
as questions rather than guessed at.

---

## The three tiers in detail

### Tier 1 — Groq (cloud, default)

Sends your raw text to Groq's free API along with an instruction template telling
it how to restructure.

- **Speed:** ~1.9s measured.
- **Quality:** highest of the three.
- **Cost:** free. Does not touch Claude or ChatGPT quota.
- **Needs:** internet, and a free API key from console.groq.com.
- **Model:** `openai/gpt-oss-120b`. (`llama-3.3-70b-versatile` was the original
  choice but Groq retired it - see D19.)

**Failure handling:** if the request errors, times out (8 seconds), or hits a rate
limit, it falls through to Tier 2 silently. You are never left staring at an error.

With several keys configured, a rate limit rotates to the next key before giving
up on the provider — see D18.

### Tier 2 — Gemini (cloud, backup)

The same instruction template, sent to Google's free API instead.

- **Speed:** ~1s.
- **Quality:** comparable to Tier 1.
- **Cost:** free. Does not touch Claude or ChatGPT quota.
- **Needs:** internet, and a free API key from aistudio.google.com.
- **Model:** `gemini-2.5-flash`.

**Why a second cloud provider rather than a local model:** the user works
exclusively online, so a local tier was solving a problem they do not have. Two
independent providers mean a rate limit or outage on one costs nothing. See D15.

**Failure handling:** falls through to Tier 3, with a short note saying why.

### Tier 3 — Rules (always available)

Pure Python. No model, no network, no RAM cost. It does four things:

**1. Removes filler**
Strips `uh`, `um`, `like`, `you know`, `I mean`, `basically`, `actually`, `sort of`,
`kind of` — but only when they're standing alone as filler, never when they carry
meaning. ("I want it to work **like** the old one" keeps its "like".)

**2. Fixes punctuation and casing**
Speech-to-text output arrives as one long unpunctuated run. This splits it into
sentences using pause markers and discourse words (`so`, `and then`, `but`,
`because`), and capitalises properly.

**3. Sorts sentences into the five slots**
Using keyword cues:

| Slot | Triggered by phrases like |
|---|---|
| Goal | "I want", "I need", "build me", "make a", "can you" |
| Context | "right now", "currently", "the problem is", "because" |
| Requirements | "it should", "it must", "make sure", "don't", "has to" |
| Output | "give me", "return", "in the form of", "as a file" |
| Open questions | "maybe", "not sure", "I think", "or something", "either" |

**4. Applies the target template**
Slots the sorted content into the Claude Code / ChatGPT / Gemini layout.

**Honest limitation:** Tier 3 reorganises *your words*. It cannot rephrase a
confused sentence into a clear one, and it cannot infer a requirement you only
implied. It is a genuine safety net, not a replacement for Tiers 1 and 2.

---

## The rules the rewriter must follow

These go into the instruction template for Tiers 1 and 2, and are enforced
structurally in Tier 3. They exist to satisfy R15.

1. **Never invent a requirement.** If you didn't say it, it doesn't appear.
2. **Never drop a requirement.** Every concrete thing you asked for survives.
3. **Never guess at ambiguity.** Anything genuinely unclear goes under
   "Open questions" — visibly, so you can decide.
4. **Keep specifics verbatim.** File paths, numbers, library names, error messages,
   and technical terms are copied exactly, never paraphrased.
5. **Add nothing of your own.** Structure and ordering may improve; substance may
   not. *Revised: this originally read "be shorter than the input". That was the
   wrong test — a well-structured prompt is often legitimately longer than the
   ramble it came from, and the rule pushed the model to cut real content. What
   actually matters is invention, not length.*
6. **Output the prompt and nothing else.** No "Here's your improved prompt:"
   preamble. The result should be directly pasteable.
7. **Preserve the register.** A creative brief must not come back sounding like a
   technical specification. See D17 — nothing here assumes the request is about
   code.

---

## The three target templates

### Claude Code

```
Goal
<one sentence>

Context
<the situation; files and paths involved>

Requirements
- <constraint>
- <constraint>

Output
<what should come back>

Open questions
- <anything ambiguous>
```

Claude Code works on real files, so paths and a concrete definition of "done"
matter more here than anywhere else.

### ChatGPT

```
You are <role>.

Task: <one sentence>

Context:
<background>

Constraints:
- <constraint>

Format your answer as: <format>
```

ChatGPT leans on a stated role and an explicit output format.

### Gemini

```
## Objective
<one sentence>

## Background
<context>

## Requirements
1. <requirement>
2. <requirement>

## Expected output
<format and length>
```

Gemini does well with clear markdown headings and numbered requirements.

---

## Choosing a target

A three-way toggle at the top of the panel. It remembers your last choice, since
you'll usually be working in one tool for a stretch.

There is also an **Auto** option: it scans your words for cues (mentions of files,
repositories, or terminals suggest Claude Code) and picks for you. Off by default —
predictability is worth more than cleverness here.

---

## How we'll know it works

A small test file of real examples — raw ramble on one side, the prompt we want on
the other. Every change to the engine gets checked against it, so improving one
case doesn't quietly break another.

The first entries will be your own actual dictations, collected during the first
week of use. Real input beats invented test cases every time.
