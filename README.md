# Performance Analytics Dashboard

A personal training dashboard that pulls Strava, Hevy, Withings and Google Health into one local store and puts the whole picture on one page, including a chat assistant that answers questions from your own data.

## Problem

Training data ends up scattered across apps. Runs and rides sit in Strava, lifts in Hevy, body weight on a Withings scale, sleep and steps on a Fitbit. Each app shows its own slice and none of them shows the week as a whole.

Merging them naively makes things worse, because a watch pushes the same session to several services at once. One 32 minute lift can appear four times, which inflates weekly load roughly threefold. This project syncs all four providers into a single SQLite store, matches sessions across sources by start time so each one is counted once, and serves the result as a dashboard plus a tool-calling assistant.

## Repo structure

```
app.py                      FastAPI app, scheduler, OAuth connect and callback routes
db.py                       SQLite connection and OAuth token storage
store.py                    Data layer: activities, daily metrics, personal bests, settings, conversations
manage.py                   Admin CLI (switch the assistant model)
models/activity.py          Shared Activity model every source normalises into
routes/
  activities.py             Activity feed with filters
  graphs.py                 Time series for the charts
  metrics.py                Daily metrics, active zone minutes, consistency, date range
  personal_bests.py         Personal best CRUD and refresh
  sync.py                   Manual sync trigger and status
  settings.py               Editable goals and assistant config
  assistant.py              Chat and conversation history
services/
  strava.py                 Strava OAuth and activity fetch
  hevy.py                   Hevy API key auth, full and incremental fetch
  withings.py               Withings OAuth and body weight
  google_health.py          Google Health OAuth, exercise, sleep, daily step rollups
  normalize.py              Per source normalisation into Activity
  dedupe.py                 Cross source session matching
  sync.py                   Source registry and sync orchestration
  metrics.py                Load scoring and chart series
  readiness.py              Derived readiness score
  personal_bests.py         Derivation from Strava runs and Hevy sets
  assistant.py              Tool calling loop
  assistant_tools.py        The six tools the assistant can call
frontend/
  src/tabs/                 Dashboard, Activities, Assistant
  src/components/           Charts, consistency strip, personal bests, range control
```

## Tech stack

Backend is FastAPI with SQLite, httpx for provider calls, APScheduler for the hourly sync, and Pydantic for the shared model. Frontend is React 18 with Vite. Charts are hand written SVG rather than a chart library, so mark sizing, tooltips and the colour palette stay under direct control. The assistant talks to any OpenAI compatible chat endpoint and defaults to Groq.

## Setup

```bash
pip install -r requirements.txt
npm --prefix frontend install
```

Credentials go in `.env` at the repo root. It is gitignored.

```
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REDIRECT_URI=http://127.0.0.1:8000/strava/callback

WITHINGS_CLIENT_ID=
WITHINGS_CLIENT_SECRET=
WITHINGS_REDIRECT_URI=http://127.0.0.1:8000/withings/callback

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/google/callback

HEVY_API_KEY=
ASSISTANT_API_KEY=
```

Each provider needs an app registered on its developer site, with the callback URL matching the value above exactly. Hevy is just an API key from Settings then Developer in its web app, and needs a Pro subscription. The Google Health scopes are restricted, so add your own account as a test user on the OAuth consent screen.

Start the server, then visit `/strava/connect`, `/withings/connect` and `/google/connect` once each to authorise. Tokens are stored locally and refreshed automatically.

Each metric comes from one source, chosen for whichever provider measures it best:

| Metric | Source |
| --- | --- |
| Runs, rides, hikes | Strava |
| Lifts | Hevy |
| Walks and other sessions | Google Health |
| Body weight | Withings |
| Steps, sleep and stages | Google Health |
| Readiness | Derived locally |

## Usage

```bash
uvicorn app:app --reload --port 8000
npm --prefix frontend run dev
```

The dashboard is at `http://localhost:5173`. Vite proxies `/api` to the backend, so only the frontend port needs opening.

A sync runs at startup and then hourly. To trigger one by hand:

```bash
curl -X POST "http://127.0.0.1:8000/sync"
```

Syncs are incremental by default, refetching only since the last run. Add `?full=true` to rebuild from the full history. Reads hit SQLite rather than the provider APIs, so the dashboard loads in milliseconds and keeps working when a provider is down.

Switch the assistant model without restarting:

```bash
python manage.py model --list
python manage.py model llama-3.1-8b-instant
```

## Future steps

Personal bests currently come from whole activities, so a 400m best cannot be found. Parsing Strava's lap and stream data would pick up efforts inside a longer session. The assistant replays the last 20 messages of a thread, so a summarisation step would let long conversations keep their early context. Sleep and readiness would benefit from a resting heart rate signal, which Google Health exposes but the sync does not yet read.

## Limitations

Single user and no authentication. It assumes one person's accounts and is meant to run on localhost, so do not expose it to a network as is.

Readiness is a derived score, not a measurement. No connected provider reports one, so it blends last night's sleep at 60 percent with an acute to chronic training load ratio at 40 percent. It is a transparent heuristic, not a physiological model.

Deduplication is a heuristic. Sessions are treated as the same when they start within 20 minutes of each other and belong to the same family, where strength never matches cardio. Two genuinely separate cardio sessions started close together will be merged.

Personal best detection matches on distance within a tolerance band, so a long training run can register as a race. A trail marathon logged 2 percent short of the nominal distance is counted, which is usually right and occasionally is not. Hand entered bests are never overwritten, so correcting one makes it stick.

Coverage is bounded by what each provider actually holds. Active zone minutes only exist from late July 2026 because heart rate zone data starts there, and daily steps reach back only as far as the Fitbit history.

The assistant has been tested against a stubbed model rather than a live one. The tool layer and the agent loop are verified, but prompt behaviour with a real model has not been exercised.
