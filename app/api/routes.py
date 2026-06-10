from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..config import settings
from ..core import database, feed
from ..pipeline import worker

router = APIRouter()


@router.get("/feed.xml")
async def get_feed():
    xml = await feed.generate_feed()
    return Response(content=xml, media_type="application/rss+xml")


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    path = Path(settings.audio_dir) / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    mime = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(str(path), media_type=mime)


@router.get("/episodes")
async def list_episodes():
    return await database.get_all_episodes()


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: int):
    episode = await database.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.get("/api/threads")
async def list_threads():
    """All story threads — the cross-episode memory, newest first."""
    return await database.get_all_threads()


@router.get("/api/feeds")
async def list_feeds():
    return await database.get_feeds()


class FeedIn(BaseModel):
    url: str


@router.post("/api/feeds")
async def add_feed(payload: FeedIn):
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    return await database.add_feed(url)


@router.delete("/api/feeds/{feed_id}")
async def delete_feed(feed_id: int):
    if not await database.delete_feed(feed_id):
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"status": "deleted", "id": feed_id}


@router.post("/trigger")
async def trigger_pipeline():
    return await worker.run_pipeline()
