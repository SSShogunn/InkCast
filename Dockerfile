# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm

# uv — copied from the official image (no version pinned to a python tag)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System libs Kokoro/onnxruntime need at runtime:
#   espeak-ng  — phonemizer backend for TTS
#   libgomp1   — OpenMP runtime for onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Application code
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Container-friendly defaults. Data and model files live on mounted volumes,
# so they survive rebuilds and the 350 MB models stay out of the image.
ENV AUDIO_DIR=/data/audio \
    DB_PATH=/data/inkcast.db \
    KOKORO_MODEL=/models/kokoro-v1.0.onnx \
    KOKORO_VOICES=/models/voices-v1.0.bin

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
