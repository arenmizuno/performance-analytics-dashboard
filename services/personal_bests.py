from typing import Dict, List, Optional

import store
from services.hevy import get_hevy_raw_workouts, is_hevy_connected

KG_TO_LB = 2.20462

# The reference list from the build spec. Entries start empty and are either
# entered by hand or, for lifts, derived from Hevy.
PB_CATALOG = {
    "running": ["400m", "5K", "10K", "Half Marathon", "Full Marathon"],
    "triathlon": ["Olympic", "Half Ironman", "Full Ironman"],
    "swim": ["100y Free", "200y Free", "500y Free", "200y IM"],
    "strength": [
        "Max Dumbbell Bench",
        "Dumbbell Incline",
        "Lat Pulldown",
        "Row",
        "Pull-ups",
        "Dips",
    ],
}

# Maps each strength PB onto the exercise titles actually present in the Hevy log.
HEVY_LIFT_MAP = {
    "Max Dumbbell Bench": ["Bench Press (Dumbbell)"],
    "Dumbbell Incline": ["Incline Bench Press (Dumbbell)"],
    "Lat Pulldown": ["Lat Pulldown (Cable)", "Single Arm Lat Pulldown"],
    # Kept to dumbbell only: machine and cable rows load very differently and
    # are not comparable against the other dumbbell entries here.
    "Row": ["Dumbbell Row"],
    "Pull-ups": ["Pull Up"],
    "Dips": ["Triceps Dip"],
}

# Lifts scored by reps when unweighted.
BODYWEIGHT_LIFTS = {"Pull-ups", "Dips"}


# Units where a smaller number is the better result.
LOWER_IS_BETTER = {"time", "seconds"}


def is_improvement(existing: Dict | None, value: float | None, unit: str | None) -> bool:
    """
    Whether a freshly derived value should replace what is already stored.

    A hand-entered best is authoritative and is never overwritten - the user has
    made a call the raw data cannot make (which run was really a race, whether a
    trail marathon counts). Otherwise the value only moves when it is genuinely
    better, so a derived best never regresses.
    """
    if value is None:
        return False
    if not existing or existing.get("value") is None:
        return True
    if existing.get("source") == "manual":
        return False

    if (unit or existing.get("unit")) in LOWER_IS_BETTER:
        return value < existing["value"]
    return value > existing["value"]


def seed_catalog() -> None:
    for category, names in PB_CATALOG.items():
        for name in names:
            store.upsert_personal_best(category, name, only_if_missing=True)


def _best_for_titles(workouts: List[dict], titles: List[str], bodyweight: bool) -> Optional[Dict]:
    wanted = {t.lower() for t in titles}

    best_weight_kg = 0.0
    best_weight_reps = 0
    best_weight_date = None

    best_reps = 0
    best_reps_date = None

    for workout in workouts:
        date = (workout.get("start_time") or "")[:10]

        for exercise in workout.get("exercises") or []:
            if (exercise.get("title") or "").lower() not in wanted:
                continue

            for s in exercise.get("sets") or []:
                reps = s.get("reps") or 0
                weight = s.get("weight_kg") or 0

                if not reps:
                    continue

                if weight > best_weight_kg:
                    best_weight_kg = weight
                    best_weight_reps = reps
                    best_weight_date = date

                if reps > best_reps:
                    best_reps = reps
                    best_reps_date = date

    if bodyweight and not best_weight_kg:
        if not best_reps:
            return None
        return {
            "value": float(best_reps),
            "display_value": f"{best_reps} reps",
            "unit": "reps",
            "date_achieved": best_reps_date,
        }

    if not best_weight_kg:
        return None

    lb = round(best_weight_kg * KG_TO_LB, 1)
    return {
        "value": lb,
        "display_value": f"{lb:g} lb x {best_weight_reps}",
        "unit": "lb",
        "date_achieved": best_weight_date,
    }


RUN_DISTANCES = {
    "400m": 0.248548,
    "5K": 3.106856,
    "10K": 6.213712,
    "Half Marathon": 13.109375,
    "Full Marathon": 26.218750,
}

# GPS routinely under- or over-measures, especially on trail. Accept a run whose
# recorded distance lands in this band around the nominal distance.
DISTANCE_TOLERANCE = (0.97, 1.10)


def _format_duration(minutes: float) -> str:
    total = int(round(minutes * 60))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def refresh_running_bests() -> Dict:
    runs = [
        a for a in store.get_activities(include_duplicates=True)
        if a.source == "strava" and a.activity_type == "run"
        and a.distance_miles and a.duration_minutes
    ]

    existing = {pb["name"]: pb for pb in store.get_personal_bests("running")}

    updated = {}
    for name, target in RUN_DISTANCES.items():
        low, high = target * DISTANCE_TOLERANCE[0], target * DISTANCE_TOLERANCE[1]
        matches = [a for a in runs if low <= a.distance_miles <= high]
        if not matches:
            continue

        best = min(matches, key=lambda a: a.duration_minutes)

        if not is_improvement(existing.get(name), round(best.duration_minutes, 2), "time"):
            continue

        store.upsert_personal_best(
            category="running",
            name=name,
            value=round(best.duration_minutes, 2),
            display_value=_format_duration(best.duration_minutes),
            unit="time",
            date_achieved=best.date,
            source="strava",
        )
        updated[name] = {
            "time": _format_duration(best.duration_minutes),
            "date": best.date,
            "distance_miles": best.distance_miles,
            "activity": best.name,
            "candidates": len(matches),
        }

    return {"status": "ok", "scanned_runs": len(runs), "updated": updated}


async def refresh_strength_bests() -> Dict:
    if not is_hevy_connected():
        return {"status": "not_connected", "updated": {}}

    workouts = await get_hevy_raw_workouts()
    existing = {pb["name"]: pb for pb in store.get_personal_bests("strength")}

    updated = {}
    for name, titles in HEVY_LIFT_MAP.items():
        best = _best_for_titles(workouts, titles, bodyweight=name in BODYWEIGHT_LIFTS)
        if not best:
            continue

        if not is_improvement(existing.get(name), best["value"], best["unit"]):
            continue

        store.upsert_personal_best(
            category="strength",
            name=name,
            source="hevy",
            **best,
        )
        updated[name] = best

    return {"status": "ok", "scanned_workouts": len(workouts), "updated": updated}
