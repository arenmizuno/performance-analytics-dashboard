from services.normalize import normalize_mock_activity

MOCK_WITHINGS_WORKOUTS = [
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


def get_withings_activities():
    """
    Placeholder.
    Later this can return walks / sleep / health metrics if you want.
    """
    return []