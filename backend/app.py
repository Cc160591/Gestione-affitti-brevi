"""
FastAPI app principale.
Gestisce API REST, web dashboard e avvia bot Telegram + scheduler nel lifespan.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .telegram.bot import create_application
    from .scheduler import create_scheduler

    tg_app = create_application()
    scheduler = create_scheduler(tg_app)
    scheduler.start()
    logger.info("Scheduler avviato")

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot Telegram avviato — in ascolto...")

    yield

    scheduler.shutdown()
    await tg_app.updater.stop()
    await tg_app.stop()
    logger.info("Shutdown completato")


app = FastAPI(title="Airbnb Pricing Manager", lifespan=lifespan)

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
