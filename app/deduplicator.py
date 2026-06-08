from __future__ import annotations

import logging
from typing import List

from . import database
from .models import Article

logger = logging.getLogger(__name__)


async def filter_new(articles: List[Article]) -> List[Article]:
    seen = await database.get_seen_urls([a.url for a in articles])
    new = [a for a in articles if a.url not in seen]
    logger.info(f"{len(new)} new articles out of {len(articles)} total")
    return new
