from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
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
def login(payload: LoginRequest) -> AuthResponse:
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
        raise HTTPException(status_code=401, detail="Invalid email or password.")

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
def signup(payload: SignupRequest) -> AuthResponse:
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
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
