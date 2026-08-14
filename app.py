import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from db import init_db
from store import init_store
from routes.activities import router as activities_router
from routes.graphs import router as graphs_router
from routes.sync import router as sync_router
from routes.personal_bests import router as personal_bests_router
from routes.metrics import router as metrics_router
from routes.settings import router as settings_router
from routes.assistant import router as assistant_router
from services.sync import sync_all
from services.personal_bests import seed_catalog
from services.strava import get_strava_auth_url, exchange_code_for_token
from services.google_health import (
    get_google_health_auth_url,
    exchange_code_for_token as exchange_google_code_for_token,
)
from services.withings import (
    get_withings_auth_url,
    exchange_code_for_token as exchange_withings_code_for_token,
)

logger = logging.getLogger(__name__)

SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
SYNC_ON_STARTUP = os.getenv("SYNC_ON_STARTUP", "true").lower() == "true"

scheduler = AsyncIOScheduler()


async def scheduled_sync():
    # A provider error must never take the server down. sync_all already isolates
    # per-source failures, but a few steps (e.g. the personal-best refresh) can
    # still raise, so the whole run is guarded: on startup the app comes up
    # regardless, and the hourly job lives to try again.
    try:
        results = await sync_all()
        logger.info("Scheduled sync: %s", results)
    except Exception:
        logger.exception("Sync run failed; continuing without it")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        scheduled_sync,
        "interval",
        minutes=SYNC_INTERVAL_MINUTES,
        id="sync_all",
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()

    if SYNC_ON_STARTUP:
        await scheduled_sync()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="Performance Analytics Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
init_store()
seed_catalog()

app.include_router(activities_router)
app.include_router(graphs_router)
app.include_router(sync_router)
app.include_router(personal_bests_router)
app.include_router(metrics_router)
app.include_router(settings_router)
app.include_router(assistant_router)

@app.get("/")
def root():
    return {"message": "Performance Analytics Dashboard API is running"}

@app.get("/strava/connect")
def strava_connect():
    return RedirectResponse(get_strava_auth_url())

@app.get("/strava/callback")
async def strava_callback(code: str, scope: str | None = None):
    data = await exchange_code_for_token(code, scope)
    return {
        "message": "Strava connected successfully",
        "athlete_id": data["athlete"]["id"],
        "scope": scope,
    }

@app.get("/google/connect")
def google_connect():
    return RedirectResponse(get_google_health_auth_url())

@app.get("/google/callback")
async def google_callback(code: str):
    data = await exchange_google_code_for_token(code)
    return {
        "message": "Google Health connected successfully",
        "account_id": data["account_id"],
        "scope": data["scope"],
    }

@app.get("/withings/connect")
def withings_connect():
    return RedirectResponse(get_withings_auth_url())

@app.get("/withings/callback")
async def withings_callback(code: str, state: str | None = None):
    data = await exchange_withings_code_for_token(code)
    return {
        "message": "Withings connected successfully",
        "account_id": data["account_id"],
        "scope": data["scope"],
    }