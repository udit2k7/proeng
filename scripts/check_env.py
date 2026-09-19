"""Environment check: are the libraries installed and is a microphone visible?

Runs without touching the microphone, so it is safe to run any time.
Run:  .venv\\Scripts\\python.exe scripts\\check_env.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok = True

print("\nLibraries")
print("-" * 46)
for mod, label in [
    ("numpy", "numpy"),
    ("sounddevice", "sounddevice"),
    ("webrtcvad", "webrtcvad"),
    ("faster_whisper", "faster-whisper"),
]:
    try:
        m = __import__(mod)
        print(f"  OK    {label:16} {getattr(m, '__version__', '')}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  FAIL  {label:16} {exc}")

print("\nMicrophones")
print("-" * 46)
try:
    from proeng.audio.recorder import default_microphone, list_microphones

    mics = list_microphones()
    if not mics:
        ok = False
        print("  FAIL  no input devices found")
    for idx, name, ch in mics[:8]:
        print(f"  [{idx}] {name} ({ch} ch)")
    d = default_microphone()
    print(f"\n  Default: {d[1] if d else 'NONE'}")
    if d is None:
        ok = False
except Exception as exc:  # noqa: BLE001
    ok = False
    print(f"  FAIL  {exc}")

print("\nCPU threads chosen by CTranslate2")
print("-" * 46)
try:
    import os

    print(f"  logical processors: {os.cpu_count()}")
except Exception as exc:  # noqa: BLE001
    print(f"  ? {exc}")

print()
print("ENVIRONMENT OK" if ok else "PROBLEMS FOUND")
print()
sys.exit(0 if ok else 1)
