from __future__ import annotations

import asyncio
import logging
import wave
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)

_SILENT_MP3 = bytes([0xFF, 0xFB, 0x90, 0x00] + [0x00] * 413)


async def synthesize(script: str, base_path: Path) -> Path:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    provider = settings.tts_provider.lower()

    if provider == "mock":
        return _mock(base_path.with_suffix(".mp3"))
    if provider == "gtts":
        return await _gtts(script, base_path.with_suffix(".mp3"))
    if provider == "openai":
        return await _openai_tts(script, base_path.with_suffix(".mp3"))
    if provider == "kokoro":
        return await _kokoro(script, base_path)

    logger.warning(f"Unknown TTS provider {provider!r} — falling back to mock")
    return _mock(base_path.with_suffix(".mp3"))


def _mock(output_path: Path) -> Path:
    output_path.write_bytes(_SILENT_MP3)
    logger.info(f"Mock TTS: placeholder written to {output_path}")
    return output_path


async def _gtts(script: str, output_path: Path) -> Path:
    try:
        from gtts import gTTS  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("gTTS not installed — run: uv add gtts") from exc
    loop = asyncio.get_running_loop()
    tts_obj = gTTS(text=script, lang="en", slow=False)
    await loop.run_in_executor(None, tts_obj.save, str(output_path))
    logger.info(f"gTTS: audio saved to {output_path}")
    return output_path


async def _openai_tts(script: str, output_path: Path) -> Path:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    async with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=script,
    ) as response:
        await response.stream_to_file(str(output_path))
    logger.info(f"OpenAI TTS: audio saved to {output_path}")
    return output_path


async def _kokoro(script: str, base_path: Path) -> Path:
    try:
        from kokoro_onnx import Kokoro  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("kokoro-onnx not installed — run: uv add kokoro-onnx") from exc

    import numpy as np

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
