from services.normalize import normalize_mock_activity

MOCK_HEVY_WORKOUTS = [
    {
        "id": 101,
        "source": "hevy",
        "activity_type": "strength",
        "name": "Leg Day",
        "date": "2026-04-18",
        "distance_miles": None,
        "duration_minutes": 65,
        "avg_mph": None,
        "elevation_gain_ft": None,
        "calories": 350,
    },
    {
        "id": 102,
        "source": "hevy",
        "activity_type": "strength",
        "name": "Push Day",
        "date": "2026-04-15",
        "distance_miles": None,
        "duration_minutes": 58,
        "avg_mph": None,
        "elevation_gain_ft": None,
        "calories": 310,
    },
]


def get_hevy_activities():
    return [normalize_mock_activity(a) for a in MOCK_HEVY_WORKOUTS]