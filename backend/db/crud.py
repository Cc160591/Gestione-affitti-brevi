from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime
from typing import Optional
from . import models


# ─────────────────────────────────────────
# APARTMENTS
# ─────────────────────────────────────────

def get_all_apartments(db: Session) -> list[models.Apartment]:
    return db.query(models.Apartment).filter(models.Apartment.is_active == True).all()


def get_apartment(db: Session, apartment_id: int) -> Optional[models.Apartment]:
    return db.query(models.Apartment).filter(models.Apartment.id == apartment_id).first()


def update_apartment_current_price(db: Session, apartment_id: int, price: float) -> None:
    db.query(models.Apartment).filter(models.Apartment.id == apartment_id).update(
        {"current_price": price, "updated_at": datetime.utcnow()}
    )
    db.commit()


# ─────────────────────────────────────────
# PRICING RULES
# ─────────────────────────────────────────

def get_rules_for_apartment(db: Session, apartment_id: int) -> list[models.PricingRule]:
    return (
        db.query(models.PricingRule)
        .filter(
            models.PricingRule.apartment_id == apartment_id,
            models.PricingRule.is_active == True,
        )
        .order_by(models.PricingRule.priority)
        .all()
    )


# ─────────────────────────────────────────
# COMPETITOR SNAPSHOTS
# ─────────────────────────────────────────

def get_latest_competitor_snapshot(
    db: Session, zone: str, snapshot_date: date
) -> Optional[models.CompetitorSnapshot]:
    return (
        db.query(models.CompetitorSnapshot)
        .filter(
            models.CompetitorSnapshot.zone == zone,
            models.CompetitorSnapshot.snapshot_date == snapshot_date,
        )
        .first()
    )


def save_competitor_snapshot(db: Session, data: dict) -> models.CompetitorSnapshot:
    snapshot = models.CompetitorSnapshot(**data)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


# ─────────────────────────────────────────
# MARKET EVENTS
# ─────────────────────────────────────────

def get_upcoming_events(
    db: Session, start_date: date, end_date: date
) -> list[models.MarketEvent]:
    return (
        db.query(models.MarketEvent)
        .filter(
            models.MarketEvent.end_date >= start_date,
            models.MarketEvent.start_date <= end_date,
        )
        .all()
    )


def create_market_event(db: Session, data: dict) -> models.MarketEvent:
    event = models.MarketEvent(**data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ─────────────────────────────────────────
# TELEGRAM SESSIONS
# ─────────────────────────────────────────

def create_session(db: Session, chat_id: str, session_date: date) -> models.TelegramSession:
    session = models.TelegramSession(
        chat_id=chat_id,
        session_date=session_date,
        status=models.SessionStatus.pending,
        conversation_log=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_active_session(db: Session, chat_id: str) -> Optional[models.TelegramSession]:
    return (
        db.query(models.TelegramSession)
        .filter(
            models.TelegramSession.chat_id == chat_id,
            models.TelegramSession.status == models.SessionStatus.pending,
        )
        .order_by(desc(models.TelegramSession.started_at))
        .first()
    )


def update_session(db: Session, session_id: int, data: dict) -> None:
    db.query(models.TelegramSession).filter(
        models.TelegramSession.id == session_id
    ).update(data)
    db.commit()


def append_to_conversation_log(
    db: Session, session_id: int, role: str, content: str
) -> None:
    session = db.query(models.TelegramSession).filter(
        models.TelegramSession.id == session_id
    ).first()
    if session:
        log = session.conversation_log or []
        log.append({"role": role, "content": content, "ts": datetime.utcnow().isoformat()})
        session.conversation_log = log
        db.commit()


# ─────────────────────────────────────────
# PRICE HISTORY
# ─────────────────────────────────────────

def create_price_history_entries(
    db: Session,
    session_id: int,
    entries: list[dict],
) -> None:
    for entry in entries:
        record = models.PriceHistory(session_id=session_id, **entry)
        db.add(record)
    db.commit()


def get_recent_price_history(
    db: Session, apartment_id: int, days: int = 30
) -> list[models.PriceHistory]:
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    return (
        db.query(models.PriceHistory)
        .filter(
            models.PriceHistory.apartment_id == apartment_id,
            models.PriceHistory.price_date >= cutoff,
            models.PriceHistory.approved_price.isnot(None),
        )
        .order_by(desc(models.PriceHistory.price_date))
        .all()
    )


# ─────────────────────────────────────────
# AI LEARNING PATTERNS
# ─────────────────────────────────────────

def get_learning_patterns(
    db: Session, apartment_id: Optional[int] = None
) -> list[models.AILearningPattern]:
    query = db.query(models.AILearningPattern).filter(
        models.AILearningPattern.is_active == True
    )
    if apartment_id:
        query = query.filter(
            (models.AILearningPattern.apartment_id == apartment_id)
            | (models.AILearningPattern.apartment_id.is_(None))
        )
    return query.all()


def upsert_learning_pattern(
    db: Session,
    apartment_id: Optional[int],
    pattern_type: str,
    new_correction: float,
) -> None:
    pattern = (
        db.query(models.AILearningPattern)
        .filter(
            models.AILearningPattern.apartment_id == apartment_id,
            models.AILearningPattern.pattern_type == pattern_type,
        )
        .first()
    )
    if pattern:
        # Media mobile delle correzioni
        n = pattern.sample_count
        pattern.learned_adjustment = (pattern.learned_adjustment * n + new_correction) / (n + 1)
        pattern.sample_count = n + 1
        pattern.confidence = min(1.0, pattern.sample_count / 10)  # max confidence dopo 10 sample
        pattern.last_updated = datetime.utcnow()
    else:
        pattern = models.AILearningPattern(
            apartment_id=apartment_id,
            pattern_type=pattern_type,
            learned_adjustment=new_correction,
            sample_count=1,
            confidence=0.1,
        )
        db.add(pattern)
    db.commit()
