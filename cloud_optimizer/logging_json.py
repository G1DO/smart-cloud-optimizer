"""logging_json.py — single-line JSON formatter with redaction + trace.

Starter §Service standards Logging (substantive only): single-line JSON to
stdout with timestamp/level/service/msg/trace, secret/PII redaction tested,
no secrets in logs. Trace follows W3C traceparent where propagated, else
env correlation IDs.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
from datetime import datetime, timezone

REDACTED = "[REDACTED]"

# Context-local trace/span id set per-request by backend_api middleware.
_trace_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)


def set_trace_id(value: str) -> None:
    """Set the current request trace id (internal use by middleware/tests)."""
    _trace_ctx.set(value or "")


def get_trace_id() -> str:
    """Return W3C trace id if set, else env correlation id, else '-'."""
    current = _trace_ctx.get()
    if current:
        return current
    for env_key in ("TRACE_ID", "CORRELATION_ID", "REQUEST_ID"):
        val = os.getenv(env_key, "")
        if val:
            return val
    return "-"


# Keys whose values must never appear in logs (case-insensitive).
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "client_secret",
    "api_key",
    "apikey",
    "google_api_key",
    "openai_api_key",
    "access_token",
    "auth_token",
    "id_token",
    "refresh_token",
    "session_token",
    "aws_secret_access_key",
    "aws_access_key_id",
    "aws_session_token",
    "authorization",
    "x-api-token",
    "onboarding_api_token",
    "private_key",
    "email",
}

# key[=:]value  and  "key": "value" shapes (covers query strings, headers, JSON).
_KEY_ALT = (
    r"password|passwd|pwd|secret|client_secret|api[_-]?key|access[_-]?token|"
    r"auth[_-]?token|id[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"aws_secret_access_key|aws_session_token|aws_access_key_id|"
    r"authorization|x[_-]?api[_-]?token|onboarding_api_token|private_key"
)
_RE_KV = re.compile(
    rf"(?i)(({_KEY_ALT})\s*[:=]\s*)([\"']?)([^\s\"',;}}&]+)([\"']?)"
)
_RE_JSON_KV = re.compile(
    rf"(?i)(\"(?:{_KEY_ALT})\"\s*:\s*\")(.*?)(\")"
)
_RE_BEARER = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/=]+")
_RE_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_AWS_SECRET = re.compile(r"\b[A-Za-z0-9/+=]{40}\b")
_RE_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact_str(text: str) -> str:
    """Redact secrets/PII from a free-text log message."""
    if not isinstance(text, str):
        text = str(text)
    redacted = _RE_JSON_KV.sub(rf"\1{REDACTED}\3", text)
    redacted = _RE_KV.sub(rf"\1\3{REDACTED}\5", redacted)
    redacted = _RE_BEARER.sub(rf"\1{REDACTED}", redacted)
    redacted = _RE_AKIA.sub(REDACTED, redacted)
    redacted = _RE_PRIVATE_KEY.sub(REDACTED, redacted)
    # Only redact long base64-ish blobs when they appear next to a sensitive
    # key context is hard; keep the generic rule narrow: redact 40-char
    # AWS-secret-shaped tokens only if the message already mentions secrets.
    if re.search(rf"(?i)({_KEY_ALT})", redacted):
        redacted = _RE_AWS_SECRET.sub(REDACTED, redacted)
    redacted = _RE_EMAIL.sub(REDACTED, redacted)
    return redacted


def redact_obj(obj):
    """Recursively redact dict/list values with sensitive keys."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                out[k] = REDACTED
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact_str(obj)
    return obj


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter: timestamp/level/service/msg/trace."""

    def __init__(self, service: str = "api"):
        super().__init__()
        self.service = service or os.getenv("SERVICE_NAME", "api")

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        msg = redact_str(msg)
        payload: dict = {
            "timestamp": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", self.service),
            "msg": msg,
            "trace": get_trace_id(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            exc_text = self.formatException(record.exc_info)
            payload["error"] = redact_str(exc_text)
        # Redact any structured extras without breaking the required keys.
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload["extra"] = redact_obj(record.extra)
        return json.dumps(payload, ensure_ascii=False)
