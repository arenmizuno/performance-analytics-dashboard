"""
Tools the assistant can call.

Each one reads the local store - never a provider API - so answers are fast and
work whether or not the upstream services are reachable. Results are summarised
rather than dumped: a year of steps is 365 numbers the model does not need, so
each tool returns statistics plus a capped sample.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional

import store

MAX_POINTS = 60
MAX_ACTIVITIES = 40

METRIC_KEYS = {
    "weight": "weight_lb",
    "steps": "steps",
    "readiness": "readiness",
    "sleep": "sleep_minutes",
}


def _resolve_range(start_date: Optional[str], end_date: Optional[str], default_days: int = 30):
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=default_days - 1)
    return start.isoformat(), end.isoformat()


def _summarise(points: List[Dict], metric: str) -> Dict:
    if not points:
        return {"metric": metric, "days": 0, "note": "No data recorded in this range."}

    values = [p["value"] for p in points]
    sample = points if len(points) <= MAX_POINTS else points[:: max(1, len(points) // MAX_POINTS)]

    out = {
        "metric": metric,
        "days": len(values),
        "average": round(sum(values) / len(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "first_date": points[0]["date"],
        "last_date": points[-1]["date"],
        "latest_value": points[-1]["value"],
        "series": [{"date": p["date"], "value": p["value"]} for p in sample],
    }

    if metric == "sleep_minutes":
        out["average_hours"] = round(out["average"] / 60, 2)
        stage_totals, n = {}, 0
        for p in points:
            stages = (p.get("extra") or {}).get("stages")
            if stages:
                n += 1
                for k, v in stages.items():
                    stage_totals[k] = stage_totals.get(k, 0) + v
        if n:
            out["average_stage_minutes"] = {k: round(v / n, 1) for k, v in stage_totals.items()}

    return out


def _metric_tool(metric_name: str, start_date=None, end_date=None) -> Dict:
    key = METRIC_KEYS[metric_name]
    start, end = _resolve_range(start_date, end_date)
    points = store.get_daily_metrics(key, start_date=start, end_date=end)
    result = _summarise(points, key)
    result["range"] = {"start": start, "end": end}

    # An empty window is usually a gap in logging rather than an absence of data,
    # so hand back the most recent reading to answer with instead of nothing.
    if not points:
        everything = store.get_daily_metrics(key)
        if everything:
            latest = everything[-1]
            result["most_recent_outside_range"] = {
                "date": latest["date"],
                "value": latest["value"],
            }
            result["note"] = (
                f"No {key} recorded between {start} and {end}. "
                f"The most recent reading is {latest['value']} on {latest['date']}."
            )

    return result


def get_weight(start_date=None, end_date=None) -> Dict:
    return _metric_tool("weight", start_date, end_date)


def get_steps(start_date=None, end_date=None) -> Dict:
    return _metric_tool("steps", start_date, end_date)


def get_readiness(start_date=None, end_date=None) -> Dict:
    return _metric_tool("readiness", start_date, end_date)


def get_sleep(start_date=None, end_date=None) -> Dict:
    return _metric_tool("sleep", start_date, end_date)


def get_personal_bests(category: Optional[str] = None) -> Dict:
    bests = store.get_personal_bests(category=category)
    return {
        "count": len(bests),
        "personal_bests": [
            {
                "category": pb["category"],
                "name": pb["name"],
                "result": pb["display_value"],
                "date": pb["date_achieved"],
                "source": pb["source"],
            }
            for pb in bests
        ],
    }


def get_activities(start_date=None, end_date=None, source=None, activity_type=None) -> Dict:
    start, end = _resolve_range(start_date, end_date)
    rows = store.get_activities(
        start_date=start, end_date=end, source=source, activity_type=activity_type
    )

    by_type: Dict[str, Dict] = {}
    for a in rows:
        entry = by_type.setdefault(a.activity_type, {"count": 0, "minutes": 0.0, "miles": 0.0})
        entry["count"] += 1
        entry["minutes"] += a.duration_minutes or 0
        entry["miles"] += a.distance_miles or 0

    return {
        "range": {"start": start, "end": end},
        "count": len(rows),
        "total_minutes": round(sum(a.duration_minutes or 0 for a in rows), 1),
        "total_miles": round(sum(a.distance_miles or 0 for a in rows), 2),
        "by_type": {
            k: {"count": v["count"], "minutes": round(v["minutes"], 1), "miles": round(v["miles"], 2)}
            for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["count"])
        },
        "activities": [
            {
                "date": a.date,
                "name": a.name,
                "type": a.activity_type,
                "source": a.source,
                "minutes": round(a.duration_minutes, 1) if a.duration_minutes else None,
                "miles": a.distance_miles,
                "mph": a.avg_mph,
            }
            for a in rows[:MAX_ACTIVITIES]
        ],
        "truncated": len(rows) > MAX_ACTIVITIES,
    }


TOOL_FUNCTIONS = {
    "get_weight": get_weight,
    "get_steps": get_steps,
    "get_readiness": get_readiness,
    "get_sleep": get_sleep,
    "get_personal_bests": get_personal_bests,
    "get_activities": get_activities,
}

_DATE_RANGE_PROPS = {
    "start_date": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD."},
    "end_date": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD."},
}


def _metric_schema(name: str, description: str) -> Dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": dict(_DATE_RANGE_PROPS),
                "required": [],
            },
        },
    }


TOOL_SCHEMAS = [
    _metric_schema("get_weight", "Body weight in pounds per day. Defaults to the last 30 days."),
    _metric_schema("get_steps", "Daily step count. Defaults to the last 30 days."),
    _metric_schema(
        "get_readiness",
        "Derived daily readiness score, 0-100, blending last night's sleep with "
        "acute-to-chronic training load. Defaults to the last 30 days.",
    ),
    _metric_schema(
        "get_sleep",
        "Nightly sleep in minutes, including average time per stage "
        "(deep, REM, light, awake). Defaults to the last 30 days.",
    ),
    {
        "type": "function",
        "function": {
            "name": "get_personal_bests",
            "description": "Personal bests. Categories include running, triathlon, swim and strength.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter, e.g. running or strength.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activities",
            "description": (
                "Workouts and training sessions, with totals broken down by type. "
                "Defaults to the last 30 days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    **_DATE_RANGE_PROPS,
                    "source": {
                        "type": "string",
                        "description": "Optional: strava, hevy or google_health.",
                    },
                    "activity_type": {
                        "type": "string",
                        "description": "Optional: run, ride, hike, walk, swim, strength.",
                    },
                },
                "required": [],
            },
        },
    },
]
