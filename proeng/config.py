"""Reads config.toml. Falls back to sensible defaults if it is missing.

The file is optional on purpose: the tool must run out of the box with no
setup, on the rules tier. See docs/03-decisions.md D6.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"


@dataclass
class Config:
    tiers: list[str] = field(default_factory=lambda: ["groq", "gemini", "rules"])
    offline_only: bool = False
    default_target: str = "claude"

    groq_api_key: str | list[str] = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout: float = 8.0

    gemini_api_key: str | list[str] = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout: float = 10.0

    trigger_prefix: str = "++"
    hook_timeout: float = 5.0

    speech_model: str = "base.en"
    speech_language: str = "en"
    silence_timeout: float = 7.0
    vad_aggressiveness: int = 2
    partial_interval: float = 1.5
    speech_level_threshold: float = 300.0
    preview_model: str = "base"
    partial_window_seconds: float = 8.0

    opacity: float = 0.75
    character_size: int = 64
    panel_width: int = 380
    edge: str = "right"
    hotkey: str = "ctrl+shift+space"
    idle_fade_seconds: int = 10
    idle_unload_minutes: int = 10

    loaded_from: Path | None = None


def load(path: Path | None = None) -> Config:
    path = path or CONFIG_PATH
    cfg = Config()
    if not path.exists():
        return cfg

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # A malformed config must not stop the tool starting. Defaults are fine.
        return cfg

    rw = data.get("rewrite", {})
    cfg.tiers = rw.get("tiers", cfg.tiers)
    cfg.offline_only = rw.get("offline_only", cfg.offline_only)
    cfg.default_target = rw.get("default_target", cfg.default_target)

    g = data.get("groq", {})
    # "api_keys" (a list) wins over "api_key" (a single string).
    cfg.groq_api_key = g.get("api_keys") or g.get("api_key", cfg.groq_api_key)
    cfg.groq_model = g.get("model", cfg.groq_model)
    cfg.groq_timeout = float(g.get("timeout_seconds", cfg.groq_timeout))

    gm = data.get("gemini", {})
    cfg.gemini_api_key = gm.get("api_keys") or gm.get("api_key", cfg.gemini_api_key)
    cfg.gemini_model = gm.get("model", cfg.gemini_model)
    cfg.gemini_timeout = float(gm.get("timeout_seconds", cfg.gemini_timeout))

    h = data.get("hooks", {})
    cfg.trigger_prefix = h.get("trigger_prefix", cfg.trigger_prefix)
    cfg.hook_timeout = float(h.get("timeout_seconds", cfg.hook_timeout))

    s = data.get("speech", {})
    cfg.speech_model = s.get("model", cfg.speech_model)
    cfg.silence_timeout = float(s.get("silence_timeout", cfg.silence_timeout))
    cfg.speech_language = s.get("language", cfg.speech_language)
    cfg.vad_aggressiveness = int(s.get("vad_aggressiveness", cfg.vad_aggressiveness))
    cfg.partial_interval = float(s.get("partial_interval", cfg.partial_interval))
    cfg.speech_level_threshold = float(
        s.get("speech_level_threshold", cfg.speech_level_threshold)
    )
    cfg.preview_model = s.get("preview_model", cfg.preview_model)
    cfg.partial_window_seconds = float(
        s.get("partial_window_seconds", cfg.partial_window_seconds)
    )

    u = data.get("ui", {})
    cfg.opacity = float(u.get("opacity", cfg.opacity))
    cfg.character_size = int(u.get("character_size", cfg.character_size))
    cfg.panel_width = int(u.get("panel_width", cfg.panel_width))
    cfg.edge = u.get("edge", cfg.edge)
    cfg.hotkey = u.get("hotkey", cfg.hotkey)
    cfg.idle_fade_seconds = int(u.get("idle_fade_seconds", cfg.idle_fade_seconds))
    cfg.idle_unload_minutes = int(
        u.get("idle_unload_minutes", cfg.idle_unload_minutes)
    )

    cfg.loaded_from = path
    return cfg


def build_router(cfg: Config):
    """Assemble the tier chain described by the config."""
    from .rewrite.gemini import GeminiTier
    from .rewrite.groq import GroqTier
    from .rewrite.router import Router
    from .rewrite.rules import RulesTier

    tiers = []
    for name in cfg.tiers:
        if name == "groq":
            if cfg.offline_only:
                continue  # cloud tiers are skipped entirely in offline mode
            tiers.append(GroqTier(cfg.groq_api_key, cfg.groq_model, cfg.groq_timeout))
        elif name == "gemini":
            if cfg.offline_only:
                continue
            tiers.append(
                GeminiTier(cfg.gemini_api_key, cfg.gemini_model, cfg.gemini_timeout)
            )
        elif name == "rules":
            tiers.append(RulesTier())

    return Router(tiers)
