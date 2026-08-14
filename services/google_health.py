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

GOOGLE_HEALTH_SCOPE = " ".join([
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
])

HISTORY_DAYS = 3650  # full-sync lookback

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
    return str(data.get("healthUserId") or data.get("legacyUserId") or "me")


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


ASLEEP_STAGES = {"LIGHT", "DEEP", "REM"}


async def _list_data_points(data_type: str, filter_expr: str | None = None) -> list[dict]:
    access_token = await refresh_google_token_if_needed()

    points = []
    page_token = None

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"pageSize": 100}
            if filter_expr:
                params["filter"] = filter_expr
            if page_token:
                params["pageToken"] = page_token

            response = await client.get(
                f"{GOOGLE_HEALTH_BASE_URL}/users/me/dataTypes/{data_type}/dataPoints",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                params=params,
            )
            response.raise_for_status()
            body = response.json()

            points.extend(body.get("dataPoints") or [])

            page_token = body.get("nextPageToken")
            if not page_token:
                break

    return points


async def get_google_sleep(since: datetime | None = None) -> list[dict]:
    start = since or (datetime.utcnow() - timedelta(days=HISTORY_DAYS))
    cutoff = start.strftime("%Y-%m-%d")

    # The sleep data type rejects a civil_start_time filter (only exercise
    # accepts one), so the window is applied here instead of server-side.
    points = []
    for raw in await _list_data_points("sleep"):
        sleep = raw.get("sleep") or {}
        interval = sleep.get("interval") or {}

        start_time = interval.get("startTime")
        end_time = interval.get("endTime")
        if not start_time or not end_time:
            continue

        stage_minutes = {}
        for stage in sleep.get("stages") or []:
            s = _parse_rfc3339(stage.get("startTime"))
            e = _parse_rfc3339(stage.get("endTime"))
            if not s or not e:
                continue
            stage_minutes[stage.get("type", "UNKNOWN")] = (
                stage_minutes.get(stage.get("type", "UNKNOWN"), 0) + (e - s).total_seconds() / 60
            )

        asleep = sum(v for k, v in stage_minutes.items() if k in ASLEEP_STAGES)
        if not asleep:
            s, e = _parse_rfc3339(start_time), _parse_rfc3339(end_time)
            asleep = (e - s).total_seconds() / 60 if s and e else 0

        # A session that ends in the morning belongs to that morning's date.
        date = (_parse_rfc3339(end_time) or _parse_rfc3339(start_time)).date().isoformat()

        if date < cutoff:
            continue

        points.append({
            "date": date,
            "metric": "sleep_minutes",
            "value": round(asleep, 1),
            "source": "google_health",
            "extra": {
                "stages": {k: round(v, 1) for k, v in stage_minutes.items()},
                "start": start_time,
                "end": end_time,
            },
        })

    return _merge_same_night(points)


ROLLUP_MAX_DAYS = 90


def _civil(d) -> dict:
    """CivilDateTime wraps the date in its own field."""
    return {"date": {"year": d.year, "month": d.month, "day": d.day}}


