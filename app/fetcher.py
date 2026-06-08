from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import feedparser
from bs4 import BeautifulSoup

from .config import settings
from .models import Article

logger = logging.getLogger(__name__)


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _parse_entry(entry: feedparser.FeedParserDict, source: str) -> Optional[Article]:
    url = str(entry.get("link", "")).strip()
    if not url:
        return None

    title = str(entry.get("title", "Untitled"))

    content = ""
    entry_content = entry.get("content")
    if entry_content:
        content = str(entry_content[0].get("value", ""))
    if not content:
        content = str(entry.get("summary", ""))
    content = _strip_html(content)
    if not content:
        return None

    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if time_struct:
        t = cast(time.struct_time, time_struct)
        published = datetime(
            t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec,
            tzinfo=timezone.utc,
        )
    else:
        published = datetime.now(timezone.utc)

    return Article(title=title, url=url, content=content, published=published, source=source)


async def _fetch_one(feed_url: str) -> List[Article]:
    loop = asyncio.get_running_loop()
    try:
        parsed = await loop.run_in_executor(None, feedparser.parse, feed_url)
    except Exception as exc:
        logger.error(f"Failed to fetch {feed_url!r}: {exc}")
        return []

    feed_meta = cast(Dict[str, Any], parsed.feed)
    source = feed_meta.get("title", feed_url)
    out: List[Article] = []
    for entry in parsed.entries:
        if len(out) >= settings.max_articles_per_feed:
            break
        article = _parse_entry(entry, source)
        if article:
            out.append(article)
    logger.info(f"Fetched {len(out)} articles from {source!r}")
    return out


async def fetch_articles() -> List[Article]:
    results = await asyncio.gather(
        *(_fetch_one(url) for url in settings.feed_urls)
    )
    return [article for batch in results for article in batch]
