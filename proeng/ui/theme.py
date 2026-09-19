"""Every colour, size and duration in one place.

Deliberately quiet. This widget sits on top of the user's work all day; anything
attention-grabbing becomes irritating within a day. See docs/05-ui-spec.md.
"""

from __future__ import annotations

from . import palettes

# --- colours ---------------------------------------------------------------
#
# These are module-level and rebound by apply(). There is exactly one theme at
# a time, and threading a theme object through every widget constructor would
# be ceremony for nothing. See apply() below.

BG = palettes.DARK.bg
TEXT = palettes.DARK.text
TEXT_MUTED = palettes.DARK.text_muted
ACCENT = palettes.ACCENTS[palettes.DEFAULT_ACCENT]
SUCCESS = palettes.DARK.success
ERROR = palettes.DARK.error
BORDER = palettes.DARK.border
BORDER_ALPHA = palettes.DARK.border_alpha
OPACITY_FLOOR = palettes.DARK.opacity_floor
SCHEME_NAME = "dark"

# --- sizes -----------------------------------------------------------------

CHARACTER_SIZE = 64
PANEL_WIDTH = 380
PANEL_MIN_HEIGHT = 220
PANEL_MAX_HEIGHT = 600
CORNER_RADIUS = 12
BORDER_WIDTH = 1
PANEL_GAP = 12          # space between character and panel

# --- typography ------------------------------------------------------------

FONT_FAMILY = "Segoe UI Variable, Segoe UI, sans-serif"
FONT_SIZE = 13
FONT_SIZE_SMALL = 11

# --- timing (milliseconds) -------------------------------------------------

SLIDE_MS = 180          # fast enough to feel instant, slow enough to track
FADE_MS = 400
IDLE_FADE_MS = 10_000   # dim the character after this long untouched
BREATH_MS = 3_000       # one full idle breathing cycle
FLASH_MS = 600

IDLE_OPACITY = 0.4


def apply(cfg) -> None:
    """Overlay the user's config onto these defaults.

    Called before any widget is built, and again whenever the theme changes.
    """
    global CHARACTER_SIZE, PANEL_WIDTH, IDLE_FADE_MS
    global BG, TEXT, TEXT_MUTED, ACCENT, SUCCESS, ERROR
    global BORDER, BORDER_ALPHA, OPACITY_FLOOR, SCHEME_NAME

    CHARACTER_SIZE = max(32, min(128, int(cfg.character_size)))
    PANEL_WIDTH = max(260, min(720, int(cfg.panel_width)))
    IDLE_FADE_MS = max(0, int(cfg.idle_fade_seconds) * 1000)

    scheme = palettes.resolve_scheme(getattr(cfg, "scheme", "dark"))
    SCHEME_NAME = scheme.name
    BG = scheme.bg
    TEXT = scheme.text
    TEXT_MUTED = scheme.text_muted
    SUCCESS = scheme.success
    ERROR = scheme.error
    BORDER = scheme.border
    BORDER_ALPHA = scheme.border_alpha
    OPACITY_FLOOR = scheme.opacity_floor
    ACCENT = palettes.resolve_accent(getattr(cfg, "accent", palettes.DEFAULT_ACCENT))


def effective_opacity(requested: float) -> float:
    """Clamp opacity to what the current scheme can stay readable at.

    The light scheme needs more opacity than the dark one: pale text over a
    pale desktop simply disappears. Silently raising the floor is better than
    letting someone configure an unreadable panel and conclude the tool is
    broken.
    """
    return max(OPACITY_FLOOR, min(1.0, requested))

# --- stylesheet ------------------------------------------------------------

def panel_stylesheet(opacity: float) -> str:
    """Qt stylesheet for the panel.

    Background carries the opacity; text stays fully opaque. Translucent text
    over a busy desktop is unreadable, which would defeat the point of R11.
    """
    alpha = effective_opacity(opacity)
    r, g, b = int(BG[1:3], 16), int(BG[3:5], 16), int(BG[5:7], 16)
    br, bg_, bb = int(BORDER[1:3], 16), int(BORDER[3:5], 16), int(BORDER[5:7], 16)
    # Hover and pressed tints have to invert with the scheme: a white overlay
    # is invisible on a light panel.
    tint = "255, 255, 255" if SCHEME_NAME == "dark" else "0, 0, 0"
    on_accent = "#16181D"  # dark text on an accent-filled button, either scheme
    return f"""
    #panelRoot {{
        background-color: rgba({r}, {g}, {b}, {alpha});
        border: {BORDER_WIDTH}px solid rgba({br}, {bg_}, {bb}, {BORDER_ALPHA});
        border-radius: {CORNER_RADIUS}px;
    }}
    QLabel {{
        color: {TEXT};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
        background: transparent;
    }}
    QLabel#muted {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_SMALL}px;
    }}
    QTextEdit {{
        color: {TEXT};
        background: transparent;
        border: none;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
        selection-background-color: {ACCENT};
        selection-color: {on_accent};
    }}
    QPushButton {{
        color: {TEXT_MUTED};
        background: transparent;
        border: none;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SMALL}px;
        padding: 4px 8px;
        border-radius: 6px;
    }}
    QPushButton:hover {{
        color: {TEXT};
        background: rgba({tint}, 0.06);
    }}
    QPushButton#target:checked {{
        color: {ACCENT};
        background: {ACCENT}22;
    }}
    QPushButton#again {{
        color: {TEXT_MUTED};
        border: 1px solid rgba({tint}, 0.12);
        padding: 6px 12px;
        margin-right: 6px;
    }}
    QPushButton#again:hover {{
        color: {TEXT};
        background: rgba({tint}, 0.07);
    }}
    QPushButton#copy {{
        color: {ACCENT};
        border: 1px solid {ACCENT}59;
        padding: 6px 14px;
    }}
    QPushButton#copy:hover {{
        background: {ACCENT}22;
    }}
    /* While recording this is the only action that matters, so it is the one
       solid button in the panel - findable without reading anything. */
    QPushButton#stop {{
        color: {on_accent};
        background: {ACCENT};
        font-size: {FONT_SIZE}px;
        font-weight: 600;
        padding: 5px 18px;
        border-radius: 6px;
    }}
    QPushButton#stop:hover {{
        background: {ACCENT};
    }}
    QPushButton#stop:disabled {{
        color: {TEXT_MUTED};
        background: rgba({tint}, 0.08);
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba({tint}, 0.22);
        border-radius: 3px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
