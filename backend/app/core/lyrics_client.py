from dataclasses import dataclass
from typing import Optional

import httpx

from app.utils.logger import log


LRCLIB_BASE = "https://lrclib.net/api"
USER_AGENT = "MusicTaggerz/1.0"
TIMEOUT = 10


@dataclass
class LyricsResult:
    plain_lyrics: Optional[str] = None
    synced_lyrics: Optional[str] = None
    instrumental: bool = False


def fetch_lyrics(
    artist: str,
    title: str,
    album: str = "",
    duration: int = 0,
) -> Optional[LyricsResult]:
    """Fetch lyrics from LRCLIB. Tries exact match first, then fuzzy search."""
    if not artist or not title:
        return None

    # Try exact match
    result = _exact_match(artist, title, album, duration)
    if result:
        return result

    # Fallback: fuzzy search
    return _fuzzy_search(artist, title)


def _exact_match(artist: str, title: str, album: str, duration: int) -> Optional[LyricsResult]:
    params = {
        "artist_name": artist,
        "track_name": title,
    }
    if album:
        params["album_name"] = album
    if duration > 0:
        params["duration"] = str(duration)

    try:
        resp = httpx.get(
            f"{LRCLIB_BASE}/get",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return _parse_response(data)
    except Exception as e:
        log.debug(f"LRCLIB exact match failed for {artist} - {title}: {e}")
        return None


def _fuzzy_search(artist: str, title: str) -> Optional[LyricsResult]:
    query = f"{artist} {title}"
    try:
        resp = httpx.get(
            f"{LRCLIB_BASE}/search",
            params={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None

        # Pick the first result that has lyrics
        for item in results:
            parsed = _parse_response(item)
            if parsed and (parsed.plain_lyrics or parsed.synced_lyrics):
                return parsed

        # Check if first result is instrumental
        if results:
            parsed = _parse_response(results[0])
            if parsed:
                return parsed

        return None
    except Exception as e:
        log.debug(f"LRCLIB fuzzy search failed for {artist} - {title}: {e}")
        return None


def _parse_response(data: dict) -> Optional[LyricsResult]:
    if not data:
        return None
    return LyricsResult(
        plain_lyrics=data.get("plainLyrics") or None,
        synced_lyrics=data.get("syncedLyrics") or None,
        instrumental=bool(data.get("instrumental", False)),
    )
