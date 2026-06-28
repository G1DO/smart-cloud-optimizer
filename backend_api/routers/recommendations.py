from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from storage.db import get_connection, ensure_schema
from optimizer.engine import optimize


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

Priority = Literal["high", "medium", "low"]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_priority(value: Any) -> Priority:
    """
    Match the Streamlit behavior exactly:
    - if priority exists in data, use it if valid
    - otherwise default to 'medium'
    """
    raw = _to_str(value, "medium").strip().lower()
    if raw not in {"high", "medium", "low"}:
        return "medium"
    return raw  # type: ignore[return-value]


def _normalize_confidence(value: Any) -> str:
    raw = _to_str(value, "medium").strip().lower()
    return raw or "medium"


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row

    try:
        return dict(row)
    except Exception:
        pass

    try:
        keys = row.keys()
        return {key: row[key] for key in keys}
    except Exception:
        return {}


def _normalize_service(value: Any) -> str:
    raw = _to_str(value, "unknown").strip().lower()
    return raw or "unknown"


def _normalize_rec_type(value: Any) -> str:
    raw = _to_str(value, "optimization").strip().lower()
    return raw or "optimization"


def _normalize_recommendation_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    service = _normalize_service(row.get("service"))
    recommendation_type = _normalize_rec_type(row.get("recommendation_type"))
    resource_id = _to_str(
        row.get("resource_id"),
        f"resource-{index}",
    ).strip() or f"resource-{index}"

    monthly_savings = round(_to_float(row.get("monthly_savings")), 2)
    current_monthly_cost = round(_to_float(row.get("current_monthly_cost")), 2)
    estimated_monthly_cost = round(_to_float(row.get("estimated_monthly_cost")), 2)

    savings_percent_raw = row.get("savings_percent")
    if savings_percent_raw is None or savings_percent_raw == "":
        if current_monthly_cost > 0:
            savings_percent = round((monthly_savings / current_monthly_cost) * 100, 1)
        else:
            savings_percent = 0.0
    else:
        savings_percent = round(_to_float(savings_percent_raw), 1)

    row_id = row.get("id")
    if row_id is None:
        row_id = row.get("rowid")

    return {
        "id": _to_str(row_id, f"{resource_id}:{recommendation_type}:{index}"),
        "service": service,
        "recommendation_type": recommendation_type,
        "resource_id": resource_id,
        "monthly_savings": monthly_savings,
        "priority": _normalize_priority(row.get("priority")),
        "confidence": _normalize_confidence(row.get("confidence")),
        "current_config": _to_str(row.get("current_config"), "N/A"),
        "recommended_config": _to_str(row.get("recommended_config"), "N/A"),
        "current_monthly_cost": current_monthly_cost,
        "estimated_monthly_cost": estimated_monthly_cost,
        "savings_percent": savings_percent,
        "reasoning": _to_str(row.get("reasoning"), ""),
    }


def _read_existing_recommendations(
    conn,
    user_id: str,
    service: str | None = None,
) -> list[dict[str, Any]]:
    if service:
        sql = """
            SELECT rowid, *
            FROM recommendations
            WHERE user_id = ? AND LOWER(service) = LOWER(?)
        """
        rows = conn.execute(sql, (user_id, service)).fetchall()
    else:
        sql = """
            SELECT rowid, *
            FROM recommendations
            WHERE user_id = ?
        """
        rows = conn.execute(sql, (user_id,)).fetchall()

    return [_row_to_dict(row) for row in rows]


@router.get("")
def get_recommendations(
    user_id: str = Query(..., description="User ID, e.g. aws-SYNTHETIC-001"),
    service: str | None = Query(None, description="Optional service filter"),
    generate_if_empty: bool = Query(
        True,
        description="Generate optimizer recommendations if none exist yet",
    ),
):
    conn = None

    try:
        conn = get_connection()
        ensure_schema(conn)

        rows = _read_existing_recommendations(conn, user_id, service=service)

        if not rows and generate_if_empty:
            optimize(conn, user_id)
            rows = _read_existing_recommendations(conn, user_id, service=service)

        normalized = [
            _normalize_recommendation_row(row, idx)
            for idx, row in enumerate(rows, start=1)
        ]

        normalized.sort(
            key=lambda r: (
                -float(r["monthly_savings"]),
                str(r["service"]),
                str(r["resource_id"]),
            )
        )

        total_recommendations = len(normalized)
        potential_monthly_savings = round(
            sum(_to_float(r["monthly_savings"]) for r in normalized),
            2,
        )
        avg_savings_per_rec = round(
            potential_monthly_savings / total_recommendations,
            2,
        ) if total_recommendations > 0 else 0.0
        high_priority_count = sum(
            1 for r in normalized if r["priority"] == "high"
        )

        return {
            "user_id": user_id,
            "summary": {
                "total_recommendations": total_recommendations,
                "potential_monthly_savings": potential_monthly_savings,
                "avg_savings_per_rec": avg_savings_per_rec,
                "high_priority_count": high_priority_count,
            },
            "recommendations": normalized,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if conn is not None:
            conn.close()


@router.post("/generate")
def generate_recommendations(user_id: str = Query(...)):
    conn = None

    try:
        conn = get_connection()
        ensure_schema(conn)

        generated = optimize(conn, user_id)

        return {
            "message": "Recommendations generated successfully",
            "count": len(generated),
            "user_id": user_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {exc}",
        )
    finally:
        if conn is not None:
            conn.close()