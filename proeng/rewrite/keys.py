"""Multi-key support for the cloud tiers.

Free API tiers are rate-limited per key. Holding several keys for the same
provider and rotating between them turns "rate limited, fall back to the next
provider" into "use the next key" - which keeps quality high on a heavy day.

Rotation is round-robin with a starting offset that advances on every call, so
load spreads across keys rather than hammering the first one until it dies.
"""

from __future__ import annotations

import itertools
from typing import Iterator


class KeyRing:
    """An ordered set of API keys for one provider."""

    def __init__(self, keys: str | list[str] | None) -> None:
        if keys is None:
            items: list[str] = []
        elif isinstance(keys, str):
            items = [keys]
        else:
            items = list(keys)

        # Drop blanks and duplicates while keeping the configured order.
        seen: set[str] = set()
        self._keys: list[str] = []
        for k in items:
            k = (k or "").strip()
            if k and k not in seen:
                seen.add(k)
                self._keys.append(k)

        self._counter = itertools.count()

    def __bool__(self) -> bool:
        return bool(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def rotation(self) -> Iterator[str]:
        """Yield every key once, starting from a different one each call."""
        if not self._keys:
            return
        start = next(self._counter) % len(self._keys)
        for i in range(len(self._keys)):
            yield self._keys[(start + i) % len(self._keys)]

    @staticmethod
    def redact(key: str) -> str:
        """A safe fragment for logs and error notes - never the whole key."""
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
