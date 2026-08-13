import os
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import httpx
from dotenv import load_dotenv

from services.normalize import normalize_hevy_workout

load_dotenv()

HEVY_API_KEY = os.getenv("HEVY_API_KEY")

HEVY_WORKOUTS_URL = "https://api.hevyapp.com/v1/workouts"
HEVY_EVENTS_URL = "https://api.hevyapp.com/v1/workouts/events"

HEVY_PAGE_SIZE = 10
HEVY_MAX_PAGES = 50


def is_hevy_connected() -> bool:
    return bool(HEVY_API_KEY)


def _headers():
    if not HEVY_API_KEY:
        raise ValueError("No Hevy API key found. Set HEVY_API_KEY first.")
    return {"api-key": HEVY_API_KEY}


async def _paged(client, url, params):
    page = 1
    while page <= HEVY_MAX_PAGES:
        response = await client.get(
            url,
            headers=_headers(),
            params={**params, "page": page, "pageSize": HEVY_PAGE_SIZE},
        )
        response.raise_for_status()
        body = response.json()

        yield body

        if page >= body.get("page_count", page):
            break

        page += 1


async def get_hevy_raw_workouts() -> List[dict]:
    workouts = []
    async with httpx.AsyncClient() as client:
        async for body in _paged(client, HEVY_WORKOUTS_URL, {}):
            workouts.extend(body.get("workouts") or [])
    return workouts


async def get_hevy_activities(activity_type: str | None = None, since: datetime | None = None):
    """
    Full sync walks every page. An incremental sync uses the events feed,
    which reports the same workouts in one call instead of nine.
    """
    if since:
        activities, _ = await get_hevy_changes(since)
    else:
        raw = await get_hevy_raw_workouts()
        activities = [normalize_hevy_workout(w) for w in raw]

    if activity_type:
        activities = [
            a for a in activities
            if a.activity_type.lower() == activity_type.lower()
        ]

    return activities


async def get_hevy_changes(since: datetime) -> Tuple[List, List[str]]:
    since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    updated = []
    deleted = []

    async with httpx.AsyncClient() as client:
        async for body in _paged(client, HEVY_EVENTS_URL, {"since": since_iso}):
            for event in body.get("events") or []:
                if event.get("type") == "deleted":
                    deleted.append(str(event.get("id")))
                elif event.get("workout"):
                    updated.append(normalize_hevy_workout(event["workout"]))

    return updated, deleted
