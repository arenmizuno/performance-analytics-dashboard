from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import store

router = APIRouter(prefix="/metrics", tags=["metrics"])

SUPPORTED = ["weight_lb", "steps", "sleep_minutes", "readiness"]


@router.get("/active-zone-minutes")
def active_zone_minutes(days: int = Query(default=7)):
    """
    Fitbit-style Active Zone Minutes: moderate-zone minutes count once, vigorous
    and peak count double. Computed across every source row (including rows the
    deduper marked duplicate), because only the wearable reports heart-rate zones.
    """
    end = date.today()
    start = end - timedelta(days=days - 1)

    rows = store.get_activities(
        start_date=start.isoformat(), end_date=end.isoformat(), include_duplicates=True
    )

    by_date = {}
    for a in rows:
        if a.active_zone_minutes:
            by_date[a.date] = by_date.get(a.date, 0) + a.active_zone_minutes

    total = round(sum(by_date.values()), 1)
    goal = store.get_settings()["weekly_azm_goal"]

    return {
        "metric": "active_zone_minutes",
        "total": total,
        "goal": goal,
        "percent": round(total / goal * 100) if goal else None,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "points": [{"date": d, "value": round(v, 1)} for d, v in sorted(by_date.items())],
    }


@router.get("/consistency")
def consistency(days: int = Query(default=112)):
    """One cell per day: how much training happened, for the consistency strip."""
    end = date.today()
    start = end - timedelta(days=days - 1)

    rows = store.get_activities(start_date=start.isoformat(), end_date=end.isoformat())

    by_date = {}
    for a in rows:
        entry = by_date.setdefault(a.date, {"minutes": 0.0, "count": 0, "types": set()})
        entry["minutes"] += a.duration_minutes or 0
        entry["count"] += 1
        entry["types"].add(a.activity_type)

    points = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        entry = by_date.get(iso)
        points.append({
            "date": iso,
            "minutes": round(entry["minutes"], 1) if entry else 0.0,
            "count": entry["count"] if entry else 0,
            "types": sorted(entry["types"]) if entry else [],
        })
        cursor += timedelta(days=1)

    active = [p for p in points if p["count"]]

    # Current streak of consecutive active days, counted back from today.
    streak = 0
    for p in reversed(points):
        if p["count"]:
            streak += 1
        elif p["date"] != end.isoformat():
            break

    return {
        "days": days,
        "active_days": len(active),
        "rate": round(len(active) / len(points) * 100) if points else 0,
        "streak": streak,
        "points": points,
    }


@router.get("/range")
def data_range():
    """Earliest and latest dates on record, so the UI can offer an All view."""
    rows = store.get_activities()
    dates = [a.date for a in rows if a.date]
    return {
        "start_date": min(dates) if dates else None,
        "end_date": max(dates) if dates else None,
        "activities": len(rows),
    }


@router.get("/summary")
def summary():
    """Latest value per metric, for the dashboard tiles."""
    out = {}

    for metric in SUPPORTED:
        points = store.get_daily_metrics(metric)
        if not points:
            out[metric] = None
            continue

        latest = points[-1]
        previous = points[-2] if len(points) > 1 else None

        out[metric] = {
            "date": latest["date"],
            "value": latest["value"],
            "source": latest["source"],
            "extra": latest["extra"],
            "change": round(latest["value"] - previous["value"], 1) if previous else None,
            "days_recorded": len(points),
        }

    return {"metrics": out}


@router.get("/{metric}")
def get_metric(
    metric: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    if metric not in SUPPORTED:
        raise HTTPException(status_code=404, detail=f"Unknown metric '{metric}'. Try one of {SUPPORTED}.")

    points = store.get_daily_metrics(metric, start_date=start_date, end_date=end_date)
    values = [p["value"] for p in points]

    stats = None
    if values:
        stats = {
            "average": round(sum(values) / len(values), 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "first": points[0]["date"],
            "last": points[-1]["date"],
            "days": len(values),
        }

        # For a stacked-stage metric, average each stage over the same window.
        stage_totals, stage_days = {}, 0
        for p in points:
            stages = (p.get("extra") or {}).get("stages")
            if not stages:
                continue
            stage_days += 1
            for k, v in stages.items():
                stage_totals[k] = stage_totals.get(k, 0) + v
        if stage_days:
            stats["stage_averages"] = {
                k: round(v / stage_days, 1) for k, v in stage_totals.items()
            }

    return {
        "metric": metric,
        "count": len(points),
        "stats": stats,
        "points": points,
    }
