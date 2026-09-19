"""The About box: version, what it does, and who funds it.

The supporter line is read from SUPPORTERS.md **on disk**. Deliberately not
fetched from anywhere:

  - A network call the user did not ask for is a network call they did not ask
    for, however small. This tool's whole claim is that nothing leaves the
    machine except the text you dictate, to the provider you chose.
  - A fetch would reveal who is running the tool, and how often. That is
    exactly the tracking an ad network would have done, arriving by a side door.
  - It would fail offline, or hang on a slow connection, for a cosmetic line.

So supporters are baked in at release time. Adding one means editing a file and
cutting a release, which is a fair price for not surveilling anybody.
"""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import theme

VERSION = "0.1.0"
REPO_URL = "https://github.com/udit2k7/proeng"
SPONSOR_URL = "https://github.com/sponsors/udit2k7"

ROOT = Path(__file__).resolve().parent.parent.parent
SUPPORTERS_FILE = ROOT / "SUPPORTERS.md"


def read_supporters() -> str:
    """The text between the SUPPORTERS markers, as a single plain line."""
    try:
        text = SUPPORTERS_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""

    match = re.search(
        r"<!--\s*SUPPORTERS:START\s*-->(.*?)<!--\s*SUPPORTERS:END\s*-->",
        text,
        re.DOTALL,
    )
    if not match:
        return ""

    body = match.group(1).strip()
    if not body or body.startswith("_No sponsors yet"):
        return ""

    # Flatten markdown to something a QLabel can show without fuss.
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)   # links -> text
    body = re.sub(r"[*_`#>-]", "", body)
    return " ".join(body.split())


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ProEng")
        self.setMinimumWidth(420)
        self.setStyleSheet(_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel("ProEng")
        title.setObjectName("title")
        layout.addWidget(title)

        layout.addWidget(self._muted(f"Version {VERSION}  ·  MIT licence"))
        layout.addWidget(self._body(
            "Turns rambling speech into clear, structured prompts, using free "
            "APIs so your Claude and ChatGPT tokens are never spent on the "
            "messy version."
        ))

        layout.addSpacing(6)
        layout.addWidget(self._muted("PRIVACY"))
        layout.addWidget(self._body(
            "No telemetry, no analytics, no accounts, no ads. Your speech is "
            "transcribed on this machine and never uploaded. Your text goes "
            "only to the API provider whose key you configured."
        ))

        supporters = read_supporters()
        if supporters:
            layout.addSpacing(6)
            layout.addWidget(self._muted("SUPPORTED BY"))
            names = QLabel(supporters)
            names.setWordWrap(True)
            names.setObjectName("supporters")
            layout.addWidget(names)

        layout.addSpacing(8)
        row = QHBoxLayout()
        sponsor = QPushButton("Sponsor")
        sponsor.setObjectName("primary")
        sponsor.setCursor(Qt.CursorShape.PointingHandCursor)
        sponsor.setToolTip(SPONSOR_URL)
        sponsor.clicked.connect(lambda: webbrowser.open(SPONSOR_URL))
        row.addWidget(sponsor)

        source = QPushButton("Source code")
        source.setCursor(Qt.CursorShape.PointingHandCursor)
        source.setToolTip(REPO_URL)
        source.clicked.connect(lambda: webbrowser.open(REPO_URL))
        row.addWidget(source)

        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _body(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        return label


def _stylesheet() -> str:
    surface = "#1B1E24" if theme.SCHEME_NAME == "dark" else "#FFFFFF"
    field = "#24282F" if theme.SCHEME_NAME == "dark" else "#EFEFEC"
    tint = "255, 255, 255" if theme.SCHEME_NAME == "dark" else "0, 0, 0"
    return f"""
    QDialog {{ background: {surface}; }}
    QLabel {{
        color: {theme.TEXT};
        font-family: {theme.FONT_FAMILY};
        font-size: {theme.FONT_SIZE}px;
    }}
    QLabel#title {{
        font-size: 20px;
        font-weight: 600;
        color: {theme.ACCENT};
    }}
    QLabel#muted {{
        color: {theme.TEXT_MUTED};
        font-size: {theme.FONT_SIZE_SMALL}px;
        letter-spacing: 0.5px;
    }}
    QLabel#supporters {{
        color: {theme.TEXT};
        background: {field};
        border-radius: 6px;
        padding: 8px 10px;
    }}
    QPushButton {{
        color: {theme.TEXT};
        background: rgba({tint}, 0.07);
        border: none;
        border-radius: 6px;
        padding: 7px 16px;
        font-family: {theme.FONT_FAMILY};
        font-size: {theme.FONT_SIZE}px;
    }}
    QPushButton:hover {{ background: rgba({tint}, 0.13); }}
    QPushButton#primary {{
        color: #16181D;
        background: {theme.ACCENT};
        font-weight: 600;
    }}
    """
