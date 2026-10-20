"""check:hygiene (part 2) — pasted mermaid fence scan. Fails closed.

Diagrams live as .mmd sources rendered with mermaid-cli (`poe diagrams`),
never as pasted ```mermaid fences in docs.

Usage: python scripts/check_no_pasted_diagrams.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Canonical index exception: none — ultra-minimal docs keep no mermaid fences.
ALLOWED = set()


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        print(f"check_no_pasted_diagrams: missing tool git ({out.stderr.strip()})")
        sys.exit(2)
    return out.stdout


def main() -> int:
    rels = _git("ls-files", "-z", "--", "docs").split("\0")
    violations: list[str] = []
    for rel in rels:
        if not rel or not rel.endswith(".md"):
            continue
        if rel in ALLOWED:
            continue
        p = ROOT / rel
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("```mermaid"):
                violations.append(f"{rel}:{lineno}")
    if violations:
        print("check_no_pasted_diagrams FAIL — pasted mermaid fences:")
        for v in violations:
            print(f"  {v}")
        print("Put the diagram in docs/<area>/<name>.mmd, render with "
              "`poe diagrams` (mermaid-cli), and link the SVG instead.")
        return 1
    print("check_no_pasted_diagrams ok: no pasted fences in docs/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
