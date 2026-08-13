"""
Chat agent with tool calling.

Talks to any OpenAI-compatible /chat/completions endpoint, so the provider is a
config change rather than a code change. Defaults to Groq. No agent framework:
the loop below is the whole thing - call the model, run whatever tools it asks
for, hand the results back, repeat until it answers in prose.
"""

import json
import logging
import os
from datetime import date
from typing import Dict, List

import httpx
from dotenv import load_dotenv

import store
from services.assistant_tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

load_dotenv()

logger = logging.getLogger(__name__)

ASSISTANT_API_KEY = os.getenv("ASSISTANT_API_KEY") or os.getenv("GROQ_API_KEY")

ENV_BASE_URL = os.getenv("ASSISTANT_BASE_URL", "https://api.groq.com/openai/v1")
ENV_MODEL = os.getenv("ASSISTANT_MODEL", "llama-3.3-70b-versatile")


def active_config() -> Dict[str, str]:
    """
    Model and endpoint are read per request, with a stored setting taking
    precedence over .env. Switching models is therefore a live change - no
    restart, no code edit.
    """
    settings = store.get_settings()
    return {
        "model": settings.get("assistant_model") or ENV_MODEL,
        "base_url": (settings.get("assistant_base_url") or ENV_BASE_URL).rstrip("/"),
    }

# Each turn is one model call; the ceiling stops a malformed loop running away.
MAX_TOOL_ROUNDS = 6

# How many stored messages to replay. Bounds context growth on long threads.
HISTORY_LIMIT = 20

SYSTEM_PROMPT = """You are the assistant inside Aren's personal training dashboard.

Answer questions about his training, sleep, weight, steps and personal bests by \
calling the tools available to you. Never invent numbers: if a tool returns no \
data for a period, say so plainly rather than guessing.

Today is {today}. Work out concrete date ranges yourself before calling a tool - \
for "last month" pass explicit start_date and end_date rather than leaving them off.

Data notes worth knowing:
- Readiness is a derived score, not a figure from a wearable. It blends last \
night's sleep (60%) with acute-to-chronic training load (40%).
- Weight comes from a Withings scale; steps and sleep from a Fitbit via Google \
Health; runs and rides from Strava; lifts from Hevy.
- Sessions recorded by several apps at once are deduplicated, so counts reflect \
real sessions.

Be brief and concrete. Lead with the number that answers the question, then at \
most a sentence or two of context. Use imperial units, matching the dashboard."""


def is_configured() -> bool:
    return bool(ASSISTANT_API_KEY)


def _run_tool(name: str, arguments: str) -> Dict:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"error": f"Unknown tool '{name}'"}

    try:
        kwargs = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return {"error": f"Could not parse arguments for {name}: {arguments!r}"}

    try:
        return fn(**kwargs)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": f"{type(exc).__name__}: {exc}"}


async def _complete(client: httpx.AsyncClient, messages: List[Dict], config: Dict) -> Dict:
    response = await client.post(
        f"{config['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {ASSISTANT_API_KEY}"},
        json={
            "model": config["model"],
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "temperature": 0.2,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


async def chat(message: str, conversation_id: str | None = None) -> Dict:
    if not is_configured():
        raise RuntimeError(
            "No assistant API key configured. Set ASSISTANT_API_KEY (or GROQ_API_KEY) in .env."
        )

    if not conversation_id or not store.conversation_exists(conversation_id):
        conversation_id = store.create_conversation()

    # History comes from the store, not the client, and is capped so a long
    # conversation cannot grow past the model's context window.
    history = store.get_messages(conversation_id, limit=HISTORY_LIMIT)

    messages: List[Dict] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}
    ]
    for turn in history:
        if turn["role"] in ("user", "assistant") and turn["content"]:
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    store.add_message(conversation_id, "user", message)

    tool_trace = []
    config = active_config()

    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await _complete(client, messages, config)
            tool_calls = reply.get("tool_calls") or []

            if not tool_calls:
                answer = reply.get("content") or ""
                store.add_message(conversation_id, "assistant", answer, tool_trace or None)
                return {
                    "reply": answer,
                    "conversation_id": conversation_id,
                    "tools_used": tool_trace,
                    "model": config["model"],
                }

            messages.append(reply)

            for call in tool_calls:
                fn = call["function"]
                result = _run_tool(fn["name"], fn.get("arguments"))
                tool_trace.append({"name": fn["name"], "arguments": fn.get("arguments")})

                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": fn["name"],
                    "content": json.dumps(result, default=str),
                })

    exhausted = "I looked that up several times without settling on an answer. Try narrowing the question."
    store.add_message(conversation_id, "assistant", exhausted, tool_trace or None)
    return {
        "reply": exhausted,
        "conversation_id": conversation_id,
        "tools_used": tool_trace,
        "model": config["model"],
    }


async def list_models() -> Dict:
    """
    Ask the provider what it serves. Model line-ups change often, so a live list
    beats anything hardcoded here.
    """
    config = active_config()
    base = {"current": config["model"], "base_url": config["base_url"]}

    if not is_configured():
        return {"source": "unconfigured", "models": [], **base}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{config['base_url']}/models",
                headers={"Authorization": f"Bearer {ASSISTANT_API_KEY}"},
            )
            response.raise_for_status()
            models = sorted(m["id"] for m in response.json().get("data", []))
        return {"source": "provider", "models": models, **base}
    except Exception as exc:
        logger.warning("Could not list models: %s", exc)
        return {"source": "error", "models": [], "error": str(exc), **base}
