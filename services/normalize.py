from models.activity import Activity


def normalize_mock_activity(raw: dict) -> Activity:
    return Activity(
        id=str(raw["id"]),
        source=raw["source"],
        activity_type=raw["activity_type"],
        name=raw["name"],
        date=raw["date"],
        duration_minutes=raw.get("duration_minutes"),
        distance_miles=raw.get("distance_miles"),
        avg_mph=raw.get("avg_mph"),
        elevation_gain_ft=raw.get("elevation_gain_ft"),
        calories=raw.get("calories"),
    )


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


def normalize_hevy_workout(raw: dict) -> Activity:
    duration_minutes = raw.get("duration_minutes") or raw.get("durationMinutes")
    date = raw.get("start_time", "")[:10] if raw.get("start_time") else raw.get("date", "")

    return Activity(
        id=str(raw.get("id")),
        source="hevy",
        activity_type="strength",
        name=raw.get("title", raw.get("name", "Hevy Workout")),
        date=date,
        duration_minutes=duration_minutes,
        distance_miles=None,
        avg_mph=None,
        elevation_gain_ft=None,
        calories=raw.get("calories"),
    )