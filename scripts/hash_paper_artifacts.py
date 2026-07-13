#!/usr/bin/env python3
"""Print SHA-256 hashes for paper submission artifacts.

Usage:
  python scripts/hash_paper_artifacts.py
  python scripts/hash_paper_artifacts.py --json > docs/paper_artifact_hashes.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"

DEFAULT_GLOBS = (
    "results*.json",
    "numbers*.tex",
    "table_*.tex",
    "*_tabular.tex",
    "figures/*.pdf",
    "journal/final/journal_final.pdf",
    "final/conference_final.pdf",
    "trace_rnd_hourly.csv",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def collect(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paths: list[Path] = []
    for pattern in DEFAULT_GLOBS:
        paths.extend(PAPER.glob(pattern))

    rows = collect(paths)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    for row in rows:
        print(f"{row['sha256']}  {row['path']}  ({row['bytes']} bytes)")
    print(f"\n{len(rows)} files hashed under paper/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
