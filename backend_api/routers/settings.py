from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from storage.db import get_connection, ensure_schema, get_aws_connections


router = APIRouter(prefix="/api/settings", tags=["settings"])

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = BASE_DIR / "runtime_settings.json"


RiskTolerance = Literal["Conservative", "Moderate", "Aggressive"]
ForecastModel = Literal["Prophet", "SARIMAX", "ETS", "Seasonal Naive", "Naive"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class RuntimeSettings(BaseModel):
    forecast_horizon_days: int = Field(default=30, ge=7, le=180)
    seasonality_period_days: int = Field(default=7, ge=1, le=30)
    minimum_training_days: int = Field(default=30, ge=14, le=365)
    confidence_interval: float = Field(default=0.80, ge=0.5, le=0.99)

    monthly_budget_cap: float = Field(default=5000.0, ge=0, le=100000)
    minimum_recommendation_savings: float = Field(default=5.0, ge=0, le=1000)
    risk_tolerance: RiskTolerance = "Moderate"
    allow_spot_recommendations: bool = False

    default_forecasting_model: ForecastModel = "Prophet"
    enable_ensemble_forecasting: bool = False

    collection_interval_hours: int = Field(default=24, ge=1, le=168)
    retention_period_days: int = Field(default=365, ge=30, le=730)
    api_timeout_seconds: int = Field(default=30, ge=10, le=300)
    max_api_retries: int = Field(default=3, ge=1, le=10)
    log_level: LogLevel = "INFO"


class SettingsResponse(BaseModel):
    user_id: str
    editable: bool
    reason: str
    settings: RuntimeSettings


def _is_demo_user(user_id: str) -> bool:
    return user_id == "aws-SYNTHETIC-001" or "SYNTHETIC" in user_id.upper()


def _load_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}

    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_all_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _has_connected_aws_account(user_id: str) -> bool:
    conn = get_connection()
    try:
        ensure_schema(conn)
        connections = get_aws_connections(conn, user_id)

        return any(
            str(item.get("sync_status", "")).lower() in {"success", "never", "in_progress"}
            or int(item.get("access_verified") or 0) == 1
            for item in connections
        )
    finally:
        conn.close()


def _editable_status(user_id: str) -> tuple[bool, str]:
    if _is_demo_user(user_id):
        return False, "Demo mode uses locked synthetic settings."

    if not _has_connected_aws_account(user_id):
        return False, "Connect an AWS account first to customize runtime settings."

    return True, "Settings are editable for this connected AWS workspace."


@router.get("", response_model=SettingsResponse)
def get_settings(user_id: str = Query(...)):
    all_settings = _load_all_settings()
    raw_settings = all_settings.get(user_id, {})

    settings = RuntimeSettings(**raw_settings)
    editable, reason = _editable_status(user_id)

    return SettingsResponse(
        user_id=user_id,
        editable=editable,
        reason=reason,
        settings=settings,
    )


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: RuntimeSettings,
    user_id: str = Query(...),
):
    editable, reason = _editable_status(user_id)

    if not editable:
        raise HTTPException(status_code=403, detail=reason)

    all_settings = _load_all_settings()
    all_settings[user_id] = payload.model_dump()
    _save_all_settings(all_settings)

    return SettingsResponse(
        user_id=user_id,
        editable=True,
        reason="Settings saved successfully.",
        settings=payload,
    )


@router.post("/reset", response_model=SettingsResponse)
def reset_settings(user_id: str = Query(...)):
    editable, reason = _editable_status(user_id)

    if not editable:
        raise HTTPException(status_code=403, detail=reason)

    all_settings = _load_all_settings()
    all_settings[user_id] = RuntimeSettings().model_dump()
    _save_all_settings(all_settings)

    return SettingsResponse(
        user_id=user_id,
        editable=True,
        reason="Settings reset to defaults.",
        settings=RuntimeSettings(),
    )