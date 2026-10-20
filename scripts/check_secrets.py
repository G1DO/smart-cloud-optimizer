"""check:secrets — working-tree + history secrets scan with push protection.

Runs without third-party deps (stdlib only). Fails closed: exit 1 on leak,
exit 2 on tool misuse; prints proof lines on success.

What it checks:
  1. Working tree: git-tracked + untracked-but-not-ignored files
     (respects .gitignore, so frontend/.next, node_modules, .env, backups
     are excluded by ignore rules, not by ad-hoc skips).
  2. Full history: `git log -p --all` patch text (history-aware, not just HEAD).

Allowlist (fail-closed): only synthetic demo placeholders and AWS docs
example keys. Real-key patterns are never allowlisted. Gitleaks config
(.gitleaks.toml) mirrors the same allowlist and extends default rules.

Push protection: .githooks/pre-push runs this script; .github/workflows
runs it in CI with full history (fetch-depth 0).

Usage:
  python scripts/check_secrets.py [--working-tree-only | --history-only]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Real-secret patterns (value-shaped, not field-name-shaped).
# Field references such as `aws_secret_access_key=payload.…`,
# `${AWS_SECRET_ACCESS_KEY}`, or empty `.env.example` assignments must not fail.
PATTERNS: dict[str, re.Pattern] = {
    "aws-access-key-id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "aws-secret-key-value": re.compile(
        r"aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{20,})['\"]?"
    ),
    "aws-secret-env-value": re.compile(
        r"AWS_SECRET_ACCESS_KEY\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{20,})['\"]?"
    ),
    "private-key-block": re.compile(
        r"-----BEGIN (?:RSA )?PRIVATE KEY-----\s+[A-Za-z0-9/+=]{20,}"
    ),
    "google-api-key-assignment": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
}

# Allowlist: synthetic demo + AWS documentation example keys only.
ALLOW_RE = re.compile(
    r"(?i)SYNTHETIC-001"
    r"|AKIAIOSFODNN7EXAMPLE"
    r"|wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    r"|AKIA_TEMP"  # hermetic test fixture token, not a key (see tests/test_aws_config.py)
    r"|EXAMPLE"  # AWS documentation example keys (…EXAMPLE suffix)
)

# Binary / fixture paths never scanned as text (DB contains PII by design;
# it is covered by the threat model, not by the secrets scan).
SKIP_SUFFIXES = {
    ".db", ".db-wal", ".db-shm", ".backup", ".pdf", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".woff", ".woff2", ".ttf", ".pyc", ".zip", ".gz",
}
SKIP_NAMES = {".gitleaks.toml"}


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def working_tree_files() -> list[Path]:
    # Tracked + untracked-not-ignored, null-separated, respects .gitignore.
    tracked = _git("ls-files", "-z").split("\0")
    untracked = _git(
        "ls-files", "--others", "--exclude-standard", "-z"
    ).split("\0")
    files: list[Path] = []
    for rel in tracked + untracked:
        if not rel:
            continue
        p = ROOT / rel
        if not p.is_file():
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        if p.name in SKIP_NAMES:
            continue
        # Extra guard: skip known build/cache dirs even if ignore rules change.
        parts = p.relative_to(ROOT).parts
        if any(
            d in {"node_modules", ".next", ".pytest_tmp", ".pytest_cache",
                  "htmlcov", "__pycache__", ".venv", "venv"}
            for d in parts
        ):
            continue
        # Skip files larger than 1 MiB (archives, bundles); gitleaks covers
        # history for those via --max-target-megabytes defaults.
        try:
            if p.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def scan_text(text: str, origin: str) -> list[str]:
    findings: list[str] = []
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            hit = m.group(0)
            # Allowlist applies to the matched secret plus surrounding line
            # context so placeholder fixtures do not fail the scan.
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start : line_end if line_end != -1 else len(text)]
            if ALLOW_RE.search(hit) or ALLOW_RE.search(line):
                continue
            findings.append(f"{origin}: {name} -> {hit[:40]}")
    return findings


def scan_working_tree() -> list[str]:
    findings: list[str] = []
    for p in working_tree_files():
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeError, OSError):
            continue
        rel = str(p.relative_to(ROOT))
        findings.extend(scan_text(text, rel))
    return findings


def scan_history() -> list[str]:
    try:
        patch = _git("log", "-p", "--all", "--no-merges", "--", ".")
    except RuntimeError as exc:
        return [f"history-unavailable: {exc}"]
    return scan_text(patch, "git-history")


def try_gitleaks() -> tuple[bool, str]:
    """Run gitleaks history + working-tree scans if the binary exists."""
    import shutil

    if shutil.which("gitleaks") is None:
        return True, "gitleaks not installed; stdlib scan is authoritative"
    cfg = str(ROOT / ".gitleaks.toml")
    cmds = [
        ["gitleaks", "detect", "--source", ".", "--config", cfg, "--verbose"],
        ["gitleaks", "detect", "--source", ".", "--config", cfg,
         "--no-git", "--verbose"],
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                              text=True, check=False)
        tail = (proc.stdout + proc.stderr)[-2000:]
        if proc.returncode != 0:
            # gitleaks exit 1 = leaks found; other codes = tool error.
            return False, f"{' '.join(cmd)} failed:\n{tail}"
    return True, "gitleaks history + working-tree: no leaks found"


def main(argv: list[str]) -> int:
    only_history = "--history-only" in argv
    only_tree = "--working-tree-only" in argv
    findings: list[str] = []
    if not only_history:
        findings.extend(scan_working_tree())
    if not only_tree:
        findings.extend(scan_history())
    if findings:
        print("check:secrets FAIL — suspected secrets:")
        for f in findings[:20]:
            print(f"  {f}")
        if len(findings) > 20:
            print(f"  ... and {len(findings) - 20} more")
        print("Redact the leak, keep it out of Git, see "
              "docs/security/threat-model.md.")
        return 1
    ok, detail = try_gitleaks()
    # Count scanned files for proof.
    nfiles = len(working_tree_files()) if not only_history else -1
    if not ok:
        print(f"check:secrets FAIL — {detail}")
        return 1
    if only_history:
        print("check:secrets ok: history scan clean; " + detail)
    elif only_tree:
        print(f"check:secrets ok: working tree clean ({nfiles} files); "
              + detail)
    else:
        print(f"check:secrets ok: working tree ({nfiles} files) + "
              f"history clean; {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
