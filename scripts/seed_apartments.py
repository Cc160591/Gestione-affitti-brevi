"""
Script per popolare il DB con appartamenti di esempio.
Modifica i dati con quelli reali del tuo amico.

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

APARTMENTS = [
    {"name": "Navigli Classic",    "zone": "Navigli",       "base_price": 105, "min_price": 75,  "max_price": 160, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Navigli Loft",       "zone": "Navigli",       "base_price": 120, "min_price": 85,  "max_price": 180, "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Brera Suite",        "zone": "Brera",         "base_price": 145, "min_price": 100, "max_price": 220, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Brera Attico",       "zone": "Brera",         "base_price": 170, "min_price": 120, "max_price": 250, "beds": 2, "bathrooms": 2, "max_guests": 4},
    {"name": "Duomo View",         "zone": "Duomo",         "base_price": 160, "min_price": 110, "max_price": 240, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Porta Romana Studio","zone": "Porta Romana",  "base_price": 95,  "min_price": 65,  "max_price": 145, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Porta Romana Apt",   "zone": "Porta Romana",  "base_price": 110, "min_price": 75,  "max_price": 160, "beds": 2, "bathrooms": 1, "max_guests": 3},
    {"name": "Isola Design",       "zone": "Isola",         "base_price": 115, "min_price": 80,  "max_price": 170, "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Garibaldi Modern",   "zone": "Garibaldi",     "base_price": 125, "min_price": 85,  "max_price": 185, "beds": 2, "bathrooms": 1, "max_guests": 4},
    {"name": "Porta Venezia Gem",  "zone": "Porta Venezia", "base_price": 108, "min_price": 75,  "max_price": 165, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Città Studi Cozy",   "zone": "Città Studi",   "base_price": 82,  "min_price": 55,  "max_price": 125, "beds": 1, "bathrooms": 1, "max_guests": 2},
    {"name": "Città Studi Family", "zone": "Città Studi",   "base_price": 95,  "min_price": 65,  "max_price": 140, "beds": 3, "bathrooms": 1, "max_guests": 5},
]

# Regole default applicate a tutti gli appartamenti
DEFAULT_RULES = [
    {
        "name": "Weekend boost",
        "rule_type": RuleType.percentage_above_market,
        "adjustment_pct": 12.0,
        "condition": {"days_of_week": ["friday", "saturday"]},
        "description": "Venerdì e sabato alza del 12% rispetto alla media zona",
        "priority": 1,
    },
    {
        "name": "Last minute sconto",
        "rule_type": RuleType.last_minute,
        "adjustment_pct": -10.0,
        "condition": {"days_before": 2},
        "description": "Se mancano meno di 2 giorni e non è prenotato, sconto del 10%",
        "priority": 2,
    },
    {
        "name": "Segui mercato",
        "rule_type": RuleType.percentage_above_market,
        "adjustment_pct": 5.0,
        "condition": None,
        "description": "Base: stai sempre al +5% rispetto alla media dei competitor",
        "priority": 3,
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
            apt = Apartment(**apt_data, current_price=apt_data["base_price"])
            db.add(apt)
            db.flush()  # Per avere l'ID

            for rule_data in DEFAULT_RULES:
                rule = PricingRule(apartment_id=apt.id, **rule_data)
                db.add(rule)

        db.commit()
        print(f"✓ Inseriti {len(APARTMENTS)} appartamenti con regole default.")

    except Exception as e:
        db.rollback()
        print(f"Errore: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
