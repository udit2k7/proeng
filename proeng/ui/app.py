"""Wires the character, the panel, the worker thread and the hotkey together.

This is the only file that knows about all of them. Everything else stays
ignorant of everything else, which is what keeps the threading honest.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import clipboard
from ..config import CONFIG_PATH, Config, load
from ..rewrite.base import Target
from . import character as ch
from . import theme
from .character import Character
from .hotkey import HotkeyFilter
from .panel import Panel
from .settings import SettingsDialog
from .worker import DictationWorker


class ProEngApp(QObject):
    start_dictation = Signal()
    rewrite_requested = Signal(str)

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.target = Target(cfg.default_target)

        # Must happen before any widget is constructed - they read these at
        # build time.
        theme.apply(cfg)

        self.character = Character()
        self.panel = Panel(opacity=cfg.opacity)
        self.panel.set_target(self.target)

        self._build_worker()
        self._connect()
        self._build_tray()
        self._place_character()

        self.hotkey = HotkeyFilter()
        self.hotkey.activated.connect(self.toggle)

        # Free ~400 MB after a spell of not using it - see D12. The model
        # reloads in about 1.2s, which happens while the panel slides open.
        self._idle_unload = QTimer(self)
        self._idle_unload.setSingleShot(True)
        self._idle_unload.timeout.connect(self.worker.release_model)

    # -- setup ----------------------------------------------------------

    def _build_worker(self) -> None:
        self.thread = QThread()
        self.worker = DictationWorker(self.cfg)
        self.worker.moveToThread(self.thread)
        self.start_dictation.connect(self.worker.run_dictation)
        self.rewrite_requested.connect(self.worker.rewrite_text)
        self.thread.start()

    def _connect(self) -> None:
        self.character.clicked.connect(self.toggle)
        self.character.right_clicked.connect(self._show_menu)
        self.character.moved.connect(self._follow_character)

        self.panel.stop_recording.connect(self.worker.stop_recording)
        self.panel.submit.connect(self._on_submit)
        self.panel.target_changed.connect(self._on_target_changed)
        self.panel.copy_requested.connect(self._copy)
        self.panel.settings_requested.connect(self.open_settings)
        self.panel.closed.connect(self.hide_panel)

        w = self.worker
        w.recording_started.connect(self._on_recording_started)
        w.level.connect(self._on_level)
        w.countdown.connect(self._on_countdown)
        w.recording_stopped.connect(self._on_recording_stopped)
        w.model_loading.connect(
            lambda: self.panel.set_status("loading speech model...")
        )
        w.partial.connect(self.panel.set_partial)
        w.transcribed.connect(self.panel.set_transcript)
        w.rewriting.connect(self._on_rewriting)
        w.rewritten.connect(self._on_rewritten)
        w.failed.connect(self._on_failed)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self._tray_icon(), self)
        self.tray.setToolTip("ProEng - prompt rewriter")
        menu = QMenu()
        act_open = QAction("Dictate", menu)
        act_open.triggered.connect(self.toggle)
        act_settings = QAction("Settings...", menu)
        act_settings.triggered.connect(self.open_settings)
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit)
        menu.addAction(act_open)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.toggle()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    @staticmethod
    def _tray_icon() -> QIcon:
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(6, 6, 20, 20)
        painter.end()
        return QIcon(pix)

    def _place_character(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        if self.cfg.edge == "left":
            x = screen.left() + 16
        else:
            x = screen.right() - theme.CHARACTER_SIZE - 16
        self.character.move(x, screen.center().y() - theme.CHARACTER_SIZE // 2)
        self.character.show()

    # -- flow -----------------------------------------------------------

    @Slot()
    def toggle(self) -> None:
        if self.panel.isVisible():
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self) -> None:
        self._idle_unload.stop()
        self.panel.slide_in(self.character.geometry(), self.character.on_right_edge())
        self.panel.begin_recording()
        self.panel.reset_copy_button()
        self.character.set_state(ch.LISTENING)
        self.panel.activateWindow()
        self.start_dictation.emit()

    def hide_panel(self) -> None:
        self.worker.stop_recording()
        self.panel.hide()
        self.character.set_state(ch.IDLE)
        minutes = max(0, self.cfg.idle_unload_minutes)
        if minutes:
            self._idle_unload.start(minutes * 60 * 1000)

    # -- worker signals -------------------------------------------------

    @Slot()
    def _on_recording_started(self) -> None:
        self.character.set_state(ch.LISTENING)

    @Slot(float)
    def _on_level(self, level: float) -> None:
        self.character.set_level(level)
        self._level = level

    @Slot(float)
    def _on_countdown(self, remaining: float) -> None:
        self.panel.set_meter(
            getattr(self, "_level", 0.0), remaining, self.cfg.silence_timeout
        )

    @Slot(str)
    def _on_recording_stopped(self, reason: str) -> None:
        self.panel.end_recording(reason)
        self.character.set_state(ch.THINKING)

    @Slot()
    def _on_rewriting(self) -> None:
        self.character.set_state(ch.THINKING)
        self.panel.set_status("rewriting...")

    @Slot(str, str, float, str)
    def _on_rewritten(self, text: str, tier: str, elapsed: float, alert: str) -> None:
        self.panel.show_result(text, tier, elapsed, alert)
        self.character.set_state(ch.ERROR if alert else ch.DONE)
        if alert:
            print(f"\n!! API KEY PROBLEM: {alert}\n", file=sys.stderr)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.panel.set_status(message)
        self.character.set_state(ch.ERROR)

    @Slot(str)
    def _on_submit(self, text: str) -> None:
        if not text:
            return
        self.character.set_state(ch.THINKING)
        self.rewrite_requested.emit(text)

    @Slot(object)
    def _on_target_changed(self, target: Target) -> None:
        self.target = target
        self.worker.set_target(target)

    @Slot()
    def open_settings(self) -> None:
        """Edit keys and the by-feel settings without touching the CLI."""
        dialog = SettingsDialog(CONFIG_PATH, parent=self.panel)
        dialog.saved.connect(self._reload_config)
        dialog.exec()

    def _reload_config(self) -> None:
        """Re-read config.toml and apply what can change without a restart.

        Keys, language and microphone sensitivity all take effect on the next
        dictation. Sizes and the hotkey do not - they are read when widgets are
        built and when the hotkey is registered, so those still need a restart.
        """
        self.cfg = load()
        self.worker.cfg = self.cfg
        # The speech model may have changed with the language, so drop the
        # loaded one; the next dictation reloads the right one.
        self.worker.release_model()
        self.panel.set_status("settings saved")

    def _follow_character(self) -> None:
        """Keep the panel attached while the character is dragged."""
        self.panel.follow(
            self.character.geometry(), self.character.on_right_edge()
        )

    def _copy(self) -> None:
        text = self.panel.result_text() or self.panel.current_text()
        if not text:
            return
        if clipboard.copy(text):
            self.panel.flash_copied()
            self.character.set_state(ch.DONE)
            QTimer.singleShot(900, self.panel.reset_copy_button)
        else:
            self.panel.set_status("could not reach the clipboard")

    # -- menu / lifecycle -----------------------------------------------

    def _show_menu(self, pos) -> None:
        menu = QMenu()
        act = QAction("Dictate", menu)
        act.triggered.connect(self.toggle)
        menu.addAction(act)
        act_settings = QAction("Settings...", menu)
        act_settings.triggered.connect(self.open_settings)
        menu.addAction(act_settings)
        menu.addSeparator()
        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)
        menu.exec(pos)

    def quit(self) -> None:
        self.hotkey.unregister()
        self.worker.stop_recording()
        self.thread.quit()
        self.thread.wait(3000)
        QApplication.quit()


def main() -> int:
    cfg = load()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # it lives in the tray

    proeng = ProEngApp(cfg)
    app.installNativeEventFilter(proeng.hotkey)

    if proeng.hotkey.register(cfg.hotkey):
        print(f"hotkey: {cfg.hotkey}")
    else:
        print(f"hotkey unavailable - {proeng.hotkey.error}")
        print("click the character instead")

    print("ProEng running. Right-click the character, or the tray icon, to quit.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
