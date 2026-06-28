from __future__ import annotations

import re
import sqlite3
import threading

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aws_collector.config import AWSConfig
from aws_collector.runner import CollectorRunner
from storage.db import (
    _rows_to_dicts,
    add_aws_connection,
    delete_aws_connection,
    ensure_schema,
    ensure_user,
    get_aws_connections,
    get_connection,
    update_aws_connection_status,
)

router = APIRouter(prefix="/api/connections", tags=["connections"])

# Validation patterns enforced before any AWS call (untrusted input boundary).
# AKIA = long-lived IAM keys, ASIA = temporary STS keys (require a session token).
_ACCESS_KEY_ID_RE = re.compile(r"^(AKIA|ASIA)[A-Z0-9]{16}$")
_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")

# Tracks connection ids whose sync thread is live, guarded by _SYNC_LOCK so a
# second /sync cannot slip past the in_progress check while a thread is starting.
_SYNCING: set[int] = set()
_SYNC_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestConnectionRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str = ""
    aws_region: str = "us-east-1"


class TestConnectionResponse(BaseModel):
    ok: bool
    account_id: str | None = None
    error: str | None = None


class SaveConnectionRequest(BaseModel):
    connection_name: str = ""
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str = ""
    aws_region: str = "us-east-1"
    aws_account_id: str | None = None


class ConnectionOut(BaseModel):
    # SECURITY: aws_secret_access_key, aws_session_token, external_id and
    # iam_role_arn are intentionally OMITTED — secrets must never leave the
    # backend. Only the last 4 chars of the access key id are exposed so the
    # UI can show which key is in use.
    id: int
    connection_name: str | None = None
    aws_account_id: str
    aws_region: str
    auth_type: str
    access_verified: bool
    access_key_last4: str
    sync_status: str
    last_sync_at: str | None = None
    error_message: str | None = None
    connected_at: str | None = None
    data_user_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_out(row: dict) -> ConnectionOut:
    account_id = str(row["aws_account_id"])
    access_key_id = row.get("aws_access_key_id") or ""
    return ConnectionOut(
        id=int(row["id"]),
        connection_name=row.get("connection_name"),
        aws_account_id=account_id,
        aws_region=row.get("aws_region") or "us-east-1",
        auth_type=row.get("auth_type") or "role",
        access_verified=bool(row.get("access_verified") or 0),
        access_key_last4=access_key_id[-4:] if access_key_id else "",
        sync_status=row.get("sync_status") or "never",
        last_sync_at=row.get("last_sync_at"),
        error_message=row.get("error_message"),
        connected_at=row.get("connected_at"),
        data_user_id=f"aws-{account_id}",
    )


def _validate_keys(access_key_id: str, secret_access_key: str) -> None:
    if not _ACCESS_KEY_ID_RE.match(access_key_id or ""):
        raise HTTPException(status_code=400, detail="invalid aws_access_key_id")
    if not (secret_access_key or "").strip():
        raise HTTPException(status_code=400, detail="missing aws_secret_access_key")


def _validate_account_id(account_id: str) -> None:
    if not _ACCOUNT_ID_RE.match(account_id or ""):
        raise HTTPException(status_code=400, detail="invalid aws_account_id")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/test", response_model=TestConnectionResponse)
def test_connection(payload: TestConnectionRequest) -> TestConnectionResponse:
    # Validate untrusted input BEFORE reaching out to AWS. Malformed input is a
    # client error (400); well-formed keys that AWS rejects are *not* — that
    # returns 200 with ok=False so the frontend can surface the reason inline.
    _validate_keys(payload.aws_access_key_id, payload.aws_secret_access_key)

    try:
        cfg = AWSConfig.from_keys(
            payload.aws_access_key_id,
            payload.aws_secret_access_key,
            payload.aws_session_token,
            payload.aws_region,
        )
        account_id = cfg.account_id
    except (ClientError, BotoCoreError, Exception) as exc:  # noqa: B014
        # Never 500 on an auth / user-input failure — the keys may be wrong,
        # disabled, or lack sts:GetCallerIdentity. Do NOT echo the secret.
        return TestConnectionResponse(ok=False, error=str(exc))

    # A successful test verifies access for any already-saved connection on this
    # account. No storage helper exists for this, so update inline + commit.
    conn = get_connection()
    try:
        ensure_schema(conn)
        conn.execute(
            "UPDATE aws_connections SET access_verified = 1 "
            "WHERE user_id = ? AND aws_account_id = ?",
            (f"aws-{account_id}", account_id),
        )
        conn.commit()
    finally:
        conn.close()

    return TestConnectionResponse(ok=True, account_id=account_id)


