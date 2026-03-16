"""
Telegram Bot — interfaccia principale con l'utente.
Gestisce i messaggi in entrata e li passa all'agente AI.
"""
import os
import logging
from datetime import date
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction

from ..db.database import SessionLocal
from ..db import crud
from ..agent.pricing_agent import run_agent

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")  # Solo questo chat_id può usare il bot


# ─────────────────────────────────────────
# MIDDLEWARE: verifica autorizzazione
# ─────────────────────────────────────────

def is_authorized(update: Update) -> bool:
    """Accetta messaggi solo dal proprietario del bot."""
    if not ALLOWED_CHAT_ID:
        return True  # In sviluppo, accetta tutti
    return str(update.effective_chat.id) == str(ALLOWED_CHAT_ID)


# ─────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    await update.message.reply_text(
        "Ciao! Sono il tuo assistente per la gestione prezzi Airbnb 🏠\n\n"
        "Ogni mattina alle 8:00 ti invierò una proposta prezzi da approvare.\n\n"
        "Comandi disponibili:\n"
        "/analizza — avvia un'analisi manuale adesso\n"
        "/stato — mostra i prezzi attuali degli appartamenti\n"
        "/aiuto — mostra questo messaggio"
    )


async def handle_analizza(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Avvia manualmente un'analisi prezzi, come se fosse il trigger mattutino."""
    if not is_authorized(update):
        return

    chat_id = str(update.effective_chat.id)
    await update.message.chat.send_action(ChatAction.TYPING)

    db = SessionLocal()
    try:
        # Controlla se c'è già una sessione attiva oggi
        existing = crud.get_active_session(db, chat_id)
        if existing:
            await update.message.reply_text(
                "C'è già una sessione aperta per oggi. "
                "Rispondimi pure per modificare le proposte, oppure di' 'approva tutto' per confermare."
            )
            return

        # Crea nuova sessione
        session = crud.create_session(db, chat_id, date.today())

        await update.message.reply_text("Sto analizzando il mercato... ⏳")

        # Avvia l'agente con il trigger mattutino
        reply = await run_agent(db, session, is_morning_trigger=True)

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Errore in handle_analizza: {e}", exc_info=True)
        await update.message.reply_text("Si è verificato un errore durante l'analisi. Riprova tra poco.")
    finally:
        db.close()


async def handle_stato(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra i prezzi correnti di tutti gli appartamenti."""
    if not is_authorized(update):
        return

    db = SessionLocal()
    try:
        apartments = crud.get_all_apartments(db)
        if not apartments:
            await update.message.reply_text("Nessun appartamento configurato.")
            return

        lines = ["*Prezzi attuali:*\n"]
        for apt in apartments:
            price_str = f"€{apt.current_price:.0f}" if apt.current_price else "—"
            lines.append(f"• *{apt.name}* ({apt.zone}): {price_str}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Gestisce tutti i messaggi di testo durante una sessione attiva.
    Passa il messaggio all'agente AI per interpretazione e risposta.
    """
    if not is_authorized(update):
        return

    chat_id = str(update.effective_chat.id)
    user_text = update.message.text.strip()

    db = SessionLocal()
    try:
        # Cerca sessione attiva
        session = crud.get_active_session(db, chat_id)
        if not session:
            await update.message.reply_text(
                "Non c'è nessuna sessione aperta.\n"
                "Usa /analizza per avviare una nuova analisi prezzi."
            )
            return

        await update.message.chat.send_action(ChatAction.TYPING)

        # Passa all'agente
        reply = await run_agent(db, session, user_message=user_text)

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Errore in handle_message: {e}", exc_info=True)
        await update.message.reply_text("Errore nell'elaborazione. Riprova.")
    finally:
        db.close()


async def handle_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await handle_start(update, context)


# ─────────────────────────────────────────
# TRIGGER MATTUTINO (chiamato dallo scheduler)
# ─────────────────────────────────────────

async def morning_trigger(application: Application) -> None:
    """
    Funzione chiamata ogni mattina dallo scheduler.
    Apre una sessione e invia la proposta prezzi.
    """
    if not ALLOWED_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID non configurato, skip morning trigger")
        return

    db = SessionLocal()
    try:
        # Evita sessioni doppie
        existing = crud.get_active_session(db, ALLOWED_CHAT_ID)
        if existing:
            logger.info("Sessione già attiva, skip morning trigger")
            return

        session = crud.create_session(db, ALLOWED_CHAT_ID, date.today())
        reply = await run_agent(db, session, is_morning_trigger=True)

        await application.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            text=reply,
            parse_mode="Markdown",
        )
        logger.info("Morning trigger inviato con successo")

    except Exception as e:
        logger.error(f"Errore morning trigger: {e}", exc_info=True)
        await application.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            text="Errore nell'analisi mattutina. Usa /analizza per riprovare.",
        )
    finally:
        db.close()


# ─────────────────────────────────────────
# SETUP BOT
# ─────────────────────────────────────────

def create_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    handle_start))
    app.add_handler(CommandHandler("analizza", handle_analizza))
    app.add_handler(CommandHandler("stato",    handle_stato))
    app.add_handler(CommandHandler("aiuto",    handle_aiuto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
