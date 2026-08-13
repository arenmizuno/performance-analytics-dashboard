from typing import Optional
from fastapi import APIRouter, Query

from services.aggregate import collect_activities
from services.metrics import (
    filter_activities,
    build_mph_over_time,
    build_weekly_load,
    build_duration_over_time,
)

router = APIRouter(prefix="/graphs", tags=["graphs"])


async def _gather(activity_type: Optional[str], source: Optional[str]):
    activities, sources = await collect_activities(source=source)
    return filter_activities(activities, activity_type=activity_type, source=source), sources


@router.get("/mph-over-time")
async def mph_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities, sources = await _gather(activity_type, source)

    return {
        "metric": "avg_mph",
        "activity_type": activity_type,
        "source": source,
        "sources": sources,
        "points": build_mph_over_time(activities),
    }


@router.get("/weekly-load")
async def weekly_load(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities, sources = await _gather(activity_type, source)

    return {
        "metric": "weekly_load",
        "activity_type": activity_type,
        "source": source,
        "sources": sources,
        "points": build_weekly_load(activities),
    }


@router.get("/duration-over-time")
async def duration_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities, sources = await _gather(activity_type, source)

    return {
        "metric": "duration_minutes",
        "activity_type": activity_type,
        "source": source,
        "sources": sources,
        "points": build_duration_over_time(activities),
    }
