from __future__ import annotations

import asyncio
import logging
import wave
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


async def synthesize(script: str, base_path: Path) -> Path:
    try:
        from kokoro_onnx import Kokoro  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("kokoro-onnx not installed — run: uv add kokoro-onnx") from exc

    import numpy as np

    base_path.parent.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_running_loop()

    def _generate() -> tuple:
        kokoro = Kokoro(settings.kokoro_model, settings.kokoro_voices)
        return kokoro.create(
            script,
            voice=settings.kokoro_voice,
            speed=1.0,
            lang="en-us",
        )

    samples, sample_rate = await loop.run_in_executor(None, _generate)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)

    output_path = base_path.with_suffix(".wav")
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    logger.info(f"Kokoro TTS: audio saved to {output_path}")
    return output_path


def audio_duration_seconds(path: Path) -> int:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        return int(wf.getnframes() / rate) if rate else 0
