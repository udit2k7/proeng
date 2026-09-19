"""Every colour, size and duration in one place.

Deliberately quiet. This widget sits on top of the user's work all day; anything
attention-grabbing becomes irritating within a day. See docs/05-ui-spec.md.
"""

from __future__ import annotations

# --- colours ---------------------------------------------------------------

BG = "#16181D"          # panel background (alpha applied separately)
TEXT = "#E8EAED"        # off-white, softer on the eyes than pure white
TEXT_MUTED = "#8B919B"  # timestamps, the tier line
ACCENT = "#E0A458"      # warm amber: recording ring, buttons
SUCCESS = "#6FAF7F"
ERROR = "#C97A7A"
BORDER = "#FFFFFF"      # at 8% opacity - just enough edge definition

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

    Called once at startup, before any widget is built. Module-level constants
    rather than passing a theme object around: there is exactly one theme, and
    threading it through every constructor would be ceremony for nothing.
    """
    global CHARACTER_SIZE, PANEL_WIDTH, IDLE_FADE_MS

    CHARACTER_SIZE = max(32, min(128, int(cfg.character_size)))
    PANEL_WIDTH = max(260, min(720, int(cfg.panel_width)))
    IDLE_FADE_MS = max(0, int(cfg.idle_fade_seconds) * 1000)

# --- stylesheet ------------------------------------------------------------

def panel_stylesheet(opacity: float) -> str:
    """Qt stylesheet for the panel.

    Background carries the opacity; text stays fully opaque. Translucent text
    over a busy desktop is unreadable, which would defeat the point of R11.
    """
    alpha = max(0.0, min(1.0, opacity))
    r, g, b = int(BG[1:3], 16), int(BG[3:5], 16), int(BG[5:7], 16)
    return f"""
    #panelRoot {{
        background-color: rgba({r}, {g}, {b}, {alpha});
        border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.08);
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
        selection-color: #16181D;
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
        background: rgba(255, 255, 255, 0.06);
    }}
    QPushButton#target:checked {{
        color: {ACCENT};
        background: rgba(224, 164, 88, 0.12);
    }}
    QPushButton#copy {{
        color: {ACCENT};
        border: 1px solid rgba(224, 164, 88, 0.35);
        padding: 6px 14px;
    }}
    QPushButton#copy:hover {{
        background: rgba(224, 164, 88, 0.12);
    }}
    /* While recording this is the only action that matters, so it is the one
       solid button in the panel - findable without reading anything. */
    QPushButton#stop {{
        color: #16181D;
        background: {ACCENT};
        font-size: {FONT_SIZE}px;
        font-weight: 600;
        padding: 5px 18px;
        border-radius: 6px;
    }}
    QPushButton#stop:hover {{
        background: #EDB268;
    }}
    QPushButton#stop:disabled {{
        color: {TEXT_MUTED};
        background: rgba(255, 255, 255, 0.08);
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
