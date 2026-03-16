"""
Agente AI per la gestione dei prezzi Airbnb.
Usa OpenAI function calling per analizzare il mercato,
proporre prezzi e interpretare le risposte dell'utente.
"""
import json
import os
from datetime import date, timedelta
from typing import Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from ..db import crud, models
from ..integrations.market_data import get_competitor_prices
from ..integrations.beds24 import update_prices_bulk

OPENAI_MODEL_SMART = os.getenv("OPENAI_MODEL_SMART", "gpt-4o")
OPENAI_MODEL_FAST  = os.getenv("OPENAI_MODEL_FAST",  "gpt-4o-mini")

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Sei un assistente esperto di gestione prezzi per appartamenti Airbnb a Milano.
Il tuo compito è analizzare i prezzi di mercato e proporre prezzi ottimali per i 12 appartamenti
del gestore, seguendo una logica market-based con fasce temporali.

LOGICA DI PRICING (applica sempre questa logica per ogni data):
- Prezzo di riferimento = prezzo medio dei competitor nella stessa zona (get_market_data)
- 0-30 giorni alla data: riferimento mercato -5% (stimola prenotazioni last minute)
- 30-60 giorni alla data: riferimento mercato -2%
- 60-90 giorni alla data: esattamente il prezzo di mercato
- 90+ giorni alla data: riferimento mercato +20% (chi prenota in anticipo paga di più)

COMPORTAMENTO:
- Parla sempre in italiano, in modo chiaro e diretto
- Quando proponi prezzi, spiega SEMPRE il motivo (fascia temporale, mercato, evento in città, ecc.)
- Non usare i campi base_price/min_price/max_price come vincoli — usa il mercato come riferimento
- Quando l'utente chiede modifiche, interpretale anche se espresse informalmente
  (es. "abbassa il navigli di 5" = riduci il prezzo del Navigli di €5)
- Prima di applicare i prezzi, mostra sempre un riepilogo e chiedi conferma esplicita
- Se hai imparato pattern dall'utente (correzioni passate), applicali proattivamente
- Tieni conto degli eventi a Milano (fiere, concerti, ecc.) per aumentare i prezzi nelle date interessate

