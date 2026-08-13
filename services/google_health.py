import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

from db import get_any_oauth_token, save_oauth_token
from services.normalize import normalize_google_health_exercise

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_HEALTH_BASE_URL = "https://health.googleapis.com/v4"

GOOGLE_HEALTH_SCOPE = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"

PROVIDER = "google_health"


def get_google_health_auth_url():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_HEALTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def _fetch_account_id(client, access_token):
    response = await client.get(
        f"{GOOGLE_HEALTH_BASE_URL}/users/me/identity",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != 200:
        return "me"

    data = response.json()
    return str(data.get("googleUserId") or data.get("fitbitUserId") or "me")


async def exchange_code_for_token(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        data = response.json()

        account_id = await _fetch_account_id(client, data["access_token"])

    save_oauth_token(
        provider=PROVIDER,
        account_id=account_id,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=int(time.time()) + int(data.get("expires_in", 3600)),
        scope=data.get("scope"),
    )

    return {"account_id": account_id, "scope": data.get("scope")}


def is_google_health_connected() -> bool:
    return get_any_oauth_token(PROVIDER) is not None


async def refresh_google_token_if_needed():
    token_row = get_any_oauth_token(PROVIDER)
    if not token_row:
        raise ValueError("No Google Health token found. Connect Google Health first.")

    if token_row["expires_at"] > int(time.time()) + 60:
        return token_row["access_token"]

    if not token_row["refresh_token"]:
        raise ValueError("Google Health token expired and no refresh token is stored. Reconnect Google Health.")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": token_row["refresh_token"],
            },
        )
        response.raise_for_status()
        data = response.json()

    save_oauth_token(
        provider=PROVIDER,
        account_id=token_row["account_id"],
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=int(time.time()) + int(data.get("expires_in", 3600)),
        scope=data.get("scope", token_row["scope"]),
    )

    return data["access_token"]


async def get_google_health_activities(activity_type: str | None = None):
    access_token = await refresh_google_token_if_needed()

    after = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%dT00:00:00")

    all_points = []
    page_token = None

    async with httpx.AsyncClient() as client:
        while True:
            params = {
                "filter": f'exercise.interval.civil_start_time >= "{after}"',
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await client.get(
                f"{GOOGLE_HEALTH_BASE_URL}/users/me/dataTypes/exercise/dataPoints",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            body = response.json()

            all_points.extend(body.get("dataPoints") or [])

            page_token = body.get("nextPageToken")
            if not page_token:
                break

    normalized = [normalize_google_health_exercise(p) for p in all_points]

    if activity_type:
        normalized = [
            a for a in normalized
            if a.activity_type.lower() == activity_type.lower()
        ]

    return normalized
