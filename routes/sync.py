from typing import Optional
from fastapi import APIRouter, Query

import store
from services.sync import sync_all

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("")
async def run_sync(
    source: Optional[str] = Query(default=None),
    full: bool = Query(default=False, description="Ignore last sync time and refetch the full window"),
):
    results = await sync_all(source=source, full=full)
    return {"results": results}


@router.get("/status")
def sync_status():
    return {"sync": store.get_sync_state()}
