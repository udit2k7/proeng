"""Key safety: recognising keys, spotting exposure, and failing loudly.

What this can and cannot do, stated plainly:

CAN
  - Recognise API-key-shaped strings, so we can scan for them.
  - Detect a key that has been REVOKED or is invalid (the provider returns 401
    or 403). That is the state a key ends up in right after you rotate it
    because it leaked - so this is the practical detection point.
  - Check the obvious exposure routes: is config.toml committed? Is it ignored?
    Does a key appear anywhere else in the project?

CANNOT
  - Know that a key has leaked. No provider offers an API that says "this key
    appeared publicly". Only they know, and they would email you. Any tool
    claiming otherwise is guessing.

So the design is: make leaking hard, and make a revoked key impossible to
ignore. See docs/11-key-security.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Shapes of the keys we handle. Deliberately loose enough to catch a key even
# if a provider tweaks its format, and anchored enough not to match ordinary
# prose or base64 blobs.
KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "groq": re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "gemini": re.compile(r"\b(?:AIza[A-Za-z0-9_\-]{30,}|AQ\.[A-Za-z0-9_\-.]{20,})\b"),
    "openai": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    "anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
}


def redact(key: str) -> str:
    """A fragment safe to print. Never returns enough to use."""
    key = (key or "").strip()
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def find_keys(text: str) -> list[tuple[str, str]]:
    """Return (provider, key) for every API key found in `text`."""
    found: list[tuple[str, str]] = []
    for provider, pattern in KEY_PATTERNS.items():
        for match in pattern.findall(text):
            found.append((provider, match))
    return found


def looks_like_key(value: str) -> bool:
    return bool(find_keys(value))


# --- exposure checks -------------------------------------------------------

@dataclass
class Finding:
    level: str      # "critical" | "warning" | "ok"
    message: str
    fix: str = ""


def check_gitignore(root: Path) -> Finding:
    gi = root / ".gitignore"
    if not gi.exists():
        return Finding(
            "critical",
            ".gitignore is missing - config.toml could be committed",
            "create .gitignore with a line: config.toml",
        )
    lines = [ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()]
    if "config.toml" not in lines:
        return Finding(
            "critical",
            "config.toml is NOT in .gitignore - your keys could be committed",
            "add a line to .gitignore: config.toml",
        )
    return Finding("ok", "config.toml is in .gitignore")


def scan_tree(root: Path, skip: tuple[str, ...] = (".venv", ".git", "models",
                                                  "__pycache__")) -> list[Finding]:
    """Look for keys in files that are not config.toml.

    A key in config.toml is expected. A key anywhere else - a script, a note,
    a committed example - is an accident waiting to be pushed.
    """
    findings: list[Finding] = []
    text_suffixes = {
        ".py", ".md", ".toml", ".txt", ".json", ".yml", ".yaml",
        ".ini", ".cfg", ".sh", ".ps1", ".bat", ".env",
    }

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.name == "config.toml":
            continue  # keys belong here
        if path.suffix.lower() not in text_suffixes:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for provider, key in find_keys(content):
            # config.example.toml carries obvious placeholders, not real keys.
            if path.name == "config.example.toml" and (
                "..." in key or "first" in key or "second" in key
            ):
                continue
            findings.append(
                Finding(
                    "critical",
                    f"{provider} key {redact(key)} found in "
                    f"{path.relative_to(root)}",
                    "remove it, then REVOKE that key at the provider - "
                    "assume it is compromised",
                )
            )
    return findings


def check_permissions(root: Path) -> Finding:
    cfg = root / "config.toml"
    if not cfg.exists():
        return Finding("ok", "no config.toml yet")
    return Finding(
        "ok",
        f"config.toml exists ({cfg.stat().st_size} bytes) - keep it off shared "
        "drives and out of backups that sync publicly",
    )
