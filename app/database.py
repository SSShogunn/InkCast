from __future__ import annotations

from datetime import date
from typing import List, Optional, Set

import aiosqlite

from .config import settings
from .models import Episode


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
