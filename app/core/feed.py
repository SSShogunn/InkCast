from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from . import database
from ..config import settings

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def generate_feed() -> bytes:
    episodes = await database.get_all_episodes()

    fg = FeedGenerator()
    fg.id(f"{settings.feed_base_url}/feed.xml")
    fg.title(settings.feed_title)
    fg.description(settings.feed_description)
    fg.link(href=settings.feed_base_url, rel="alternate")
    fg.link(href=f"{settings.feed_base_url}/feed.xml", rel="self")
    fg.language("en")

    try:
        fg.load_extension("podcast")
        fg.podcast.itunes_author("Inkcast")  # type: ignore[attr-defined]
        fg.podcast.itunes_explicit("no")  # type: ignore[attr-defined]
    except Exception:
        pass

    for episode in episodes:
        audio_file = episode.audio_path.split("/")[-1]
        audio_url = f"{settings.feed_base_url}/audio/{audio_file}"

        fe = fg.add_entry()
        fe.id(audio_url)
        fe.title(episode.title)
        fe.description(episode.script or episode.title)
        mime = "audio/wav" if audio_file.endswith(".wav") else "audio/mpeg"
        local_path = Path(settings.audio_dir) / audio_file
        length = str(local_path.stat().st_size) if local_path.exists() else "0"
        fe.enclosure(url=audio_url, length=length, type=mime)
        fe.pubDate(_ensure_utc(episode.created_at))

    return fg.rss_str(pretty=True)
