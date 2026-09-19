"""Colour schemes: light, dark, and a choice of accents.

Kept apart from theme.py so that adding a scheme is editing data, not code.

A note on the light scheme. A translucent panel over a light background is a
harder problem than over a dark one: pale text on pale wallpaper disappears.
So the light scheme is deliberately more opaque than the dark one, and its
text is darker than a pure "inverted dark" would give. That is why the two are
not mirror images of each other.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Scheme:
    name: str
    bg: str           # panel background, before opacity
    text: str         # body text - always fully opaque
    text_muted: str   # timestamps, the tier line
    border: str       # panel edge
    border_alpha: float
    success: str
    error: str
    # Light backgrounds need more opacity to stay readable - see the note above.
    opacity_floor: float


DARK = Scheme(
    name="dark",
    bg="#16181D",
    text="#E8EAED",        # off-white; pure white is harsh on a dark panel
    text_muted="#8B919B",
    border="#FFFFFF",
    border_alpha=0.08,
    success="#6FAF7F",
    error="#C97A7A",
    opacity_floor=0.50,
)

LIGHT = Scheme(
    name="light",
    bg="#F7F7F5",
    text="#1F2328",        # near-black, not pure black: less glare
    text_muted="#6A7178",
    border="#000000",
    border_alpha=0.12,
    success="#3F8551",
    error="#B3403F",
    opacity_floor=0.80,    # below this, light-on-light becomes unreadable
)

SCHEMES = {"dark": DARK, "light": LIGHT}


# Accent colours. Used for the recording ring, the Stop button and highlights.
# Each needs to read acceptably on BOTH backgrounds, which rules out anything
# very pale or very dark.
ACCENTS: dict[str, str] = {
    "amber": "#E0A458",     # the original - warm, calm, not alarming
    "blue": "#5B9BD5",
    "teal": "#4FA8A0",
    "green": "#6FAF7F",
    "purple": "#9B7FD4",
    "pink": "#D57FA8",
    "red": "#C9705F",
    "grey": "#8B919B",      # for anyone who wants no colour at all
}

DEFAULT_ACCENT = "amber"


def resolve_scheme(name: str) -> Scheme:
    """Turn a configured name into a scheme, following the OS when asked."""
    name = (name or "dark").lower()
    if name == "system":
        return SCHEMES[detect_system_scheme()]
    return SCHEMES.get(name, DARK)


def detect_system_scheme() -> str:
    """Ask Windows whether apps should be light or dark.

    Falls back to dark, which is both the safer default for a translucent
    overlay and what most developers run.
    """
    if sys.platform != "win32":
        return "dark"
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        # 0 = dark, 1 = light. Note this is AppsUseLightTheme, so the value is
        # inverted relative to what you might expect.
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


def resolve_accent(name: str) -> str:
    """A named accent, or a literal #RRGGBB the user typed themselves."""
    name = (name or DEFAULT_ACCENT).strip()
    if name.startswith("#") and len(name) in (4, 7):
        return name
    return ACCENTS.get(name.lower(), ACCENTS[DEFAULT_ACCENT])
