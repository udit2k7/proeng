"""Shared types for the rewrite tiers.

Every tier - Groq, Gemini, rules - implements the same small interface, so the
router can try them in order without caring which is which.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Target(str, Enum):
    """Which AI the prompt is being written for. See docs/03-decisions.md D11."""

    CLAUDE = "claude"
    CHATGPT = "chatgpt"
    GEMINI = "gemini"

    @property
    def label(self) -> str:
        return {"claude": "Claude Code", "chatgpt": "ChatGPT", "gemini": "Gemini"}[
            self.value
        ]


@dataclass
class RewriteResult:
    text: str
    tier: str              # "groq" | "gemini" | "rules"
    elapsed: float
    note: str = ""         # why we fell back to this tier, if we did
    alert: str = ""        # a security event the user MUST see (revoked key)


class TierUnavailable(Exception):
    """This tier cannot run right now - try the next one.

    Raised for missing API keys, no network, a service not running, or too
    little free RAM. The router catches it and moves on; the user sees a short
    note rather than an error.
    """


class KeyRevoked(TierUnavailable):
    """Every key for this provider was rejected (HTTP 401/403).

    This is the state a key lands in immediately after you rotate it because it
    leaked - so it is the one security event this tool can actually detect.
    It must never be swallowed: the router promotes it to a visible alert
    rather than quietly using the next tier. See proeng/security.py.

    Subclasses TierUnavailable so that a caller which does not care about the
    distinction still degrades gracefully - but the router checks for it first.
    """


class Tier(Protocol):
    name: str

    def available(self) -> tuple[bool, str]:
        """Return (usable, reason-if-not). Cheap to call - no network requests."""
        ...

    def rewrite(self, raw: str, target: Target) -> str:
        """Turn raw dictation into a structured prompt.

        Raise TierUnavailable to fall through to the next tier.
        """
        ...
