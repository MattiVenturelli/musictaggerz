import os
import struct
import unicodedata
import re
from typing import Optional, List, Tuple

import httpx

from app.config import settings
from app.utils.logger import log


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9 ]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _text_match(a: str, b: str) -> float:
    """Word overlap ratio between two strings (0.0-1.0)."""
    wa = set(_normalize(a).split())
    wb = set(_normalize(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa | wb), 1)

# Timeout for HTTP requests
HTTP_TIMEOUT = 30.0


def _get_image_size(data: bytes) -> Tuple[int, int]:
    """Get image dimensions from raw bytes (JPEG or PNG)."""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        # PNG: width and height at bytes 16-24
        w = struct.unpack('>I', data[16:20])[0]
        h = struct.unpack('>I', data[20:24])[0]
        return w, h
    elif data[:2] == b'\xff\xd8':
        # JPEG: scan for SOF markers
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = struct.unpack('>H', data[i + 5:i + 7])[0]
                w = struct.unpack('>H', data[i + 7:i + 9])[0]
                return w, h
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + length
    return 0, 0


def _download_image(url: str) -> Optional[bytes]:
    """Download an image from URL, return raw bytes."""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type and not resp.content[:4] in (b'\xff\xd8\xff', b'\x89PNG'):
                log.debug(f"Not an image: {url} (content-type: {content_type})")
                return None
            return resp.content
    except Exception as e:
        log.debug(f"Failed to download {url}: {e}")
        return None


def _check_min_size(data: bytes, min_size: int) -> bool:
    """Check if image meets minimum size requirement."""
    w, h = _get_image_size(data)
    if w == 0 or h == 0:
        return True  # can't determine size, allow it
    return min(w, h) >= min_size


def fetch_from_filesystem(folder_path: str) -> Optional[Tuple[bytes, str]]:
    """Look for existing cover art in the album folder.

    Returns (image_data, mime_type) or None.
    """
    cover_names = [
        "cover.jpg", "cover.jpeg", "cover.png",
        "front.jpg", "front.jpeg", "front.png",
        "folder.jpg", "folder.jpeg", "folder.png",
        "albumart.jpg", "albumart.jpeg", "albumart.png",
        "album.jpg", "album.jpeg", "album.png",
    ]

    for name in cover_names:
        filepath = os.path.join(folder_path, name)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "rb") as f:
                    data = f.read()
                if data:
                    mime = "image/png" if name.endswith(".png") else "image/jpeg"
                    w, h = _get_image_size(data)
                    log.info(f"Found filesystem cover: {name} ({w}x{h})")
                    return data, mime
            except Exception as e:
                log.debug(f"Error reading {filepath}: {e}")

    # Also check case-insensitive
    try:
        files = os.listdir(folder_path)
        for f in files:
            if f.lower() in cover_names:
                filepath = os.path.join(folder_path, f)
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as fh:
                        data = fh.read()
                    if data:
                        mime = "image/png" if f.lower().endswith(".png") else "image/jpeg"
                        w, h = _get_image_size(data)
                        log.info(f"Found filesystem cover: {f} ({w}x{h})")
                        return data, mime
    except Exception:
        pass

    return None


def fetch_from_itunes(artist: str, album: str) -> Optional[Tuple[bytes, str]]:
    """Fetch cover from iTunes Search API (no API key needed).

    Returns up to 1400x1400 artwork.
    """
    try:
        query = f"{artist} {album}"
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "entity": "album",
                    "limit": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.debug(f"iTunes search error: {e}")
        return None

    results = data.get("results", [])
    if not results:
        log.debug(f"iTunes: no results for '{artist}' - '{album}'")
        return None

    # Score results by artist+album similarity, pick best match
    scored = []
    for result in results:
        r_artist = result.get("artistName", "")
        r_album = result.get("collectionName", "")
        score = _text_match(artist, r_artist) * 0.5 + _text_match(album, r_album) * 0.5
        scored.append((score, result))
    scored.sort(key=lambda x: x[0], reverse=True)

    for score, result in scored:
        if score < 0.3:
            log.debug(f"iTunes: skipping '{result.get('artistName')}' - '{result.get('collectionName')}' (score {score:.2f})")
            continue

        artwork_url = result.get("artworkUrl100", "")
        if not artwork_url:
            continue

        # Replace 100x100 with max resolution
        hires_url = artwork_url.replace("100x100bb", "1400x1400bb")

        image_data = _download_image(hires_url)
        if image_data and _check_min_size(image_data, settings.artwork_min_size):
            w, h = _get_image_size(image_data)
            log.info(f"iTunes cover: {w}x{h} for '{artist}' - '{album}' (match: {score:.2f}, from: '{result.get('artistName')}' - '{result.get('collectionName')}')")
            return image_data, "image/jpeg"

    log.debug(f"iTunes: no suitable artwork for '{artist}' - '{album}'")
    return None


def fetch_from_fanarttv(musicbrainz_release_group_id: str) -> Optional[Tuple[bytes, str]]:
    """Fetch cover from fanart.tv API.

    Requires API key and MusicBrainz release group ID.
    """
    api_key = settings.fanarttv_api_key
    if not api_key:
        log.debug("fanart.tv: no API key configured")
        return None

    if not musicbrainz_release_group_id:
        log.debug("fanart.tv: no release group ID")
        return None

    try:
        url = f"https://webservice.fanart.tv/v3/music/albums/{musicbrainz_release_group_id}"
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, params={"api_key": api_key})
            if resp.status_code == 404:
                log.debug(f"fanart.tv: no data for release group {musicbrainz_release_group_id}")
                return None
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.debug(f"fanart.tv error: {e}")
        return None

    # Look for album covers in the "albums" section
    albums = data.get("albums", {})
    for album_id, album_data in albums.items():
        covers = album_data.get("albumcover", [])
        for cover in covers:
            cover_url = cover.get("url", "")
            if not cover_url:
                continue

            image_data = _download_image(cover_url)
            if image_data and _check_min_size(image_data, settings.artwork_min_size):
                w, h = _get_image_size(image_data)
                log.info(f"fanart.tv cover: {w}x{h}")
                return image_data, "image/jpeg"

    log.debug(f"fanart.tv: no suitable covers for {musicbrainz_release_group_id}")
    return None


def fetch_from_coverart_archive(musicbrainz_release_id: str) -> Optional[Tuple[bytes, str]]:
    """Fetch cover from Cover Art Archive (coverartarchive.org).

    Free, no API key needed. Variable quality.
    """
    if not musicbrainz_release_id:
        return None

    try:
        # Try front cover first
        url = f"https://coverartarchive.org/release/{musicbrainz_release_id}/front"
        image_data = _download_image(url)
        if image_data and _check_min_size(image_data, settings.artwork_min_size):
            w, h = _get_image_size(image_data)
            mime = "image/png" if image_data[:4] == b'\x89PNG' else "image/jpeg"
            log.info(f"Cover Art Archive cover: {w}x{h}")
            return image_data, mime
    except Exception as e:
        log.debug(f"Cover Art Archive error: {e}")

    return None


def fetch_artwork(
    folder_path: str,
    artist: str = "",
    album: str = "",
    musicbrainz_release_id: str = "",
    musicbrainz_release_group_id: str = "",
) -> Optional[Tuple[bytes, str]]:
    """Fetch best available artwork following configured source priority.

    Returns (image_data, mime_type) or None.
    Source order from settings: filesystem, itunes, fanarttv, coverart
    """
    source_map = {
        "filesystem": lambda: fetch_from_filesystem(folder_path),
        "itunes": lambda: fetch_from_itunes(artist, album),
        "fanarttv": lambda: fetch_from_fanarttv(musicbrainz_release_group_id),
        "coverart": lambda: fetch_from_coverart_archive(musicbrainz_release_id),
    }

    for source_name in settings.artwork_sources:
        fetcher = source_map.get(source_name)
        if not fetcher:
            continue

        log.debug(f"Trying artwork source: {source_name}")
        result = fetcher()
        if result:
            log.info(f"Artwork found from: {source_name}")
            return result

    log.warning(f"No artwork found for '{artist}' - '{album}'")
    return None


def save_artwork_to_folder(folder_path: str, image_data: bytes, mime: str = "image/jpeg") -> Optional[str]:
    """Save artwork as albumart.jpg/png in the album folder."""
    ext = ".png" if mime == "image/png" else ".jpg"
    filename = f"albumart{ext}"
    filepath = os.path.join(folder_path, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(image_data)
        w, h = _get_image_size(image_data)
        log.info(f"Saved artwork: {filepath} ({w}x{h}, {len(image_data)} bytes)")
        return filepath
    except Exception as e:
        log.error(f"Error saving artwork to {filepath}: {e}")
        return None
