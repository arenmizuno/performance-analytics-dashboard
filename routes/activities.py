from typing import Optional
from fastapi import APIRouter, Query

from services.aggregate import collect_activities
from services.metrics import filter_activities

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
async def get_activities(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
):
    activities, sources = await collect_activities(source=source)
    activities = filter_activities(activities, activity_type=activity_type, source=source)
    activities.sort(key=lambda x: x.date, reverse=True)

    return {
        "count": len(activities),
        "filters": {
            "activity_type": activity_type,
            "source": source,
        },
        "sources": sources,
        "activities": [a.model_dump() for a in activities],
    }
