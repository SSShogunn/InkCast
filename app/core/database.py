from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

import aiosqlite

from ..config import settings
from ..models import Episode, StoryThread


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_articles (
                url      TEXT PRIMARY KEY,
                seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        DATE UNIQUE,
                title       TEXT NOT NULL,
                audio_path  TEXT NOT NULL,
                duration    INTEGER,
                script      TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                url       TEXT UNIQUE NOT NULL,
                added_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS story_threads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id  INTEGER,
                date        DATE,
                topic       TEXT NOT NULL,
                summary     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
            )
        """)
        await db.commit()
        await _seed_feeds(db)


async def _seed_feeds(db: aiosqlite.Connection) -> None:
    """Populate the feeds table from .env on first run only."""
    async with db.execute("SELECT COUNT(*) FROM feeds") as cursor:
        row = await cursor.fetchone()
        if row and row[0] > 0:
            return
    if not settings.feed_urls:
        return
    await db.executemany(
        "INSERT OR IGNORE INTO feeds (url) VALUES (?)",
        [(url,) for url in settings.feed_urls],
    )
    await db.commit()


async def get_seen_urls(urls: List[str]) -> Set[str]:
    if not urls:
        return set()
    placeholders = ",".join("?" * len(urls))
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT url FROM seen_articles WHERE url IN ({placeholders})", urls
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}


async def mark_seen(urls: List[str]) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO seen_articles (url) VALUES (?)",
            [(url,) for url in urls],
        )
        await db.commit()


async def prune_seen(days: int) -> int:
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute(
            "DELETE FROM seen_articles WHERE seen_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        await db.commit()
        return cursor.rowcount


async def save_episode(
    d: date,
    title: str,
    audio_path: str,
    duration: Optional[int],
    script: str,
) -> int:
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute(
            """INSERT INTO episodes (date, title, audio_path, duration, script) VALUES (?, ?, ?, ?, ?)""",
            (d.isoformat(), title, audio_path, duration, script),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_all_episodes() -> List[Episode]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM episodes ORDER BY date DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [Episode(**dict(row)) for row in rows]


async def get_episode(episode_id: int) -> Optional[Episode]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return Episode(**dict(row)) if row else None


async def episode_exists_for_date(d: date) -> bool:
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            "SELECT 1 FROM episodes WHERE date = ?", (d.isoformat(),)
        ) as cursor:
            return await cursor.fetchone() is not None


# --- Feeds -----------------------------------------------------------------

async def get_feed_urls() -> List[str]:
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute("SELECT url FROM feeds ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_feeds() -> List[Dict[str, object]]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM feeds ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def add_feed(url: str) -> Dict[str, object]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("INSERT OR IGNORE INTO feeds (url) VALUES (?)", (url,))
        await db.commit()
        async with db.execute("SELECT * FROM feeds WHERE url = ?", (url,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def delete_feed(feed_id: int) -> bool:
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        await db.commit()
        return cursor.rowcount > 0


# --- Story threads (cross-episode memory) ----------------------------------

async def save_threads(
    episode_id: int, d: date, threads: List[Dict[str, str]]
) -> None:
    if not threads:
        return
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executemany(
            "INSERT INTO story_threads (episode_id, date, topic, summary) VALUES (?, ?, ?, ?)",
            [
                (episode_id, d.isoformat(), t["topic"], t["summary"])
                for t in threads
                if t.get("topic") and t.get("summary")
            ],
        )
        await db.commit()


async def get_recent_threads(days: int, limit: int = 40) -> List[StoryThread]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM story_threads
               WHERE date >= date('now', ?)
               ORDER BY date DESC, id DESC
               LIMIT ?""",
            (f"-{days} days", limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [StoryThread(**dict(row)) for row in rows]


async def get_all_threads(limit: int = 200) -> List[StoryThread]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM story_threads ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [StoryThread(**dict(row)) for row in rows]
