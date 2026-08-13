from typing import Optional
from fastapi import APIRouter, Query

import store

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
def get_activities(
    activity_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    activities = store.get_activities(
        start_date=start_date,
        end_date=end_date,
        source=source,
        activity_type=activity_type,
    )

    return {
        "count": len(activities),
        "filters": {
            "activity_type": activity_type,
            "source": source,
            "start_date": start_date,
            "end_date": end_date,
        },
        "sync": store.get_sync_state(),
        "activities": [a.model_dump() for a in activities],
    }
