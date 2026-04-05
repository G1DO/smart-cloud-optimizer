from __future__ import annotations

from pathlib import Path
import hashlib
import sqlite3
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ml_engine.anomaly import flag_anomalies
from ml_engine.forecaster import build_forecaster

router = APIRouter(prefix="/api", tags=["forecast"])

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR.parent / "data" / "cloud_optimizer.db"

_FORECAST_CACHE: dict[tuple, dict[str, Any]] = {}
_COMPARISON_CACHE: dict[tuple, dict[str, Any]] = {}


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_historical_costs(user_id: str, days: int = 365) -> pd.DataFrame:
    query = """
        SELECT date, total_cost
        FROM daily_costs
        WHERE user_id = ?
        ORDER BY date ASC
    """

    with _get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=[user_id])

    if df.empty:
        return pd.DataFrame(columns=["date", "total_cost"])

    df["date"] = pd.to_datetime(df["date"])
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0.0)
    df = df.sort_values("date").dropna(subset=["date"]).reset_index(drop=True)

    if len(df) > days:
        df = df.tail(days).reset_index(drop=True)

    return df


def _normalize_historical(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    data["total_cost"] = pd.to_numeric(data["total_cost"], errors="coerce").fillna(0.0)
    return data.reset_index(drop=True)


def _apply_anomaly_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    flagged = flag_anomalies(
        df.copy(),
        value_col="total_cost",
        methods=["zscore", "iqr"],
        zscore_window=30,
        zscore_threshold=3.0,
        iqr_multiplier=1.5,
    )

    if "is_anomaly" not in flagged.columns:
        return df.copy()

    cleaned = flagged.loc[~flagged["is_anomaly"]].copy()

    # fallback: never return unusably small training set
    if len(cleaned) < 30:
        return df.copy()

    return cleaned.reset_index(drop=True)


def _series_fingerprint(df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"

    payload = (
        df["date"].astype(str).str.cat(sep="|")
        + "||"
        + df["total_cost"].round(6).astype(str).str.cat(sep="|")
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _serialize_historical(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")

    return [
        {
            "date": row["date"],
            "total_cost": float(row["total_cost"]),
        }
        for _, row in out.iterrows()
    ]


def _serialize_forecast(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")

    return [
        {
            "date": row["date"],
            "forecast": float(row["forecast"]),
            "lower": float(row["lower"]),
            "upper": float(row["upper"]),
        }
        for _, row in out.iterrows()
    ]


def _build_summary(
    model_name: str,
    horizon: int,
    historical_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> dict[str, Any]:
    historical_avg = float(historical_df["total_cost"].mean()) if not historical_df.empty else 0.0
    avg_predicted = float(forecast_df["forecast"].mean()) if not forecast_df.empty else 0.0
    total_predicted = float(forecast_df["forecast"].sum()) if not forecast_df.empty else 0.0
    min_predicted = float(forecast_df["forecast"].min()) if not forecast_df.empty else 0.0
    max_predicted = float(forecast_df["forecast"].max()) if not forecast_df.empty else 0.0

    vs_historical_pct = None
    if historical_avg != 0:
        vs_historical_pct = ((avg_predicted - historical_avg) / historical_avg) * 100.0

    return {
        "model": model_name,
        "horizon": horizon,
        "historical_days": int(len(historical_df)),
        "predicted_total": total_predicted,
        "avg_daily_forecast": avg_predicted,
        "min_forecast": min_predicted,
        "max_forecast": max_predicted,
        "historical_avg_daily": historical_avg,
        "vs_historical_pct": vs_historical_pct,
    }


def _run_single_model(
    model_name: str,
    train_df: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    model = build_forecaster(model_name)
    model.fit(train_df)
    pred = model.predict(horizon=horizon)

    pred = pred.copy()
    pred["date"] = pd.to_datetime(pred["date"])
    pred["forecast"] = pd.to_numeric(pred["forecast"], errors="coerce")
    pred["lower"] = pd.to_numeric(pred["lower"], errors="coerce")
    pred["upper"] = pd.to_numeric(pred["upper"], errors="coerce")
    pred = pred.dropna(subset=["date", "forecast", "lower", "upper"]).reset_index(drop=True)

    return pred


@router.get("/forecast")
def get_forecast(
    user_id: str = Query(..., description="AWS user/account id"),
    model: str = Query("Prophet", description="Forecast model"),
    horizon: int = Query(30, ge=1, le=90, description="Days to forecast"),
):
    model_name = model.strip()

    try:
        historical_df = _normalize_historical(_load_historical_costs(user_id=user_id, days=365))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load historical cost data: {exc}")

    if historical_df.empty:
        raise HTTPException(status_code=404, detail="No historical cost data found.")

    if len(historical_df) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical data for forecasting. Need at least 30 days, found {len(historical_df)}.",
        )

    train_df = _apply_anomaly_filter(historical_df[["date", "total_cost"]].copy())
    fingerprint = _series_fingerprint(train_df)

    cache_key = (user_id, model_name, horizon, fingerprint)
    cached = _FORECAST_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        forecast_df = _run_single_model(model_name=model_name, train_df=train_df, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate forecast with {model_name}: {exc}",
        )

    payload = {
        "summary": _build_summary(
            model_name=model_name,
            horizon=horizon,
            historical_df=historical_df,
            forecast_df=forecast_df,
        ),
        "historical": _serialize_historical(historical_df),
        "forecast": _serialize_forecast(forecast_df),
    }

    _FORECAST_CACHE[cache_key] = payload
    return payload


@router.get("/forecast/compare")
def compare_forecast_models(
    user_id: str = Query(..., description="AWS user/account id"),
    horizon: int = Query(30, ge=1, le=90, description="Days to forecast"),
):
    try:
        historical_df = _normalize_historical(_load_historical_costs(user_id=user_id, days=365))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load historical cost data: {exc}")

    if historical_df.empty:
        raise HTTPException(status_code=404, detail="No historical cost data found.")

    if len(historical_df) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical data for comparison. Need at least 30 days, found {len(historical_df)}.",
        )

    train_df = _apply_anomaly_filter(historical_df[["date", "total_cost"]].copy())
    fingerprint = _series_fingerprint(train_df)

    cache_key = (user_id, horizon, fingerprint)
    cached = _COMPARISON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    models = ["Prophet", "SARIMAX", "ETS", "Seasonal Naive", "Naive"]
    historical_avg = float(historical_df["total_cost"].mean()) if not historical_df.empty else 0.0

    rows: list[dict[str, Any]] = []

    for model_name in models:
        try:
            pred = _run_single_model(model_name=model_name, train_df=train_df, horizon=horizon)

            avg_pred = float(pred["forecast"].mean()) if not pred.empty else None
            total_pred = float(pred["forecast"].sum()) if not pred.empty else None

            vs_historical_pct = None
            if avg_pred is not None and historical_avg != 0:
                vs_historical_pct = ((avg_pred - historical_avg) / historical_avg) * 100.0

            rows.append(
                {
                    "model": model_name,
                    "avg_daily_forecast": avg_pred,
                    "total_forecast": total_pred,
                    "historical_avg_daily": historical_avg,
                    "vs_historical_pct": vs_historical_pct,
                }
            )
        except Exception:
            rows.append(
                {
                    "model": model_name,
                    "avg_daily_forecast": None,
                    "total_forecast": None,
                    "historical_avg_daily": historical_avg if historical_avg != 0 else None,
                    "vs_historical_pct": None,
                }
            )

    payload = {"comparison": rows}
    _COMPARISON_CACHE[cache_key] = payload
    return payload