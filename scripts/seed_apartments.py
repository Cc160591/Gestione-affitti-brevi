"""
Script per popolare il DB con gli appartamenti.
I prezzi sono placeholder — il sistema usa il mercato come riferimento reale.

Esegui con: python -m scripts.seed_apartments
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from backend.db.database import SessionLocal, engine, Base
from backend.db.models import Apartment, PricingRule, RuleType

Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────
# APPARTAMENTI
# Aggiorna con i dati reali dell'amico.
# base_price/min_price/max_price sono placeholder — il sistema usa i prezzi di mercato.
# ─────────────────────────────────────────
APARTMENTS = [
    {"name": "Appartamento 1",  "zone": "Milano", "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Appartamento 2",  "zone": "Milano", "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Appartamento 3",  "zone": "Milano", "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Appartamento 4",  "zone": "Milano", "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Appartamento 5",  "zone": "Milano", "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Appartamento 6",  "zone": "Milano", "beds": 2, "bathrooms": 2, "max_guests": 4},
    {"name": "Appartamento 7",  "zone": "Milano", "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Appartamento 8",  "zone": "Milano", "beds": 2, "bathrooms": 1, "max_guests": 3},
    {"name": "Appartamento 9",  "zone": "Milano", "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Appartamento 10", "zone": "Milano", "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Appartamento 11", "zone": "Milano", "beds": 3, "bathrooms": 1, "max_guests": 5},
    {"name": "Appartamento 12", "zone": "Milano", "beds": 2, "bathrooms": 2, "max_guests": 4},
]

# ─────────────────────────────────────────
# REGOLE DEFAULT — logica market-based con fasce temporali
# Il prezzo di riferimento è sempre il mercato competitor della zona.
# ─────────────────────────────────────────
DEFAULT_RULES = [
    {
        "name": "Early bird (90+ giorni)",
        "rule_type": RuleType.percentage_above_market,
        "adjustment_pct": 20.0,
        "condition": {"days_min": 90},
        "description": "Prenotazione con 90+ giorni di anticipo: mercato +20%",
        "priority": 1,
    },
    {
        "name": "Standard (60-90 giorni)",
        "rule_type": RuleType.percentage_above_market,
        "adjustment_pct": 0.0,
        "condition": {"days_min": 60, "days_max": 90},
        "description": "60-90 giorni prima: prezzo di mercato senza variazioni",
        "priority": 2,
    },
    {
        "name": "Medio termine (30-60 giorni)",
        "rule_type": RuleType.percentage_below_market,
        "adjustment_pct": -2.0,
        "condition": {"days_min": 30, "days_max": 60},
        "description": "30-60 giorni prima: mercato -2%",
        "priority": 3,
    },
    {
        "name": "Last minute (0-30 giorni)",
        "rule_type": RuleType.last_minute,
        "adjustment_pct": -5.0,
        "condition": {"days_min": 0, "days_max": 30},
        "description": "Meno di 30 giorni: mercato -5% per stimolare prenotazioni",
        "priority": 4,
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Apartment).count()
        if existing > 0:
            print(f"DB già popolato con {existing} appartamenti. Skip.")
            return

        for apt_data in APARTMENTS:
            apt = Apartment(
                **apt_data,
                base_price=0,
                min_price=0,
                max_price=9999,
                current_price=None,
            )
            db.add(apt)
            db.flush()

            for rule_data in DEFAULT_RULES:
                rule = PricingRule(apartment_id=apt.id, **rule_data)
                db.add(rule)

        db.commit()
        print(f"✓ Inseriti {len(APARTMENTS)} appartamenti con regole market-based.")
        print("  Aggiorna nomi, zone e dettagli con i dati reali del tuo amico.")

    except Exception as e:
        db.rollback()
        print(f"Errore: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
