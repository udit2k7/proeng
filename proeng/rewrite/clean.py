"""Normalise model output into characters that survive a Windows terminal.

Models like to emit typographic punctuation: curly quotes, en dashes,
non-breaking hyphens, ellipsis characters. Three problems with that here:

1. Windows consoles default to cp1252, which cannot encode many of them. The
   result is a crash - 'charmap' codec can't encode character '\\u2011'.
2. The output gets pasted into terminals, YAML, JSON and code, where a curly
   quote is at best noise and at worst a syntax error.
3. A non-breaking hyphen looks identical to a hyphen but is not one, so
   searching for a flag like --verbose silently fails.

So we fold them all back to plain ASCII equivalents.
"""

from __future__ import annotations

# Deliberately explicit rather than clever: each mapping is a decision.
_REPLACEMENTS = {
    "‘": "'",   # left single quote
    "’": "'",   # right single quote / apostrophe
    "‚": "'",
    "‛": "'",
    "“": '"',   # left double quote
    "”": '"',   # right double quote
    "„": '"',
    "–": "-",   # en dash
    "—": "-",   # em dash
    "‑": "-",   # non-breaking hyphen - the one that crashed
    "‒": "-",   # figure dash
    "−": "-",   # minus sign
    "…": "...",  # ellipsis
    " ": " ",   # non-breaking space
    " ": " ",   # narrow no-break space
    " ": " ",   # thin space
    "​": "",    # zero-width space
    "﻿": "",    # byte order mark
    "•": "-",   # bullet
    "·": "-",   # middle dot
    "→": "->",  # right arrow
    "≤": "<=",
    "≥": ">=",
    "×": "x",   # multiplication sign
}

_TABLE = str.maketrans(_REPLACEMENTS)


def to_ascii_safe(text: str) -> str:
    """Fold typographic characters to ASCII; drop anything still unencodable."""
    out = text.translate(_TABLE)
    # Anything exotic left over (emoji, unusual scripts) would still break a
    # cp1252 console, so drop it rather than crash. Rare in practice.
    try:
        out.encode("cp1252")
    except UnicodeEncodeError:
        out = out.encode("ascii", "ignore").decode("ascii")
    return tidy_whitespace(out)


def tidy_whitespace(text: str) -> str:
    """Strip trailing spaces and collapse runs of blank lines.

    Models often end list items with two spaces - Markdown's line-break syntax -
    which is invisible clutter once the text is pasted into a terminal.
    """
    lines = [line.rstrip() for line in text.splitlines()]

    out: list[str] = []
    blank = 0
    for line in lines:
        if line:
            blank = 0
            out.append(line)
        else:
            blank += 1
            if blank <= 1:  # at most one blank line in a row
                out.append(line)
    return "\n".join(out).strip()
