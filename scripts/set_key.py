"""Manage API keys in config.toml without them touching your shell history.

The key is typed at a hidden prompt (nothing echoes), so it never appears in
your terminal scrollback, your PowerShell history file, or any log. Passing a
key as a command-line argument would land it in all three.

    set_key.py groq              replace the Groq key
    set_key.py gemini            replace the Gemini key
    set_key.py groq --clear      remove the Groq key
    set_key.py --status          show which keys are set (redacted)

If a key has leaked: revoke it at the provider FIRST, then run this to put the
replacement in. Revoking is what actually stops the damage; this only updates
what the tool uses.
"""

from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONFIG = ROOT / "config.toml"
EXAMPLE = ROOT / "config.example.toml"

PROVIDERS = {
    "groq": ("[groq]", "https://console.groq.com/keys"),
    "gemini": ("[gemini]", "https://aistudio.google.com/apikey"),
}


def ensure_config() -> bool:
    if CONFIG.exists():
        return True
    if not EXAMPLE.exists():
        print("config.example.toml is missing - cannot create config.toml")
        return False
    CONFIG.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    print("created config.toml from the example")
    return True


def write_key(provider: str, key: str) -> bool:
    """Replace api_key inside this provider's section only."""
    section = PROVIDERS[provider][0]
    text = CONFIG.read_text(encoding="utf-8")

    start = text.find(section)
    if start == -1:
        print(f"could not find the {section} section in config.toml")
        return False

    nxt = text.find("\n[", start + 1)
    end = nxt if nxt != -1 else len(text)
    block = text[start:end]

    new_block, count = re.subn(
        r'^api_key\s*=\s*".*?"',
        f'api_key = "{key}"',
        block,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        print(f"could not find an api_key line inside {section}")
        return False

    CONFIG.write_text(text[:start] + new_block + text[end:], encoding="utf-8")
    return True


def show_status() -> int:
    from proeng import config as cfgmod
    from proeng import security as sec
    from proeng.rewrite.keys import KeyRing

    cfg = cfgmod.load()
    print("\nConfigured keys")
    print("-" * 46)
    for name, value in [("groq", cfg.groq_api_key), ("gemini", cfg.gemini_api_key)]:
        ring = KeyRing(value)
        if ring:
            shown = ", ".join(sec.redact(k) for k in ring.rotation())
            print(f"  {name:8} {len(ring)} key(s): {shown}")
        else:
            print(f"  {name:8} not set")
    print("\nTo check they are still accepted by the providers:")
    print("  .venv\\Scripts\\python.exe scripts\\audit_keys.py\n")
    return 0


def main() -> int:
    args = sys.argv[1:]

    if "--status" in args:
        return show_status()

    if not args or args[0] not in PROVIDERS:
        print(__doc__)
        return 1

    provider = args[0]
    section, url = PROVIDERS[provider]

    if not ensure_config():
        return 1

    if "--clear" in args:
        if write_key(provider, ""):
            print(f"{provider} key removed from config.toml")
            print("Remember to REVOKE it at the provider too - removing it here")
            print(f"does not disable it. {url}")
            return 0
        return 1

    print(f"\nPaste your {provider} key (from {url}).")
    print("It will NOT be shown as you type, and will not enter your history.\n")

    try:
        key = getpass.getpass(f"{provider} key: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled")
        return 1

    if not key:
        print("nothing entered - config.toml unchanged")
        return 1

    from proeng import security as sec

    if not sec.looks_like_key(key):
        print("\nWarning: that does not look like a known API key format.")
        print("Saving it anyway - but check you pasted the whole thing.")

    if not write_key(provider, key):
        return 1

    print(f"\nSaved under {section}  ({sec.redact(key)})")
    print("config.toml is in .gitignore, so it will never be committed.")
    print("\nVerify it works:")
    print("  .venv\\Scripts\\python.exe scripts\\audit_keys.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
