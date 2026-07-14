#!/usr/bin/env python3
"""Scan the repo for secrets, PII, and paths unsafe for a public release.

Usage (from repo root):
  python scripts/audit_release_safety.py
  python scripts/audit_release_safety.py --path data/cloud_optimizer.db

Exit 0 if no critical findings; exit 1 if any critical finding.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "frontend/.next",
    "frontend/node_modules",
    "__pycache__",
    ".pytest_cache",
    "docs",
    "docs-gp",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_temp_key", re.compile(r"ASIA[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("openai_key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("arn_with_account", re.compile(r"arn:aws:iam::\d{12}:")),
    ("twelve_digit_account", re.compile(r"(?<![0-9.])1[0-9]{11}(?![0-9.])")),
    ("home_path", re.compile(r"/home/[a-zA-Z0-9._-]+")),
    ("env_file", re.compile(r"^\.env$")),
]

ALLOWLIST_SUBSTRINGS = (
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG",
    "123456789012",
    "111111111111",
    "999999999999",
    "888888888888",
    "your_google_gemini_api_key_here",
    "arn:aws:iam::123456789012:role/",
    "arn:aws:iam::111111111111:role/",
    "example",
    "EXAMPLE",
)


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    if path.suffix in {".pyc", ".db-shm", ".db-wal"}:
        return True
    if path.name.endswith(".db.backup"):
        return True
    return False


def scan_text_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for line_no, line in enumerate(text.splitlines(), 1):
        if any(token in line for token in ALLOWLIST_SUBSTRINGS):
            continue
        if "../home/" in line or "dashboard/home/" in line or 'e.g. ``"' in line:
            continue
        if '"/home/' in line and ("in searchable" in line or "file:///" in line):
            continue
        for label, pattern in SECRET_PATTERNS:
            if label == "env_file":
                continue
            if pattern.search(line):
                findings.append(f"{path}:{line_no}: {label}: {line.strip()[:120]}")
    return findings


def scan_tree(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or should_skip(path):
            continue
        if path.name == ".env" or (
            path.name.startswith(".env")
            and path.name not in {".env.example", ".env.docker.example"}
            and not path.name.endswith(".example")
        ):
            findings.append(f"{path}: critical: .env file present")
            continue
        if path.suffix in {
            ".py",
            ".md",
            ".txt",
            ".json",
            ".tex",
            ".csv",
            ".sh",
            ".yml",
            ".yaml",
            ".ts",
            ".tsx",
            ".sql",
        } or path.name in {"Dockerfile", "Makefile"}:
            findings.extend(scan_text_file(path))
    return findings


SYNTHETIC_USER = "aws-SYNTHETIC-001"
DB_ACCOUNT_RE = re.compile(rb"(?<![0-9])[1-9][0-9]{11}(?![0-9])")
DB_EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DB_ALLOWED_ACCOUNTS = {
    b"123456789012",
    b"111111111111",
    b"999999999999",
    b"888888888888",
}


def scan_database_raw(db_path: Path) -> list[str]:
    """Byte-level scan: catches values in free pages, indexes, and columns
    the table-level scan does not know about."""
    findings: list[str] = []
    data = db_path.read_bytes()
    accounts = {
        m.group(0) for m in DB_ACCOUNT_RE.finditer(data)
    } - DB_ALLOWED_ACCOUNTS
    for account in sorted(accounts):
        findings.append(
            f"{db_path}: critical: possible real 12-digit AWS account id "
            f"in raw bytes: {account.decode()}"
        )
    for match in {m.group(0) for m in DB_EMAIL_RE.finditer(data)}:
        email = match.decode(errors="replace")
        # Raw SQLite cells concatenate without separators, so the synthetic
        # placeholder may appear with adjacent cell bytes glued on.
        if "@aws.local" in email or "example" in email.lower():
            continue
        findings.append(
            f"{db_path}: critical: non-synthetic email in raw bytes: {email}"
        )
    return findings


def scan_database(db_path: Path) -> list[str]:
    findings: list[str] = []
    if not db_path.is_file():
        return [f"{db_path}: critical: database missing"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    for row in cur.execute("SELECT user_id, email FROM users"):
        email = row["email"] or ""
        if "@" in email and not email.endswith("@aws.local"):
            findings.append(
                f"{db_path}: critical: non-synthetic user email in users: {row['user_id']} {email}"
            )
    tables = [
        row["name"]
        for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    for table in tables:
        columns = {row["name"] for row in cur.execute(f"PRAGMA table_info({table})")}
        if "user_id" not in columns:
            continue
        for row in cur.execute(
            f"SELECT user_id, COUNT(*) AS n FROM {table} "
            "WHERE user_id != ? GROUP BY user_id",
            (SYNTHETIC_USER,),
        ):
            findings.append(
                f"{db_path}: critical: non-synthetic user rows in {table}: "
                f"{row['user_id']} ({row['n']} rows)"
            )
    try:
        for row in cur.execute(
            "SELECT aws_account_id, iam_role_arn FROM aws_connections"
        ):
            acct = row["aws_account_id"] or ""
            if acct and acct != "SYNTHETIC-001":
                findings.append(
                    f"{db_path}: critical: real aws_connections row account_id={acct} "
                    f"role={row['iam_role_arn']}"
                )
    except sqlite3.OperationalError:
        pass
    try:
        for row in cur.execute(
            "SELECT aws_account_id, aws_secret_access_key FROM aws_connections "
            "WHERE aws_secret_access_key IS NOT NULL AND aws_secret_access_key != ''"
        ):
            findings.append(
                f"{db_path}: critical: plaintext secret in aws_connections "
                f"account_id={row['aws_account_id']}"
            )
    except sqlite3.OperationalError:
        pass
    conn.close()
    findings.extend(scan_database_raw(db_path))
    return findings


def scan_git_history() -> list[str]:
    findings: list[str] = []
    try:
        out = subprocess.check_output(
            ["git", "log", "--all", "-p", "-S", "AKIA", "--", "*.env", ".env"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        if out.strip():
            findings.append("git history: possible AKIA in .env commits (review manually)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT,
        help="Root directory or a single file (e.g. data/cloud_optimizer.db)",
    )
    args = parser.parse_args()
    target = args.path.resolve()

    findings: list[str] = []
    if target.is_file() and target.suffix == ".db":
        findings.extend(scan_database(target))
    else:
        root = target if target.is_dir() else target.parent
        findings.extend(scan_tree(root))
        db = root / "data" / "cloud_optimizer.db"
        if db.is_file():
            findings.extend(scan_database(db))
        findings.extend(scan_git_history())

    if not findings:
        print("OK: no critical release-safety findings.")
        return 0

    print(f"FOUND {len(findings)} issue(s):\n")
    for item in findings:
        print(item)
    return 1


if __name__ == "__main__":
    sys.exit(main())
