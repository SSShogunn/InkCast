from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from ..config import settings
from ..models import Article, StoryThread

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)

_PROMPT = """\
You are a podcast host writing a daily tech news briefing. \
Write a natural, conversational podcast script based on the articles below. \
Plain spoken English only — no markdown, no bullet points, no headers.
{memory_block}
Structure:
- Open with: "Good morning. Here's your Inkcast for {date}."
- Cover the most interesting stories, grouped loosely by theme
- Keep each story to 2-3 sentences
- If a story below continues or updates one of the ongoing storylines, say so \
naturally (e.g. "An update on..." or "Remember the... story? Well,").
- Close with: "That's your briefing for today. See you tomorrow."

Articles:
{articles}

Script:"""

_MEMORY_INTRO = """\

For continuity, here are ongoing storylines from your recent episodes. \
Only reference one if today's articles genuinely continue it — never invent \
an update:
{threads}
"""

_EXTRACT_PROMPT = """\
You are maintaining a memory of ongoing storylines for a daily tech podcast. \
Read today's script and extract the distinct stories it covered, so future \
episodes can reference them.

Respond with ONLY a JSON array (no prose, no code fences). Each item:
{{"topic": "<3-6 word handle for the storyline>", "summary": "<one sentence on what happened today>"}}
Extract at most 8 items. If nothing substantive was covered, respond with [].

Script:
{script}

JSON:"""


def _format_articles(articles: List[Article]) -> str:
    lines: List[str] = []
    for i, a in enumerate(articles, 1):
        lines.append(f"[{i}] {a.title} (via {a.source})")
        lines.append(a.content[:500].strip())
        lines.append("")
    return "\n".join(lines)


def _format_threads(threads: List[StoryThread]) -> str:
    # Collapse to the most recent mention per topic, preserving recency order.
    seen: set[str] = set()
    lines: List[str] = []
    for t in threads:
        key = t.topic.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {t.topic} ({t.date.isoformat()}): {t.summary}")
        if len(lines) >= 12:
            break
    return "\n".join(lines)


async def write_script(
    articles: List[Article],
    today: date,
    prior_threads: Optional[List[StoryThread]] = None,
) -> Optional[str]:
    date_str = f"{today.strftime('%B')} {today.day}, {today.year}"

    memory_block = ""
    if prior_threads:
        formatted = _format_threads(prior_threads)
        if formatted:
            memory_block = _MEMORY_INTRO.format(threads=formatted)

    prompt = _PROMPT.format(
        date=date_str,
        articles=_format_articles(articles),
        memory_block=memory_block,
    )
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                logger.info(
                    "Script written in one shot (%d prior threads in context)",
                    len(prior_threads or []),
                )
                return content.strip()
            logger.warning(f"Script attempt {attempt + 1} returned empty content")
        except Exception as exc:
            logger.warning(f"Script attempt {attempt + 1} failed: {exc}")
    logger.error("LLM unreachable after 2 attempts — skipping episode")
    return None


def _parse_threads(raw: str) -> List[Dict[str, str]]:
    """Best-effort JSON extraction — tolerates code fences and stray prose."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    out: List[Dict[str, str]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if topic and summary:
            out.append({"topic": topic, "summary": summary})
    return out[:8]


async def extract_threads(script: str) -> List[Dict[str, str]]:
    """Distil a finished script into structured storylines for future memory.

    Never raises — memory is best-effort and must not fail the pipeline."""
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(script=script)}],
            temperature=0.2,
            max_tokens=600,
        )
        content = response.choices[0].message.content or ""
        threads = _parse_threads(content)
        logger.info("Extracted %d story threads from episode", len(threads))
        return threads
    except Exception as exc:
        logger.warning(f"Thread extraction failed (non-fatal): {exc}")
        return []
