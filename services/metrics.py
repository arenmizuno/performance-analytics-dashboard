from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional

from models.activity import Activity


def compute_load_score(activity: Activity) -> float:
    """
    Simple starter load metric.
    You can replace this later with something more advanced.
    """
    duration = activity.duration_minutes or 0

    multipliers = {
        "run": 1.3,
        "bike": 1.0,
        "ride": 1.0,
        "hike": 0.9,
        "walk": 0.6,
        "strength": 1.1,
        "swim": 1.2,
    }

    multiplier = multipliers.get(activity.activity_type.lower(), 1.0)
    return round(duration * multiplier, 2)


def attach_load_scores(activities: List[Activity]) -> List[Activity]:
    updated = []
    for activity in activities:
        activity.load_score = compute_load_score(activity)
        updated.append(activity)
    return updated


def filter_activities(
    activities: List[Activity],
    activity_type: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Activity]:
    filtered = activities

    if activity_type:
        filtered = [
            a for a in filtered
            if a.activity_type.lower() == activity_type.lower()
        ]

    if source:
        filtered = [
            a for a in filtered
            if a.source.lower() == source.lower()
        ]

    return filtered


def build_mph_over_time(activities: List[Activity]) -> List[Dict]:
    points = []
    for activity in activities:
        if activity.avg_mph is not None:
            points.append({
                "date": activity.date,
                "name": activity.name,
                "activity_type": activity.activity_type,
                "value": activity.avg_mph,
            })

    points.sort(key=lambda x: x["date"])
    return points


def build_duration_over_time(activities: List[Activity]) -> List[Dict]:
    points = []
    for activity in activities:
        if activity.duration_minutes is not None:
            points.append({
                "date": activity.date,
                "name": activity.name,
                "activity_type": activity.activity_type,
                "value": activity.duration_minutes,
            })

    points.sort(key=lambda x: x["date"])
    return points


def build_weekly_load(activities: List[Activity]) -> List[Dict]:
    weekly_totals = defaultdict(float)

    for activity in activities:
        date_obj = datetime.fromisoformat(activity.date)
        iso_year, iso_week, _ = date_obj.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        weekly_totals[week_key] += activity.load_score or 0

    points = [{"week": week, "value": round(value, 2)} for week, value in weekly_totals.items()]
    points.sort(key=lambda x: x["week"])
    return points