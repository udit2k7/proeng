"""List the models your API keys can actually use.

Providers retire models. When a rewrite fails with HTTP 404, the model name in
config.toml has almost certainly been withdrawn - run this to see what is
available now, then update config.toml.

Run:  .venv\\Scripts\\python.exe scripts\\list_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proeng import config as cfgmod  # noqa: E402
from proeng.rewrite.keys import KeyRing  # noqa: E402


def groq(cfg) -> None:
    ring = KeyRing(cfg.groq_api_key)
    print("\nGroq")
    print("-" * 52)
    if not ring:
        print("  no key in config.toml")
        return
    key = next(ring.rotation())
    try:
        r = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  request failed: {exc}")
        return
    if r.status_code != 200:
        print(f"  HTTP {r.status_code} - key may be invalid")
        return
    for m in sorted(x["id"] for x in r.json()["data"]):
        mark = " <- current" if m == cfg.groq_model else ""
        print(f"  {m}{mark}")


def gemini(cfg) -> None:
    ring = KeyRing(cfg.gemini_api_key)
    print("\nGemini")
    print("-" * 52)
    if not ring:
        print("  no key in config.toml")
        return
    key = next(ring.rotation())
    try:
        r = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  request failed: {exc}")
        return
    if r.status_code != 200:
        print(f"  HTTP {r.status_code} - key may be invalid")
        return
    for m in sorted(x["name"].replace("models/", "") for x in r.json().get("models", [])):
        # Only chat-capable models are useful to us.
        if "embedding" in m or "aqa" in m:
            continue
        mark = " <- current" if m == cfg.gemini_model else ""
        print(f"  {m}{mark}")


def main() -> int:
    cfg = cfgmod.load()
    groq(cfg)
    gemini(cfg)
    print("\nSet the one you want in config.toml, then rerun test_rewrite.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
