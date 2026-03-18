"""
API per l'analisi dei prezzi di mercato.
Calcola prezzo minimo/massimo competitor e prezzo consigliato (server-side, no AI)
per ogni appartamento su un range di date.
"""
import math
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud, models

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
def get_pricing_analysis(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Restituisce per ogni appartamento, per ogni data nel range:
    - market_min / market_max  (da competitor_snapshots per zona)
    - suggested_price          (calcolato server-side con pricing_rules)
    """
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=29)

    apartments = crud.get_all_apartments(db)
    events_in_range = crud.get_upcoming_events(db, start_date, end_date)

    # Pre-carica snapshot competitor per zona (ordinati DESC per data)
    zones = list({apt.zone for apt in apartments})
    zone_snapshots: dict[str, list] = {}
    for zone in zones:
        snaps = (
            db.query(models.CompetitorSnapshot)
            .filter(models.CompetitorSnapshot.zone == zone)
            .order_by(models.CompetitorSnapshot.snapshot_date.desc())
            .all()
        )
        zone_snapshots[zone] = snaps

    result = []
    for apt in apartments:
        rules = crud.get_rules_for_apartment(db, apt.id)
        snaps = zone_snapshots.get(apt.zone, [])

        dates_data = []
        current = start_date
        while current <= end_date:
            # Trova snapshot più recente <= current date per la zona
            snap = None
            for s in snaps:
                if s.snapshot_date <= current:
                    snap = s
                    break  # lista già ordinata DESC

            market_min = snap.min_price if snap else None
            market_max = snap.max_price if snap else None

            # Eventi attivi in questa data
            active_events = [
                e for e in events_in_range
                if e.start_date <= current <= e.end_date
            ]

            if market_min is not None:
                suggested = _apply_rules(
                    market_min, rules, current,
                    active_events, apt.min_price, apt.max_price
                )
            else:
                suggested = None

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
            "dates": dates_data,
        })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "apartments": result,
    }
