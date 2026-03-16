from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, timedelta

from ..db.database import get_db
from ..db import crud, models

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    apartments = crud.get_all_apartments(db)
    prices = [a.current_price for a in apartments if a.current_price]
    avg_price = round(sum(prices) / len(prices), 2) if prices else 0

    last_session = (
        db.query(models.TelegramSession)
        .order_by(desc(models.TelegramSession.started_at))
        .first()
    )

    today = date.today()
    upcoming_events = crud.get_upcoming_events(db, today, today + timedelta(days=30))

    return {
        "total_apartments": len(apartments),
        "apartments_with_price": len(prices),
        "avg_current_price": avg_price,
        "last_session": (
            {
                "date": last_session.session_date.isoformat(),
                "status": last_session.status,
            }
            if last_session
            else None
        ),
        "upcoming_events": [
            {
                "name": e.name,
                "start_date": e.start_date.isoformat(),
                "end_date": e.end_date.isoformat(),
                "expected_impact_pct": e.expected_impact_pct,
            }
            for e in upcoming_events[:5]
        ],
    }
