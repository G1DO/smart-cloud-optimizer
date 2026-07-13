#!/usr/bin/env python3
"""Produce a public-release-safe copy of cloud_optimizer.db.

Removes non-synthetic users and all aws_connections rows. Does not modify the
source file unless --in-place is passed (use only on a release branch).

Usage:
  python scripts/sanitize_release_db.py \\
    --source data/cloud_optimizer.db \\
    --output data/cloud_optimizer.release.db

  # verify before replacing committed DB on release branch:
  python scripts/audit_release_safety.py --path data/cloud_optimizer.release.db
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "data" / "cloud_optimizer.db"
SYNTHETIC_USER = "aws-SYNTHETIC-001"


def sanitize(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    stats: dict[str, int] = {}

    cur.execute("SELECT COUNT(*) FROM users WHERE user_id != ?", (SYNTHETIC_USER,))
    n_users = cur.fetchone()[0]
    cur.execute("DELETE FROM users WHERE user_id != ?", (SYNTHETIC_USER,))
    stats["users_removed"] = n_users

    try:
        cur.execute("SELECT COUNT(*) FROM aws_connections")
        n_conn = cur.fetchone()[0]
        cur.execute("DELETE FROM aws_connections")
        stats["connections_removed"] = n_conn
    except sqlite3.OperationalError:
        stats["connections_removed"] = 0

    # Scrub synthetic user email to a neutral placeholder if it was personalized.
    cur.execute(
        "UPDATE users SET email = ? WHERE user_id = ?",
        (f"{SYNTHETIC_USER}@aws.local", SYNTHETIC_USER),
    )
    conn.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=False)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite source (creates .backup first)",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 1

    if args.in_place:
        backup = source.with_suffix(source.suffix + ".pre-sanitize.backup")
        shutil.copy2(source, backup)
        target = source
        print(f"Backup written to {backup}")
    else:
        if not args.output:
            print("ERROR: --output required unless --in-place", file=sys.stderr)
            return 1
        target = args.output.resolve()
        shutil.copy2(source, target)

    conn = sqlite3.connect(target)
    try:
        stats = sanitize(conn)
    finally:
        conn.close()

    print(f"Sanitized {target}")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("Run: python scripts/audit_release_safety.py --path", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
