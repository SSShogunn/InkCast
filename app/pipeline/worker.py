from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from . import deduplicator, fetcher, scripter, tts
from ..core import database
from ..config import settings

logger = logging.getLogger(__name__)


async def run_pipeline(today: Optional[date] = None) -> Dict[str, Any]:
    if today is None:
        today = date.today()

    logger.info(f"Pipeline starting for {today}")

    if await database.episode_exists_for_date(today):
        logger.info(f"Episode already exists for {today} — skipping")
        return {"status": "skipped", "reason": "already generated today"}

    articles = await fetcher.fetch_articles()
    if not articles:
        logger.info("No articles fetched from any feed")
        return {"status": "skipped", "reason": "no articles fetched"}

    new_articles = await deduplicator.filter_new(articles)
    if not new_articles:
        logger.info("All articles already seen — nothing new today")
        return {"status": "skipped", "reason": "nothing new today"}

    capped = new_articles[:settings.max_articles_total]
    if len(new_articles) > len(capped):
        logger.info(f"Capped articles from {len(new_articles)} to {len(capped)}")

    prior_threads = await database.get_recent_threads(settings.memory_window_days)
    script = await scripter.write_script(capped, today, prior_threads)
    if not script:
        logger.info("No script produced (LLM unreachable) — skipping episode")
        return {"status": "skipped", "reason": "LLM unreachable"}

    audio_base = Path(settings.audio_dir) / today.isoformat()
    try:
        actual_audio = await tts.synthesize(script, audio_base)
    except Exception as exc:
        logger.error(f"TTS failed: {exc}")
        return {"status": "failed", "reason": f"TTS error: {exc}"}

    duration = tts.audio_duration_seconds(actual_audio)
    title = f"Inkcast — {today.strftime('%B')} {today.day}, {today.year}"

    try:
        episode_id = await database.save_episode(
            d=today,
            title=title,
            audio_path=f"audio/{actual_audio.name}",
            duration=duration,
            script=script,
        )
        await database.mark_seen([a.url for a in capped])
        await database.prune_seen(settings.seen_retention_days)
        logger.info(f"Episode {episode_id} saved for {today}")
    except Exception as exc:
        logger.error(f"Failed to save episode: {exc}")
        return {"status": "failed", "reason": f"database error: {exc}"}

    # Cross-episode memory: distil this episode into storylines for tomorrow.
    threads = await scripter.extract_threads(script)
    await database.save_threads(episode_id, today, threads)

    return {
        "status": "ok",
        "date": today.isoformat(),
        "episode_id": episode_id,
        "articles_processed": len(capped),
        "duration_seconds": duration,
        "threads_extracted": len(threads),
        "threads_recalled": len(prior_threads),
    }
