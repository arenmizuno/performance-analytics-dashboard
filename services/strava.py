from services.normalize import normalize_mock_activity

MOCK_STRAVA_ACTIVITIES = [
    {
        "id": 1,
        "source": "strava",
        "activity_type": "run",
        "name": "Morning Run",
        "date": "2026-04-20",
        "distance_miles": 5.2,
        "duration_minutes": 42,
        "avg_mph": 7.43,
        "elevation_gain_ft": 120,
        "calories": 480,
    },
    {
        "id": 2,
        "source": "strava",
        "activity_type": "bike",
        "name": "Lakefront Ride",
        "date": "2026-04-19",
        "distance_miles": 22.1,
        "duration_minutes": 80,
        "avg_mph": 16.58,
        "elevation_gain_ft": 300,
        "calories": 700,
    },
    {
        "id": 3,
        "source": "strava",
        "activity_type": "hike",
        "name": "Trail Hike",
        "date": "2026-04-17",
        "distance_miles": 6.8,
        "duration_minutes": 140,
        "avg_mph": 2.91,
        "elevation_gain_ft": 900,
        "calories": 620,
    },
]


def get_strava_activities():
    return [normalize_mock_activity(a) for a in MOCK_STRAVA_ACTIVITIES]