"""Tier 2: Google's Gemini free API.

A second, independent cloud provider. If Groq is rate-limited or down, this
takes over in well under a second, so the user never notices. See
docs/03-decisions.md D15.
"""

from __future__ import annotations

import httpx

from .base import KeyRevoked, Target, TierUnavailable
from .instructions import SYSTEM, build_user_message
from .keys import KeyRing

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiTier:
    name = "gemini"

    def __init__(
        self,
        api_key: str | list[str] | None = None,
        model: str = "gemini-3.5-flash-lite",
        timeout: float = 10.0,
    ) -> None:
        self.keys = KeyRing(api_key)
        self.model = model
        self.timeout = timeout

    def available(self) -> tuple[bool, str]:
        if not self.keys:
            return False, "no Gemini API key in config.toml"
        return True, ""

    def rewrite(self, raw: str, target: Target) -> str:
        ok, why = self.available()
        if not ok:
            raise TierUnavailable(why)

        payload = {
            # Gemini takes the system prompt separately from the conversation.
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_message(raw, target)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 900,
            },
        }

        last_error = "Gemini unavailable"
        rejected = 0
        for key in self.keys.rotation():
            try:
                resp = httpx.post(
                    ENDPOINT.format(model=self.model),
                    json=payload,
                    headers={
                        # Header rather than a query parameter, so the key
                        # never ends up in a URL that might be logged.
                        "x-goog-api-key": key,
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
            except httpx.TimeoutException:
                raise TierUnavailable(f"Gemini timed out after {self.timeout}s")
            except httpx.RequestError as exc:
                raise TierUnavailable(
                    f"no connection to Gemini ({exc.__class__.__name__})"
                )

            if resp.status_code in (401, 403):
                rejected += 1
                last_error = f"Gemini rejected key {KeyRing.redact(key)}"
                continue
            if resp.status_code == 429:
                last_error = f"Gemini rate limit on key {KeyRing.redact(key)}"
                continue
            if resp.status_code >= 400:
                raise TierUnavailable(f"Gemini returned HTTP {resp.status_code}")

            try:
                data = resp.json()
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts)
            except (KeyError, IndexError, ValueError) as exc:
                raise TierUnavailable(
                    "unexpected response shape from Gemini"
                ) from exc

            if not text.strip():
                # Usually a safety filter, or the model hit the token cap
                # before producing anything.
                raise TierUnavailable("Gemini returned empty content")

            return _strip_wrapping(text)

        if rejected and rejected == len(self.keys):
            # Every key was rejected outright. That is revocation, not a rate
            # limit - the user needs to know, not have it quietly hidden.
            raise KeyRevoked(
                f"Gemini: all {len(self.keys)} key(s) REJECTED. The key is invalid "
                f"or has been revoked. If you did not revoke it, treat it as "
                f"compromised and replace it now."
            )
        raise TierUnavailable(last_error)


def _strip_wrapping(text: str) -> str:
    """Remove a code fence the model may have wrapped the whole prompt in."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines)
    return t.strip()
