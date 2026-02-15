"""Artwork discovery: query all sources for thumbnail metadata without downloading full images."""

import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.config import settings
from app.utils.logger import log

HTTP_TIMEOUT = 15.0


@dataclass
class ArtworkOption:
    source: str  # "caa", "itunes", "fanarttv", "filesystem"
    thumbnail_url: str
    full_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    label: str = ""


def discover_caa(release_id: str) -> List[ArtworkOption]:
    """Query Cover Art Archive JSON API for available images.

    Returns list of ArtworkOption with 250px thumbnails and full URLs.
    """
    if not release_id:
        return []

    try:
        url = f"https://coverartarchive.org/release/{release_id}"
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.debug(f"CAA discovery error for {release_id}: {e}")
        return []

    options = []
    for img in data.get("images", []):
        full_url = img.get("image", "")
        if not full_url:
            continue

        thumbnails = img.get("thumbnails", {})
        thumb_url = thumbnails.get("250", thumbnails.get("small", ""))
        if not thumb_url:
            thumb_url = full_url

        # Build label from image types
        types = img.get("types", [])
        label = ", ".join(types) if types else "Cover"
        if img.get("comment"):
            label += f" ({img['comment']})"

        options.append(ArtworkOption(
            source="caa",
            thumbnail_url=thumb_url,
            full_url=full_url,
            label=label,
        ))

    log.debug(f"CAA: found {len(options)} images for release {release_id}")
    return options


def discover_itunes(artist: str, album: str) -> List[ArtworkOption]:
    """Search iTunes API and return artwork options with 250x250 thumbnails."""
    if not artist and not album:
        return []

    try:
        query = f"{artist} {album}"
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                "https://itunes.apple.com/search",
                params={"term": query, "entity": "album", "limit": 5},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.debug(f"iTunes discovery error: {e}")
        return []

    options = []
    for result in data.get("results", []):
        artwork_url = result.get("artworkUrl100", "")
        if not artwork_url:
            continue

        thumb_url = artwork_url.replace("100x100bb", "250x250bb")
        full_url = artwork_url.replace("100x100bb", "1400x1400bb")

        r_artist = result.get("artistName", "")
        r_album = result.get("collectionName", "")
        label = f"{r_artist} - {r_album}"

        options.append(ArtworkOption(
            source="itunes",
            thumbnail_url=thumb_url,
            full_url=full_url,
            width=1400,
            height=1400,
            label=label,
        ))

    log.debug(f"iTunes: found {len(options)} results for '{artist}' - '{album}'")
    return options


def discover_fanarttv(release_group_id: str) -> List[ArtworkOption]:
    """Query fanart.tv for album covers using the release group ID."""
    api_key = settings.fanarttv_api_key
    if not api_key:
        return []
    if not release_group_id:
        return []

    try:
        url = f"https://webservice.fanart.tv/v3/music/albums/{release_group_id}"
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, params={"api_key": api_key})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.debug(f"fanart.tv discovery error: {e}")
        return []

    options = []
    albums = data.get("albums", {})
    for album_id, album_data in albums.items():
        for cover_type in ("albumcover", "cdart"):
            for cover in album_data.get(cover_type, []):
                full_url = cover.get("url", "")
                if not full_url:
                    continue

                # fanart.tv provides /preview endpoint for thumbnails
                thumb_url = full_url.replace("/fanart/", "/preview/")

                label = cover_type.replace("albumcover", "Cover").replace("cdart", "CD Art")
                if cover.get("lang"):
                    label += f" ({cover['lang']})"

                options.append(ArtworkOption(
                    source="fanarttv",
                    thumbnail_url=thumb_url,
                    full_url=full_url,
                    label=label,
                ))

    log.debug(f"fanart.tv: found {len(options)} images for release group {release_group_id}")
    return options


def discover_filesystem(folder_path: str, album_id: int) -> List[ArtworkOption]:
    """Find local cover art files and return them as options.

    Thumbnail URLs point to GET /api/albums/{album_id}/cover?file={name}.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    cover_keywords = {"cover", "front", "folder", "albumart", "album", "artwork"}

    options = []
    try:
        for name in os.listdir(folder_path):
            ext = os.path.splitext(name)[1].lower()
            if ext not in image_extensions:
                continue

            base = os.path.splitext(name)[0].lower()
            if not any(kw in base for kw in cover_keywords):
                continue

            filepath = os.path.join(folder_path, name)
            if not os.path.isfile(filepath):
                continue

            url = f"/api/albums/{album_id}/cover?file={name}"
            options.append(ArtworkOption(
                source="filesystem",
                thumbnail_url=url,
                full_url=url,
                label=name,
            ))
    except Exception as e:
        log.debug(f"Filesystem discovery error for {folder_path}: {e}")

    log.debug(f"Filesystem: found {len(options)} images in {folder_path}")
    return options
