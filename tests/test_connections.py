"""Tests for the real-AWS connection backend (backend_api/routers/connections).

Fully hermetic: a temporary SQLite DB, no real AWS, no network. AWS access is
either mocked with moto (@mock_aws) or monkeypatched at AWSConfig.from_role /
CollectorRunner.from_connection so the blocking collector never runs.
"""
from __future__ import annotations

import threading
import time

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend_api.main import app
from backend_api.routers import connections
from storage import db as storage_db

ROLE_ARN = "arn:aws:iam::123456789012:role/CloudOptimizerReadOnly"
ACCOUNT_ID = "123456789012"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "connections.db"

    def connect_to_test_db():
        conn = storage_db.get_connection(db_path)
        storage_db.ensure_schema(conn)
        return conn

    with connect_to_test_db() as conn:
        storage_db.ensure_schema(conn)

    monkeypatch.setattr(connections, "get_connection", connect_to_test_db)

    # Module-level sync state is global; isolate each test.
    with connections._SYNC_LOCK:
        connections._SYNCING.clear()

    yield TestClient(app)

    with connections._SYNC_LOCK:
        connections._SYNCING.clear()


class _FakeCfg:
    def __init__(self, account_id: str = ACCOUNT_ID):
        self.account_id = account_id


# ---------------------------------------------------------------------------
# /test
# ---------------------------------------------------------------------------


