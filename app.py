from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from db import init_db
from routes.activities import router as activities_router
from routes.graphs import router as graphs_router
from services.strava import get_strava_auth_url, exchange_code_for_token
from services.google_health import (
    get_google_health_auth_url,
    exchange_code_for_token as exchange_google_code_for_token,
)
from services.withings import (
    get_withings_auth_url,
    exchange_code_for_token as exchange_withings_code_for_token,
)

app = FastAPI(title="Performance Analytics Dashboard")

init_db()

app.include_router(activities_router)
app.include_router(graphs_router)

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