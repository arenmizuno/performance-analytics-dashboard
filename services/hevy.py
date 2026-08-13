import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

from services.normalize import normalize_hevy_workout

load_dotenv()

HEVY_API_KEY = os.getenv("HEVY_API_KEY")

HEVY_WORKOUTS_URL = "https://api.hevyapp.com/v1/workouts"

HEVY_PAGE_SIZE = 10
HEVY_MAX_PAGES = 50


def is_hevy_connected() -> bool:
    return bool(HEVY_API_KEY)


async def get_hevy_activities(activity_type: str | None = None):
    if not HEVY_API_KEY:
        raise ValueError("No Hevy API key found. Set HEVY_API_KEY first.")

    cutoff = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")

    all_workouts = []
    page = 1

    async with httpx.AsyncClient() as client:
        while page <= HEVY_MAX_PAGES:
            response = await client.get(
                HEVY_WORKOUTS_URL,
                headers={"api-key": HEVY_API_KEY},
                params={"page": page, "pageSize": HEVY_PAGE_SIZE},
            )
            response.raise_for_status()
            body = response.json()

            all_workouts.extend(body.get("workouts") or [])

            if page >= body.get("page_count", page):
                break

            page += 1

    normalized = [normalize_hevy_workout(w) for w in all_workouts]
    normalized = [a for a in normalized if a.date >= cutoff]

    if activity_type:
        normalized = [
            a for a in normalized
            if a.activity_type.lower() == activity_type.lower()
        ]

    return normalized