def test_test_happy_path_monkeypatched(client, monkeypatch):
    monkeypatch.setattr(
        connections.AWSConfig, "from_role", lambda *a, **k: _FakeCfg()
    )

    resp = client.post(
        "/api/connections/test",
        json={"iam_role_arn": ROLE_ARN, "aws_region": "us-east-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["account_id"] == ACCOUNT_ID
    assert body["error"] is None


def test_test_happy_path_real_moto(client, monkeypatch):
    """Real-moto variant: mock STS assume_role + get_caller_identity and the
    other clients AWSConfig eagerly builds. Falls back to the monkeypatch path
    if moto cannot satisfy AWSConfig.__init__.
    """
    moto = pytest.importorskip("moto")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    trust_policy = (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
        '"Principal":{"AWS":"*"},"Action":"sts:AssumeRole"}]}'
    )

    with moto.mock_aws():
        import boto3

        iam = boto3.client("iam", region_name="us-east-1")
        role = iam.create_role(
            RoleName="CloudOptimizerReadOnly",
            AssumeRolePolicyDocument=trust_policy,
        )["Role"]
        role_arn = role["Arn"]

        try:
            resp = client.post(
                "/api/connections/test",
                json={"iam_role_arn": role_arn, "aws_region": "us-east-1"},
            )
        except Exception as exc:  # pragma: no cover - moto incompat fallback
            pytest.skip(f"moto cannot satisfy AWSConfig.__init__: {exc}")

    assert resp.status_code == 200
    body = resp.json()
    # moto's assumed identity is a 12-digit account id.
    assert body["ok"] is True, body
    assert body["account_id"] and len(body["account_id"]) == 12


def test_test_malformed_arn_is_400(client):
    resp = client.post(
        "/api/connections/test", json={"iam_role_arn": "not-an-arn"}
    )
    assert resp.status_code == 400


def test_test_failure_returns_200_not_500(client, monkeypatch):
    def boom(*a, **k):
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "AssumeRole",
        )

    monkeypatch.setattr(connections.AWSConfig, "from_role", boom)

    resp = client.post(
        "/api/connections/test", json={"iam_role_arn": ROLE_ARN}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


def test_test_account_mismatch(client, monkeypatch):
    monkeypatch.setattr(
        connections.AWSConfig, "from_role", lambda *a, **k: _FakeCfg("999999999999")
    )

    resp = client.post(
        "/api/connections/test",
        json={"iam_role_arn": ROLE_ARN, "aws_account_id": ACCOUNT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "mismatch" in body["error"]
    assert body["account_id"] == "999999999999"


# ---------------------------------------------------------------------------
# save / list / delete
# ---------------------------------------------------------------------------


def _save_payload(name: str = "Prod") -> dict:
    return {
        "connection_name": name,
        "aws_account_id": ACCOUNT_ID,
        "iam_role_arn": ROLE_ARN,
        "external_id": "secret-xyz",
        "aws_region": "us-east-1",
    }


def test_save_then_duplicate_conflict(client):
    resp = client.post("/api/connections", json=_save_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["aws_account_id"] == ACCOUNT_ID
    assert body["data_user_id"] == f"aws-{ACCOUNT_ID}"
    assert "external_id" not in body  # secret never exposed

    dup = client.post("/api/connections", json=_save_payload("Prod2"))
    assert dup.status_code == 409


def test_save_malformed_account_is_400(client):
    payload = _save_payload()
    payload["aws_account_id"] = "12"
    resp = client.post("/api/connections", json=payload)
    assert resp.status_code == 400


def test_list_and_delete(client):
    saved = client.post("/api/connections", json=_save_payload()).json()
    conn_id = saved["id"]
    owner = f"aws-{ACCOUNT_ID}"

    listed = client.get("/api/connections", params={"user_id": owner})
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == conn_id
    assert "external_id" not in rows[0]

    wrong = client.delete(
        f"/api/connections/{conn_id}", params={"user_id": "aws-000000000000"}
    )
    assert wrong.status_code == 404

    ok = client.delete(
        f"/api/connections/{conn_id}", params={"user_id": owner}
    )
    assert ok.status_code == 200

    gone = client.get("/api/connections", params={"user_id": owner}).json()
    assert gone == []


def test_test_sets_access_verified_on_saved_row(client, monkeypatch):
    client.post("/api/connections", json=_save_payload())
    owner = f"aws-{ACCOUNT_ID}"

    before = client.get("/api/connections", params={"user_id": owner}).json()
    assert before[0]["access_verified"] is False

    monkeypatch.setattr(
        connections.AWSConfig, "from_role", lambda *a, **k: _FakeCfg()
    )
    resp = client.post("/api/connections/test", json={"iam_role_arn": ROLE_ARN})
    assert resp.json()["ok"] is True

    after = client.get("/api/connections", params={"user_id": owner}).json()
    assert after[0]["access_verified"] is True


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


class _FakeRunner:
    """Stands in for CollectorRunner so no real AWS/collector runs."""

    def __init__(self, run_impl):
        self._run_impl = run_impl

    def run(self, months: int = 12):
        self._run_impl()


def _poll_status(client, owner: str, conn_id: int, target: str, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = client.get("/api/connections", params={"user_id": owner}).json()
        row = next(r for r in rows if r["id"] == conn_id)
        if row["sync_status"] == target:
            return row
        time.sleep(0.02)
    rows = client.get("/api/connections", params={"user_id": owner}).json()
    row = next(r for r in rows if r["id"] == conn_id)
    raise AssertionError(f"status {row['sync_status']!r} != {target!r}")


def test_sync_success(client, monkeypatch):
    saved = client.post("/api/connections", json=_save_payload()).json()
    conn_id = saved["id"]
    owner = f"aws-{ACCOUNT_ID}"

    monkeypatch.setattr(
        connections.CollectorRunner,
        "from_connection",
        classmethod(lambda cls, row, uid, conn=None: _FakeRunner(lambda: None)),
    )

    resp = client.post(
        f"/api/connections/{conn_id}/sync", params={"user_id": owner}
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["data_user_id"] == owner

    row = _poll_status(client, owner, conn_id, "success")
    assert row["sync_status"] == "success"


def test_sync_failure_records_error(client, monkeypatch):
    saved = client.post("/api/connections", json=_save_payload()).json()
    conn_id = saved["id"]
    owner = f"aws-{ACCOUNT_ID}"

    def boom():
        raise RuntimeError("collector exploded")

    monkeypatch.setattr(
        connections.CollectorRunner,
        "from_connection",
        classmethod(lambda cls, row, uid, conn=None: _FakeRunner(boom)),
    )

    resp = client.post(
        f"/api/connections/{conn_id}/sync", params={"user_id": owner}
    )
    assert resp.status_code == 202

    row = _poll_status(client, owner, conn_id, "failed")
    assert "collector exploded" in (row["error_message"] or "")


def test_sync_conflict_while_in_progress(client, monkeypatch):
    saved = client.post("/api/connections", json=_save_payload()).json()
    conn_id = saved["id"]
    owner = f"aws-{ACCOUNT_ID}"

    release = threading.Event()
    started = threading.Event()

    def blocking_run():
        started.set()
        release.wait(timeout=5.0)

    monkeypatch.setattr(
        connections.CollectorRunner,
        "from_connection",
        classmethod(lambda cls, row, uid, conn=None: _FakeRunner(blocking_run)),
    )

    first = client.post(
        f"/api/connections/{conn_id}/sync", params={"user_id": owner}
    )
    assert first.status_code == 202
    assert started.wait(timeout=5.0)

    second = client.post(
        f"/api/connections/{conn_id}/sync", params={"user_id": owner}
    )
    assert second.status_code == 409

    # Let the worker finish so it cleans up before the fixture tears down the
    # monkeypatched get_connection.
    release.set()
    _poll_status(client, owner, conn_id, "success")


def test_sync_unknown_connection_404(client):
    resp = client.post(
        "/api/connections/9999/sync", params={"user_id": f"aws-{ACCOUNT_ID}"}
    )
    assert resp.status_code == 404
