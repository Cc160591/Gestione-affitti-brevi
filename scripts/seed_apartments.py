"""
Script per popolare il DB con gli appartamenti reali.
I prezzi base/min/max sono placeholder — il sistema usa il mercato come riferimento.

Esegui con: python -m scripts.seed_apartments
"""
from dotenv import load_dotenv
load_dotenv()

from backend.db.database import SessionLocal, engine, Base
from backend.db.models import Apartment, PricingRule, RuleType

Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────
# APPARTAMENTI REALI (10/12 — aggiungere gli ultimi 2)
# ─────────────────────────────────────────
APARTMENTS = [
    {
        "name": "Milano Argonne - Città Studi",
        "zone": "Città Studi",
        "airbnb_id": "1180318632008544966",
        "beds": 3, "bathrooms": 2, "max_guests": 10,
        "address": "Argonne, Milano",
        "base_price": 150, "min_price": 80,  "max_price": 350,
    },
    {
        "name": "Milano Centro - Corso Como + Terrazza",
        "zone": "Corso Como",
        "airbnb_id": "1458873214878783684",
        "beds": 1, "bathrooms": 1, "max_guests": 4,
        "address": "Corso Como, Milano",
        "base_price": 120, "min_price": 70,  "max_price": 250,
    },
    {
        "name": "Milano Isola - Duomo #02",
        "zone": "Isola",
        "airbnb_id": "912084201406663998",
        "beds": 1, "bathrooms": 1, "max_guests": 3,
        "address": "Isola, Milano",
        "base_price": 90,  "min_price": 55,  "max_price": 200,
    },
    {
        "name": "Milano Isola - Duomo #03",
        "zone": "Isola",
        "airbnb_id": "1115892614185441040",
        "beds": 1, "bathrooms": 1, "max_guests": 2,
        "address": "Isola, Milano",
        "base_price": 80,  "min_price": 50,  "max_price": 180,
    },
    {
        "name": "Milano Isola - Duomo + Terrazza #04",
        "zone": "Isola",
        "airbnb_id": "1376802547601831461",
        "beds": 1, "bathrooms": 1, "max_guests": 2,
        "address": "Isola, Milano",
        "base_price": 90,  "min_price": 55,  "max_price": 200,
    },
    {
        "name": "Milano Porta Venezia + Terrazza",
        "zone": "Porta Venezia",
        "airbnb_id": "1197796592915430096",
        "beds": 1, "bathrooms": 1, "max_guests": 2,
        "address": "Porta Venezia, Milano",
        "base_price": 95,  "min_price": 55,  "max_price": 210,
    },
    {
        "name": "Milano Navigli - San Gottardo",
        "zone": "Navigli",
        "airbnb_id": "1377600493238075570",
        "beds": 2, "bathrooms": 1, "max_guests": 5,
        "address": "Corso San Gottardo 18, Navigli, Milano",
        "base_price": 120, "min_price": 70,  "max_price": 250,
    },
    {
        "name": "Milano CityLife - Sempione #01",
        "zone": "CityLife",
        "airbnb_id": "1615309089277313630",
        "beds": 1, "bathrooms": 1, "max_guests": 4,
        "address": "CityLife, Milano",
        "base_price": 100, "min_price": 60,  "max_price": 220,
    },
    {
        "name": "Milano CityLife - Sempione #02",
        "zone": "CityLife",
        "airbnb_id": "1615305262544083656",
        "beds": 2, "bathrooms": 1, "max_guests": 4,
        "address": "CityLife, Milano",
        "base_price": 120, "min_price": 75,  "max_price": 260,
    },
    {
        "name": "Milano Corso Buenos Aires",
        "zone": "Porta Venezia",
        "airbnb_id": "1615281215291884120",
        "beds": 2, "bathrooms": 1, "max_guests": 6,
        "address": "Corso Buenos Aires, Milano",
        "base_price": 110, "min_price": 65,  "max_price": 240,
    },
    # ── DA AGGIUNGERE: appartamenti 11 e 12 ──
    # {
    #     "name": "...",
    #     "zone": "...",
    #     "airbnb_id": "...",
    #     "beds": X, "bathrooms": X, "max_guests": X,
    #     "address": "...",
    #     "base_price": X, "min_price": X, "max_price": X,
    # },
]

# ─────────────────────────────────────────
# REGOLE DEFAULT — logica market-based con fasce temporali
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
            apt = Apartment(**apt_data, current_price=None)
            db.add(apt)
            db.flush()

            for rule_data in DEFAULT_RULES:
                rule = PricingRule(apartment_id=apt.id, **rule_data)
                db.add(rule)

        db.commit()
        print(f"✓ Inseriti {len(APARTMENTS)} appartamenti con regole market-based.")

    except Exception as e:
        db.rollback()
        print(f"Errore: {e}")
        raise
    finally:
        db.close()


def update_prices():
    """
    Aggiorna base_price / min_price / max_price per gli appartamenti esistenti.
    Identifica gli appartamenti tramite airbnb_id.
    Utile quando il seed ha già girato con valori placeholder (0 / 9999).
    """
    db = SessionLocal()
    try:
        updated = 0
        for apt_data in APARTMENTS:
            apt = db.query(Apartment).filter(
                Apartment.airbnb_id == apt_data["airbnb_id"]
            ).first()
            if apt:
                apt.base_price = apt_data["base_price"]
                apt.min_price  = apt_data["min_price"]
                apt.max_price  = apt_data["max_price"]
                updated += 1
        db.commit()
        print(f"✓ Aggiornati prezzi per {updated} appartamenti.")
    except Exception as e:
        db.rollback()
        print(f"Errore: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "update-prices":
        update_prices()
    else:
        seed()
