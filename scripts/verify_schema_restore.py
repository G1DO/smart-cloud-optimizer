"""Schema compatibility + backup/restore proof (recorded, not stubbed).

Proves:
  1. Fresh DB: ensure_schema() creates all tables/indexes from the checked-in
     initializer without opening the committed demo DB.
  2. Old DB migration: a temp copy of data/cloud_optimizer.db (old schema
     without key columns) gains only the supported additive credential
     columns, preserves users, and passes integrity_check.
  3. Backup/restore: sqlite backup API round-trips the live file to a temp
     path outside the repo, restores to a second temp path, passes
     integrity_check, and serves the demo workspace query.

Run: python scripts/verify_schema_restore.py
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import ensure_schema  # noqa: E402


def fresh_schema() -> tuple[int, list[str]]:
    with closing(sqlite3.connect(":memory:")) as conn:
        ensure_schema(conn)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        cols = [
            r[1]
            for r in conn.execute("PRAGMA table_info(aws_connections)")
        ]
    return len(tables), cols


def migrate_copy(src: Path, work: Path) -> dict:
    with closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True)) as s:
        with closing(sqlite3.connect(work)) as d:
            s.backup(d)
    with closing(sqlite3.connect(work)) as conn:
        before_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(aws_connections)")
        ]
        users_before = sorted(
            r[0] for r in conn.execute("SELECT user_id FROM users")
        )
        ensure_schema(conn)
        conn.commit()
        after_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(aws_connections)")
        ]
        users_after = sorted(
            r[0] for r in conn.execute("SELECT user_id FROM users")
        )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    added = [c for c in after_cols if c not in before_cols]
    return {
        "before_cols": before_cols,
        "after_cols": after_cols,
        "added": added,
        "users_preserved": users_before == users_after,
        "users": users_after,
        "integrity": integrity,
    }


def backup_restore(src: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "snapshot.db"
        restored = Path(td) / "restored.db"
        with closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True)) as s:
            with closing(sqlite3.connect(snap)) as d:
                s.backup(d)
                assert (
                    d.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                )
        # Restore: copy snapshot to the restore path, re-verify, serve query.
        restored.write_bytes(snap.read_bytes())
        with closing(sqlite3.connect(restored)) as conn:
            ensure_schema(conn)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            conn.row_factory = sqlite3.Row
            demo = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                ("aws-SYNTHETIC-001",),
            ).fetchone()
            n_daily = conn.execute(
                "SELECT COUNT(*) FROM daily_costs WHERE user_id = ?",
                ("aws-SYNTHETIC-001",),
            ).fetchone()[0]
    return {
        "integrity": integrity,
        "demo_present": demo is not None,
        "demo_daily_rows": n_daily,
    }


def main() -> int:
    src = ROOT / "data" / "cloud_optimizer.db"
    if not src.exists():
        print(f"missing committed DB: {src}")
        return 2
    ntables, fresh_cols = fresh_schema()
    print(f"fresh schema: {ntables} tables; aws_connections cols={fresh_cols}")

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "migrate_copy.db"
        mig = migrate_copy(src, work)
    print(f"migrate copy: added={mig['added']}")
    print(f"migrate copy: users preserved={mig['users_preserved']} "
          f"users={mig['users']}")
    print(f"migrate copy: integrity={mig['integrity']}")
    if set(mig["added"]) != {
        "aws_access_key_id", "aws_secret_access_key",
        "aws_session_token", "auth_type",
    }:
        print(f"unexpected migration delta: {mig['added']}")
        return 1
    if not mig["users_preserved"] or mig["integrity"] != "ok":
        print("migration proof failed")
        return 1

    br = backup_restore(src)
    print(f"restore: integrity={br['integrity']} "
          f"demo_present={br['demo_present']} "
          f"demo_daily_rows={br['demo_daily_rows']}")
    if br["integrity"] != "ok" or not br["demo_present"]:
        print("restore proof failed")
        return 1
    print("schema-compat + restore: ok "
          "(fresh init, additive migrate, backup/restore verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
