from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

from . import database, feed, worker
from . import scheduler as sched
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    logger.info(f"Feeds configured: {settings.feed_urls}")
    logger.info(f"LLM: {settings.lm_studio_base_url} model={settings.lm_studio_model}")
    sched.start()
    yield
    sched.stop()


app = FastAPI(title="Inkcast", lifespan=lifespan)


@app.get("/feed.xml")
async def get_feed():
    xml = await feed.generate_feed()
    return Response(content=xml, media_type="application/rss+xml")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    path = Path(settings.audio_dir) / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    mime = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(str(path), media_type=mime)


@app.get("/episodes")
async def list_episodes():
    return await database.get_all_episodes()


@app.post("/trigger")
async def trigger_pipeline():
    return await worker.run_pipeline()
