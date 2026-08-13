"""
Derived readiness score.

None of the four connected providers reports a readiness or recovery score,
so this composes one from signals we do have. It is a transparent heuristic,
not a physiological model - swap it out if a provider ever supplies a real one.

Two components, each scored 0-100 and then weighted:

  sleep (60%)  last night's asleep minutes against an 8 hour target
  load  (40%)  7-day training load against the trailing 28-day average,
               penalising both spikes (overreaching) and long layoffs
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import store

SLEEP_TARGET_MINUTES = 8 * 60
SLEEP_WEIGHT = 0.6
LOAD_WEIGHT = 0.4


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _sleep_component(sleep_minutes: Optional[float]) -> Optional[float]:
    if sleep_minutes is None:
        return None
    return _clamp(sleep_minutes / SLEEP_TARGET_MINUTES * 100)


def _load_component(acute: float, chronic: float) -> Optional[float]:
    if chronic <= 0:
        return None

    ratio = acute / chronic

    # 0.8-1.3 is the comfortable band; deviation either way costs points.
    if ratio < 0.8:
        return _clamp(100 - (0.8 - ratio) * 100)
    if ratio > 1.3:
        return _clamp(100 - (ratio - 1.3) * 150)
    return 100.0


def compute_readiness(days: int = 180) -> List[Dict]:
    end = date.today()
    start = end - timedelta(days=days)

    activities = store.get_activities(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    load_by_date: Dict[str, float] = {}
    for a in activities:
        if a.date:
            load_by_date[a.date] = load_by_date.get(a.date, 0) + (a.load_score or 0)

    sleep_by_date = {
        p["date"]: p["value"]
        for p in store.get_daily_metrics("sleep_minutes", start.isoformat(), end.isoformat())
    }

    points = []
    cursor = start

    while cursor <= end:
        iso = cursor.isoformat()

        acute = sum(
            load_by_date.get((cursor - timedelta(days=i)).isoformat(), 0)
            for i in range(7)
        ) / 7
        chronic = sum(
            load_by_date.get((cursor - timedelta(days=i)).isoformat(), 0)
            for i in range(28)
        ) / 28

        components = {
            "sleep": _sleep_component(sleep_by_date.get(iso)),
            "load": _load_component(acute, chronic),
        }

        weights = {"sleep": SLEEP_WEIGHT, "load": LOAD_WEIGHT}
        available = {k: v for k, v in components.items() if v is not None}

        if available:
            total_weight = sum(weights[k] for k in available)
            score = sum(available[k] * weights[k] for k in available) / total_weight

            points.append({
                "date": iso,
                "metric": "readiness",
                "value": round(score, 1),
                "source": "derived",
                "extra": {
                    "components": {k: round(v, 1) for k, v in available.items()},
                    "acute_load": round(acute, 1),
                    "chronic_load": round(chronic, 1),
                },
            })

        cursor += timedelta(days=1)

    return points
