from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import store

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    weekly_azm_goal: Optional[int] = Field(default=None, ge=1, le=5000)
    weekly_cardio_minutes_goal: Optional[int] = Field(default=None, ge=1, le=5000)
    # Empty string clears the override and falls back to .env.
    assistant_model: Optional[str] = Field(default=None, max_length=120)
    assistant_base_url: Optional[str] = Field(default=None, max_length=300)


@router.get("")
def get_settings():
    return {"settings": store.get_settings(), "defaults": store.DEFAULT_SETTINGS}


@router.put("")
def update_settings(payload: SettingsUpdate):
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(status_code=400, detail="No settings provided")

    return {"settings": store.set_settings(values)}
