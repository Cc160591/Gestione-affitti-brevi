from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db.database import get_db
from ..db import models

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session(s: models.TelegramSession, full: bool = False) -> dict:
    d = {
        "id": s.id,
        "session_date": s.session_date.isoformat(),
        "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "approved_at": s.approved_at.isoformat() if s.approved_at else None,
        "applied_at": s.applied_at.isoformat() if s.applied_at else None,
        "proposed_prices": s.proposed_prices,
        "approved_prices": s.approved_prices,
        "n_proposed": len(s.proposed_prices) if s.proposed_prices else 0,
        "n_approved": len(s.approved_prices) if s.approved_prices else 0,
    }
    if full:
        d["conversation_log"] = s.conversation_log
    return d


@router.get("")
def list_sessions(limit: int = 20, db: Session = Depends(get_db)):
    sessions = (
        db.query(models.TelegramSession)
        .order_by(desc(models.TelegramSession.started_at))
        .limit(limit)
        .all()
    )
    return [_session(s) for s in sessions]


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = (
        db.query(models.TelegramSession)
        .filter(models.TelegramSession.id == session_id)
        .first()
    )
    if not s:
        raise HTTPException(404)
    return _session(s, full=True)
