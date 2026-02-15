# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MusicTaggerz is an automatic music tagger with MusicBrainz integration. It scans a music directory, matches albums against MusicBrainz, scores candidates (0-100), and auto-tags high-confidence matches while queuing uncertain ones for manual review. Docker-ready for Unraid.

## Development Commands

### Backend
```bash
cd musictaggerz/backend
source venv/bin/activate
MUSIC_DIR=/home/matti/Music uvicorn app.main:app --port 8765 --reload
```

### Frontend
```bash
cd musictaggerz/frontend
npm run dev          # Dev server on :3000, proxies /api and /ws to :8765
npm run build        # TypeScript check + Vite build -> outputs to ../backend/static/
```

The production build is served by FastAPI's StaticFiles mount at `/` when `backend/static/` exists.

## Architecture

The codebase lives in `musictaggerz/musictaggerz/` with two main parts:

### Backend (`backend/app/`)

**FastAPI application** with four API routers mounted in `main.py`:
- `/api/albums` → `api/albums.py` — Album CRUD, tagging, batch ops, scan trigger, cover art serving
- `/api/settings` → `api/settings.py` — Key-value settings CRUD
- `/api/stats` → `api/stats.py` — Dashboard stats + activity log
- `/ws` → `api/websocket.py` — Single WS endpoint for real-time updates

**Processing pipeline** (runs in background threads):
1. `services/album_scanner.py` — Recursively finds album folders with audio files
2. `services/queue_manager.py` — FIFO queue with worker thread, max 3 retries
3. `services/tagging_service.py` — Orchestrates: read tags → search MusicBrainz → score → decide → write tags → fetch artwork
4. `services/file_watcher.py` — Watchdog inotify monitor with debounce (30s stabilization)
5. `services/notification_service.py` — Thread-safe WebSocket broadcast (sync→async bridge)

**Core modules** (`core/`):
- `audio_reader.py` — Mutagen-based multi-format reader (FLAC, MP3, M4A, OGG, Opus, WMA)
- `matcher.py` — Scoring algorithm: text similarity (30pts), track count (20), durations (20), media (10), country (10), year (10), multi-disc penalty (-15)
- `musicbrainz_client.py` — MB API wrapper with 1.1s rate limiting
- `tagger.py` — Writes tags back to audio files via Mutagen
- `artwork_fetcher.py` — Priority chain: filesystem → iTunes → fanart.tv → Spotify → Cover Art Archive

**Data layer**: SQLite + SQLAlchemy ORM. Models in `models.py`, Pydantic schemas in `schemas.py`, config via pydantic-settings in `config.py`. DB created on startup via `database.py:init_db()`.

**Album status flow**: `pending` → `matching` → `tagged` | `needs_review` | `failed` | `skipped`

### Frontend (`frontend/src/`)

React 18 + TypeScript + Vite + TailwindCSS (Catppuccin Mocha dark theme).

**State management**: Zustand stores in `store/` — `useAlbumStore` (list/detail/CRUD/WS handler), `useStatsStore`, `useSettingsStore`, `useNotificationStore` (toasts).

**WebSocket**: `services/websocket.ts` connects with exponential backoff reconnect. `hooks/useWebSocket.ts` dispatches WS messages to appropriate stores. Message types: `album_update`, `progress`, `notification`, `scan_update`.

**Routes** (React Router v6 in `App.tsx`): `/` Dashboard, `/albums` list, `/albums/:id` detail, `/settings`.

**API client**: `services/api.ts` — Axios instance with `baseURL: '/api'`, typed functions for all endpoints.

**Path alias**: `@/` maps to `./src/` (configured in tsconfig.json + vite.config.ts).

## Key Design Decisions

- **Text-based matching only** — Never trusts embedded MusicBrainz IDs, always searches by artist+album text
- **In-place tagging** — Never moves or renames files, only writes tags
- **Sequential processing** — FIFO queue processes one album at a time to respect MusicBrainz rate limits
- **Thread-safe WS bridge** — Background worker threads use `asyncio.run_coroutine_threadsafe()` to broadcast via the async FastAPI WebSocket
- **Cover endpoint** — `GET /api/albums/{id}/cover` serves images from filesystem since `cover_path` is an absolute path inaccessible to browsers
