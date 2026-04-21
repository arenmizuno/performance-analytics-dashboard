from typing import Optional
from fastapi import APIRouter, Query

from services.strava import get_strava_activities
from services.hevy import get_hevy_activities
from services.withings import get_withings_activities
from services.metrics import attach_load_scores, filter_activities

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
def get_activities(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities = []
    activities.extend(get_strava_activities())
    activities.extend(get_hevy_activities())
    activities.extend(get_withings_activities())

    activities = attach_load_scores(activities)
    activities = filter_activities(activities, activity_type=activity_type, source=source)

    activities.sort(key=lambda x: x.date, reverse=True)

    return {
        "count": len(activities),
        "filters": {
            "activity_type": activity_type,
            "source": source,
        },
        "activities": [a.model_dump() for a in activities],
    }