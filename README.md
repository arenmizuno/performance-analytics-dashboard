# Performance Analytics Dashboard

A personal training dashboard that pulls Strava, Hevy, Withings and Google Health into one local store and puts the whole picture on one page, including a chat assistant that answers questions from your own data.

## Problem

Training data ends up scattered across apps. Runs and rides sit in Strava, lifts in Hevy, body weight on a Withings scale, sleep and steps on a Fitbit. Each app shows its own slice and none of them shows the week as a whole.

Merging them naively makes things worse, because a watch pushes the same session to several services at once. One 32 minute lift can appear four times, which inflates weekly load roughly threefold. This project syncs all four providers into a single SQLite store, matches sessions across sources by start time so each one is counted once, and serves the result as a dashboard plus a tool-calling assistant.

## Repo structure

```
app.py         # FastAPI app, hourly scheduler, OAuth connect and callback routes
db.py          # SQLite connection and OAuth token storage
store.py       # Data layer: activities, daily metrics, personal bests, settings, conversations
manage.py      # Admin CLI (switch the assistant model)
models/        # Shared Activity model every source normalises into
routes/        # API endpoints: activities, graphs, metrics, personal bests, sync, settings, assistant
services/      # Provider clients, normalisation, dedupe, metrics, readiness, assistant tool loop
frontend/      # React and Vite dashboard: Dashboard, Activities and Assistant tabs
```

## Tech stack

Backend is FastAPI with SQLite, httpx for provider calls, APScheduler for the hourly sync, and Pydantic for the shared model. Frontend is React 18 with Vite, styled as a dark single-page dashboard. Charts are hand written SVG rather than a chart library, so mark sizing, tooltips and the colour palette stay under direct control. The assistant talks to any OpenAI compatible chat endpoint and defaults to Groq.

## Data

Everything comes from the four provider APIs over OAuth or an API key and lands in `app.db`, a local SQLite file. Nothing is bundled in the repo: `app.db` is gitignored, the data is tied to my own accounts, and a fresh clone starts empty and fills on the first sync.

Current store is roughly 980 activities going back to November 2023, split across Strava, Hevy and Google Health, plus about 480 daily metric rows and a small set of hand checked personal bests. Activities normalise into one shared `Activity` model regardless of source; daily metrics are stored long, one row per date and metric.

Each metric comes from one source, chosen for whichever provider measures it best:

| Metric | Source |
| --- | --- |
| Runs, rides, hikes | Strava |
| Lifts | Hevy |
| Walks and other sessions | Google Health |
| Body weight | Withings |
| Steps, sleep, energy, resting HR, HRV | Google Health |
| Active zone minutes | Summed from synced activities |
| Readiness | Derived locally |

History depth varies a lot by metric, because each provider only holds what its hardware recorded. Activities reach back years, while active zone minutes, sleep, resting HR and HRV only begin in late July 2026, and daily steps reach back only as far as the Fitbit record.

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

Syncs are incremental by default, refetching only since the last run. Add `?full=true` to rebuild from the full history. A failing provider is logged and skipped rather than taking the server down, so startup and the hourly job both survive it. Reads hit SQLite rather than the provider APIs, so the dashboard loads in milliseconds and keeps working when a provider is down.

The assistant answers from the local store through ten tools: weight, steps, sleep, energy, resting HR, HRV, active zone minutes, readiness, personal bests and activities. Switch the model without restarting:

```bash
python manage.py model --list
python manage.py model openai/gpt-oss-120b
```

Model choice matters more than it looks. Tool calling has to be reliable, and smaller instruct models are not. `openai/gpt-oss-120b` is the current default because it answers correctly every time in testing, where `llama-3.3-70b-versatile` produced a malformed tool call on roughly one question in three.

## Future steps

Personal bests currently come from whole activities, so a 400m best cannot be found. Parsing Strava's lap and stream data would pick up efforts inside a longer session. The assistant replays the last 20 messages of a thread, so a summarisation step would let long conversations keep their early context. Resting heart rate and HRV are now synced and charted but readiness still ignores them, so folding them into the score is the obvious next change.

## Limitations

Single user and no authentication. It assumes one person's accounts and is meant to run on localhost, so do not expose it to a network as is.

Readiness is a derived score, not a measurement. No connected provider reports one, so it blends last night's sleep at 60 percent with an acute to chronic training load ratio at 40 percent. It is a transparent heuristic, not a physiological model.

Deduplication and personal best detection are both heuristics. Sessions are treated as the same when they start within 20 minutes of each other and belong to the same family, where strength never matches cardio, so two genuinely separate cardio sessions started close together will be merged. Bests match on distance within a tolerance band running from 3 percent short to 10 percent long, which means a long training run can register as a race. Hand entered bests are never overwritten, so correcting one makes it stick.

The assistant depends on the model emitting well formed tool calls, which smaller models do not reliably do. A malformed call is retried once at a higher temperature, and after that the request fails with a message naming the model. Switching to a stronger model is the fix, not rephrasing the question. The free Groq tier also rate limits by the minute, so a burst of questions returns a 429 until it clears. Answers are only as good as the sync, since every tool reads the local store rather than the provider APIs.
