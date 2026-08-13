import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

import store
from services.metrics import attach_load_scores
from services.strava import get_strava_activities, is_strava_connected
from services.hevy import get_hevy_activities, get_hevy_changes, is_hevy_connected
from services.withings import get_withings_weight, is_withings_connected
from services.google_health import (
    get_google_health_activities,
    get_google_sleep,
    get_google_steps,
    is_google_health_connected,
)
from services.readiness import compute_readiness
from services.dedupe import rebuild_primary_flags
from services.personal_bests import refresh_running_bests, refresh_strength_bests

logger = logging.getLogger(__name__)

# Re-fetch a little before the last sync so edits to recent entries are not missed.
INCREMENTAL_OVERLAP = timedelta(days=2)


@dataclass
class SourceAdapter:
    fetch: Callable
    is_connected: Callable
    fetch_changes: Optional[Callable] = None


# Withings is deliberately absent: it contributes body metrics only. Its workout
# feed just mirrors sessions the watch already sends to Strava and Google.
SOURCES = {
    "strava": SourceAdapter(get_strava_activities, is_strava_connected),
    "hevy": SourceAdapter(get_hevy_activities, is_hevy_connected, get_hevy_changes),
    "google_health": SourceAdapter(get_google_health_activities, is_google_health_connected),
}


def _incremental_since(name: str, full: bool) -> Optional[datetime]:
    if full:
        return None

    state = store.get_sync_state().get(name)
    if not state or state.get("status") != "ok" or not state.get("last_synced_at"):
        return None

    last = datetime.fromtimestamp(state["last_synced_at"], tz=timezone.utc)
    return last - INCREMENTAL_OVERLAP


async def sync_source(name: str, full: bool = False) -> Dict:
    adapter = SOURCES[name]

    if not adapter.is_connected():
        store.set_sync_state(name, "not_connected", 0)
        return {"status": "not_connected", "written": 0}

    since = _incremental_since(name, full)
    mode = "full" if since is None else "incremental"

    try:
        deleted = 0
        if since and adapter.fetch_changes:
            activities, deleted_ids = await adapter.fetch_changes(since)
            deleted = store.delete_activities(name, deleted_ids)
        else:
            activities = await adapter.fetch(since=since)
    except Exception as exc:
        logger.exception("Sync failed for %s", name)
        store.set_sync_state(name, "error", 0, str(exc))
        return {"status": "error", "written": 0, "error": str(exc)}

    written = store.upsert_activities(attach_load_scores(activities))
    store.set_sync_state(name, "ok", written)

    return {"status": "ok", "mode": mode, "written": written, "deleted": deleted}


# Withings supplies body metrics only; the watch is the better step counter.
METRIC_FETCHERS = {
    "weight_lb": (get_withings_weight, is_withings_connected),
    "steps": (get_google_steps, is_google_health_connected),
    "sleep_minutes": (get_google_sleep, is_google_health_connected),
}


async def sync_metrics(full: bool = False) -> Dict:
    results = {}

    for metric, (fetch, is_connected) in METRIC_FETCHERS.items():
        if not is_connected():
            results[metric] = {"status": "not_connected", "written": 0}
            continue

        since = _incremental_since(f"metric:{metric}", full)

        try:
            points = await fetch(since=since)
        except Exception as exc:
            logger.exception("Metric sync failed for %s", metric)
            store.set_sync_state(f"metric:{metric}", "error", 0, str(exc))
            results[metric] = {"status": "error", "written": 0, "error": str(exc)}
            continue

        written = store.upsert_daily_metrics(points)
        store.set_sync_state(f"metric:{metric}", "ok", written)
        results[metric] = {"status": "ok", "written": written}

    # Readiness is derived from what the others just wrote, so it runs last.
    readiness = compute_readiness()
    results["readiness"] = {"status": "ok", "written": store.upsert_daily_metrics(readiness)}
    store.set_sync_state("metric:readiness", "ok", len(readiness))

    return results


async def sync_all(source: Optional[str] = None, full: bool = False) -> Dict:
    targets = [source.lower()] if source else list(SOURCES)
    results = {
        name: await sync_source(name, full=full)
        for name in targets if name in SOURCES
    }

    results["dedupe"] = rebuild_primary_flags()
    results["personal_bests"] = {
        "running": refresh_running_bests(),
        "strength": await refresh_strength_bests(),
    }

    if not source:
        results["metrics"] = await sync_metrics(full=full)

    return results
