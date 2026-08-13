from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import store
from services.personal_bests import (
    PB_CATALOG,
    refresh_running_bests,
    refresh_strength_bests,
    seed_catalog,
)

router = APIRouter(prefix="/personal-bests", tags=["personal-bests"])

# Categories that carry automatic derivation. Anything else is user-defined.
DERIVED_CATEGORIES = {"running", "strength"}


class PersonalBestUpdate(BaseModel):
    value: Optional[float] = None
    display_value: Optional[str] = None
    unit: Optional[str] = None
    date_achieved: Optional[str] = None


class PersonalBestCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    value: Optional[float] = None
    display_value: Optional[str] = None
    unit: Optional[str] = None
    date_achieved: Optional[str] = None


@router.get("")
def list_personal_bests(category: Optional[str] = Query(default=None)):
    bests = store.get_personal_bests(category=category)

    grouped = {}
    for pb in bests:
        grouped.setdefault(pb["category"], []).append(pb)

    return {
        "count": len(bests),
        "categories": grouped,
        "known_categories": sorted(set(list(PB_CATALOG) + list(grouped))),
        "derived_categories": sorted(DERIVED_CATEGORIES),
    }


@router.post("")
def create_personal_best(payload: PersonalBestCreate):
    """Add an entry - an event in an existing category, or a whole new category."""
    category = payload.category.strip().lower()
    name = payload.name.strip()

    if store.get_personal_best(category, name):
        raise HTTPException(status_code=409, detail=f"'{name}' already exists in {category}")

    store.upsert_personal_best(
        category=category,
        name=name,
        value=payload.value,
        display_value=payload.display_value,
        unit=payload.unit,
        date_achieved=payload.date_achieved,
        source="manual" if (payload.display_value or payload.value is not None) else None,
    )

    return {"message": "Created", "category": category, "name": name}


@router.put("/{category}/{name}")
def update_personal_best(category: str, name: str, payload: PersonalBestUpdate):
    category = category.lower()

    if not store.get_personal_best(category, name):
        raise HTTPException(status_code=404, detail=f"'{name}' not found in {category}")

    cleared = payload.display_value is None and payload.value is None

    store.upsert_personal_best(
        category=category,
        name=name,
        value=payload.value,
        display_value=payload.display_value,
        unit=payload.unit,
        date_achieved=payload.date_achieved,
        # Clearing an entry hands it back to automatic derivation.
        source=None if cleared else "manual",
    )

    return {
        "message": "Reset to automatic" if cleared else "Updated",
        "category": category,
        "name": name,
        "source": None if cleared else "manual",
    }


@router.delete("/{category}/{name}")
def delete_personal_best(category: str, name: str):
    if not store.delete_personal_best(category, name):
        raise HTTPException(status_code=404, detail=f"'{name}' not found in {category}")
    return {"message": "Deleted", "category": category, "name": name}


@router.post("/seed")
def seed():
    seed_catalog()
    return {"message": "Catalog seeded", "count": len(store.get_personal_bests())}


@router.post("/refresh-strength")
async def refresh_strength():
    return await refresh_strength_bests()


@router.post("/refresh-running")
def refresh_running():
    return refresh_running_bests()
