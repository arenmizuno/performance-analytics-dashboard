from typing import Optional
from fastapi import APIRouter, Query

from services.strava import get_strava_activities
from services.hevy import get_hevy_activities
from services.withings import get_withings_activities
from services.metrics import (
    attach_load_scores,
    filter_activities,
    build_mph_over_time,
    build_weekly_load,
    build_duration_over_time,
)

router = APIRouter(prefix="/graphs", tags=["graphs"])


async def get_all_activities():
    activities = []
    activities.extend(await get_strava_activities())
    activities.extend(get_hevy_activities())
    activities.extend(get_withings_activities())
    activities = attach_load_scores(activities)
    return activities


@router.get("/mph-over-time")
async def mph_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities = await get_all_activities()
    activities = filter_activities(activities, activity_type=activity_type, source=source)

    return {
        "metric": "avg_mph",
        "activity_type": activity_type,
        "source": source,
        "points": build_mph_over_time(activities),
    }


@router.get("/weekly-load")
async def weekly_load(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities = await get_all_activities()
    activities = filter_activities(activities, activity_type=activity_type, source=source)

    return {
        "metric": "weekly_load",
        "activity_type": activity_type,
        "source": source,
        "points": build_weekly_load(activities),
    }


@router.get("/duration-over-time")
async def duration_over_time(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities = await get_all_activities()
    activities = filter_activities(activities, activity_type=activity_type, source=source)

    return {
        "metric": "duration_minutes",
        "activity_type": activity_type,
        "source": source,
        "points": build_duration_over_time(activities),
    }