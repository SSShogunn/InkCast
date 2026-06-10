from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..pipeline import worker
from ..config import settings

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


def start() -> None:
    _scheduler.add_job(
        worker.run_pipeline,
        trigger="cron",
        hour=settings.schedule_hour,
        minute=0,
        id="daily_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Scheduler started — pipeline runs daily at {settings.schedule_hour:02d}:00")


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown()
