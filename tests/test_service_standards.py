"""Service standards: health split + JSON logging with redaction (Starter §Service standards)."""
from __future__ import annotations

import io
import json
import logging

import backend_api.main as main
from cloud_optimizer import config
from cloud_optimizer.logging_json import (
    JsonFormatter,
    get_trace_id,
    redact_obj,
    redact_str,
    set_trace_id,
)
from fastapi.testclient import TestClient


def test_health_is_cheap_liveness_no_db(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError("liveness must not touch dependencies")

    monkeypatch.setattr(main, "get_connection", _fail)
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "ok"


def test_ready_ok_with_db(monkeypatch, tmp_path):
    import sqlite3

    db_file = tmp_path / "ready.db"
    real_connect = sqlite3.connect

    def fake_get_connection(*a, **k):
        conn = real_connect(str(db_file))
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        return conn

    monkeypatch.setattr(main, "get_connection", fake_get_connection)
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["database"] == "ok"


def test_ready_fails_closed_503(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "get_connection", _boom)
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["checks"]["database"] == "fail"
    # No leak of internal error text to clients.
    assert "db down" not in json.dumps(body)


def test_traceparent_propagated(monkeypatch, tmp_path):
    import sqlite3

    trace_id = "0af7651916cd43dd8448eb211c80319c"
    traceparent = f"00-{trace_id}-b7ad6b7169203331-01"

    def fake_get_connection(*a, **k):
        conn = sqlite3.connect(":memory:")
        return conn

    monkeypatch.setattr(main, "get_connection", fake_get_connection)
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/ready", headers={"traceparent": traceparent})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == trace_id


def test_json_single_line_shape():
    set_trace_id("abc123")
    try:
        fmt = JsonFormatter(service="backend_api")
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__,
            lineno=1, msg="hello %s", args=("world",), exc_info=None,
        )
        line = fmt.format(record)
    finally:
        set_trace_id("")
    assert "\n" not in line
    payload = json.loads(line)  # must be single-line JSON
    assert set(["timestamp", "level", "service", "msg", "trace"]) <= set(payload)
    assert payload["level"] == "INFO"
    assert payload["service"] == "backend_api"
    assert payload["msg"] == "hello world"
    assert payload["trace"] == "abc123"
    assert "timestamp" in payload and payload["timestamp"].endswith("Z")


def test_redaction_secrets_and_pii():
    cases = [
        "password=supersecret123",
        '{"password": "supersecret123"}',
        "api_key=AKIAIOSFODNN7EXAMPLE extra",
        "AKIAIOSFODNN7EXAMPLE",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload",
        "Bearer mytoken123",
        "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "user mariam@example.com logged in",
        "-----BEGIN RSA PRIVATE KEY----- MIIE",
    ]
    for raw in cases:
        redacted = redact_str(raw)
        assert "supersecret123" not in redacted, raw
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted, raw
        assert "mariam@example.com" not in redacted, raw
        assert "wJalrXUtnFEMI" not in redacted, raw
        assert "[REDACTED]" in redacted, raw
    # Dict values with sensitive keys.
    obj = redact_obj({"password": "x", "nested": {"api_key": "y"}, "ok": "keep"})
    assert obj == {
        "password": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]"},
        "ok": "keep",
    }


def test_setup_logging_emits_json_stdout(capsys):
    config.setup_logging(level="INFO", service="svc-test")
    try:
        logger = logging.getLogger("svc-test-logger")
        logger.info("password=hunter2 hello user bob@example.com")
        out = capsys.readouterr().out
    finally:
        # Restore default-ish state for other tests; next setup_logging resets.
        pass
    assert out.strip(), "expected JSON log on stdout"
    for line in out.strip().splitlines():
        payload = json.loads(line)
        assert {"timestamp", "level", "service", "msg", "trace"} <= set(payload)
    joined = "\n".join(out.strip().splitlines())
    assert "hunter2" not in joined
    assert "bob@example.com" not in joined


def test_trace_falls_back_to_env(monkeypatch):
    set_trace_id("")
    monkeypatch.setenv("TRACE_ID", "env-trace-1")
    assert get_trace_id() == "env-trace-1"
    monkeypatch.delenv("TRACE_ID")
    assert get_trace_id() == "-"
