"""Tier 1: Groq's free API. Fast and good, when there is internet.

Costs nothing and does not touch the user's Claude or ChatGPT quota, which is
requirement R2 - see docs/03-decisions.md D4.

Supports several keys: on a rate limit it rotates to the next one rather than
giving up on the provider. See keys.py.
"""

from __future__ import annotations

import httpx

from .base import KeyRevoked, Target, TierUnavailable
from .instructions import SYSTEM, build_user_message
from .keys import KeyRing

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqTier:
    name = "groq"

    def __init__(
        self,
        api_key: str | list[str] | None = None,
        model: str = "openai/gpt-oss-120b",
        timeout: float = 8.0,
    ) -> None:
        self.keys = KeyRing(api_key)
        self.model = model
        self.timeout = timeout

    def available(self) -> tuple[bool, str]:
        if not self.keys:
            return False, "no Groq API key in config.toml"
        return True, ""

    def rewrite(self, raw: str, target: Target) -> str:
        ok, why = self.available()
        if not ok:
            raise TierUnavailable(why)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_user_message(raw, target)},
            ],
            # Low but not zero: rewriting is a precision task, and near-greedy
            # decoding keeps the model from embellishing.
            "temperature": 0.2,
            "max_tokens": 900,
        }

        last_error = "Groq unavailable"
        rejected = 0
        for key in self.keys.rotation():
            try:
                resp = httpx.post(
                    ENDPOINT,
                    json=payload,
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=self.timeout,
                )
            except httpx.TimeoutException:
                # A timeout is about the network, not the key - another key
                # would time out too.
                raise TierUnavailable(f"Groq timed out after {self.timeout}s")
            except httpx.RequestError as exc:
                raise TierUnavailable(
                    f"no connection to Groq ({exc.__class__.__name__})"
                )

            if resp.status_code in (401, 403):
                rejected += 1
                last_error = f"Groq rejected key {KeyRing.redact(key)}"
                continue  # a different key may still work
            if resp.status_code == 429:
                last_error = f"Groq rate limit on key {KeyRing.redact(key)}"
                continue
            if resp.status_code >= 400:
                raise TierUnavailable(f"Groq returned HTTP {resp.status_code}")

            try:
                text = resp.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                raise TierUnavailable("unexpected response shape from Groq") from exc

            return _strip_wrapping(text)

        if rejected and rejected == len(self.keys):
            # Every key was rejected outright. That is revocation, not a rate
            # limit - the user needs to know, not have it quietly hidden.
            raise KeyRevoked(
                f"Groq: all {len(self.keys)} key(s) REJECTED. The key is invalid "
                f"or has been revoked. If you did not revoke it, treat it as "
                f"compromised and replace it now."
            )
        raise TierUnavailable(last_error)


def _strip_wrapping(text: str) -> str:
    """Remove a code fence the model may have wrapped the whole prompt in.

    Rule 6 in the instructions forbids this, but models do it anyway often
    enough to be worth handling rather than shipping stray backticks to the
    user's clipboard.
    """
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines)
    return t.strip()
