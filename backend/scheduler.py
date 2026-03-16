"""
Scheduler per il trigger mattutino automatico.
"""
import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

DAILY_HOUR   = int(os.getenv("DAILY_ANALYSIS_HOUR", "8"))
DAILY_MINUTE = int(os.getenv("DAILY_ANALYSIS_MINUTE", "0"))


def create_scheduler(application) -> AsyncIOScheduler:
    """
    Crea lo scheduler e registra il job mattutino.
    application: l'istanza del Telegram Application (per accesso al bot).
    """
    from .telegram.bot import morning_trigger

    scheduler = AsyncIOScheduler(timezone="Europe/Rome")

    scheduler.add_job(
        morning_trigger,
        trigger=CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone="Europe/Rome"),
        args=[application],
        id="morning_pricing",
        name="Analisi prezzi mattutina",
        replace_existing=True,
    )

    logger.info(f"Scheduler configurato: analisi ogni giorno alle {DAILY_HOUR:02d}:{DAILY_MINUTE:02d}")
    return scheduler
