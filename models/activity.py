from pydantic import BaseModel
from typing import Optional


class Activity(BaseModel):
    id: str
    source: str
    activity_type: str
    name: str
    date: str
    duration_minutes: Optional[float] = None
    distance_miles: Optional[float] = None
    avg_mph: Optional[float] = None
    elevation_gain_ft: Optional[float] = None
    calories: Optional[float] = None
    load_score: Optional[float] = None