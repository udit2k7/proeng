"""A system-wide hotkey, via the Windows API directly.

Why not a library: `keyboard` and `pynput` install a low-level keyboard hook,
which sees every keystroke you type anywhere. That is a lot of privilege for a
shortcut, it sometimes needs elevation, and antivirus software reasonably treats
global key hooks with suspicion.

`RegisterHotKey` asks Windows to notify us about one specific combination and
nothing else. No hook, no elevation, no dependency. The cost is that it is
Windows-only - which this project already is (R1).

Falls back to doing nothing if registration fails; the character is still
clickable, so a taken shortcut is an inconvenience rather than a breakage.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # do not fire repeatedly while held

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
}

# Virtual-key codes for the keys anyone actually binds.
_KEYS = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "backspace": 0x08,
    **{str(n): 0x30 + n for n in range(10)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)},
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


def parse(sequence: str) -> tuple[int, int] | None:
    """'ctrl+shift+space' -> (modifiers, virtual key code)."""
    mods = 0
    key = None
    for part in sequence.lower().replace(" ", "").split("+"):
        if part in _MODIFIERS:
            mods |= _MODIFIERS[part]
        elif part in _KEYS:
            key = _KEYS[part]
        else:
            return None
    if key is None or mods == 0:
        return None  # a bare key would hijack normal typing
    return mods | MOD_NOREPEAT, key


class HotkeyFilter(QAbstractNativeEventFilter, QObject):
    """Registers one hotkey and turns WM_HOTKEY into a Qt signal."""

    activated = Signal()

    HOTKEY_ID = 0xB17E

    def __init__(self) -> None:
        QAbstractNativeEventFilter.__init__(self)
        QObject.__init__(self)
        self.registered = False
        self.error = ""

    def register(self, sequence: str) -> bool:
        parsed = parse(sequence)
        if parsed is None:
            self.error = f"could not understand hotkey '{sequence}'"
            return False

        mods, key = parsed
        try:
            user32 = ctypes.windll.user32
            user32.RegisterHotKey.argtypes = [
                wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
            ]
            ok = user32.RegisterHotKey(None, self.HOTKEY_ID, mods, key)
        except Exception as exc:  # noqa: BLE001
            self.error = f"RegisterHotKey failed: {exc}"
            return False

        if not ok:
            # Almost always means another application already owns it.
            self.error = f"'{sequence}' is already taken by another program"
            return False

        self.registered = True
        return True

    def unregister(self) -> None:
        if not self.registered:
            return
        try:
            ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        except Exception:
            pass
        self.registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if event_type == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                self.activated.emit()
        return False, 0
