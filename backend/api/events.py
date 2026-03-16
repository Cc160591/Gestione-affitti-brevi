from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from ..db.database import get_db
from ..db import crud, models

router = APIRouter(prefix="/api/events", tags=["events"])


class EventCreate(BaseModel):
    name: str
    event_type: Optional[str] = None
    start_date: date
    end_date: date
    zones_affected: Optional[List[str]] = None
    expected_impact_pct: Optional[float] = None
    source: Optional[str] = None
    notes: Optional[str] = None


def _event(e: models.MarketEvent) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "event_type": e.event_type,
        "start_date": e.start_date.isoformat(),
        "end_date": e.end_date.isoformat(),
        "zones_affected": e.zones_affected,
        "expected_impact_pct": e.expected_impact_pct,
        "actual_impact_pct": e.actual_impact_pct,
        "source": e.source,
        "notes": e.notes,
    }


@router.get("")
def list_events(db: Session = Depends(get_db)):
    events = (
        db.query(models.MarketEvent)
        .order_by(desc(models.MarketEvent.start_date))
        .all()
    )
    return [_event(e) for e in events]


@router.post("")
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    event = crud.create_market_event(db, data.model_dump())
    return _event(event)


@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.MarketEvent).filter(models.MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(404)
    db.delete(event)
    db.commit()
    return {"ok": True}
