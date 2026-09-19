"""The small floating character. Click it to start dictating.

Frameless, translucent, always on top, draggable, and it snaps to whichever
screen edge it is released nearest. See docs/05-ui-spec.md R9-R12.
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme

IDLE = "idle"
LISTENING = "listening"
THINKING = "thinking"
DONE = "done"
ERROR = "error"


class Character(QWidget):
    """A 64x64 always-on-top blob that reacts to what the tool is doing."""

    clicked = Signal()
    right_clicked = Signal(QPoint)
    moved = Signal()          # emitted while dragging, so the panel can follow

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keeps it out of the taskbar and alt-tab
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(theme.CHARACTER_SIZE, theme.CHARACTER_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._state = IDLE
        self._phase = 0.0       # drives the idle breathing and thinking spin
        self._level = 0.0       # microphone loudness, 0-1
        self._drag_from: QPoint | None = None
        self._moved = False

        # ~30 fps: smooth enough for a gentle pulse, cheap enough to ignore.
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start(33)

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._fade_out)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(theme.FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self.set_state(IDLE))

    # -- state ----------------------------------------------------------

    def set_state(self, state: str) -> None:
        self._state = state
        if state in (DONE, ERROR):
            self._flash_timer.start(theme.FLASH_MS)
        if state == IDLE:
            self._level = 0.0
            self._restart_idle_fade()
        else:
            self._wake()
        self.update()

    def set_level(self, level: float) -> None:
        """Microphone loudness, so the ring pulses with the user's voice.

        This matters more than it looks: it is how you know the mic is actually
        picking you up, without reading anything.
        """
        self._level = max(0.0, min(1.0, level))

    # -- painting -------------------------------------------------------

    def _tick(self) -> None:
        self._phase += 0.033
        if self._state != IDLE or self._level > 0:
            self.update()
        elif int(self._phase * 30) % 2 == 0:
            self.update()  # idle: repaint at half rate, it is only breathing

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        centre = self.rect().center()
        base = theme.CHARACTER_SIZE * 0.30

        colour = {
            IDLE: QColor(theme.TEXT_MUTED),
            LISTENING: QColor(theme.ACCENT),
            THINKING: QColor(theme.ACCENT),
            DONE: QColor(theme.SUCCESS),
            ERROR: QColor(theme.ERROR),
        }[self._state]

        if self._state == LISTENING:
            self._draw_voice_ring(painter, centre, base, colour)
        elif self._state == THINKING:
            self._draw_spinner(painter, centre, base, colour)

        # The body: a slow breath when idle, steady otherwise.
        if self._state == IDLE:
            breath = 1.0 + 0.06 * math.sin(self._phase * 2 * math.pi / 3.0)
        else:
            breath = 1.0
        radius = base * breath

        painter.setPen(Qt.PenStyle.NoPen)
        body = QColor(colour)
        body.setAlphaF(0.9 if self._state != IDLE else 0.65)
        painter.setBrush(body)
        painter.drawEllipse(centre, radius, radius)

        # A small highlight, so it reads as an object rather than a dot.
        gloss = QColor(255, 255, 255, 40)
        painter.setBrush(gloss)
        painter.drawEllipse(
            centre + QPoint(int(-radius * 0.25), int(-radius * 0.3)),
            radius * 0.3,
            radius * 0.22,
        )

    def _draw_voice_ring(self, painter, centre, base, colour) -> None:
        # Two rings: a steady one for "armed", a reactive one for your voice.
        pen = QPen(QColor(colour.red(), colour.green(), colour.blue(), 60))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(centre, base * 1.4, base * 1.4)

        reach = base * (1.4 + self._level * 0.6)
        pen = QPen(QColor(colour.red(), colour.green(), colour.blue(), 190))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(centre, reach, reach)

    def _draw_spinner(self, painter, centre, base, colour) -> None:
        pen = QPen(QColor(colour.red(), colour.green(), colour.blue(), 200))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        radius = base * 1.45
        path = QPainterPath()
        rect = self.rect().adjusted(
            int(centre.x() - radius - self.rect().left()),
            int(centre.y() - radius - self.rect().top()),
            int(-(self.rect().right() - centre.x() - radius)),
            int(-(self.rect().bottom() - centre.y() - radius)),
        )
        start = int((-self._phase * 200) % 360) * 16
        path.arcMoveTo(rect, start / 16)
        path.arcTo(rect, start / 16, 110)
        painter.drawPath(path)

    # -- interaction ----------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._wake()
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.pos()
            self._moved = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is None:
            return
        new_pos = event.globalPosition().toPoint() - self._drag_from
        if (new_pos - self.pos()).manhattanLength() > 3:
            self._moved = True
        self.move(new_pos)
        self.moved.emit()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_from = None
        if self._moved:
            self._snap_to_edge()
        else:
            self.clicked.emit()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._wake()

    # -- placement ------------------------------------------------------

    def _snap_to_edge(self) -> None:
        """Park against the nearest side, so it never floats mid-screen."""
        screen = self.screen().availableGeometry()
        x, y = self.x(), self.y()
        margin = 8

        left_gap = x - screen.left()
        right_gap = screen.right() - (x + self.width())
        x = screen.left() + margin if left_gap < right_gap else \
            screen.right() - self.width() - margin

        y = max(screen.top() + margin,
                min(y, screen.bottom() - self.height() - margin))

        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setEndValue(QPoint(x, y))
        # Keep the panel glued to it for the whole snap, not just at the end.
        anim.valueChanged.connect(lambda _v: self.moved.emit())
        anim.finished.connect(self.moved.emit)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def on_right_edge(self) -> bool:
        screen = self.screen().availableGeometry()
        return self.x() + self.width() / 2 > screen.center().x()

    # -- idle fading ----------------------------------------------------

    def _wake(self) -> None:
        self._fade.stop()
        self.setWindowOpacity(1.0)
        self._restart_idle_fade()

    def _restart_idle_fade(self) -> None:
        if theme.IDLE_FADE_MS > 0:
            self._idle_timer.start(theme.IDLE_FADE_MS)

    def _fade_out(self) -> None:
        if self._state != IDLE:
            return
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(theme.IDLE_OPACITY)
        self._fade.start()
