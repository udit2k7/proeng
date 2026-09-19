"""Settings dialog: API keys and the handful of things worth changing often.

D6 chose a plain TOML file over a settings screen, on the grounds that it would
be opened twice a year. That reasoning held for sizes and timeouts. It did not
hold for API keys: keys get rotated, revoked and replaced, and telling someone
to run a CLI script for that is a poor answer when the tool is already on screen.

So: keys and the two settings that actually need tuning by feel (microphone
sensitivity and dictation language) live here. Everything else stays in the file.

Writing back preserves the file's comments - it edits the lines in place rather
than re-serialising, because the comments are most of what makes config.toml
readable.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..security import redact
from . import palettes, theme

SCHEMES = [
    ("Follow Windows", "system"),
    ("Dark", "dark"),
    ("Light", "light"),
]

LANGUAGES = [
    ("Auto-detect (Hindi + English)", "auto"),
    ("English", "en"),
    ("Hindi", "hi"),
]


class SettingsDialog(QDialog):
    """Edits config.toml in place, preserving its comments."""

    saved = Signal()

    def __init__(self, config_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.path = config_path
        self.setWindowTitle("ProEng settings")
        self.setMinimumWidth(460)
        self.setStyleSheet(_stylesheet())

        self._existing = self._read()
        self._build()

    # -- reading --------------------------------------------------------

    def _read(self) -> dict[str, str]:
        """Pull the values we edit out of the file, section-aware."""
        out = {
            "groq_api_key": "",
            "gemini_api_key": "",
            "language": "auto",
            "speech_level_threshold": "300",
            "scheme": "dark",
            "accent": "amber",
        }
        if not self.path.exists():
            return out

        text = self.path.read_text(encoding="utf-8")
        section = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                section = stripped.strip("[]")
                continue
            m = re.match(r'^\s*(\w+)\s*=\s*"?([^"#]*)"?', line)
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip()
            if section == "groq" and key == "api_key":
                out["groq_api_key"] = value
            elif section == "gemini" and key == "api_key":
                out["gemini_api_key"] = value
            elif section == "speech" and key in (
                "language", "speech_level_threshold"
            ):
                out[key] = value
            elif section == "ui" and key in ("scheme", "accent"):
                out[key] = value
        return out

    # -- building -------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.groq = self._key_field(
            self._existing["groq_api_key"], "gsk_..."
        )
        form.addRow("Groq API key", self.groq)
        form.addRow("", self._hint(
            "Free at console.groq.com - the fast one, used first."
        ))

        self.gemini = self._key_field(
            self._existing["gemini_api_key"], "AIza... or AQ..."
        )
        form.addRow("Gemini API key", self.gemini)
        form.addRow("", self._hint(
            "Free at aistudio.google.com/apikey - the backup."
        ))

        self.language = QComboBox()
        for label, value in LANGUAGES:
            self.language.addItem(label, value)
        current = self._existing["language"]
        index = self.language.findData(current)
        self.language.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Dictation language", self.language)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(50, 3000)
        self.threshold.setSingleStep(50)
        self.threshold.setDecimals(0)
        try:
            self.threshold.setValue(float(self._existing["speech_level_threshold"]))
        except ValueError:
            self.threshold.setValue(300)
        form.addRow("Microphone sensitivity", self.threshold)
        form.addRow("", self._hint(
            "Higher ignores people talking near you. Lower if it cuts you off."
        ))

        # --- appearance -------------------------------------------------
        form.addRow("", self._hint(""))  # a little breathing room

        self.scheme = QComboBox()
        for label, value in SCHEMES:
            self.scheme.addItem(label, value)
        index = self.scheme.findData(self._existing["scheme"])
        self.scheme.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Theme", self.scheme)

        self.accent = QComboBox()
        for name, hexcode in palettes.ACCENTS.items():
            # A swatch beside each name, so the choice is visible rather than
            # a word you have to imagine.
            self.accent.addItem(_swatch(hexcode), name.capitalize(), name)
        index = self.accent.findData(self._existing["accent"])
        if index < 0 and self._existing["accent"].startswith("#"):
            # A custom hex the user typed into config.toml by hand - keep it
            # rather than silently resetting them to amber.
            self.accent.addItem(
                _swatch(self._existing["accent"]),
                self._existing["accent"],
                self._existing["accent"],
            )
            index = self.accent.count() - 1
        self.accent.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Accent colour", self.accent)
        form.addRow("", self._hint(
            "Theme and colour apply when you reopen the panel. A light theme "
            "is made less see-through automatically - pale text over a pale "
            "desktop is unreadable."
        ))

        layout.addLayout(form)

        self.message = QLabel("")
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        note = self._hint(
            "Saved to config.toml, which is gitignored. Changes to language "
            "take effect on the next dictation."
        )
        layout.addWidget(note)

    def _key_field(self, value: str, placeholder: str) -> QLineEdit:
        field = QLineEdit(value)
        field.setPlaceholderText(placeholder)
        # Masked by default so a key is not left readable on a shared screen,
        # with a reveal for when you need to check what you pasted.
        field.setEchoMode(QLineEdit.EchoMode.Password)
        action = field.addAction(
            _eye_icon(), QLineEdit.ActionPosition.TrailingPosition
        )
        action.setToolTip("Show / hide")
        action.triggered.connect(
            lambda: field.setEchoMode(
                QLineEdit.EchoMode.Normal
                if field.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password
            )
        )
        return field

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    # -- saving ---------------------------------------------------------

    def _save(self) -> None:
        updates = {
            ("groq", "api_key"): self.groq.text().strip(),
            ("gemini", "api_key"): self.gemini.text().strip(),
            ("speech", "language"): self.language.currentData(),
            ("speech", "speech_level_threshold"): str(int(self.threshold.value())),
            ("ui", "scheme"): self.scheme.currentData(),
            ("ui", "accent"): self.accent.currentData(),
        }
        try:
            self._write(updates)
        except Exception as exc:  # noqa: BLE001
            self.message.setText(f"Could not save: {exc}")
            return

        self.saved.emit()
        self.accept()

    def _write(self, updates: dict[tuple[str, str], str]) -> None:
        """Rewrite values in place, leaving every comment untouched."""
        if not self.path.exists():
            example = self.path.parent / "config.example.toml"
            if not example.exists():
                raise FileNotFoundError("config.example.toml is missing")
            self.path.write_text(
                example.read_text(encoding="utf-8"), encoding="utf-8"
            )

        lines = self.path.read_text(encoding="utf-8").splitlines()
        section = ""
        seen: set[tuple[str, str]] = set()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("["):
                section = stripped.strip("[]")
                continue
            m = re.match(r'^(\s*)(\w+)(\s*=\s*)', line)
            if not m:
                continue
            key = m.group(2)
            if (section, key) not in updates:
                continue

            value = updates[(section, key)]
            quoted = not value.replace(".", "").isdigit()
            rendered = f'"{value}"' if quoted else value
            # Keep any trailing comment on the line.
            comment = ""
            if "#" in line:
                after = line.split("=", 1)[1]
                if "#" in after:
                    comment = "  " + after[after.index("#"):].strip()
            lines[i] = f"{m.group(1)}{key}{m.group(3)}{rendered}{comment}"
            seen.add((section, key))

        missing = set(updates) - seen
        if missing:
            names = ", ".join(f"[{s}].{k}" for s, k in sorted(missing))
            raise ValueError(f"could not find {names} in config.toml")

        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- status ---------------------------------------------------------

    def summary(self) -> str:
        parts = []
        for name, value in (
            ("Groq", self._existing["groq_api_key"]),
            ("Gemini", self._existing["gemini_api_key"]),
        ):
            parts.append(f"{name}: {redact(value) if value else 'not set'}")
        return "   ".join(parts)


def _swatch(hexcode: str):
    """A small filled circle, so a colour choice can be seen not guessed."""
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pix = QPixmap(16, 16)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(0, 0, 0, 60))
    p.setBrush(QColor(hexcode))
    p.drawEllipse(2, 2, 12, 12)
    p.end()
    return QIcon(pix)


def _eye_icon():
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pix = QPixmap(16, 16)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(theme.TEXT_MUTED))
    p.drawEllipse(3, 5, 10, 6)
    p.setBrush(QColor(theme.TEXT_MUTED))
    p.drawEllipse(6, 6, 4, 4)
    p.end()
    return QIcon(pix)


def _stylesheet() -> str:
    return f"""
    QDialog {{
        background: #1B1E24;
    }}
    QLabel {{
        color: {theme.TEXT};
        font-family: {theme.FONT_FAMILY};
        font-size: {theme.FONT_SIZE}px;
    }}
    QLabel#hint {{
        color: {theme.TEXT_MUTED};
        font-size: {theme.FONT_SIZE_SMALL}px;
    }}
    QLabel#message {{
        color: {theme.ERROR};
        font-size: {theme.FONT_SIZE_SMALL}px;
    }}
    QLineEdit, QComboBox, QDoubleSpinBox {{
        color: {theme.TEXT};
        background: #24282F;
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 6px;
        padding: 6px 8px;
        font-family: {theme.FONT_FAMILY};
        font-size: {theme.FONT_SIZE}px;
    }}
    QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {theme.ACCENT};
    }}
    QComboBox QAbstractItemView {{
        background: #24282F;
        color: {theme.TEXT};
        selection-background-color: {theme.ACCENT};
        selection-color: #16181D;
    }}
    QPushButton {{
        color: {theme.TEXT};
        background: rgba(255, 255, 255, 0.07);
        border: none;
        border-radius: 6px;
        padding: 7px 18px;
        font-family: {theme.FONT_FAMILY};
        font-size: {theme.FONT_SIZE}px;
    }}
    QPushButton:hover {{
        background: rgba(255, 255, 255, 0.12);
    }}
    QPushButton#primary {{
        color: #16181D;
        background: {theme.ACCENT};
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background: #EDB268;
    }}
    """
