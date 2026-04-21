import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

from db import get_any_strava_token, save_strava_token
from services.normalize import normalize_strava_activity

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def get_strava_auth_url():
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": STRAVA_REDIRECT_URI,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all",
    }
    return f"{STRAVA_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, scope: str | None = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        data = response.json()

    athlete_id = str(data["athlete"]["id"])
    save_strava_token(
        athlete_id=athlete_id,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=data["expires_at"],
        scope=scope,
    )

    return data


async def refresh_strava_token_if_needed():
    token_row = get_any_strava_token()
    if not token_row:
        raise ValueError("No Strava token found. Connect Strava first.")

    if token_row["expires_at"] > int(time.time()) + 60:
        return token_row["access_token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": token_row["refresh_token"],
            },
        )
        response.raise_for_status()
        data = response.json()

    save_strava_token(
        athlete_id=token_row["athlete_id"],
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=data["expires_at"],
        scope=token_row["scope"],
    )

    return data["access_token"]


async def get_strava_activities(activity_type: str | None = None):
    access_token = await refresh_strava_token_if_needed()

    after_dt = datetime.utcnow() - timedelta(days=180)
    after_ts = int(after_dt.timestamp())

    all_activities = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                STRAVA_ACTIVITIES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "after": after_ts,
                    "page": page,
                    "per_page": 100,
                },
            )
            response.raise_for_status()
            batch = response.json()

            if not batch:
                break

            all_activities.extend(batch)

            if len(batch) < 100:
                break

            page += 1

    normalized = [normalize_strava_activity(a) for a in all_activities]

    if activity_type:
        normalized = [
            a for a in normalized
            if a.activity_type.lower() == activity_type.lower()
        ]

    return normalized