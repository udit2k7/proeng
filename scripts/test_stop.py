"""Does Stop actually stop, while the worker thread is busy?

This is the case the UI smoke test could not catch. It checked that clicking
Stop emitted a signal - which it always did. What failed was delivery: the
worker lives on another thread and is stuck inside the recording loop, so Qt
queued the call to an event loop that never ran until recording was already
over.

So this test blocks the worker thread the same way a real recording does, then
presses Stop and checks whether it lands. No microphone involved.

Run:  .venv\\Scripts\\python.exe scripts\\test_stop.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QObject, Qt, QThread, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

BUSY_SECONDS = 3.0


class FakeWorker(QObject):
    """Stands in for DictationWorker: busy, on its own thread, stoppable."""

    def __init__(self) -> None:
        super().__init__()
        self.stop_event = threading.Event()
        self.stopped_at: float | None = None
        self.started_at: float | None = None
        self.finished = threading.Event()

    def stop_recording(self) -> None:
        """Exactly what the real one does: set a threading.Event."""
        self.stop_event.set()

    def run(self) -> None:
        """Block this thread, as a real recording loop does."""
        self.started_at = time.monotonic()
        deadline = self.started_at + BUSY_SECONDS
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                self.stopped_at = time.monotonic()
                break
            time.sleep(0.02)
        self.finished.set()


class Emitter(QObject):
    stop_recording = Signal()


def run_case(name: str, connection_type) -> tuple[bool, str]:
    worker = FakeWorker()
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    emitter = Emitter()
    emitter.stop_recording.connect(worker.stop_recording, connection_type)

    thread.start()
    time.sleep(0.4)          # let the worker get properly stuck
    press = time.monotonic()
    emitter.stop_recording.emit()

    worker.finished.wait(BUSY_SECONDS + 2)
    thread.quit()
    thread.wait(2000)

    if worker.stopped_at is None:
        return False, f"{name}: never stopped - ran the full {BUSY_SECONDS:.0f}s"
    delay = worker.stopped_at - press
    if delay > 0.5:
        return False, f"{name}: stopped, but {delay:.2f}s late"
    return True, f"{name}: stopped {delay * 1000:.0f}ms after the press"


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841 - required for QThread

    print("\nStop-button delivery")
    print("=" * 58)
    print(f"  worker blocks its thread for {BUSY_SECONDS:.0f}s, as a recording does")
    print("  Stop is pressed 0.4s in; it must land almost immediately\n")

    ok_direct, msg_direct = run_case(
        "DirectConnection  (what we now use)",
        Qt.ConnectionType.DirectConnection,
    )
    print(f"  [{'PASS' if ok_direct else 'FAIL'}] {msg_direct}")

    ok_queued, msg_queued = run_case(
        "QueuedConnection  (the bug)",
        Qt.ConnectionType.QueuedConnection,
    )
    # This one is EXPECTED to fail - that was the bug. If it ever starts
    # passing, Qt's behaviour has changed and the comment in app.py is stale.
    print(f"  [{'unexpected' if ok_queued else 'as expected'}] {msg_queued}")

    print("\n" + "=" * 58)
    if not ok_direct:
        print("FAIL - Stop does not reach a busy worker. The button is dead.\n")
        return 1
    if ok_queued:
        print("Stop works, but the queued case now passes too - Qt behaviour")
        print("may have changed. Re-read the comment in ui/app.py.\n")
        return 0
    print("PASS - Stop lands immediately on a busy worker,")
    print("       and the old queued approach is confirmed broken.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
