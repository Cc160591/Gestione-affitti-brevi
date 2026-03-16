from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class RuleType(str, enum.Enum):
    percentage_above_market = "percentage_above_market"   # es. sempre +10% sopra media
    percentage_below_market = "percentage_below_market"   # es. sempre -5% sotto media
    fixed_price              = "fixed_price"              # prezzo fisso per certi giorni
    event_boost              = "event_boost"              # +X% quando c'è un evento
    last_minute              = "last_minute"              # sconto se data vicina e non prenotato
    occupancy_based          = "occupancy_based"          # abbassa se occupancy sotto soglia


class SessionStatus(str, enum.Enum):
    pending   = "pending"    # proposta inviata, attesa risposta
    approved  = "approved"   # approvata senza modifiche
    modified  = "modified"   # approvata dopo modifiche
    skipped   = "skipped"    # saltata dall'utente
    applied   = "applied"    # prezzi aggiornati su Airbnb


# ─────────────────────────────────────────
# APARTMENTS
# ─────────────────────────────────────────

class Apartment(Base):
    __tablename__ = "apartments"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(100), nullable=False)           # es. "Navigli 2"
    airbnb_id      = Column(String(50), nullable=True, unique=True)
    beds24_id      = Column(String(50), nullable=True, unique=True)
    zone           = Column(String(100), nullable=False)           # es. "Navigli", "Brera"
    address        = Column(String(200), nullable=True)
    beds           = Column(Integer, nullable=False, default=1)
    bathrooms      = Column(Integer, nullable=False, default=1)
    max_guests     = Column(Integer, nullable=False, default=2)

    # Prezzi
    base_price     = Column(Float, nullable=False)   # prezzo di partenza
    min_price      = Column(Float, nullable=False)   # mai scendere sotto
    max_price      = Column(Float, nullable=False)   # mai salire sopra
    current_price  = Column(Float, nullable=True)    # prezzo attuale su Airbnb

    is_active      = Column(Boolean, default=True)
    notes          = Column(Text, nullable=True)     # note libere del gestore
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni
    rules          = relationship("PricingRule", back_populates="apartment", cascade="all, delete")
    price_history  = relationship("PriceHistory", back_populates="apartment", cascade="all, delete")


# ─────────────────────────────────────────
# PRICING RULES
# ─────────────────────────────────────────

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id               = Column(Integer, primary_key=True, index=True)
    apartment_id     = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    name             = Column(String(100), nullable=False)          # es. "Weekend boost"
    rule_type        = Column(SAEnum(RuleType), nullable=False)
    adjustment_pct   = Column(Float, nullable=True)                 # es. 10.0 = +10%
    fixed_value      = Column(Float, nullable=True)                 # per regole a valore fisso
    condition        = Column(JSON, nullable=True)
    # esempi condition:
    # {"days_before": 3}                          → last_minute se <3 giorni
    # {"occupancy_below": 40}                     → abbassa se <40% occupazione mese
    # {"days_of_week": ["friday", "saturday"]}    → solo weekend
    priority         = Column(Integer, default=1)                   # ordine applicazione regole
    is_active        = Column(Boolean, default=True)
    description      = Column(Text, nullable=True)                  # spiegazione in chiaro
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    apartment        = relationship("Apartment", back_populates="rules")


# ─────────────────────────────────────────
# COMPETITOR SNAPSHOTS
# Prezzi giornalieri appartamenti simili per zona
# ─────────────────────────────────────────

