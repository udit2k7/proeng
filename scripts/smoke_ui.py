"""Build the whole interface, exercise it without a human, then quit.

Catches construction errors, signal-connection mistakes and paint crashes
without needing anyone to sit and click. It does NOT prove the thing looks
right - only a human can say that.

Run:  .venv\\Scripts\\python.exe scripts\\smoke_ui.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from proeng.config import load  # noqa: E402
from proeng.rewrite.base import Target  # noqa: E402
from proeng.ui import character as ch  # noqa: E402
from proeng.ui.app import ProEngApp  # noqa: E402

failures: list[str] = []
steps: list[str] = []


def step(name: str, fn) -> None:
    try:
        fn()
        steps.append(f"  [PASS] {name}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"  [FAIL] {name}: {exc}")
        steps.append(f"  [FAIL] {name}: {exc}")
        traceback.print_exc()


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    cfg = load()
    proeng = None

    def build() -> None:
        nonlocal proeng
        proeng = ProEngApp(cfg)

    step("construct the app", build)
    if proeng is None:
        print("\n".join(steps))
        return 1

    step("register the hotkey", lambda: _hotkey(proeng, cfg))
    step("show the character", proeng.character.show)
    step("paint every character state", lambda: _states(proeng))
    step("slide the panel in", proeng.show_panel)
    step("drive the level meter", lambda: _meter(proeng))
    step("render a result", lambda: _result(proeng))
    step("switch target to ChatGPT",
         lambda: proeng.panel.set_target(Target.CHATGPT))
    step("switch target to Gemini",
         lambda: proeng.panel.set_target(Target.GEMINI))
    step("stop button appears while recording", lambda: _stop_visible(proeng))
    step("stop button ends recording", lambda: _stop_works(proeng))
    step("render a VERY long result", lambda: _long_result(proeng))
    step("panel stays fully on screen", lambda: _on_screen(proeng))
    step("panel follows the character", lambda: _follows(proeng))
    step("Speak again restarts dictation", lambda: _again(proeng))
    step("settings dialog builds", lambda: _settings(proeng))
    step("render a key alert", lambda: _alert(proeng))
    step("hide the panel", proeng.hide_panel)

    def finish() -> None:
        try:
            proeng.quit()
        except Exception:
            pass
        app.quit()

    QTimer.singleShot(1500, finish)
    app.exec()

    print("\nInterface smoke test")
    print("=" * 52)
    print("\n".join(steps))
    print("=" * 52)
    if failures:
        print(f"{len(failures)} step(s) FAILED\n")
        return 1
    print("all steps passed - it builds, paints and responds\n")
    print("Nothing here proves it LOOKS right. Run it and see:")
    print("  .venv\\Scripts\\python.exe -m proeng\n")
    return 0


def _hotkey(proeng, cfg) -> None:
    QApplication.instance().installNativeEventFilter(proeng.hotkey)
    ok = proeng.hotkey.register(cfg.hotkey)
    if not ok:
        # Not fatal - the character still works. Report it, don't fail.
        steps.append(f"         note: hotkey unavailable ({proeng.hotkey.error})")


def _states(proeng) -> None:
    for state in (ch.IDLE, ch.LISTENING, ch.THINKING, ch.DONE, ch.ERROR):
        proeng.character.set_state(state)
        proeng.character.set_level(0.5)
        proeng.character.repaint()
    proeng.character.set_state(ch.IDLE)


def _meter(proeng) -> None:
    for i in range(12):
        proeng._on_level(i / 12)
        proeng._on_countdown(7.0 - i * 0.5)


def _result(proeng) -> None:
    proeng._on_rewritten(
        "Goal\nAdd a dark mode toggle to the settings page.\n\n"
        "Requirements\n- Remember the choice between visits.\n"
        "- No white flash on load.\n\n"
        "Open questions\n- Use local storage?",
        "groq",
        1.42,
        "",
    )


def _stop_visible(proeng) -> None:
    """While dictating, Stop must be on screen and usable."""
    proeng.panel.begin_recording()
    QApplication.processEvents()
    if not proeng.panel.stop_button.isVisible():
        raise AssertionError("Stop button is not visible while recording")
    if not proeng.panel.stop_button.isEnabled():
        raise AssertionError("Stop button is disabled while recording")


def _stop_works(proeng) -> None:
    """Clicking Stop must request a stop, and refuse a confused second click."""
    fired: list[int] = []
    proeng.panel.stop_recording.connect(lambda: fired.append(1))

    proeng.panel.stop_button.click()
    QApplication.processEvents()
    if not fired:
        raise AssertionError("Stop did not request a stop")
    if proeng.panel.stop_button.isEnabled():
        raise AssertionError("Stop stayed enabled - a second click would confuse")

    # A second click while it is stopping must do nothing.
    proeng.panel.stop_button.click()
    QApplication.processEvents()
    if len(fired) > 1:
        raise AssertionError("a second click fired another stop")

    # Once recording actually ends, the button goes away.
    proeng.panel.end_recording("manual")
    QApplication.processEvents()
    if proeng.panel.stop_button.isVisible():
        raise AssertionError("Stop button lingered after recording ended")


def _long_result(proeng) -> None:
    """A result long enough to have pushed the copy button off-screen before."""
    body = "\n".join(
        f"- Requirement number {i} that is deliberately long enough to wrap "
        f"onto more than one line in the panel."
        for i in range(1, 25)
    )
    proeng._on_rewritten(
        f"Goal\nSomething substantial.\n\nRequirements\n{body}\n\n"
        "Open questions\n- Does this still fit on the screen?",
        "groq", 2.1, "",
    )
    QApplication.processEvents()


def _on_screen(proeng) -> None:
    """The whole panel - including the copy button - must be reachable.

    This is the bug from the screenshot: the panel grew downward from a Y
    chosen for its old height, so the bottom fell off the display.
    """
    # The slide animation has to land before geometry means anything.
    end = proeng.panel._slide.endValue()
    geo = end if end is not None else proeng.panel.geometry()
    screen = proeng.panel.screen().availableGeometry()

    problems = []
    if geo.bottom() > screen.bottom():
        problems.append(
            f"bottom {geo.bottom()} is below the screen ({screen.bottom()})"
        )
    if geo.top() < screen.top():
        problems.append(f"top {geo.top()} is above the screen ({screen.top()})")
    if geo.right() > screen.right():
        problems.append("right edge is off-screen")
    if geo.left() < screen.left():
        problems.append("left edge is off-screen")
    if problems:
        raise AssertionError("; ".join(problems))


def _follows(proeng) -> None:
    """Dragging the character must bring the panel with it."""
    before = proeng.panel.pos()
    screen = proeng.character.screen().availableGeometry()
    proeng.character.move(screen.left() + 40, screen.top() + 60)
    proeng.character.moved.emit()
    QApplication.processEvents()
    after = proeng.panel.pos()
    if before == after:
        raise AssertionError("panel did not move with the character")


def _again(proeng) -> None:
    """After a result, "Speak again" must start over cleanly.

    The important part is not that it fires - it is that the previous result
    is cleared. Leaving the old rewrite on screen while recording the next one
    would be actively misleading.
    """
    if not proeng.panel.again_button.isVisible():
        raise AssertionError("Speak again is not shown beside a result")

    fired: list[int] = []
    proeng.panel.again_requested.connect(lambda: fired.append(1))
    proeng.panel.again_button.click()
    QApplication.processEvents()
    if not fired:
        raise AssertionError("Speak again did not request a new dictation")

    # dictate_again() runs on the click; check it reset the panel.
    if proeng.panel.output.isVisible():
        raise AssertionError("the previous result is still on screen")
    if proeng.panel.copy_button.isVisible():
        raise AssertionError("the copy button survived into the new recording")
    if proeng.panel.again_button.isVisible():
        raise AssertionError("Speak again survived into the new recording")
    if not proeng.panel.stop_button.isVisible():
        raise AssertionError("Stop is missing from the new recording")
    if proeng.panel.input.toPlainText():
        raise AssertionError("the previous transcript was not cleared")


def _settings(proeng) -> None:
    """The dialog must build and read the real config without saving."""
    from proeng.config import CONFIG_PATH
    from proeng.ui.settings import SettingsDialog

    dialog = SettingsDialog(CONFIG_PATH, parent=proeng.panel)
    if dialog.language.count() < 3:
        raise AssertionError("language choices missing")
    if not dialog.summary():
        raise AssertionError("key summary empty")
    from PySide6.QtWidgets import QLineEdit
    if dialog.groq.echoMode() != QLineEdit.EchoMode.Password:
        raise AssertionError("API key field is not masked")
    dialog.deleteLater()


def _alert(proeng) -> None:
    proeng._on_rewritten(
        "Goal\nSomething.", "rules", 0.0,
        "Groq: all 1 key(s) REJECTED. Replace it now.",
    )


if __name__ == "__main__":
    sys.exit(main())
