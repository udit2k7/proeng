"""The translucent side panel: live text, the rewrite, and click-to-copy.

See-through enough to read what is behind it (R11), because you are usually
looking at code while you dictate. Text itself stays fully opaque - translucent
text over a busy desktop is unreadable.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..rewrite.base import Target
from . import theme


class Panel(QWidget):
    """The box that slides out from the character."""

    submit = Signal(str)          # user pressed Enter with this text
    stop_recording = Signal()
    target_changed = Signal(object)
    copy_requested = Signal()
    settings_requested = Signal()
    closed = Signal()

    def __init__(self, opacity: float = 0.75) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(theme.panel_stylesheet(opacity))

        self._recording = False
        self._build()

        self._slide = QPropertyAnimation(self, b"geometry", self)
        self._slide.setDuration(theme.SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- construction ---------------------------------------------------

    def _build(self) -> None:
        root = QFrame(self)
        root.setObjectName("panelRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header())

        self.input = QTextEdit()
        self.input.setPlaceholderText("Speak, or type here...")
        self.input.setMinimumHeight(64)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        status_row.addWidget(self.status, 1)

        # A visible stop, because Enter only works when this panel has keyboard
        # focus - click anywhere else while dictating and the key goes nowhere.
        # It is also the escape hatch when someone talking nearby keeps the
        # voice detector convinced you are still speaking, so the silence timer
        # never fires.
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop")
        self.stop_button.setVisible(False)
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setToolTip("Finish dictating (or press Enter)")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        status_row.addWidget(self.stop_button)

        layout.addLayout(status_row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setVisible(False)
        self.output.setCursor(Qt.CursorShape.PointingHandCursor)
        self.output.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.output.mousePressEvent = self._output_clicked  # type: ignore[method-assign]
        layout.addWidget(self.output, 1)

        layout.addLayout(self._build_footer())

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(2)

        self._targets = QButtonGroup(self)
        self._targets.setExclusive(True)
        for target in (Target.CLAUDE, Target.CHATGPT, Target.GEMINI):
            btn = QPushButton(target.label)
            btn.setObjectName("target")
            btn.setCheckable(True)
            btn.setProperty("target", target)
            btn.clicked.connect(
                lambda _checked, t=target: self.target_changed.emit(t)
            )
            self._targets.addButton(btn)
            row.addWidget(btn)

        row.addStretch(1)

        settings = QPushButton("⚙")  # gear
        settings.setFixedWidth(26)
        settings.setToolTip("Settings - API keys, language, microphone")
        settings.setCursor(Qt.CursorShape.PointingHandCursor)
        settings.clicked.connect(self.settings_requested.emit)
        row.addWidget(settings)

        close = QPushButton("×")  # multiplication sign: a rounder x
        close.setFixedWidth(24)
        close.setToolTip("Close (Esc)")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.closed.emit)
        row.addWidget(close)
        return row

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.tier_label = QLabel("")
        self.tier_label.setObjectName("muted")
        row.addWidget(self.tier_label)
        row.addStretch(1)

        self.copy_button = QPushButton("Click to copy")
        self.copy_button.setObjectName("copy")
        self.copy_button.setVisible(False)
        self.copy_button.clicked.connect(self.copy_requested.emit)
        row.addWidget(self.copy_button)
        return row

    # -- public API -----------------------------------------------------

    def set_target(self, target: Target) -> None:
        for btn in self._targets.buttons():
            btn.setChecked(btn.property("target") == target)

    def begin_recording(self) -> None:
        self._recording = True
        self.input.clear()
        self.input.setReadOnly(False)
        self.output.setVisible(False)
        self.copy_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.stop_button.setText("Stop")
        self.tier_label.setText("")
        self.status.setText("listening...")
        self.input.setFocus()

    def _on_stop_clicked(self) -> None:
        """Stop dictating and rewrite what was captured.

        Disabled immediately: stopping takes a moment to take effect, and a
        second click in that window would be confusing.
        """
        if not self._recording:
            return
        self.stop_button.setEnabled(False)
        self.stop_button.setText("stopping...")
        self.stop_recording.emit()

    def set_meter(self, level: float, countdown: float, timeout: float) -> None:
        if not self._recording:
            return
        filled = int(max(0.0, min(1.0, level)) * 14)
        bar = "|" * filled + "." * (14 - filled)
        if countdown >= timeout - 0.05:
            self.status.setText(f"[{bar}]  listening")
        else:
            self.status.setText(f"[{bar}]  silence {countdown:.0f}s")

    def end_recording(self, reason: str) -> None:
        self._recording = False
        self.stop_button.setVisible(False)
        self.status.setText(
            "stopped (silence)" if reason == "silence" else "stopped"
        )

    def set_partial(self, text: str) -> None:
        """Live text, while the user is still speaking (R4).

        Only updates while recording: once dictation has stopped, a late
        partial arriving would overwrite the final transcript with a
        worse, earlier version.
        """
        if not self._recording:
            return
        self.input.setPlainText(text)
        # Keep the newest words in view rather than making the user scroll.
        cursor = self.input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input.setTextCursor(cursor)

    def set_transcript(self, text: str) -> None:
        self.input.setPlainText(text)

    def set_status(self, message: str) -> None:
        self.status.setText(message)

    def show_result(self, text: str, tier: str, elapsed: float, alert: str) -> None:
        self._recording = False
        self.output.setPlainText(text)
        self.output.setVisible(True)
        self.copy_button.setVisible(True)
        self.status.setText("")

        mark = {"groq": "*", "gemini": "*", "rules": "-"}.get(tier, "?")
        self.tier_label.setText(f"{mark} {tier} - {elapsed:.1f}s")
        if alert:
            # A rejected key is a security event; it must not be a quiet note.
            self.tier_label.setText(f"! KEY PROBLEM - see terminal")
            self.status.setText(alert[:90])
        self._fit_height()

    def flash_copied(self) -> None:
        self.copy_button.setText("copied")
        self.copy_button.setStyleSheet(f"color: {theme.SUCCESS};")

    def reset_copy_button(self) -> None:
        self.copy_button.setText("Click to copy")
        self.copy_button.setStyleSheet("")

    def current_text(self) -> str:
        return self.input.toPlainText().strip()

    def result_text(self) -> str:
        return self.output.toPlainText().strip()

    # -- geometry -------------------------------------------------------

    def slide_in(self, anchor: QRect, on_right: bool) -> None:
        """Slide out from the character, on whichever side it is parked."""
        screen = self.screen().availableGeometry()
        width = theme.PANEL_WIDTH
        # Never taller than the screen, whatever the previous result left behind.
        height = max(
            theme.PANEL_MIN_HEIGHT,
            min(self.height(), screen.height() - 16),
        )

        if on_right:
            end_x = anchor.left() - width - theme.PANEL_GAP
            start_x = end_x + 40
        else:
            end_x = anchor.right() + theme.PANEL_GAP
            start_x = end_x - 40

        end_x = max(screen.left() + 8,
                    min(end_x, screen.right() - width - 8))
        y = max(screen.top() + 8,
                min(anchor.center().y() - height // 2,
                    screen.bottom() - height - 8))

        self.setGeometry(QRect(start_x, y, width, height))
        self.show()
        self.raise_()
        self._slide.stop()
        self._slide.setStartValue(QRect(start_x, y, width, height))
        self._slide.setEndValue(QRect(end_x, y, width, height))
        self._slide.start()

    def _fit_height(self) -> None:
        """Grow to fit the result - without falling off the bottom of the screen.

        The original version grew downward from a Y chosen for the old, shorter
        height, which pushed the copy button off-screen entirely. Growing has to
        re-clamp both the height and the position.
        """
        screen = self.screen().availableGeometry()
        margin = 8
        usable = screen.height() - margin * 2

        doc = self.output.document().size().height()
        wanted = int(min(theme.PANEL_MAX_HEIGHT, usable, 200 + doc))

        geo = self.geometry()
        y = geo.y()
        # Pull it back up if the new height would overflow the bottom, then
        # make sure that has not pushed it off the top.
        if y + wanted > screen.bottom() - margin:
            y = screen.bottom() - margin - wanted
        y = max(screen.top() + margin, y)

        if abs(wanted - geo.height()) < 12 and y == geo.y():
            return

        self._slide.stop()
        self._slide.setStartValue(geo)
        self._slide.setEndValue(QRect(geo.x(), y, geo.width(), wanted))
        self._slide.start()

    def follow(self, anchor: QRect, on_right: bool) -> None:
        """Move with the character, without re-animating a slide.

        Called while the character is being dragged, so it must be immediate -
        an animation here would lag behind the mouse.
        """
        if not self.isVisible():
            return
        screen = self.screen().availableGeometry()
        margin = 8
        width, height = self.width(), self.height()

        x = (anchor.left() - width - theme.PANEL_GAP) if on_right \
            else (anchor.right() + theme.PANEL_GAP)
        x = max(screen.left() + margin, min(x, screen.right() - width - margin))

        y = anchor.center().y() - height // 2
        y = max(screen.top() + margin,
                min(y, screen.bottom() - height - margin))

        self._slide.stop()  # a running slide would fight the drag
        self.move(x, y)

    # -- keyboard -------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.input and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & Qt.KeyboardModifier.ShiftModifier:
                    return False  # Shift+Enter: newline, as expected
                if self._recording:
                    self.stop_recording.emit()
                else:
                    self.submit.emit(self.current_text())
                return True

            if key == Qt.Key.Key_Escape:
                self.closed.emit()
                return True

            # Ctrl+Shift+C copies the result from anywhere in the panel.
            # The button can end up scrolled out of reach on a long result;
            # a keystroke never can.
            if (
                key == Qt.Key.Key_C
                and mods & Qt.KeyboardModifier.ControlModifier
                and mods & Qt.KeyboardModifier.ShiftModifier
            ):
                self.copy_requested.emit()
                return True

            # Typing cancels dictation - you changed your mind, that is fine.
            if self._recording and event.text().isprintable() and event.text():
                self.stop_recording.emit()

        return super().eventFilter(obj, event)

    def _output_clicked(self, event) -> None:
        self.copy_requested.emit()