@router.post("", response_model=ConnectionOut)
def save_connection(payload: SaveConnectionRequest) -> ConnectionOut:
    _validate_keys(payload.aws_access_key_id, payload.aws_secret_access_key)

    # Derive the account id. If supplied, trust it (after format check);
    # otherwise resolve it from the keys — which also verifies them.
    if payload.aws_account_id is not None:
        _validate_account_id(payload.aws_account_id)
        account_id = payload.aws_account_id
    else:
        try:
            cfg = AWSConfig.from_keys(
                payload.aws_access_key_id,
                payload.aws_secret_access_key,
                payload.aws_session_token,
                payload.aws_region,
            )
            account_id = cfg.account_id
        except (ClientError, BotoCoreError, Exception) as exc:  # noqa: B014
            raise HTTPException(status_code=400, detail=str(exc))

    owner = f"aws-{account_id}"
    conn = get_connection()
    try:
        ensure_schema(conn)
        ensure_user(conn, account_id)
        try:
            new_id = add_aws_connection(
                conn,
                user_id=owner,
                aws_account_id=account_id,
                iam_role_arn="",
                connection_name=payload.connection_name,
                aws_region=payload.aws_region,
                aws_access_key_id=payload.aws_access_key_id,
                aws_secret_access_key=payload.aws_secret_access_key,
                aws_session_token=payload.aws_session_token,
                auth_type="keys",
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="connection already exists for this account",
            )

        rows = get_aws_connections(conn, owner)
        row = next((r for r in rows if int(r["id"]) == int(new_id)), None)
        if row is None:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail="saved row not found")
        return _row_to_out(row)
    finally:
        conn.close()


@router.get("", response_model=list[ConnectionOut])
def list_connections(user_id: str = Query(...)) -> list[ConnectionOut]:
    conn = get_connection()
    try:
        ensure_schema(conn)
        rows = get_aws_connections(conn, user_id)
        return [_row_to_out(r) for r in rows]
    finally:
        conn.close()


@router.delete("/{connection_id}")
def remove_connection(connection_id: int, user_id: str = Query(...)) -> dict:
    conn = get_connection()
    try:
        ensure_schema(conn)
        deleted = delete_aws_connection(conn, int(connection_id), user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="connection not found")
        return {"ok": True, "deleted": int(connection_id)}
    finally:
        conn.close()


@router.post("/{connection_id}/sync")
def sync_connection(connection_id: int, user_id: str = Query(...)) -> JSONResponse:
    conn = get_connection()
    try:
        ensure_schema(conn)
        rows = get_aws_connections(conn, user_id)
        row = next((r for r in rows if int(r["id"]) == int(connection_id)), None)
        if row is None:
            raise HTTPException(status_code=404, detail="connection not found")

        data_user_id = f"aws-{row['aws_account_id']}"

        with _SYNC_LOCK:
            if connection_id in _SYNCING or row.get("sync_status") == "in_progress":
                raise HTTPException(status_code=409, detail="sync already in progress")
            _SYNCING.add(connection_id)
            update_aws_connection_status(conn, connection_id, "in_progress")
    finally:
        conn.close()

    thread = threading.Thread(
        target=_run_sync, args=(connection_id,), daemon=True
    )
    thread.start()

    return JSONResponse(
        status_code=202,
        content={
            "status": "in_progress",
            "connection_id": connection_id,
            "data_user_id": data_user_id,
        },
    )


def _run_sync(connection_id: int) -> None:
    # Runs in a daemon thread. SQLite connections are not shareable across
    # threads, so open a fresh one here and own its lifecycle. The stored row
    # already carries the access keys, so no keys are re-sent from the frontend.
    thread_conn = get_connection()
    try:
        ensure_schema(thread_conn)
        row = _get_connection_row(thread_conn, connection_id)
        if row is None:  # pragma: no cover - row vanished mid-sync
            return
        data_user_id = f"aws-{row['aws_account_id']}"
        try:
            CollectorRunner.from_connection(
                row, data_user_id, conn=thread_conn
            ).run(months=12)
            update_aws_connection_status(thread_conn, connection_id, "success")
        except Exception as exc:
            update_aws_connection_status(
                thread_conn, connection_id, "failed", str(exc)[:500]
            )
    finally:
        with _SYNC_LOCK:
            _SYNCING.discard(connection_id)
        thread_conn.close()


def _get_connection_row(conn: sqlite3.Connection, connection_id: int) -> dict | None:
    # The sync thread only knows the connection id (not the owning user_id), so
    # look the row up directly rather than through the user-scoped helper.
    rows = _rows_to_dicts(
        conn.execute(
            "SELECT * FROM aws_connections WHERE id = ?", (int(connection_id),)
        )
    )
    return rows[0] if rows else None
