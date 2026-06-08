from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from openai import AsyncOpenAI

from .config import settings
from .models import Article

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=settings.lm_studio_base_url,
    api_key=settings.openai_api_key,
)

_PROMPT = """\
You are a podcast host writing a daily tech news briefing. \
Write a natural, conversational podcast script based on the articles below. \
Plain spoken English only — no markdown, no bullet points, no headers.

Structure:
- Open with: "Good morning. Here's your Inkcast for {date}."
- Cover the most interesting stories, grouped loosely by theme
- Keep each story to 2-3 sentences
- Close with: "That's your briefing for today. See you tomorrow."

Articles:
{articles}

Script:"""


def _format_articles(articles: List[Article]) -> str:
    lines: List[str] = []
    for i, a in enumerate(articles, 1):
        lines.append(f"[{i}] {a.title} (via {a.source})")
        lines.append(a.content[:500].strip())
        lines.append("")
    return "\n".join(lines)


async def write_script(articles: List[Article], today: date) -> Optional[str]:
    date_str = f"{today.strftime('%B')} {today.day}, {today.year}"
    prompt = _PROMPT.format(
        date=date_str,
        articles=_format_articles(articles),
    )
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.lm_studio_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                logger.info("Script written in one shot")
                return content.strip()
            logger.warning(f"Script attempt {attempt + 1} returned empty content")
        except Exception as exc:
            logger.warning(f"Script attempt {attempt + 1} failed: {exc}")
    logger.error("LLM unreachable after 2 attempts — skipping episode")
    return None
