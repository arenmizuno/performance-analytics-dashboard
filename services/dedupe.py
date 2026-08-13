"""
Cross-source deduplication.

One session commonly lands in several providers at once: a watch pushes it to
Google Health and Withings, Strava picks it up, and a lift also lands in Hevy.
Every row is kept for provenance, but only one per real session is marked
primary, and that is what the dashboard reads.

Sessions are matched on **start time** rather than duration, because the
providers clock the same workout slightly differently - a Fitbit run and the
Strava copy of it routinely differ by a minute or two in length and by a few
minutes in start time. Start time is the reliable signal.

Preference is by richness of data for the kind of session:
  strength      -> Hevy (sets, reps, weight), then Strava
  anything else -> Strava (pace, distance, elevation), then the wearables
"""

from typing import Dict, List

import store
from db import get_connection

CARDIO_PRIORITY = ["strava", "withings", "google_health", "hevy"]
STRENGTH_PRIORITY = ["hevy", "strava", "withings", "google_health"]

# Two sessions starting within this window are the same session.
START_TOLERANCE_SECONDS = 20 * 60

# Fallback when a row has no start timestamp at all.
DURATION_TOLERANCE_MINUTES = 3


def _priority(activity) -> int:
    order = STRENGTH_PRIORITY if activity.activity_type == "strength" else CARDIO_PRIORITY
    try:
        return order.index(activity.source)
    except ValueError:
        return len(order)


def _family(activity) -> str:
    """
    Strength work and cardio are never the same session, even when they start
    minutes apart - lifting and then riding home is two activities, not one.
    Within cardio the labels are allowed to disagree, because the providers
    classify the same session differently (Fitbit walk vs Strava run).
    """
    return "strength" if activity.activity_type == "strength" else "cardio"


def _same_session(a, b) -> bool:
    if _family(a) != _family(b):
        return False

    if a.start_ts and b.start_ts:
        return abs(a.start_ts - b.start_ts) <= START_TOLERANCE_SECONDS

    da, db = a.duration_minutes or 0, b.duration_minutes or 0
    return bool(da and db and abs(da - db) <= DURATION_TOLERANCE_MINUTES)


def _cluster_by_time(activities: List) -> List[List]:
    """
    Sweep the whole timeline in timestamp order rather than bucketing by date.

    Bucketing by date was wrong: Strava dates an activity in local time while the
    wearables date theirs in UTC, so an evening session lands on different days in
    different sources and identical timestamps never got compared.
    """
    timed = sorted([a for a in activities if a.start_ts], key=lambda a: a.start_ts)
    untimed = [a for a in activities if not a.start_ts]

    # One sweep per family, and each cluster is measured from its own anchor so a
    # run of near-misses cannot chain into one oversized cluster.
    clusters: List[List] = []
    open_cluster = {}

    for activity in timed:
        family = _family(activity)
        current = open_cluster.get(family)

        if current and activity.start_ts - current[0].start_ts <= START_TOLERANCE_SECONDS:
            current.append(activity)
        else:
            new_cluster = [activity]
            clusters.append(new_cluster)
            open_cluster[family] = new_cluster

    # Anything without a timestamp still falls back to same-day + duration.
    by_date: Dict[str, List] = {}
    for a in untimed:
        by_date.setdefault(a.date, []).append(a)

    for same_day in by_date.values():
        for activity in same_day:
            for cluster in clusters:
                if not cluster[0].start_ts and any(_same_session(activity, o) for o in cluster):
                    cluster.append(activity)
                    break
            else:
                clusters.append([activity])

    return clusters


def rebuild_primary_flags() -> Dict:
    activities = store.get_activities(include_duplicates=True)

    primary, duplicate = [], []

    for cluster in _cluster_by_time(activities):
        if len(cluster) == 1:
            primary.append(cluster[0])
            continue

        winner = min(cluster, key=_priority)
        primary.append(winner)
        duplicate.extend(a for a in cluster if a is not winner)

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        "UPDATE activities SET is_primary = 1 WHERE source = ? AND id = ?",
        [(a.source, a.id) for a in primary],
    )
    cur.executemany(
        "UPDATE activities SET is_primary = 0 WHERE source = ? AND id = ?",
        [(a.source, a.id) for a in duplicate],
    )
    conn.commit()
    conn.close()

    dropped_by_source: Dict[str, int] = {}
    for a in duplicate:
        dropped_by_source[a.source] = dropped_by_source.get(a.source, 0) + 1

    return {
        "primary": len(primary),
        "duplicates": len(duplicate),
        "dropped_by_source": dropped_by_source,
    }
