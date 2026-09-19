"""Scan GitHub repositories for leaked secrets - working tree AND git history.

History matters more than the working tree. Deleting a key from a file does
nothing: it stays in every clone of the repository forever, and making the
repository private afterwards does not retrieve the copies people already have.

Usage:
    scan_repos.py owner/repo [owner/repo ...]
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Patterns kept specific enough to avoid drowning the report in false
# positives. A generic "any 32 hex chars" rule matches every git hash.
PATTERNS: dict[str, re.Pattern[str]] = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS secret": re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "Google OAuth": re.compile(r"\b[0-9]+-[0-9a-z_]{32}\.apps\.googleusercontent\.com\b"),
    "Firebase key": re.compile(r"(?i)\"?apiKey\"?\s*[=:]\s*['\"]AIza[0-9A-Za-z_\-]{35}"),
    "Groq key": re.compile(r"\bgsk_[A-Za-z0-9]{40,}\b"),
    "OpenAI key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),
    "Stripe key": re.compile(r"\b[sr]k_(?:live|test)_[0-9A-Za-z]{24,}\b"),
    "Twilio SID": re.compile(r"\bAC[0-9a-fA-F]{32}\b"),
    "SendGrid key": re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "MongoDB URI": re.compile(r"mongodb(?:\+srv)?://[^\s:]+:[^\s@]+@"),
    "Postgres URI": re.compile(r"postgres(?:ql)?://[^\s:]+:[^\s@]+@"),
    "Generic password=": re.compile(
        r"(?i)\b(?:password|passwd|secret|api_key|apikey|auth_token|access_token)"
        r"\s*[=:]\s*['\"]([^'\"\s]{10,})['\"]"
    ),
}

# Placeholders that look like secrets but are not.
NOISE = re.compile(
    r"(?i)(example|sample|dummy|placeholder|your[_-]?key|xxx+|<[^>]+>|"
    r"changeme|insert[_-]?here|\.\.\.|test[_-]?key|redacted|\*{4,})"
)

SENSITIVE_FILES = re.compile(
    r"(?i)(^|/)("
    r"\.env(\.|$)|credentials\.json|serviceaccount.*\.json|"
    r"id_rsa|id_dsa|id_ecdsa|id_ed25519|.*\.pem$|.*\.pfx$|.*\.p12$|"
    r"secrets?\.(json|ya?ml|toml|ini)|"
    r".*\.keystore$|.*\.jks$|google-services\.json|GoogleService-Info\.plist"
    r")"
)


def run(args: list[str], cwd: Path | None = None, timeout: int = 900) -> str:
    try:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, text=True,
            errors="ignore", timeout=timeout,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return f"__ERROR__ {exc}"


def redact(value: str) -> str:
    value = value.strip()
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]} ({len(value)} chars)"


def scan_text(text: str, where: str) -> list[tuple[str, str, str]]:
    hits = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            found = match.group(0)
            if NOISE.search(found):
                continue
            hits.append((name, redact(found), where))
    return hits


def scan_repo(slug: str, workdir: Path) -> dict:
    print(f"\n{'=' * 66}")
    print(f"  {slug}")
    print("=" * 66)

    dest = workdir / slug.replace("/", "_")
    print("  cloning (history included, large blobs skipped)...", flush=True)
    out = run([
        "git", "clone", "--quiet",
        # Secrets are small; skipping big blobs keeps a 288 MB repo tractable
        # without missing anything that matters.
        "--filter=blob:limit=1m",
        f"https://github.com/{slug}.git", str(dest),
    ])
    if not dest.exists():
        print(f"  CLONE FAILED: {out[:200]}")
        return {"slug": slug, "error": "clone failed"}

    findings: list[tuple[str, str, str]] = []

    # 1. sensitive filenames, anywhere in history
    names = run(["git", "log", "--all", "--pretty=format:", "--name-only",
                 "--diff-filter=A"], cwd=dest)
    sensitive = sorted({
        n for n in names.splitlines()
        if n.strip() and SENSITIVE_FILES.search(n)
    })

    # 2. secrets in the current tree
    tracked = run(["git", "ls-files"], cwd=dest).splitlines()
    for rel in tracked:
        path = dest / rel
        try:
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            findings += scan_text(
                path.read_text(encoding="utf-8", errors="ignore"),
                f"working tree: {rel}",
            )
        except Exception:
            continue

    # 3. secrets anywhere in history
    print("  scanning history...", flush=True)
    diff = run(["git", "log", "--all", "-p", "--no-color"], cwd=dest)
    if not diff.startswith("__ERROR__"):
        findings += scan_text(diff, "git history")

    # Collapse duplicates, keeping the worst location.
    unique: dict[tuple[str, str], str] = {}
    for kind, value, where in findings:
        key = (kind, value)
        if key not in unique or "working tree" in where:
            unique[key] = where

    print(f"\n  tracked files: {len([t for t in tracked if t])}")
    if sensitive:
        print(f"\n  SENSITIVE FILENAMES ever committed ({len(sensitive)}):")
        for n in sensitive[:20]:
            print(f"    - {n}")
    else:
        print("  no sensitive filenames in history")

    if unique:
        print(f"\n  POSSIBLE SECRETS ({len(unique)}):")
        for (kind, value), where in sorted(unique.items()):
            print(f"    [{kind}] {value}")
            print(f"        {where}")
    else:
        print("  no secret-shaped strings found")

    shutil.rmtree(dest, ignore_errors=True)
    return {
        "slug": slug,
        "files": len([t for t in tracked if t]),
        "sensitive_names": sensitive,
        "secrets": unique,
    }


def main() -> int:
    slugs = sys.argv[1:]
    if not slugs:
        print(__doc__)
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="repoScan_"))
    results = []
    try:
        for slug in slugs:
            results.append(scan_repo(slug, workdir))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n{'=' * 66}")
    print("  SUMMARY")
    print("=" * 66)
    total = 0
    for r in results:
        if r.get("error"):
            print(f"  {r['slug']:<24} ERROR: {r['error']}")
            continue
        n = len(r["secrets"]) + len(r["sensitive_names"])
        total += n
        state = "CLEAN" if n == 0 else f"{n} ITEM(S) TO REVIEW"
        print(f"  {r['slug']:<24} {r['files']:>5} files   {state}")
    print()
    if total:
        print("  Anything flagged should be treated as PUBLIC ALREADY.")
        print("  Making the repo private does not retrieve copies people have.")
        print("  ROTATE the credential; that is the only real fix.")
    else:
        print("  Nothing found. Note this scans for known patterns only -")
        print("  a clean result is reassuring, not a guarantee.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
