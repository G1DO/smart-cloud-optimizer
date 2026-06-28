"""React-facing backend contract tests.

These tests exercise the backend functions behind the API endpoints consumed by
the Next.js frontend. They run against a temporary SQLite database, so they
never modify local demo data.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from backend_api.routers import auth, costs, dashboard, forecast, recommendations, settings
from storage import db as storage_db


@pytest.fixture
def test_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "contract.db"
    settings_path = tmp_path / "runtime_settings.json"

    def connect_to_test_db():
        conn = storage_db.get_connection(db_path)
        storage_db.ensure_schema(conn)
        return conn

    with connect_to_test_db() as conn:
        storage_db.ensure_schema(conn)

    monkeypatch.setattr(auth, "DB_PATH", db_path)
    monkeypatch.setattr(auth, "_schema_ready", False)
    monkeypatch.setattr(dashboard, "get_connection", connect_to_test_db)
    monkeypatch.setattr(costs, "get_connection", connect_to_test_db)
    monkeypatch.setattr(recommendations, "get_connection", connect_to_test_db)
    monkeypatch.setattr(settings, "get_connection", connect_to_test_db)
    monkeypatch.setattr(settings, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(forecast, "DB_PATH", db_path)
    forecast._FORECAST_CACHE.clear()
    forecast._COMPARISON_CACHE.clear()

    return db_path


def _seed_cost_workspace(db_path, user_id: str) -> None:
    start = date(2026, 1, 1)
    daily_rows = []
    service_rows = []

    for index in range(45):
        day = start + timedelta(days=index)
        daily_total = 80 + index
        daily_rows.append({"date": day.isoformat(), "total_cost": daily_total})
        service_rows.extend(
            [
                {"date": day.isoformat(), "service": "EC2", "daily_cost": daily_total * 0.55},
                {"date": day.isoformat(), "service": "RDS", "daily_cost": daily_total * 0.30},
                {"date": day.isoformat(), "service": "S3", "daily_cost": daily_total * 0.15},
            ]
        )

    with storage_db.get_connection(db_path) as conn:
        storage_db.ensure_schema(conn)
        storage_db.ensure_user(conn, user_id.replace("aws-", ""))
        storage_db.insert_daily_costs(conn, user_id, daily_rows)
        storage_db.insert_service_costs(conn, user_id, service_rows)
        storage_db.insert_recommendations(
            conn,
            user_id,
            [
                {
                    "service": "ec2",
                    "resource_id": "i-contract-001",
                    "recommendation_type": "rightsize",
                    "current_config": "m5.large",
                    "recommended_config": "t3.medium",
                    "current_monthly_cost": 220.0,
                    "estimated_monthly_cost": 120.0,
                    "monthly_savings": 100.0,
                    "savings_percent": 45.5,
                    "confidence": "high",
                    "reasoning": "CPU usage is consistently below target.",
                }
            ],
        )
        storage_db.insert_anomalies(
            conn,
            user_id,
            [
                {
                    "service": "EC2",
                    "anomaly_date": (start + timedelta(days=40)).isoformat(),
                    "expected_cost": 100.0,
                    "actual_cost": 145.0,
                    "deviation_percent": 45.0,
                    "severity": "warning",
                    "description": "Unexpected EC2 spend increase.",
                }
            ],
        )


def test_auth_contract_matches_login_signup_demo_flow(test_db_path):
    with pytest.raises(HTTPException) as weak_signup:
        auth.signup(
            auth.SignupRequest(
                display_name="Mariam",
                email="mariam@example.com",
                password="weakpass",
                confirm_password="weakpass",
            )
        )
    assert weak_signup.value.status_code == 400
    assert "uppercase" in weak_signup.value.detail.lower()

    signup = auth.signup(
        auth.SignupRequest(
            display_name="Mariam Emad",
            email="mariam@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
        )
    )
    assert signup.success is True
    assert signup.demo_mode is False
    assert signup.email == "mariam@example.com"
    assert signup.profile_name == "Mariam Emad"
    assert signup.user_id.startswith("usr-")

    login = auth.login(
        auth.LoginRequest(email="mariam@example.com", password="StrongPass1!")
    )
    assert login.success is True
    assert login.user_id == signup.user_id
    assert login.demo_mode is False

    demo = auth.enter_demo_mode()
    assert demo.success is True
    assert demo.demo_mode is True
    assert demo.selected_user == "aws-SYNTHETIC-001"


def test_dashboard_pages_return_empty_contract_for_real_user_without_aws(test_db_path):
    signup = auth.signup(
        auth.SignupRequest(
            display_name="Empty User",
            email="empty@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
        )
    )
    user_id = signup.user_id

    with pytest.raises(HTTPException) as home_error:
        dashboard.get_dashboard_home(user_id=user_id)
    assert home_error.value.status_code == 404

    with pytest.raises(HTTPException) as costs_error:
        costs.get_costs(user_id=user_id)
    assert costs_error.value.status_code == 404

    with pytest.raises(HTTPException) as forecast_error:
        forecast.get_forecast(user_id=user_id, model="Naive", horizon=7)
    assert forecast_error.value.status_code == 404

    recs = recommendations.get_recommendations(
        user_id=user_id,
        service=None,
        generate_if_empty=False,
    )
    assert recs["summary"]["total_recommendations"] == 0
    assert recs["recommendations"] == []

    runtime_settings = settings.get_settings(user_id=user_id)
    assert runtime_settings.editable is False
    assert "Connect an AWS account first" in runtime_settings.reason


def test_frontend_dashboard_contract_with_seeded_workspace(test_db_path):
    user_id = "aws-CONTRACT-001"
    _seed_cost_workspace(test_db_path, user_id)

    home = dashboard.get_dashboard_home(user_id=user_id)
    assert home["summary"]["days_count"] == 30
    assert home["summary"]["recommendations_count"] == 1
    assert len(home["daily_costs"]) == 30
    assert home["top_services"][0]["service"] == "EC2"
    assert home["top_recommendations"][0]["priority"] == "High"

    costs_payload = costs.get_costs(user_id=user_id, preset="Last 30 Days")
    assert costs_payload["date_range"]["days_count"] == 30
    assert costs_payload["summary"]["total_cost"] > 0
    assert {item["service"] for item in costs_payload["service_breakdown"]} == {"EC2", "RDS", "S3"}

    forecast_payload = forecast.get_forecast(user_id=user_id, model="Naive", horizon=7)
    assert forecast_payload["summary"]["model"] == "Naive"
    assert forecast_payload["summary"]["horizon"] == 7
    assert len(forecast_payload["forecast"]) == 7

    recs = recommendations.get_recommendations(
        user_id=user_id,
        service=None,
        generate_if_empty=True,
    )
    assert recs["summary"]["total_recommendations"] == 1
    assert recs["summary"]["potential_monthly_savings"] == 100.0
    assert recs["recommendations"][0]["service"] == "ec2"
