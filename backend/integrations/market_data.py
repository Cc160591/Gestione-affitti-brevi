"""
Integrazione per i dati di mercato (prezzi competitor per zona).

Per ora usa dati mock realistici per Milano.
Quando si attiva AirDNA, basta sostituire _fetch_from_airdna().
"""
import httpx
import random
import os
from datetime import date
from sqlalchemy.orm import Session
from ..db import crud


# Prezzi base realistici per zona Milano (€/notte)
ZONE_BASE_PRICES = {
    "Navigli":        {"min": 75,  "max": 180, "avg": 110},
    "Brera":          {"min": 90,  "max": 220, "avg": 145},
    "Duomo":          {"min": 100, "max": 250, "avg": 165},
    "Porta Romana":   {"min": 70,  "max": 160, "avg": 105},
    "Isola":          {"min": 75,  "max": 175, "avg": 115},
    "Garibaldi":      {"min": 80,  "max": 190, "avg": 125},
    "Porta Venezia":  {"min": 75,  "max": 170, "avg": 110},
    "Città Studi":    {"min": 60,  "max": 130, "avg": 85},
}

AIRDNA_API_KEY = os.getenv("AIRDNA_API_KEY")


async def get_competitor_prices(db: Session, zone: str, target_date: date) -> dict:
    """
    Restituisce prezzi competitor per una zona in una data.
    Prima controlla il DB (cache giornaliera), poi chiama l'API.
    """
    cached = crud.get_latest_competitor_snapshot(db, zone, target_date)
    if cached:
        return {
            "zone": zone,
            "date": str(target_date),
            "avg_price": cached.avg_price,
            "min_price": cached.min_price,
            "max_price": cached.max_price,
            "median_price": cached.median_price,
            "sample_count": cached.sample_count,
            "source": cached.source,
        }

    if AIRDNA_API_KEY:
        data = await _fetch_from_airdna(zone, target_date)
    else:
        data = _mock_competitor_prices(zone, target_date)

    crud.save_competitor_snapshot(db, {
        "zone": zone,
        "snapshot_date": target_date,
        "avg_price": data["avg_price"],
        "min_price": data["min_price"],
        "max_price": data["max_price"],
        "median_price": data.get("median_price"),
        "sample_count": data["sample_count"],
        "source": data["source"],
    })

    return data


async def _fetch_from_airdna(zone: str, target_date: date) -> dict:
    """Chiamata reale ad AirDNA. Da completare con endpoint e parametri corretti."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.airdna.co/api/v1/market/search",
            params={
                "access_token": AIRDNA_API_KEY,
                "location": f"{zone}, Milano, Italy",
                "start_date": str(target_date),
                "end_date": str(target_date),
            },
        )
        response.raise_for_status()
        raw = response.json()

        # TODO: adattare al formato reale della risposta AirDNA
        return {
            "zone": zone,
            "date": str(target_date),
            "avg_price": raw.get("avg_daily_rate", 0),
            "min_price": raw.get("percentile_25", 0),
            "max_price": raw.get("percentile_75", 0),
            "median_price": raw.get("median_daily_rate"),
            "sample_count": raw.get("active_listings", 0),
            "source": "airdna",
        }


def _mock_competitor_prices(zone: str, target_date: date) -> dict:
    """
    Dati mock realistici per sviluppo e testing.
    Simula variazioni weekend e stagionali.
    """
    base = ZONE_BASE_PRICES.get(zone, {"min": 70, "max": 160, "avg": 105})

    # Weekend +15%
    is_weekend = target_date.weekday() >= 4
    multiplier = 1.15 if is_weekend else 1.0

    # Piccola variazione casuale giornaliera (±5%)
    daily_variation = random.uniform(0.95, 1.05)

    avg = round(base["avg"] * multiplier * daily_variation, 2)
    spread = (base["max"] - base["min"]) / 2

    return {
        "zone": zone,
        "date": str(target_date),
        "avg_price": avg,
        "min_price": round(avg - spread * 0.6, 2),
        "max_price": round(avg + spread * 0.6, 2),
        "median_price": round(avg * random.uniform(0.97, 1.03), 2),
        "sample_count": random.randint(15, 45),
        "source": "mock",
    }
