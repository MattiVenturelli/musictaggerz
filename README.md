# MusicTaggerz

Automatic music tagger with MusicBrainz integration. Docker-ready for Unraid.

## Features

- **Smart matching** - Searches MusicBrainz by text (artist + album), ignoring potentially wrong embedded IDs
- **Scoring algorithm** - Rates candidates 0-100 based on text match, track count, durations, media, country, year
- **Auto-decisions** - Auto-tags high confidence matches, queues uncertain ones for manual review
- **Multi-format** - Reads and writes tags for FLAC, MP3, M4A, OGG/Opus
- **HD artwork** - Fetches covers from iTunes (1400px), fanart.tv, Cover Art Archive, with filesystem fallback
- **File watcher** - Auto-detects new albums added to the music folder
- **Web UI** - Modern dashboard with React + TailwindCSS (coming soon)
- **In-place tagging** - Never moves or renames files, only writes tags

## Stack

| Component | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Database | SQLite + SQLAlchemy |
| Audio tags | mutagen |
| MusicBrainz | musicbrainzngs |
| File watcher | watchdog |
| Frontend | React 18 + TypeScript + TailwindCSS + Vite |
| Container | Docker multi-stage build |

## Quick Start

### Development

```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export MUSIC_DIR=/path/to/music
export DATABASE_URL=sqlite:////data/autotagger.db

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8765
```

### Docker

```bash
docker build -t musictaggerz .
docker run -d \
  -p 8765:8765 \
  -v /path/to/music:/music \
  -v /path/to/data:/data \
  -e FANARTTV_API_KEY=your_key \
  musictaggerz
```

## Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `MUSIC_DIR` | `/music` | Path to music library |
| `DATABASE_URL` | `sqlite:////data/autotagger.db` | Database path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CONFIDENCE_AUTO_THRESHOLD` | `85.0` | Auto-tag above this score |
| `CONFIDENCE_REVIEW_THRESHOLD` | `50.0` | Queue for review above this score |
| `ARTWORK_MIN_SIZE` | `500` | Minimum artwork dimension (px) |
| `ARTWORK_SOURCES` | `filesystem,itunes,fanarttv,coverart` | Artwork source priority |
| `FANARTTV_API_KEY` | | fanart.tv API key |
| `PREFERRED_COUNTRIES` | `US,GB,DE,IT` | Preferred release countries |
| `PREFERRED_MEDIA` | `Digital Media,CD` | Preferred media formats |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/albums` | List albums (filters, pagination, search) |
| GET | `/api/albums/{id}` | Album detail with tracks and match candidates |
| POST | `/api/albums/{id}/tag` | Tag album (optional: specific release_id) |
| POST | `/api/albums/{id}/skip` | Skip album |
| POST | `/api/scan` | Trigger directory scan |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/settings` | Current settings |
| PUT | `/api/settings` | Update settings |
| GET | `/api/health` | Health check |
| WS | `/ws` | WebSocket for real-time updates |

## Matching Algorithm

1. Search MusicBrainz by **text** (artist + album name)
2. Filter by track count tolerance
3. Score each candidate (0-100):
   - Artist + album text match: 30 pts
   - Track count match: 20 pts
   - Duration comparison: 20 pts
   - Preferred media format: 10 pts
   - Preferred country: 10 pts
   - Year match: 10 pts
   - Multi-disc penalty: -15 pts
4. Decision:
   - Score >= 85: auto-tag
   - Score 50-84: queue for manual review
   - Score < 50: skip

## License

MIT
