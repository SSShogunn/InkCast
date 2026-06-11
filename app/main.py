from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .config import settings
from .core import database
from .core import scheduler as sched

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    logger.info(f"Feeds configured: {settings.feed_urls}")
    logger.info(
        f"LLM: provider={settings.llm_provider} "
        f"url={settings.llm_base_url} model={settings.llm_model}"
    )
    sched.start()
    yield
    sched.stop()


app = FastAPI(title="Inkcast", lifespan=lifespan)
app.include_router(router)
