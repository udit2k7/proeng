"""Any OpenAI-compatible provider the user cares to point us at.

Groq and Gemini are free and fast, but not everyone can reach them - some
countries block them, some workplaces forbid them, and some people already pay
for something else and would rather use that.

Almost every provider speaks the OpenAI chat-completions shape, so one adapter
covers a very large number of them:

  OpenRouter      https://openrouter.ai/api/v1
  DeepSeek        https://api.deepseek.com/v1
  Together        https://api.together.xyz/v1
  Mistral         https://api.mistral.ai/v1
  Cerebras        https://api.cerebras.ai/v1
  Fireworks       https://api.fireworks.ai/inference/v1
  OpenAI          https://api.openai.com/v1
  Ollama (local)  http://localhost:11434/v1
  LM Studio       http://localhost:1234/v1
  vLLM, llama.cpp, LocalAI, text-generation-webui, and most others

Note the last few: this is also how you run ProEng entirely offline again, on
your own hardware, without any of this file knowing that is what is happening.
"""

from __future__ import annotations

import httpx

from .base import KeyRevoked, Target, TierUnavailable
from .instructions import SYSTEM, build_user_message
from .keys import KeyRing


class CustomTier:
    """One user-configured, OpenAI-compatible endpoint."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | list[str] | None = None,
        model: str = "",
        timeout: float = 20.0,
        requires_key: bool = True,
    ) -> None:
        # The tier name shows up in the panel, so use what the user called it.
        self.name = name or "custom"
        self.base_url = (base_url or "").rstrip("/")
        self.keys = KeyRing(api_key)
        self.model = model
        self.timeout = timeout
        # Local servers (Ollama, LM Studio) accept any key or none at all.
        self.requires_key = requires_key

    @property
    def endpoint(self) -> str:
        # Accept either ".../v1" or a full ".../chat/completions".
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, f"{self.name}: no base_url configured"
        if not self.model:
            return False, f"{self.name}: no model configured"
        if self.requires_key and not self.keys:
            return False, f"{self.name}: no API key configured"
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
            "temperature": 0.2,
            "max_tokens": 900,
        }

        # A local server needs no credential; send a placeholder rather than
        # nothing, because some of them reject a missing header outright.
        keys = list(self.keys.rotation()) or ["not-needed"]

        last_error = f"{self.name} unavailable"
        rejected = 0
        for key in keys:
            try:
                resp = httpx.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
            except httpx.TimeoutException:
                raise TierUnavailable(
                    f"{self.name} timed out after {self.timeout}s"
                )
            except httpx.RequestError as exc:
                raise TierUnavailable(
                    f"cannot reach {self.name} at {self.base_url} "
                    f"({exc.__class__.__name__})"
                )

            if resp.status_code in (401, 403):
                rejected += 1
                last_error = f"{self.name} rejected key {KeyRing.redact(key)}"
                continue
            if resp.status_code == 429:
                last_error = f"{self.name} rate limit on {KeyRing.redact(key)}"
                continue
            if resp.status_code == 404:
                # By far the most common misconfiguration, so say what to check
                # rather than just reporting the number.
                raise TierUnavailable(
                    f"{self.name}: 404 - check base_url ({self.endpoint}) "
                    f"and that model '{self.model}' exists"
                )
            if resp.status_code >= 400:
                detail = ""
                try:
                    detail = str(resp.json().get("error", {}).get("message", ""))[:80]
                except Exception:
                    pass
                raise TierUnavailable(
                    f"{self.name} returned HTTP {resp.status_code}"
                    + (f": {detail}" if detail else "")
                )

            try:
                text = resp.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                raise TierUnavailable(
                    f"{self.name}: response was not in OpenAI format - is this "
                    f"an OpenAI-compatible endpoint?"
                ) from exc

            return _strip_wrapping(text)

        if rejected and rejected == len(keys):
            raise KeyRevoked(
                f"{self.name}: all {len(keys)} key(s) REJECTED. The key is "
                f"invalid or has been revoked. If you did not revoke it, treat "
                f"it as compromised and replace it now."
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
