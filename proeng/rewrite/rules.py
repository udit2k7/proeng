"""Tier 3: rewriting with plain code. No model, no network, no RAM.

This is the safety net. It must never fail and never need anything installed.

Be clear about what it can and cannot do. It REORGANISES your words: strips
filler, repairs punctuation, sorts sentences into slots, applies a template. It
cannot rephrase a confused sentence into a clear one, and it cannot infer a
requirement you only implied. That is Tier 1 and 2's job.

See docs/04-rewrite-engine.md for the design.
"""

from __future__ import annotations

import re

from .base import Target

# --- filler removal --------------------------------------------------------

# Words that are pure filler when standing alone. Order matters: longer phrases
# first, so "you know" is removed before "know" could ever be considered.
_FILLER_PHRASES = [
    "you know what i mean",
    "if you know what i mean",
    "at the end of the day",
    "to be honest",
    "i mean like",
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "or something like that",
    "or something",
    "and all that",
    "and everything",
    "stuff like that",
]

_FILLER_WORDS = [
    "uh", "um", "umm", "uhh", "er", "erm", "ah", "hmm", "mm",
    "basically", "actually", "literally", "honestly", "obviously",
    "essentially", "anyway", "right", "okay", "ok", "so",
]

# "like" and "so" carry real meaning often enough that blanket removal damages
# sentences ("work like the old one", "so that it saves tokens"). Only strip
# them when they open a clause, which is where they are filler.
_LEADING_ONLY = {"so", "like", "right", "okay", "ok", "anyway", "and", "but"}


