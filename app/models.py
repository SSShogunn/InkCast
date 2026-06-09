from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    url: str
    content: str
    published: datetime.datetime
    source: str


class Episode(BaseModel):
    id: int
    date: datetime.date
    title: str
    audio_path: str
    duration: Optional[int] = None
    script: Optional[str] = None
    created_at: datetime.datetime