class CompetitorSnapshot(Base):
    __tablename__ = "competitor_snapshots"

    id            = Column(Integer, primary_key=True, index=True)
    zone          = Column(String(100), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    avg_price     = Column(Float, nullable=False)
    min_price     = Column(Float, nullable=False)
    max_price     = Column(Float, nullable=False)
    median_price  = Column(Float, nullable=True)
    sample_count  = Column(Integer, nullable=False)   # quanti appartamenti campionati
    raw_data      = Column(JSON, nullable=True)       # dati grezzi per audit
    source        = Column(String(50), default="airdna")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────
# MARKET EVENTS
# Eventi a Milano che impattano la domanda
# ─────────────────────────────────────────

class MarketEvent(Base):
    __tablename__ = "market_events"

    id                  = Column(Integer, primary_key=True, index=True)
    name                = Column(String(200), nullable=False)       # es. "Design Week 2025"
    event_type          = Column(String(50), nullable=True)         # es. "fiera", "concerto", "festival"
    start_date          = Column(Date, nullable=False)
    end_date            = Column(Date, nullable=False)
    zones_affected      = Column(JSON, nullable=True)               # ["Navigli", "Brera"]
    expected_impact_pct = Column(Float, nullable=True)              # stima +X% domanda
    actual_impact_pct   = Column(Float, nullable=True)              # rilevato a posteriori
    source              = Column(String(100), nullable=True)        # url o fonte
    notes               = Column(Text, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────
# PRICE HISTORY
# Cuore del sistema di apprendimento
# ─────────────────────────────────────────

class PriceHistory(Base):
    __tablename__ = "price_history"

    id                = Column(Integer, primary_key=True, index=True)
    apartment_id      = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    session_id        = Column(Integer, ForeignKey("telegram_sessions.id"), nullable=True)
    price_date        = Column(Date, nullable=False)                # per quale data è il prezzo

    # Prezzi
    price_before      = Column(Float, nullable=True)               # prezzo prima della sessione
    proposed_price    = Column(Float, nullable=False)              # proposto dall'AI
    approved_price    = Column(Float, nullable=True)               # approvato dall'utente
    applied_price     = Column(Float, nullable=True)               # effettivamente messo online

    # Contesto mercato al momento della proposta
    competitor_avg    = Column(Float, nullable=True)
    competitor_min    = Column(Float, nullable=True)
    competitor_max    = Column(Float, nullable=True)
    active_events     = Column(JSON, nullable=True)                # eventi attivi quel giorno

    # AI reasoning — cosa ha pensato l'agente
    ai_reasoning      = Column(Text, nullable=True)
    user_feedback     = Column(Text, nullable=True)                # cosa ha detto l'utente per modificare

    # Delta: differenza tra proposta e approvazione (base per il learning)
    correction_delta  = Column(Float, nullable=True)              # approved - proposed
    correction_pct    = Column(Float, nullable=True)              # % di correzione

    was_autonomous    = Column(Boolean, default=False)            # applicato senza approvazione
    created_at        = Column(DateTime(timezone=True), server_default=func.now())

    apartment         = relationship("Apartment", back_populates="price_history")
    session           = relationship("TelegramSession", back_populates="price_history")


# ─────────────────────────────────────────
# TELEGRAM SESSIONS
# Ogni sessione mattutina di approvazione
# ─────────────────────────────────────────

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"

    id                = Column(Integer, primary_key=True, index=True)
    chat_id           = Column(String(50), nullable=False)
    status            = Column(SAEnum(SessionStatus), default=SessionStatus.pending)
    session_date      = Column(Date, nullable=False)               # data di riferimento

    proposed_prices   = Column(JSON, nullable=True)                # {apartment_id: price}
    approved_prices   = Column(JSON, nullable=True)                # {apartment_id: price}

    conversation_log  = Column(JSON, nullable=True)                # lista messaggi {role, content, ts}

    started_at        = Column(DateTime(timezone=True), server_default=func.now())
    approved_at       = Column(DateTime(timezone=True), nullable=True)
    applied_at        = Column(DateTime(timezone=True), nullable=True)

    price_history     = relationship("PriceHistory", back_populates="session")


# ─────────────────────────────────────────
# AI LEARNING PATTERNS
# Pattern appresi dalle correzioni dell'utente
# ─────────────────────────────────────────

class AILearningPattern(Base):
    __tablename__ = "ai_learning_patterns"

    id                  = Column(Integer, primary_key=True, index=True)
    apartment_id        = Column(Integer, ForeignKey("apartments.id"), nullable=True)
    # NULL = pattern globale, non specifico per appartamento

    pattern_type        = Column(String(100), nullable=False)
    # es. "weekend_correction", "event_boost_too_high", "zone_bias"

    description         = Column(Text, nullable=True)
    # es. "Per Navigli, l'utente abbassa sempre del 5% rispetto alla proposta in estate"

    learned_adjustment  = Column(Float, nullable=True)            # delta medio delle correzioni
    confidence          = Column(Float, default=0.0)              # 0-1, cresce con i sample
    sample_count        = Column(Integer, default=0)              # quante osservazioni
    is_active           = Column(Boolean, default=True)

    last_updated        = Column(DateTime(timezone=True), onupdate=func.now())
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
