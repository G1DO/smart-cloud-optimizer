from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from storage.db import (
    authenticate_user,
    register_user,
    get_connection,
    ensure_schema,
    ensure_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR.parent / "data" / "cloud_optimizer.db"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
_schema_ready = False

# Lightweight in-process throttle for auth endpoints (m7). Keyed by client IP,
# stores monotonic timestamps of recent failed attempts. Not distributed/durable —
# good enough to blunt brute-force/enumeration on a single-process backend.
_THROTTLE_MAX_ATTEMPTS = 10
_THROTTLE_WINDOW_SECONDS = 300
_failed_attempts: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_throttle(request: Optional[Request]) -> Optional[str]:
    """Raise 429 if the caller's IP has too many recent failures.

    Returns the client IP for follow-up bookkeeping, or None for the direct
    (non-HTTP) call path used by the contract tests, which is never throttled.
    """
    if request is None:
        return None
    ip = _client_ip(request)
    cutoff = time.monotonic() - _THROTTLE_WINDOW_SECONDS
    attempts = [t for t in _failed_attempts.get(ip, []) if t >= cutoff]
    _failed_attempts[ip] = attempts
    if len(attempts) >= _THROTTLE_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a few minutes and try again.",
        )
    return ip


def _record_failure(ip: Optional[str]) -> None:
    if ip is not None:
        _failed_attempts.setdefault(ip, []).append(time.monotonic())


def get_db_connection():
    global _schema_ready

    conn = get_connection(DB_PATH)
    if not _schema_ready:
        ensure_schema(conn)
        _schema_ready = True
    return conn


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class SignupRequest(BaseModel):
    display_name: str = ""
    email: str
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=1)


class LogoutResponse(BaseModel):
    success: bool
    message: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    profile_name: Optional[str] = None
    demo_mode: bool = False
    selected_user: Optional[str] = None


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request = None) -> AuthResponse:
    # `request` is injected by FastAPI on real HTTP calls and is None on the
    # direct calls made by the contract tests; only the HTTP path is throttled.
    client_ip = _enforce_throttle(request)

    email = payload.email.strip().lower()
    password = payload.password

    if not email or not password:
        raise HTTPException(status_code=400, detail="Please enter both email and password.")

    conn = get_db_connection()
    try:
        user = authenticate_user(conn, email, password)
    finally:
        conn.close()

    if user is None:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _failed_attempts.pop(client_ip, None)
    return AuthResponse(
        success=True,
        message="Login successful.",
        user_id=user["user_id"],
        email=user["email"],
        profile_name=user["profile_name"],
        demo_mode=False,
        selected_user=None,
    )


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, request: Request = None) -> AuthResponse:
    # See login(): None on the contract-test path, injected on HTTP calls.
    client_ip = _enforce_throttle(request)

    display_name = payload.display_name.strip()
    email = payload.email.strip().lower()
    password = payload.password
    confirm_password = payload.confirm_password

    if not display_name:
        raise HTTPException(status_code=400, detail="Display name is required.")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    if not PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least 8 characters and include an uppercase "
                "letter, a number, and a symbol."
            ),
        )

    conn = get_db_connection()
    try:
        try:
            user_id = register_user(conn, email, password, display_name)
        except ValueError as exc:
            # Soften register_user's message (e.g. "email already registered") to
            # avoid account enumeration — a generic 400 doesn't confirm whether the
            # address exists. Count it toward the throttle to slow scanning.
            _record_failure(client_ip)
            raise HTTPException(
                status_code=400,
                detail="Could not create account. Please check your details and try again.",
            ) from exc
    finally:
        conn.close()

    return AuthResponse(
        success=True,
        message="Account created successfully.",
        user_id=user_id,
        email=email,
        profile_name=display_name or email.split("@")[0],
        demo_mode=False,
        selected_user=None,
    )


@router.post("/demo", response_model=AuthResponse)
def enter_demo_mode() -> AuthResponse:
    conn = get_db_connection()
    try:
        ensure_user(conn, "SYNTHETIC-001")
    finally:
        conn.close()

    return AuthResponse(
        success=True,
        message="Demo mode activated.",
        user_id="aws-SYNTHETIC-001",
        email="SYNTHETIC-001@aws.local",
        profile_name="AWS Account SYNTHETIC-001",
        demo_mode=True,
        selected_user="aws-SYNTHETIC-001",
    )


@router.post("/logout", response_model=LogoutResponse)
def logout() -> LogoutResponse:
    return LogoutResponse(
        success=True,
        message="Logged out successfully.",
    )
