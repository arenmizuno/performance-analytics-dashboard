import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

from db import get_any_oauth_token, save_oauth_token
from services.normalize import normalize_withings_workout

load_dotenv()

WITHINGS_CLIENT_ID = os.getenv("WITHINGS_CLIENT_ID")
WITHINGS_CLIENT_SECRET = os.getenv("WITHINGS_CLIENT_SECRET")
WITHINGS_REDIRECT_URI = os.getenv("WITHINGS_REDIRECT_URI")

WITHINGS_AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
WITHINGS_MEASURE_URL = "https://wbsapi.withings.net/v2/measure"

WITHINGS_SCOPE = "user.activity,user.metrics"

WITHINGS_DATA_FIELDS = ",".join([
    "calories",
    "effduration",
    "distance",
    "elevation",
    "steps",
    "hr_average",
    "intensity",
])

PROVIDER = "withings"


def get_withings_auth_url():
    params = {
        "response_type": "code",
        "client_id": WITHINGS_CLIENT_ID,
        "redirect_uri": WITHINGS_REDIRECT_URI,
        "scope": WITHINGS_SCOPE,
        "state": "performance-analytics-dashboard",
    }
    return f"{WITHINGS_AUTH_URL}?{urlencode(params)}"


def _unwrap(payload: dict) -> dict:
    if payload.get("status") != 0:
        raise ValueError(f"Withings API error {payload.get('status')}: {payload.get('error')}")
    return payload.get("body", {})


def is_withings_connected() -> bool:
    return get_any_oauth_token(PROVIDER) is not None


async def exchange_code_for_token(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            WITHINGS_TOKEN_URL,
            data={
                "action": "requesttoken",
                "grant_type": "authorization_code",
                "client_id": WITHINGS_CLIENT_ID,
                "client_secret": WITHINGS_CLIENT_SECRET,
                "code": code,
                "redirect_uri": WITHINGS_REDIRECT_URI,
            },
        )
        response.raise_for_status()
        body = _unwrap(response.json())

    save_oauth_token(
        provider=PROVIDER,
        account_id=str(body["userid"]),
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=int(time.time()) + int(body.get("expires_in", 10800)),
        scope=body.get("scope"),
    )

    return {"account_id": str(body["userid"]), "scope": body.get("scope")}


async def refresh_withings_token_if_needed():
    token_row = get_any_oauth_token(PROVIDER)
    if not token_row:
        raise ValueError("No Withings token found. Connect Withings first.")

    if token_row["expires_at"] > int(time.time()) + 60:
        return token_row["access_token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            WITHINGS_TOKEN_URL,
            data={
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": WITHINGS_CLIENT_ID,
                "client_secret": WITHINGS_CLIENT_SECRET,
                "refresh_token": token_row["refresh_token"],
            },
        )
        response.raise_for_status()
        body = _unwrap(response.json())

    save_oauth_token(
        provider=PROVIDER,
        account_id=token_row["account_id"],
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=int(time.time()) + int(body.get("expires_in", 10800)),
        scope=body.get("scope", token_row["scope"]),
    )

    return body["access_token"]


async def get_withings_activities(activity_type: str | None = None):
    access_token = await refresh_withings_token_if_needed()

    start_date = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    all_series = []
    offset = 0

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.post(
                WITHINGS_MEASURE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                data={
                    "action": "getworkouts",
                    "startdateymd": start_date,
                    "enddateymd": end_date,
                    "data_fields": WITHINGS_DATA_FIELDS,
                    "offset": offset,
                },
            )
            response.raise_for_status()
            body = _unwrap(response.json())

            all_series.extend(body.get("series") or [])

            if not body.get("more"):
                break

            offset = body.get("offset", 0)

    normalized = [normalize_withings_workout(w) for w in all_series]

    if activity_type:
        normalized = [
            a for a in normalized
            if a.activity_type.lower() == activity_type.lower()
        ]

    return normalized