def strip_filler(text: str) -> str:
    out = text
    for phrase in _FILLER_PHRASES:
        out = re.sub(rf"\b{re.escape(phrase)}\b", " ", out, flags=re.IGNORECASE)
    for word in _FILLER_WORDS:
        if word in _LEADING_ONLY:
            continue  # handled per-sentence later
        out = re.sub(rf"\b{re.escape(word)}\b", " ", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return out.strip()


def _strip_leading_filler(sentence: str) -> str:
    """Remove filler that only counts as filler at the start of a clause."""
    s = sentence.strip()
    changed = True
    while changed:
        changed = False
        for word in _LEADING_ONLY:
            m = re.match(rf"^{word}\b[,\s]*", s, flags=re.IGNORECASE)
            if m and len(s) > len(m.group(0)) + 3:
                s = s[m.end():].lstrip()
                changed = True
    return s


# --- sentence splitting ----------------------------------------------------

# Dictation arrives with no punctuation at all: one 100-word run with no full
# stops. Splitting only on punctuation therefore yields a single "sentence",
# and everything downstream then mis-classifies the whole blob. So we split on
# the words people actually start a new thought with when speaking.
#
# Ordered longest-first so "and then" wins over "and".
_CLAUSE_STARTERS = [
    # Only markers that genuinely begin a NEW thought. Subordinating words
    # (which, where, when, that) continue the current one, and splitting on
    # them shreds a single idea into fragments. Bare "and"/"so" do the same.
    "and then", "but then", "after that", "the problem is", "the issue is",
    "i want", "i need", "i would like", "i'd like",
    "i am trying", "i'm trying", "i am building", "i'm building",
    "i think", "i don't know", "i dont know",
    "it should", "it must", "it needs", "it has to",
    "make sure", "give me", "show me", "send me",
    "can you", "could you", "help me",
    "maybe", "not sure", "perhaps",
    "however", "although", "also", "plus",
    "because", "right now", "currently", "at the moment",
    "don't", "do not", "never", "always", "avoid",
]

_MIN_CHUNK_WORDS = 6


def _split_run(run: str) -> list[str]:
    """Break one unpunctuated run into clauses."""
    pattern = "|".join(rf"{re.escape(s)}" for s in _CLAUSE_STARTERS)
    # Split *before* each starter, keeping the starter with what follows.
    pieces = re.split(rf"\s+(?=\b(?:{pattern})\b)", run, flags=re.IGNORECASE)

    merged: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if len(piece.split()) < _MIN_CHUNK_WORDS:
            if merged:
                merged[-1] = f"{merged[-1]} {piece}"
            else:
                # Too short and nothing before it (a leading "so"): hold it
                # and glue it onto the next real chunk instead of dropping it.
                merged.append(piece)
            continue
        if merged and len(merged[-1].split()) < _MIN_CHUNK_WORDS:
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        part = part.strip()
        if not part:
            continue
        # Short, already-punctuated sentences need no further breaking.
        if len(part.split()) <= 12:
            out.append(part)
        else:
            out.extend(_split_run(part))
    return out


def tidy(sentence: str) -> str:
    """Capitalise, fix spacing, ensure terminal punctuation."""
    s = _strip_leading_filler(sentence)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;")
    if not s:
        return ""
    # The split can leave a connector dangling at the end ("... as I talk or").
    s = re.sub(r"\s+(so|and|or|but|because|then|which|that|if|whether|to|of|for|with)\s*$", "", s, flags=re.IGNORECASE)
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    # Keep "I" capitalised; speech-to-text sometimes lowercases it.
    s = re.sub(r"\bi\b", "I", s)
    if s[-1] not in ".!?":
        s += "."
    return s


# --- slot classification ---------------------------------------------------

_CUES: dict[str, list[str]] = {
    # Cues are domain-neutral on purpose. The user dictates software work, but
    # also stories, scripts, research, planning and business writing - so these
    # lists must not assume a technical request. See docs/03-decisions.md D17.
    "goal": [
        "i want", "i need", "i would like", "i'd like", "build me", "make me",
        "make a", "build a", "create a", "can you", "could you", "help me",
        "i am trying to", "i'm trying to", "the idea is", "i am building",
        "i'm building", "we are building", "we're building", "give me a",
        "write me", "write a", "draft a", "draft me", "plan a", "plan me",
        "the story is", "it is about", "it's about", "i am writing",
        "i'm writing", "explain", "summarise", "summarize", "research",
    ],
    "requirements": [
        "it should", "it must", "it needs to", "make sure", "don't", "do not",
        "has to", "have to", "should be", "must be", "required", "avoid",
        "never", "always", "only", "instead of", "rather than", "it has to",
        "the tone should", "make it sound", "keep it", "no more than",
        "at least", "in the style of", "set in", "aimed at", "the audience",
    ],
    "output": [
        "give me", "return", "send me", "in the form of", "as a file",
        "output", "i want back", "show me", "write it", "save it",
        "as a list", "as a table", "in bullet points", "one page",
        "word count", "how many words", "in paragraphs",
    ],
    "questions": [
        "maybe", "not sure", "i think", "or something", "either", "i don't know",
        "i dont know", "perhaps", "possibly", "what do you", "should i",
        "which is better", "suggest", "any idea",
    ],
    "context": [
        "right now", "currently", "the problem is", "at the moment", "because",
        "i am using", "i'm using", "we use", "i use", "the issue is",
        "it keeps", "it is not", "it's not", "already", "it works",
    ],
}

# Checked in this order; first match wins. "questions" is first because
# uncertainty ("maybe we should use X") matters more than the fact that the
# sentence also looks like a requirement - surfacing doubt beats burying it.
_ORDER = ["questions", "output", "requirements", "goal", "context"]


def classify(sentence: str) -> str:
    """Decide which slot a sentence belongs to.

    Cues at the START of a sentence are decisive; the same word buried in the
    middle is usually incidental. Matching anywhere was the original bug: one
    stray "maybe" in a long run sent the entire thing to Open questions.
    """
    low = sentence.lower().lstrip()

    for slot in _ORDER:
        for cue in _CUES[slot]:
            if low.startswith(cue):
                return slot

    # No leading cue. Fall back to counting cues anywhere, and require a
    # clear winner rather than letting a single stray word decide.
    scores = {
        slot: sum(1 for cue in cues if cue in low) for slot, cues in _CUES.items()
    }
    best = max(scores, key=lambda s: scores[s])
    if scores[best] >= 2:
        return best
    if scores[best] == 1 and len(low.split()) <= 15:
        return best
    return "context"  # the safe default: keep it, don't promote it


def _dedupe(items: list[str]) -> list[str]:
    """Drop near-duplicate sentences. Speech repeats the same point a lot."""
    seen: list[str] = []
    out: list[str] = []
    for item in items:
        key = re.sub(r"[^a-z0-9 ]", "", item.lower())
        words = set(key.split())
        if not words:
            continue
        duplicate = False
        for prev in seen:
            prev_words = set(prev.split())
            overlap = len(words & prev_words) / max(1, len(words | prev_words))
            if overlap > 0.7:
                duplicate = True
                break
        if not duplicate:
            seen.append(key)
            out.append(item)
    return out


def sort_into_slots(text: str) -> dict[str, list[str]]:
    slots: dict[str, list[str]] = {
        "goal": [], "context": [], "requirements": [], "output": [], "questions": [],
    }
    for raw_sentence in split_sentences(text):
        s = tidy(raw_sentence)
        if not s or len(s.split()) < 2:
            continue
        slots[classify(s)].append(s)

    for key in slots:
        slots[key] = _dedupe(slots[key])

    # If nothing landed in "goal", promote the first context sentence - every
    # prompt needs a goal, and the opening sentence is nearly always it.
    if not slots["goal"] and slots["context"]:
        slots["goal"].append(slots["context"].pop(0))
    return slots


# --- templates -------------------------------------------------------------

def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{n}. {t}" for n, t in enumerate(items, 1))


def _render_claude(s: dict[str, list[str]]) -> str:
    out = []
    if s["goal"]:
        out.append("Goal\n" + " ".join(s["goal"]))
    if s["context"]:
        out.append("Context\n" + " ".join(s["context"]))
    if s["requirements"]:
        out.append("Requirements\n" + _bullets(s["requirements"]))
    if s["output"]:
        out.append("Output\n" + " ".join(s["output"]))
    if s["questions"]:
        out.append("Open questions\n" + _bullets(s["questions"]))
    return "\n\n".join(out)


def _render_chatgpt(s: dict[str, list[str]]) -> str:
    out = []
    if s["goal"]:
        out.append("Task: " + " ".join(s["goal"]))
    if s["context"]:
        out.append("Context:\n" + " ".join(s["context"]))
    if s["requirements"]:
        out.append("Constraints:\n" + _bullets(s["requirements"]))
    if s["output"]:
        out.append("Format your answer as: " + " ".join(s["output"]))
    if s["questions"]:
        out.append("Open questions:\n" + _bullets(s["questions"]))
    return "\n\n".join(out)


def _render_gemini(s: dict[str, list[str]]) -> str:
    out = []
    if s["goal"]:
        out.append("## Objective\n" + " ".join(s["goal"]))
    if s["context"]:
        out.append("## Background\n" + " ".join(s["context"]))
    if s["requirements"]:
        out.append("## Requirements\n" + _numbered(s["requirements"]))
    if s["output"]:
        out.append("## Expected output\n" + " ".join(s["output"]))
    if s["questions"]:
        out.append("## Open questions\n" + _bullets(s["questions"]))
    return "\n\n".join(out)


_RENDERERS = {
    Target.CLAUDE: _render_claude,
    Target.CHATGPT: _render_chatgpt,
    Target.GEMINI: _render_gemini,
}


class RulesTier:
    """Tier 3. Always available, by definition."""

    name = "rules"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def rewrite(self, raw: str, target: Target) -> str:
        cleaned = strip_filler(raw)
        if not cleaned.strip():
            return ""
        slots = sort_into_slots(cleaned)
        return _RENDERERS[target](slots).strip()
