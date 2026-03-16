from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..db.database import get_db
from ..db import crud, models

router = APIRouter(prefix="/api/apartments", tags=["apartments"])


class ApartmentUpdate(BaseModel):
    base_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    notes: Optional[str] = None


def _apt(a: models.Apartment) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "zone": a.zone,
        "address": a.address,
        "beds": a.beds,
        "bathrooms": a.bathrooms,
        "max_guests": a.max_guests,
        "base_price": a.base_price,
        "min_price": a.min_price,
        "max_price": a.max_price,
        "current_price": a.current_price,
        "airbnb_id": a.airbnb_id,
        "beds24_id": a.beds24_id,
        "is_active": a.is_active,
        "notes": a.notes,
    }


def _history(h: models.PriceHistory) -> dict:
    return {
        "id": h.id,
        "price_date": h.price_date.isoformat(),
        "price_before": h.price_before,
        "proposed_price": h.proposed_price,
        "approved_price": h.approved_price,
        "applied_price": h.applied_price,
        "competitor_avg": h.competitor_avg,
        "competitor_min": h.competitor_min,
        "competitor_max": h.competitor_max,
        "ai_reasoning": h.ai_reasoning,
        "user_feedback": h.user_feedback,
        "correction_delta": h.correction_delta,
        "was_autonomous": h.was_autonomous,
    }


@router.get("")
def list_apartments(db: Session = Depends(get_db)):
    return [_apt(a) for a in crud.get_all_apartments(db)]


@router.get("/{apartment_id}")
def get_apartment(apartment_id: int, db: Session = Depends(get_db)):
    apt = crud.get_apartment(db, apartment_id)
    if not apt:
        raise HTTPException(404, "Appartamento non trovato")
    return _apt(apt)


@router.patch("/{apartment_id}")
def update_apartment(
    apartment_id: int, data: ApartmentUpdate, db: Session = Depends(get_db)
):
    apt = crud.get_apartment(db, apartment_id)
    if not apt:
        raise HTTPException(404)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(apt, k, v)
    apt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(apt)
    return _apt(apt)


@router.get("/{apartment_id}/history")
def get_price_history(
    apartment_id: int, days: int = 30, db: Session = Depends(get_db)
):
    history = crud.get_recent_price_history(db, apartment_id, days)
    return [_history(h) for h in history]
