import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import store
from services.assistant import active_config, chat, is_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None


@router.get("/status")
def status():
    # The model is reported for display only; it is changed on the backend.
    return {"configured": is_configured(), **active_config()}


@router.get("/conversations")
def list_conversations(limit: int = Query(default=30, ge=1, le=200)):
    return {"conversations": store.get_conversations(limit=limit)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    if not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "messages": store.get_messages(conversation_id),
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    if not store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Deleted", "conversation_id": conversation_id}


@router.post("/chat")
async def post_chat(payload: ChatRequest):
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Assistant is not configured. Set ASSISTANT_API_KEY in .env and restart.",
        )

    try:
        return await chat(payload.message, payload.conversation_id)
    except httpx.HTTPStatusError as exc:
        logger.exception("Assistant provider error")
        raise HTTPException(
            status_code=502,
            detail=f"Model provider returned {exc.response.status_code}.",
        )
    except Exception as exc:
        logger.exception("Assistant failed")
        raise HTTPException(status_code=500, detail=str(exc))