Quando l'utente approva, usa il tool apply_prices per aggiornare Airbnb.
"""


# ─────────────────────────────────────────
# TOOL DEFINITIONS
# ─────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_apartments_data",
            "description": "Recupera tutti gli appartamenti attivi con prezzi attuali, min/max e regole.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": "Recupera i prezzi competitor per una zona in una data specifica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {"type": "string", "description": "Zona di Milano (es. Navigli, Brera)"},
                    "target_date": {"type": "string", "description": "Data in formato YYYY-MM-DD"},
                },
                "required": ["zone", "target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "Recupera eventi a Milano nei prossimi giorni che potrebbero impattare i prezzi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Quanti giorni in avanti controllare", "default": 14},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_patterns",
            "description": "Recupera i pattern appresi dalle correzioni passate dell'utente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "apartment_id": {"type": "integer", "description": "ID appartamento (opzionale, se null restituisce pattern globali)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_proposals",
            "description": "Salva le proposte di prezzo nella sessione corrente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proposals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "apartment_id": {"type": "integer"},
                                "proposed_price": {"type": "number"},
                                "reasoning": {"type": "string"},
                            },
                            "required": ["apartment_id", "proposed_price", "reasoning"],
                        },
                    }
                },
                "required": ["proposals"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_prices",
            "description": "Applica i prezzi approvati su Airbnb tramite Beds24. Chiamare SOLO dopo conferma esplicita dell'utente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prices": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "apartment_id": {"type": "integer"},
                                "price": {"type": "number"},
                            },
                            "required": ["apartment_id", "price"],
                        },
                    },
                    "target_date": {"type": "string", "description": "Data in formato YYYY-MM-DD"},
                },
                "required": ["prices", "target_date"],
            },
        },
    },
]


# ─────────────────────────────────────────
# TOOL EXECUTORS
# ─────────────────────────────────────────

async def execute_tool(
    tool_name: str,
    tool_args: dict,
    db: Session,
    session: models.TelegramSession,
) -> str:
    """Esegue il tool richiesto dall'agente e restituisce il risultato come stringa JSON."""

    if tool_name == "get_apartments_data":
        apartments = crud.get_all_apartments(db)
        result = []
        for apt in apartments:
            rules = crud.get_rules_for_apartment(db, apt.id)
            result.append({
                "id": apt.id,
                "name": apt.name,
                "zone": apt.zone,
                "current_price": apt.current_price,
                "base_price": apt.base_price,
                "min_price": apt.min_price,
                "max_price": apt.max_price,
                "beds": apt.beds,
                "rules": [
                    {
                        "type": r.rule_type,
                        "adjustment_pct": r.adjustment_pct,
                        "condition": r.condition,
                        "description": r.description,
                    }
                    for r in rules
                ],
            })
        return json.dumps(result, ensure_ascii=False)

    elif tool_name == "get_market_data":
        target_date = date.fromisoformat(tool_args["target_date"])
        data = await get_competitor_prices(db, tool_args["zone"], target_date)
        return json.dumps(data, ensure_ascii=False)

    elif tool_name == "get_events":
        days_ahead = tool_args.get("days_ahead", 14)
        today = date.today()
        events = crud.get_upcoming_events(db, today, today + timedelta(days=days_ahead))
        result = [
            {
                "name": e.name,
                "type": e.event_type,
                "start": str(e.start_date),
                "end": str(e.end_date),
                "zones": e.zones_affected,
                "expected_impact_pct": e.expected_impact_pct,
            }
            for e in events
        ]
        return json.dumps(result, ensure_ascii=False)

    elif tool_name == "get_learning_patterns":
        apartment_id = tool_args.get("apartment_id")
        patterns = crud.get_learning_patterns(db, apartment_id)
        result = [
            {
                "apartment_id": p.apartment_id,
                "type": p.pattern_type,
                "description": p.description,
                "learned_adjustment": p.learned_adjustment,
                "confidence": p.confidence,
                "samples": p.sample_count,
            }
            for p in patterns
        ]
        return json.dumps(result, ensure_ascii=False)

    elif tool_name == "save_proposals":
        proposals = tool_args["proposals"]
        target_date = session.session_date

        # Salva le proposte nella sessione
        proposed_map = {str(p["apartment_id"]): p["proposed_price"] for p in proposals}
        crud.update_session(db, session.id, {"proposed_prices": proposed_map})

        # Crea i record in price_history
        apartments = {apt.id: apt for apt in crud.get_all_apartments(db)}
        history_entries = []
        for p in proposals:
            apt = apartments.get(p["apartment_id"])
            if apt:
                history_entries.append({
                    "apartment_id": p["apartment_id"],
                    "price_date": target_date,
                    "price_before": apt.current_price,
                    "proposed_price": p["proposed_price"],
                    "ai_reasoning": p["reasoning"],
                })
        crud.create_price_history_entries(db, session.id, history_entries)

        return json.dumps({"status": "ok", "saved": len(proposals)})

    elif tool_name == "apply_prices":
        prices = tool_args["prices"]
        target_date = date.fromisoformat(tool_args["target_date"])

        apartments = {apt.id: apt for apt in crud.get_all_apartments(db)}

        # Prepara aggiornamenti Beds24
        updates = []
        for p in prices:
            apt = apartments.get(p["apartment_id"])
            if apt and apt.beds24_id:
                updates.append({
                    "beds24_id": apt.beds24_id,
                    "date": target_date,
                    "price": p["price"],
                })

        results = await update_prices_bulk(updates)

        # Aggiorna DB con prezzi approvati e applicati
        approved_map = {str(p["apartment_id"]): p["price"] for p in prices}
        crud.update_session(db, session.id, {
            "approved_prices": approved_map,
            "status": models.SessionStatus.applied,
            "applied_at": __import__("datetime").datetime.utcnow(),
        })

        for p in prices:
            crud.update_apartment_current_price(db, p["apartment_id"], p["price"])

            # Aggiorna price_history con il prezzo approvato
            # e calcola il delta per il learning
            apt = apartments.get(p["apartment_id"])
            proposed = session.proposed_prices or {}
            proposed_price = proposed.get(str(p["apartment_id"]))
            if proposed_price:
                delta = p["price"] - proposed_price
                delta_pct = (delta / proposed_price) * 100 if proposed_price else 0
                if abs(delta_pct) > 0.5:  # Solo correzioni significative
                    crud.upsert_learning_pattern(
                        db,
                        apartment_id=p["apartment_id"],
                        pattern_type="price_correction",
                        new_correction=delta_pct,
                    )

        success_count = sum(1 for v in results.values() if v)
        return json.dumps({
            "status": "applied",
            "updated": success_count,
            "total": len(updates),
            "results": results,
        })

    return json.dumps({"error": f"Tool sconosciuto: {tool_name}"})


# ─────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────

async def run_agent(
    db: Session,
    session: models.TelegramSession,
    user_message: Optional[str] = None,
    is_morning_trigger: bool = False,
) -> str:
    """
    Esegue un turno dell'agente.
    - Se is_morning_trigger=True: avvia l'analisi mattutina
    - Altrimenti: risponde al messaggio dell'utente nella sessione attiva

    Restituisce il messaggio testuale da inviare all'utente su Telegram.
    """

    # Ricostruisce la cronologia conversazione per il contesto LLM
    log = session.conversation_log or []
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if is_morning_trigger:
        today = date.today()
        messages.append({
            "role": "user",
            "content": (
                f"È il {today.strftime('%A %d %B %Y')}. "
                "Analizza il mercato e proponi i prezzi ottimali per oggi e i prossimi 7 giorni "
                "per tutti gli appartamenti. "
                "Per ogni data calcola quanti giorni mancano e applica la fascia corretta: "
                "0-30gg → mercato -5%, 30-60gg → mercato -2%, 60-90gg → mercato, 90+gg → mercato +20%. "
                "Tieni conto di eventuali eventi a Milano. "
                "Presenta le proposte in modo chiaro con il ragionamento per ogni appartamento."
            ),
        })
    else:
        # Ricarica la storia conversazione precedente
        for entry in log:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})

        if user_message:
            messages.append({"role": "user", "content": user_message})
            crud.append_to_conversation_log(db, session.id, "user", user_message)

    # Loop tool use
    while True:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL_SMART if is_morning_trigger else OPENAI_MODEL_FAST,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # Nessun tool call → risposta finale da mandare all'utente
        if not message.tool_calls:
            reply = message.content or ""
            crud.append_to_conversation_log(db, session.id, "assistant", reply)
            return reply

        # Esegue tutti i tool calls
        messages.append(message)
        for tool_call in message.tool_calls:
            tool_args = json.loads(tool_call.function.arguments)
            tool_result = await execute_tool(
                tool_call.function.name,
                tool_args,
                db,
                session,
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })
