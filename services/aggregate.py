import logging
from typing import Dict, List, Optional, Tuple

from models.activity import Activity
from services.strava import get_strava_activities, is_strava_connected
from services.hevy import get_hevy_activities, is_hevy_connected
from services.withings import get_withings_activities, is_withings_connected
from services.google_health import get_google_health_activities, is_google_health_connected
from services.metrics import attach_load_scores

logger = logging.getLogger(__name__)

SOURCES = {
    "strava": (get_strava_activities, is_strava_connected),
    "hevy": (get_hevy_activities, is_hevy_connected),
    "withings": (get_withings_activities, is_withings_connected),
    "google_health": (get_google_health_activities, is_google_health_connected),
}


async def collect_activities(source: Optional[str] = None) -> Tuple[List[Activity], Dict]:
    """
    Fetch from every connected source, isolating failures so one broken
    provider cannot blank the whole dashboard.
    """
    activities = []
    report = {}

    for name, (fetch, is_connected) in SOURCES.items():
        if source and source.lower() != name:
            continue

        if not is_connected():
            report[name] = {"status": "not_connected", "count": 0}
            continue

        try:
            fetched = await fetch()
        except Exception as exc:
            logger.exception("Failed to fetch activities from %s", name)
            report[name] = {"status": "error", "count": 0, "error": str(exc)}
            continue

        activities.extend(fetched)
        report[name] = {"status": "ok", "count": len(fetched)}

    return attach_load_scores(activities), report
