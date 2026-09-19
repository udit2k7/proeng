"""Entry point: python -m proeng

Starts the floating widget. Ctrl+C in this terminal, or Quit from the tray
icon, to stop it.
"""

from __future__ import annotations

import sys

from .ui.app import main

if __name__ == "__main__":
    sys.exit(main())
