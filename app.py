from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from db import init_db
from routes.activities import router as activities_router
from routes.graphs import router as graphs_router
from services.strava import get_strava_auth_url, exchange_code_for_token

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