from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    # --- LLM provider: "lmstudio" (local) or "openai" (hosted) ---
    llm_provider: str = "lmstudio"

    # LM Studio (local, OpenAI-compatible API)
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "mock-model"
    lm_studio_api_key: str = "lm-studio"  # ignored by LM Studio, but the SDK needs one

    # OpenAI (hosted). Used when llm_provider == "openai".
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""

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

    # --- Resolved LLM settings (provider-agnostic) -------------------------
    # The pipeline reads these three; they fan out to the right provider.

    @property
    def _use_openai(self) -> bool:
        return self.llm_provider.strip().lower() == "openai"

    @property
    def llm_base_url(self) -> str:
        return self.openai_base_url if self._use_openai else self.lm_studio_base_url

    @property
    def llm_api_key(self) -> str:
        return self.openai_api_key if self._use_openai else self.lm_studio_api_key

    @property
    def llm_model(self) -> str:
        return self.openai_model if self._use_openai else self.lm_studio_model


settings = Settings()
