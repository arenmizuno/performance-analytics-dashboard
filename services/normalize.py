from datetime import datetime, timezone

from models.activity import Activity


def normalize_strava_activity(raw: dict) -> Activity:
    moving_time_seconds = raw.get("moving_time", 0)
    distance_meters = raw.get("distance", 0)

    duration_minutes = round(moving_time_seconds / 60, 2) if moving_time_seconds else None
    distance_miles = round(distance_meters * 0.000621371, 2) if distance_meters else None

    avg_mph = None
    if duration_minutes and distance_miles and duration_minutes > 0:
        avg_mph = round(distance_miles / (duration_minutes / 60), 2)

    return Activity(
        id=str(raw.get("id")),
        source="strava",
        activity_type=(raw.get("sport_type") or raw.get("type") or "unknown").lower(),
        name=raw.get("name", "Unnamed Activity"),
        date=raw.get("start_date_local", "")[:10],
        duration_minutes=duration_minutes,
        distance_miles=distance_miles,
        avg_mph=avg_mph,
        elevation_gain_ft=round((raw.get("total_elevation_gain", 0) or 0) * 3.28084, 2) if raw.get("total_elevation_gain") else None,
        calories=None,
    )


WITHINGS_CATEGORIES = {
    1: "walk",
    2: "run",
    3: "hike",
    6: "ride",
    7: "swim",
    16: "strength",
    17: "strength",
    18: "elliptical",
    19: "pilates",
    28: "yoga",
    34: "ski",
    35: "snowboard",
    36: "other",
    187: "rowing",
    195: "climbing",
    307: "run",
    308: "ride",
}


def normalize_withings_workout(raw: dict) -> Activity:
    data = raw.get("data") or {}

    start = raw.get("startdate")
    end = raw.get("enddate")

    duration_seconds = data.get("effduration")
    if not duration_seconds and start and end:
        duration_seconds = end - start
    duration_minutes = round(duration_seconds / 60, 2) if duration_seconds else None

    distance_meters = data.get("distance")
    distance_miles = round(distance_meters * 0.000621371, 2) if distance_meters else None

    avg_mph = None
    if duration_minutes and distance_miles and duration_minutes > 0:
        avg_mph = round(distance_miles / (duration_minutes / 60), 2)

    category = raw.get("category")
    activity_type = WITHINGS_CATEGORIES.get(category, f"withings_{category}")

    elevation_meters = data.get("elevation")

    return Activity(
        id=str(raw.get("id")),
        source="withings",
        activity_type=activity_type,
        name=activity_type.replace("_", " ").title(),
        date=datetime.fromtimestamp(start, tz=timezone.utc).date().isoformat() if start else "",
        duration_minutes=duration_minutes,
        distance_miles=distance_miles,
        avg_mph=avg_mph,
        elevation_gain_ft=round(elevation_meters * 3.28084, 2) if elevation_meters else None,
        calories=data.get("calories"),
    )


GOOGLE_EXERCISE_TYPES = {
    "RUNNING": "run",
    "TREADMILL_RUNNING": "run",
    "WALKING": "walk",
    "HIKING": "hike",
    "BIKE": "ride",
    "OUTDOOR_BIKE": "ride",
    "SPINNING": "ride",
    "SWIMMING": "swim",
    "WEIGHTS": "strength",
    "STRENGTH_TRAINING": "strength",
}


def _parse_duration_seconds(value) -> float | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).rstrip("s"))


def normalize_google_health_exercise(raw: dict) -> Activity:
    exercise = raw.get("exercise", {})
    interval = exercise.get("interval", {})
    metrics = exercise.get("metricsSummary", {})

    exercise_type = exercise.get("exerciseType", "UNKNOWN")
    activity_type = GOOGLE_EXERCISE_TYPES.get(exercise_type, exercise_type.lower())

    duration_seconds = _parse_duration_seconds(exercise.get("activeDuration"))
    duration_minutes = round(duration_seconds / 60, 2) if duration_seconds else None

    distance_mm = metrics.get("distanceMillimiters", metrics.get("distanceMillimeters"))
    distance_miles = round(distance_mm / 1_000_000 * 0.621371, 2) if distance_mm else None

    avg_mph = None
    if duration_minutes and distance_miles and duration_minutes > 0:
        avg_mph = round(distance_miles / (duration_minutes / 60), 2)

    return Activity(
        id=str(raw.get("name") or f"{exercise_type}-{interval.get('startTime', '')}"),
        source="google_health",
        activity_type=activity_type,
        name=exercise.get("displayName") or exercise_type.replace("_", " ").title(),
        date=(interval.get("startTime") or "")[:10],
        duration_minutes=duration_minutes,
        distance_miles=distance_miles,
        avg_mph=avg_mph,
        elevation_gain_ft=None,
        calories=metrics.get("caloriesKcal"),
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_hevy_workout(raw: dict) -> Activity:
    start = _parse_iso(raw.get("start_time"))
    end = _parse_iso(raw.get("end_time"))

    duration_minutes = None
    if start and end:
        duration_minutes = round((end - start).total_seconds() / 60, 2)

    distance_meters = 0
    for exercise in raw.get("exercises") or []:
        for exercise_set in exercise.get("sets") or []:
            distance_meters += exercise_set.get("distance_meters") or 0

    return Activity(
        id=str(raw.get("id")),
        source="hevy",
        activity_type="strength",
        name=raw.get("title") or "Hevy Workout",
        date=start.date().isoformat() if start else "",
        duration_minutes=duration_minutes,
        distance_miles=round(distance_meters * 0.000621371, 2) if distance_meters else None,
        avg_mph=None,
        elevation_gain_ft=None,
        calories=None,
    )