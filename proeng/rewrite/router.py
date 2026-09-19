"""Picks a rewrite tier and falls back automatically.

The user is never asked to choose mid-flow. They find out which tier answered
from a small indicator afterwards - see docs/05-ui-spec.md.
"""

from __future__ import annotations

import time

from .base import KeyRevoked, RewriteResult, Target, Tier, TierUnavailable
from .clean import to_ascii_safe
from .rules import RulesTier


class Router:
    def __init__(self, tiers: list[Tier]) -> None:
        if not tiers or tiers[-1].name != "rules":
            # Rules must be last and must always be present, or a bad day
            # (no key, no internet) would leave the user with nothing.
            tiers = [*tiers, RulesTier()]
        self.tiers = tiers

    def rewrite(self, raw: str, target: Target = Target.CLAUDE) -> RewriteResult:
        if not raw.strip():
            return RewriteResult("", "none", 0.0, "nothing to rewrite")

        notes: list[str] = []
        alerts: list[str] = []
        for tier in self.tiers:
            ok, why = tier.available()
            if not ok:
                notes.append(f"{tier.name}: {why}")
                continue

            start = time.monotonic()
            try:
                text = tier.rewrite(raw, target)
            except KeyRevoked as exc:
                # Checked before TierUnavailable because it subclasses it.
                # A rejected key is a security event, not a routine fallback.
                alerts.append(str(exc))
                notes.append(f"{tier.name}: {exc}")
                continue
            except TierUnavailable as exc:
                notes.append(f"{tier.name}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                # A tier bug must not take the whole tool down.
                notes.append(f"{tier.name}: unexpected error ({exc})")
                continue

            elapsed = time.monotonic() - start
            if not text.strip():
                notes.append(f"{tier.name}: returned nothing")
                continue

            # One place to normalise, so every tier benefits and none can
            # ship a character that crashes a Windows console.
            return RewriteResult(
                text=to_ascii_safe(text.strip()),
                tier=tier.name,
                elapsed=elapsed,
                note="; ".join(notes),
                alert=" | ".join(alerts),
            )

        return RewriteResult(
            raw.strip(), "none", 0.0, "; ".join(notes), " | ".join(alerts)
        )
