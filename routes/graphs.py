from typing import Optional
from fastapi import APIRouter, Query

import store
from services.metrics import (
    build_mph_over_time,
    build_weekly_load,
    build_duration_over_time,
)

router = APIRouter(prefix="/graphs", tags=["graphs"])


def _load(activity_type: Optional[str], source: Optional[str],
          start_date: Optional[str], end_date: Optional[str]):
    return store.get_activities(
        start_date=start_date,
        end_date=end_date,
        source=source,
        activity_type=activity_type,
    )


@router.get("/mph-over-time")
def mph_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    activities = _load(activity_type, source, start_date, end_date)

    return {
        "metric": "avg_mph",
        "activity_type": activity_type,
        "source": source,
        "points": build_mph_over_time(activities),
    }


@router.get("/weekly-load")
def weekly_load(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    activities = _load(activity_type, source, start_date, end_date)

    return {
        "metric": "weekly_load",
        "activity_type": activity_type,
        "source": source,
        "points": build_weekly_load(activities),
    }


@router.get("/duration-over-time")
def duration_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    activities = _load(activity_type, source, start_date, end_date)

    return {
        "metric": "duration_minutes",
        "activity_type": activity_type,
        "source": source,
        "points": build_duration_over_time(activities),
    }
