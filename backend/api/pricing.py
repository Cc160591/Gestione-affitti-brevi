"""
API per l'analisi dei prezzi di mercato.
Calcola prezzo minimo/massimo competitor e prezzo consigliato (server-side, no AI)
per ogni appartamento su un range di date.
"""
import math
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud, models
from backend.integrations.beds24 import update_price as beds24_update_price
from backend.integrations.market_data import get_competitor_prices

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


def _apply_rules(
    base_price: float,
    rules: list,
    target_date: date,
    active_events: list,
    apt_min: float,
    apt_max: float,
) -> float:
    """
    Applica le pricing_rules attive al prezzo base (market_min).
    Regole applicate in ordine di priorità.
    Arrotondamento finale per eccesso (math.ceil).
    """
    price = base_price

    for rule in rules:
        if rule.rule_type == models.RuleType.percentage_above_market:
            price *= 1 + rule.adjustment_pct / 100

        elif rule.rule_type == models.RuleType.percentage_below_market:
            price *= 1 - rule.adjustment_pct / 100

        elif rule.rule_type == models.RuleType.fixed_price and rule.fixed_value is not None:
            price = rule.fixed_value

        elif rule.rule_type == models.RuleType.event_boost and active_events:
            price *= 1 + rule.adjustment_pct / 100

        elif rule.rule_type == models.RuleType.last_minute:
            cond = rule.condition or {}
            days_before = cond.get("days_before", 3)
            days_until = (target_date - date.today()).days
            if 0 <= days_until <= days_before:
                price *= 1 - abs(rule.adjustment_pct) / 100

        # occupancy_based: skip — no dati occupancy in questa vista

    price = max(apt_min, min(apt_max, price))
    return math.ceil(price)


@router.get("")
async def get_pricing_analysis(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Restituisce per ogni appartamento, per ogni data nel range:
    - market_min / market_max  (da competitor_snapshots, generati on-demand se mancanti)
    - suggested_price          (calcolato server-side con pricing_rules)
    """
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=29)

    apartments = crud.get_all_apartments(db)
    events_in_range = crud.get_upcoming_events(db, start_date, end_date)

    result = []
    for apt in apartments:
        rules = crud.get_rules_for_apartment(db, apt.id)

        dates_data = []
        current = start_date
        while current <= end_date:
            # get_competitor_prices: legge da DB se esiste, altrimenti genera mock e salva
            market = await get_competitor_prices(db, apt.zone, current)
            market_min = market["min_price"]
            market_max = market["max_price"]

            # Eventi attivi in questa data
            active_events = [
                e for e in events_in_range
                if e.start_date <= current <= e.end_date
            ]

            suggested = _apply_rules(
                market_min, rules, current,
                active_events, apt.min_price, apt.max_price
            )

            dates_data.append({
                "date": current.isoformat(),
                "market_min": market_min,
                "market_max": market_max,
                "suggested_price": suggested,
                "has_event": bool(active_events),
                "events": [e.name for e in active_events],
            })
            current += timedelta(days=1)

        result.append({
            "id": apt.id,
            "name": apt.name,
            "zone": apt.zone,
            "current_price": apt.current_price,
            "min_price": apt.min_price,
            "max_price": apt.max_price,
            "beds24_id": apt.beds24_id,
            "dates": dates_data,
        })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "apartments": result,
    }


# ─────────────────────────────────────────
# APPLICA PREZZO SU BEDS24 / AIRBNB
# ─────────────────────────────────────────

class ApplyPriceRequest(BaseModel):
    apartment_id: int
    date: str          # YYYY-MM-DD
    price: float
    market_min: float | None = None
    market_max: float | None = None


@router.post("/apply")
async def apply_price(body: ApplyPriceRequest, db: Session = Depends(get_db)):
    """
    Applica il prezzo consigliato su Beds24 (→ Airbnb) per un appartamento e una data.
    Salva la decisione in price_history con was_autonomous=False.
    """
    apt = crud.get_apartment(db, body.apartment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appartamento non trovato")

    if not apt.beds24_id:
        raise HTTPException(
            status_code=400,
            detail=f"beds24_id non configurato per '{apt.name}'. Aggiungilo nella pagina appartamento."
        )

    target_date = date.fromisoformat(body.date)

    # Chiama Beds24
    success = await beds24_update_price(apt.beds24_id, target_date, body.price)
    if not success:
        raise HTTPException(status_code=502, detail="Beds24: aggiornamento fallito. Controlla i log.")

    # Salva in price_history
    record = models.PriceHistory(
        apartment_id=body.apartment_id,
        session_id=None,
        price_date=target_date,
        price_before=apt.current_price,
        proposed_price=body.price,
        approved_price=body.price,
        applied_price=body.price,
        competitor_min=body.market_min,
        competitor_max=body.market_max,
        was_autonomous=False,
    )
    db.add(record)

    # Aggiorna current_price solo se è la data di oggi
    if target_date == date.today():
        crud.update_apartment_current_price(db, body.apartment_id, body.price)

    db.commit()

    return {
        "status": "applied",
        "apartment": apt.name,
        "date": body.date,
        "price": body.price,
    }
