from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    # LLM (LM Studio via OpenAI-compatible API)
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "mock-model"
    openai_api_key: str = "lm-studio"

    # Scheduler
    schedule_hour: int = 6

    # Drop dedup records older than this many days
    seen_retention_days: int = 30

    # Cross-episode memory: how many days of story threads to recall as
    # context when writing a new episode
    memory_window_days: int = 14

    # Storage
    audio_dir: str = "audio"
    db_path: str = "inkcast.db"

    # Podcast feed metadata
    feed_title: str = "Inkcast"
    feed_description: str = "Your daily personal briefing"
    feed_base_url: str = "http://localhost:8000"

    # Pipeline limits
    max_articles_per_feed: int = 5
    max_articles_total: int = 20

    # Kokoro TTS model files
    kokoro_model: str = "kokoro-v1.0.onnx"
    kokoro_voices: str = "voices-v1.0.bin"
    kokoro_voice: str = "af_heart"

    # RSS source URLs — JSON array in .env
    feed_urls: List[str] = []


settings = Settings()
