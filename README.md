# Inkcast

> A self-hosted daily briefing engine that turns your RSS feeds into a podcast you can listen to every morning.

Inkcast reads the RSS feeds you care about, writes a natural-sounding podcast script from the day's new articles using a local LLM, converts it to audio with a local TTS engine, and serves it as a valid podcast RSS feed that any podcast app can subscribe to.

The name reflects the core transformation: **ink** (written articles) → **cast** (audio broadcast).

## How it works

```
RSS feeds → fetch → dedupe → LLM script → TTS audio → SQLite → /feed.xml
                                  ↑                ↓
                         recall threads     extract threads
                          (memory)           (memory)
```

| Stage | What it does |
|-------|--------------|
| **Fetcher** | Pulls all configured feeds in parallel, strips HTML to clean text |
| **Deduplicator** | Skips articles already turned into past episodes |
| **Scripter** | One LLM call turns the day's articles into a cohesive spoken script, with recent **story threads** injected as context |
| **Memory** | A second LLM call distils each episode into structured storylines, so future episodes can reference and update them |
| **TTS** | Converts the script to audio (Kokoro, local & free) |
| **Feed** | Serves a valid podcast RSS feed at `/feed.xml` |

Everything runs locally — no cloud APIs, no per-call cost.

### Cross-episode memory

Inkcast doesn't treat each day in isolation. After every episode, it extracts the
distinct storylines it covered (`topic` + one-line `summary`) into a `story_threads`
table. When the next episode is written, the recent threads (last
`MEMORY_WINDOW_DAYS`) are fed back into the script prompt — so the host can say
*"an update on that antitrust case we covered Tuesday"* instead of re-introducing
every story from scratch. Browse the current memory at `GET /api/threads`.

## Tech stack

FastAPI · APScheduler · feedparser · BeautifulSoup · LM Studio (OpenAI-compatible) · Kokoro ONNX TTS · SQLite (aiosqlite) · feedgen · pydantic-settings

## Project structure

```
app/
  main.py            FastAPI app, lifespan, router wiring
  config.py          pydantic-settings (.env)
  models.py          Article, Episode, StoryThread
  api/
    routes.py        all HTTP endpoints (APIRouter)
  pipeline/          the daily run, stage by stage
    fetcher.py       RSS → clean text
    deduplicator.py  drop already-seen articles
    scripter.py      LLM: write script + extract story threads
    tts.py           Kokoro text-to-speech
    worker.py        orchestrates the pipeline
  core/              cross-cutting services
    database.py      SQLite persistence
    feed.py          podcast RSS output
    scheduler.py     daily cron trigger
```

## Requirements

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **[LM Studio](https://lmstudio.ai/)** running locally with a model loaded and its server started (default `http://localhost:1234`)

## Setup

```bash
# 1. Clone and install dependencies
git clone https://github.com/SSShogunn/InkCast.git inkcast
cd inkcast
uv sync

# 2. Configure
cp .env.example .env      # then edit .env to taste

# 3. Download the Kokoro TTS model files (~310 MB) into the project root
#    (gitignored — not committed)
curl -L -o kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o voices-v1.0.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

> On Windows PowerShell, use `Invoke-WebRequest -Uri <url> -OutFile <name>` instead of `curl`.

Make sure `KOKORO_MODEL` and `KOKORO_VOICES` in `.env` point to wherever you saved those two files.

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The scheduler will generate an episode automatically each day at `SCHEDULE_HOUR`. To generate one immediately:

```bash
curl -X POST http://localhost:8000/trigger
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /feed.xml` | Podcast RSS feed — **subscribe to this URL** in any podcast app |
| `GET /audio/{filename}` | The audio file for an episode |
| `GET /episodes` | JSON list of all generated episodes |
| `GET /episodes/{id}` | A single episode with its full transcript |
| `GET /api/threads` | All story threads — the cross-episode memory, newest first |
| `GET /api/feeds` | List the configured RSS feeds |
| `POST /api/feeds` | Add a feed — body `{"url": "https://..."}` |
| `DELETE /api/feeds/{id}` | Remove a feed |
| `POST /trigger` | Manually run the pipeline now |

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example) for the full list). Highlights:

| Variable | Default | Notes |
|----------|---------|-------|
| `FEED_URLS` | (6 tech feeds) | JSON array, **single line** — seeds the feeds table on first run; manage live feeds via `/api/feeds` |
| `MAX_ARTICLES_PER_FEED` | `5` | Cap per feed |
| `MAX_ARTICLES_TOTAL` | `20` | Hard cap before the LLM call |
| `SCHEDULE_HOUR` | `6` | Daily run time (24h) |
| `SEEN_RETENTION_DAYS` | `30` | Drop dedup records older than this |
| `MEMORY_WINDOW_DAYS` | `14` | Days of story threads recalled as context per episode |
| `KOKORO_VOICE` | `af_heart` | e.g. `am_adam`, `bf_emma`, `bm_george` |

## Deployment

Inkcast is designed to run as a long-lived service on a home server. Run it with `uvicorn` (see [Run](#run) above), then subscribe your podcast app to `http://<your-server>:8000/feed.xml`.

## License

Personal project — use freely.
