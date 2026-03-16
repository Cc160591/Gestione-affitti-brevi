"""
FastAPI app principale.
Gestisce API REST, web dashboard e bot Telegram via webhook.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "airbnb-pricing-secret")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .telegram.bot import create_application
    from .scheduler import create_scheduler

    tg_app = create_application()
    app.state.tg_app = tg_app

    scheduler = create_scheduler(tg_app)
    scheduler.start()
    logger.info("Scheduler avviato")

    await tg_app.initialize()
    await tg_app.start()

    # Imposta webhook se URL configurato, altrimenti usa polling (sviluppo locale)
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await tg_app.bot.set_webhook(
            url=f"{webhook_url}/webhook/telegram",
            secret_token=WEBHOOK_SECRET,
        )
        logger.info(f"Webhook impostato: {webhook_url}/webhook/telegram")
    else:
        await tg_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot Telegram avviato in modalità polling (sviluppo)")

    yield

    # Shutdown
    if webhook_url:
        await tg_app.bot.delete_webhook()
    else:
        await tg_app.updater.stop()

    scheduler.shutdown()
    await tg_app.stop()
    logger.info("Shutdown completato")


app = FastAPI(title="Airbnb Pricing Manager", lifespan=lifespan)


# ── Webhook Telegram ───────────────────────────────────────
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Riceve gli aggiornamenti da Telegram via webhook."""
    # Verifica il secret token
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        return Response(status_code=403)

    data = await request.json()
    tg_app = request.app.state.tg_app

    from telegram import Update
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)

    return Response(status_code=200)


# ── API routers ────────────────────────────────────────────
from .api.apartments import router as apartments_router
from .api.rules import router as rules_router
from .api.dashboard import router as dashboard_router
from .api.competitor import router as competitor_router
from .api.sessions import router as sessions_router
from .api.events import router as events_router
from .web.router import router as web_router

app.include_router(apartments_router)
app.include_router(rules_router)
app.include_router(dashboard_router)
app.include_router(competitor_router)
app.include_router(sessions_router)
app.include_router(events_router)
app.include_router(web_router)

# ── Static files ───────────────────────────────────────────
static_dir = Path(__file__).parent.parent / "frontend" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
