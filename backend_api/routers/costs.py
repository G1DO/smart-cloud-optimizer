from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from storage.db import (
    get_connection,
    ensure_schema,
    get_daily_costs,
    get_service_costs,
)


router = APIRouter(prefix="/api/costs", tags=["costs"])


PRESET_TO_DAYS = {
    "Last 7 Days": 7,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
    "Last 6 Months": 183,
    "Last Year": 365,
}


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _resolve_range(
    all_daily_rows: list[dict],
    preset: str,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, str, str]:
    if not all_daily_rows:
        raise HTTPException(status_code=404, detail="No cost data found for this user")

    available_start = all_daily_rows[0]["date"]
    available_end = all_daily_rows[-1]["date"]

    if preset == "Custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required for Custom preset",
            )
        return start_date, end_date, f"{start_date} to {end_date}"

    if preset == "All Time":
        return available_start, available_end, f"{available_start} to {available_end}"

    days = PRESET_TO_DAYS.get(preset, 30)
    end_dt = _parse_date(available_end)
    start_dt = end_dt - timedelta(days=days - 1)
    resolved_start = max(_parse_date(available_start), start_dt).strftime("%Y-%m-%d")
    return resolved_start, available_end, f"{resolved_start} to {available_end}"


@router.get("")
def get_costs(
    user_id: str = Query(...),
    preset: str = Query("Last 30 Days"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    conn = get_connection()
    try:
        ensure_schema(conn)

        all_daily_rows = get_daily_costs(conn, user_id)
        if not all_daily_rows:
            raise HTTPException(status_code=404, detail="No cost data found for this user")

        available_range = {
            "start_date": all_daily_rows[0]["date"],
            "end_date": all_daily_rows[-1]["date"],
        }

        resolved_start, resolved_end, label = _resolve_range(
            all_daily_rows,
            preset,
            start_date,
            end_date,
        )

        daily_rows = get_daily_costs(
            conn,
            user_id=user_id,
            start_date=resolved_start,
            end_date=resolved_end,
        )
        if not daily_rows:
            raise HTTPException(status_code=404, detail="No cost data found for the selected range")

        daily_values = [float(r["total_cost"]) for r in daily_rows]
        total_cost = round(sum(daily_values), 2)
        avg_daily = round(total_cost / len(daily_rows), 2) if daily_rows else 0.0
        min_daily = round(min(daily_values), 2) if daily_values else 0.0
        max_daily = round(max(daily_values), 2) if daily_values else 0.0

        previous_end_dt = _parse_date(resolved_start) - timedelta(days=1)
        previous_start_dt = previous_end_dt - timedelta(days=len(daily_rows) - 1)
        previous_rows = get_daily_costs(
            conn,
            user_id=user_id,
            start_date=previous_start_dt.strftime("%Y-%m-%d"),
            end_date=previous_end_dt.strftime("%Y-%m-%d"),
        )
        previous_total = round(sum(float(r["total_cost"]) for r in previous_rows), 2)
        change_pct = None
        if previous_total > 0:
            change_pct = round(((total_cost - previous_total) / previous_total) * 100, 1)

        service_rows = get_service_costs(
            conn,
            user_id=user_id,
            start_date=resolved_start,
            end_date=resolved_end,
        )

        service_totals: dict[str, float] = {}
        for row in service_rows:
            service = row["service"]
            service_totals[service] = service_totals.get(service, 0.0) + float(row["daily_cost"])

        service_breakdown = []
        for service, cost in sorted(service_totals.items(), key=lambda x: x[1], reverse=True):
            percent = round((cost / total_cost) * 100, 2) if total_cost > 0 else 0.0
            service_breakdown.append(
                {
                    "service": service,
                    "total_cost": round(cost, 2),
                    "percent": percent,
                }
            )

        return {
            "user_id": user_id,
            "date_range": {
                "preset": preset,
                "start_date": resolved_start,
                "end_date": resolved_end,
                "days_count": len(daily_rows),
                "label": label,
            },
            "available_range": available_range,
            "summary": {
                "total_cost": total_cost,
                "avg_daily": avg_daily,
                "min_daily": min_daily,
                "max_daily": max_daily,
                "change_pct": change_pct,
            },
            "daily_costs": [
                {
                    "date": row["date"],
                    "total_cost": round(float(row["total_cost"]), 2),
                }
                for row in daily_rows
            ],
            "service_breakdown": service_breakdown,
            "service_timeline": [
                {
                    "date": row["date"],
                    "service": row["service"],
                    "daily_cost": round(float(row["daily_cost"]), 2),
                }
                for row in service_rows
            ],
            "daily_records": [
                {
                    "date": row["date"],
                    "total_cost": round(float(row["total_cost"]), 2),
                }
                for row in daily_rows
            ],
        }
    finally:
        conn.close()