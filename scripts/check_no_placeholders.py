"""check:hygiene (part 1) — stub/placeholder marker scan. Fails closed.

Fails (exit 1) on unfinished-work markers in tracked text files:
bare TODO / FIXME / XXX / HACK, lorem ipsum filler, NotImplementedError.

Tracked follow-ups pass: TODO/FIXME with a parenthesized scope reference
such as TODO(prod): or TODO(m10): are allowed anywhere. Known instances:
  - docs/operations/runbook.md TODO(prod) — required-before-prod skeleton,
    each with an explicit "Reason still N/A" (not a stub).
  - frontend/app/lib/api.ts TODO(m10) — tracked follow-up with issue ref.

The English word "placeholder" in prose is descriptive, not a stub, and
passes (synthetic fixtures, SQL "?" placeholders, documented CLI behavior).

Usage: python scripts/check_no_placeholders.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Bare markers without a "(scope)" reference. A scoped marker such as
# "TODO(prod)" or "TODO(m10): ..." is a tracked follow-up, not a stub,
# with or without the trailing colon (prose may cite the marker bare).
BARE_MARKER_RE = re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b(?!\s*\([^)]*\))")
LOREM_RE = re.compile(r"(?i)\blorem\b")
NOTIMPL_RE = re.compile(r"\bNotImplementedError\b")

# Out of scope for the application stub gate (documented, not silent):
#  - paper/ — paper artifact tree; review tracked on release/ccpe-v1.0.
#  - scripts/check_no_placeholders.py — this lint source is self-referential
#    by construction (it names the markers it scans for).
EXCLUDED_TOP = {"paper"}
SELF = Path(__file__).resolve()

SKIP_SUFFIXES = {
    ".db", ".db-wal", ".db-shm", ".backup", ".pdf", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".woff", ".woff2", ".ttf", ".pyc", ".zip", ".gz",
}
SKIP_DIRS = {
    "node_modules", ".next", ".pytest_tmp", ".pytest_cache", "htmlcov",
    "__pycache__", ".venv", "venv", ".git",
}


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        print(f"check_no_placeholders: missing tool git ({out.stderr.strip()})")
        sys.exit(2)
    return out.stdout


def candidate_files() -> list[Path]:
    rels = (
        _git("ls-files", "-z").split("\0")
        + _git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    )
    files: list[Path] = []
    for rel in rels:
        if not rel:
            continue
        p = ROOT / rel
        if p.resolve() == SELF:
            continue
        if p.relative_to(ROOT).parts[0] in EXCLUDED_TOP:
            continue
        if not p.is_file():
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        if any(d in SKIP_DIRS for d in p.relative_to(ROOT).parts):
            continue
        try:
            if p.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def scan() -> list[str]:
    findings: list[str] = []
    for p in candidate_files():
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeError, OSError):
            continue
        rel = str(p.relative_to(ROOT))
        for lineno, line in enumerate(text.splitlines(), 1):
            if BARE_MARKER_RE.search(line):
                findings.append(f"{rel}:{lineno}: bare stub marker: {line.strip()[:100]}")
            elif LOREM_RE.search(line):
                findings.append(f"{rel}:{lineno}: lorem filler: {line.strip()[:100]}")
            elif NOTIMPL_RE.search(line) and p.suffix in {".py"}:
                findings.append(f"{rel}:{lineno}: NotImplementedError: {line.strip()[:100]}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("check_no_placeholders FAIL — unfinished markers:")
        for f in findings[:20]:
            print(f"  {f}")
        if len(findings) > 20:
            print(f"  ... and {len(findings) - 20} more")
        print("Finish the work or convert to a scoped TODO(<ref>): marker.")
        return 1
    print("check_no_placeholders ok: no bare stubs "
          "(scoped TODO(<ref>) tracked items pass)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