async def _daily_rollup(
    data_type: str, wrapper: str, agg_field: str, metric: str,
    since: datetime | None = None,
) -> list[dict]:
    """
    Sum an interval data type to one value per civil day via dailyRollUp, walked
    in 90-day windows (the API's per-request cap). `wrapper` is the field the
    rollup nests its value under (named after the data type) and `agg_field` is
    the aggregate within it, e.g. steps -> countSum, active energy -> kcalSum.
    """
    access_token = await refresh_google_token_if_needed()

    start = (since or (datetime.utcnow() - timedelta(days=HISTORY_DAYS))).date()
    end = datetime.utcnow().date() + timedelta(days=1)

    points = []

    async with httpx.AsyncClient(timeout=60) as client:
        window_start = start
        while window_start < end:
            window_end = min(window_start + timedelta(days=ROLLUP_MAX_DAYS), end)

            page_token = None
            while True:
                # No pageSize: dailyRollUp rejects an explicit one, and a 90-day
                # window is well inside the default page.
                body = {
                    "range": {"start": _civil(window_start), "end": _civil(window_end)},
                    "windowSizeDays": 1,
                }
                if page_token:
                    body["pageToken"] = page_token

                response = await client.post(
                    f"{GOOGLE_HEALTH_BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()

                for row in payload.get("rollupDataPoints") or []:
                    date = _civil_date_str((row.get("civilStartTime") or {}).get("date"))
                    value = (row.get(wrapper) or {}).get(agg_field)
                    if not date or value in (None, ""):
                        continue

                    points.append({
                        "date": date,
                        "metric": metric,
                        "value": round(float(value), 1),
                        "source": "google_health",
                    })

                page_token = payload.get("nextPageToken")
                if not page_token:
                    break

            window_start = window_end

    return points


async def get_google_steps(since: datetime | None = None) -> list[dict]:
    """Daily step totals; the raw steps stream is minute-level, so aggregate it."""
    return await _daily_rollup("steps", "steps", "countSum", "steps", since)


async def get_google_energy(since: datetime | None = None) -> list[dict]:
    """Active energy burned per day, in kilocalories."""
    return await _daily_rollup(
        "active-energy-burned", "activeEnergyBurned", "kcalSum", "energy_kcal", since
    )


def _civil_date_str(civil: dict | None) -> str | None:
    civil = civil or {}
    if not civil.get("year"):
        return None
    return f"{civil['year']:04d}-{civil['month']:02d}-{civil['day']:02d}"


async def _daily_values(
    data_type: str, wrapper: str, value_field: str, metric: str,
    since: datetime | None = None,
) -> list[dict]:
    """
    One value per day for a Daily record type (resting HR, HRV). These are already
    one point per day, so this lists them and applies the window client-side, the
    way sleep does; the Daily HRV type does not accept a dailyRollUp. The point
    carries both its civil date and value inside the type-named wrapper field.
    """
    start = since or (datetime.utcnow() - timedelta(days=HISTORY_DAYS))
    cutoff = start.strftime("%Y-%m-%d")

    by_date: dict[str, dict] = {}
    for raw in await _list_data_points(data_type):
        payload = raw.get(wrapper) or {}
        date = _civil_date_str(payload.get("date"))
        value = payload.get(value_field)
        if not date or date < cutoff or value in (None, ""):
            continue

        by_date[date] = {
            "date": date,
            "metric": metric,
            "value": round(float(value), 1),
            "source": "google_health",
        }

    return sorted(by_date.values(), key=lambda p: p["date"])


async def get_google_resting_hr(since: datetime | None = None) -> list[dict]:
    """Daily resting heart rate, in beats per minute."""
    return await _daily_values(
        "daily-resting-heart-rate", "dailyRestingHeartRate", "beatsPerMinute",
        "resting_hr", since,
    )


async def get_google_hrv(since: datetime | None = None) -> list[dict]:
    """Daily heart rate variability (average RMSSD), in milliseconds."""
    return await _daily_values(
        "daily-heart-rate-variability", "dailyHeartRateVariability",
        "averageHeartRateVariabilityMilliseconds", "hrv_ms", since,
    )


def _merge_same_night(points: list[dict]) -> list[dict]:
    """Naps and split sleep produce several sessions for one date; sum them."""
    merged: dict[str, dict] = {}

    for p in points:
        existing = merged.get(p["date"])
        if not existing:
            merged[p["date"]] = p
            continue

        existing["value"] = round(existing["value"] + p["value"], 1)
        existing["extra"]["sessions"] = existing["extra"].get("sessions", 1) + 1
        for stage, minutes in (p["extra"].get("stages") or {}).items():
            existing["extra"]["stages"][stage] = round(
                existing["extra"]["stages"].get(stage, 0) + minutes, 1
            )

    return sorted(merged.values(), key=lambda x: x["date"])


def _parse_rfc3339(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def get_google_health_activities(activity_type: str | None = None, since: datetime | None = None):
    access_token = await refresh_google_token_if_needed()

    start = since or (datetime.utcnow() - timedelta(days=HISTORY_DAYS))
    after = start.strftime("%Y-%m-%dT00:00:00")

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
