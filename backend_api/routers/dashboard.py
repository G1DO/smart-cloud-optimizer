from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from storage.db import (
    get_connection,
    ensure_schema,
    get_daily_costs,
    get_service_costs,
    get_recommendations,
    get_anomalies,
)


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _last_n_days_range(rows: list[dict], days: int = 30) -> tuple[str, str, list[dict]]:
    if not rows:
        raise HTTPException(status_code=404, detail="No daily cost data found for this user")

    end_date = _parse_date(rows[-1]["date"])
    start_date = end_date - timedelta(days=days - 1)

    filtered = [r for r in rows if _parse_date(r["date"]) >= start_date]
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), filtered


def _priority_from_savings(savings: float) -> str:
    if savings >= 100:
        return "High"
    if savings >= 30:
        return "Medium"
    return "Low"


def _risk_from_confidence(confidence: str) -> str:
    confidence = (confidence or "").lower()
    if confidence == "high":
        return "Low"
    if confidence == "low":
        return "High"
    return "Medium"


def _severity_label(value: str) -> str:
    value = (value or "").lower()
    if value == "critical":
        return "High"
    if value == "warning":
        return "Medium"
    return "Low"


@router.get("/home")
def get_dashboard_home(user_id: str = Query(...)):
    conn = get_connection()
    try:
        ensure_schema(conn)

        daily_rows = get_daily_costs(conn, user_id)
        start_date, end_date, daily_30 = _last_n_days_range(daily_rows, 30)

        total_cost = round(sum(float(r["total_cost"]) for r in daily_30), 2)

        recommendations = get_recommendations(conn, user_id)
        potential_savings = round(
            sum(float(r.get("monthly_savings") or 0) for r in recommendations),
            2,
        )

        anomalies = get_anomalies(conn, user_id)
        anomaly_dates = {a["anomaly_date"] for a in anomalies if start_date <= a["anomaly_date"] <= end_date}

        service_rows = get_service_costs(conn, user_id, start_date=start_date, end_date=end_date)
        service_totals: dict[str, float] = {}
        for row in service_rows:
            service = row["service"]
            service_totals[service] = service_totals.get(service, 0.0) + float(row["daily_cost"])

        top_services = [
            {
                "service": service,
                "total_cost": round(cost, 2),
            }
            for service, cost in sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        top_recommendations = []
        for rec in recommendations[:3]:
            monthly_savings = float(rec.get("monthly_savings") or 0)
            title = rec.get("recommendation_type", "Recommendation").replace("_", " ").title()
            top_recommendations.append(
                {
                    "id": str(rec["id"]),
                    "title": title,
                    "service": rec.get("service", ""),
                    "description": rec.get("reasoning") or f"Apply {title.lower()} to reduce spend.",
                    "savings": round(monthly_savings, 2),
                    "priority": _priority_from_savings(monthly_savings),
                    "risk": _risk_from_confidence(rec.get("confidence", "medium")),
                }
            )

        recent_anomalies = []
        anomalies_sorted = sorted(
            [a for a in anomalies if start_date <= a["anomaly_date"] <= end_date],
            key=lambda x: x["anomaly_date"],
            reverse=True,
        )[:5]

        for item in anomalies_sorted:
            recent_anomalies.append(
                {
                    "id": str(item["id"]),
                    "date": item["anomaly_date"],
                    "service": item.get("service") or "All Services",
                    "actual_cost": round(float(item.get("actual_cost") or 0), 2),
                    "expected_cost": round(float(item.get("expected_cost") or 0), 2),
                    "severity": _severity_label(item.get("severity")),
                    "description": item.get("description") or "Unexpected cost deviation detected.",
                }
            )

        return {
            "summary": {
                "total_cost": total_cost,
                "potential_savings": potential_savings,
                "recommendations_count": len(recommendations),
                "anomalies_count": len(anomaly_dates),
                "start_date": start_date,
                "end_date": end_date,
                "days_count": len(daily_30),
            },
            "daily_costs": [
                {
                    "date": row["date"],
                    "total_cost": round(float(row["total_cost"]), 2),
                }
                for row in daily_30
            ],
            "top_services": top_services,
            "top_recommendations": top_recommendations,
            "recent_anomalies": recent_anomalies,
        }
    finally:
        conn.close()