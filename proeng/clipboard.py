"""Clipboard access, with a fallback that needs nothing installed."""

from __future__ import annotations

import subprocess


def copy(text: str) -> bool:
    """Put text on the clipboard. Returns whether it worked."""
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # Fall back to the clip.exe that ships with Windows, so the tool still
    # works if pyperclip is missing or broken.
    try:
        proc = subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),  # clip.exe expects UTF-16LE
            check=True,
            shell=True,
        )
        return proc.returncode == 0
    except Exception:
        return False
