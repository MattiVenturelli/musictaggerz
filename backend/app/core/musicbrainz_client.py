import time
from dataclasses import dataclass, field
from typing import Optional, List

import musicbrainzngs

from app.utils.logger import log

# Initialize musicbrainzngs
musicbrainzngs.set_useragent("MusicTaggerz", "1.0.0", "https://github.com/musictaggerz")

# Known genre names for folksonomy tag fallback (lowercase).
# Used to filter user-submitted tags like "seen live" or "my favorites".
_KNOWN_GENRES: set[str] = {
    # broad
    "rock", "pop", "electronic", "hip hop", "jazz", "classical", "metal",
    "punk", "folk", "country", "blues", "soul", "funk", "reggae", "latin",
    "r&b", "gospel", "disco", "ska", "world",
    # rock
    "alternative rock", "indie rock", "hard rock", "progressive rock",
    "psychedelic rock", "art rock", "garage rock", "surf rock", "glam rock",
    "soft rock", "southern rock", "stoner rock", "krautrock", "math rock",
    "post-rock", "noise rock", "space rock", "blues rock", "folk rock",
    "country rock", "jazz rock", "punk rock",
    # metal
    "heavy metal", "death metal", "black metal", "thrash metal", "doom metal",
    "power metal", "symphonic metal", "progressive metal", "gothic metal",
    "nu metal", "sludge metal", "post-metal", "metalcore", "deathcore",
    "grindcore", "speed metal", "folk metal", "industrial metal",
    # punk
    "hardcore punk", "post-punk", "pop punk", "anarcho-punk", "crust punk",
    "melodic hardcore", "emo", "screamo", "grunge", "riot grrrl",
    # electronic
    "techno", "house", "trance", "ambient", "drum and bass", "dubstep",
    "idm", "industrial", "synthpop", "new wave", "darkwave", "ebm",
    "trip hop", "downtempo", "breakbeat", "electro", "uk garage",
    "deep house", "tech house", "minimal techno", "acid house",
    "progressive house", "progressive trance", "psytrance", "hardcore techno",
    "gabber", "jungle", "liquid funk", "neurofunk", "future bass",
    "chillwave", "vaporwave", "synthwave", "retrowave", "lo-fi",
    "glitch", "noise", "dark ambient", "drone",
    # hip hop
    "rap", "trap", "conscious hip hop", "gangsta rap", "boom bap",
    "lo-fi hip hop", "cloud rap", "grime", "uk hip hop", "abstract hip hop",
    # jazz
    "bebop", "cool jazz", "free jazz", "fusion", "smooth jazz",
    "acid jazz", "latin jazz", "big band", "swing", "bossa nova",
    # classical
    "baroque", "romantic", "modern classical", "contemporary classical",
    "opera", "chamber music", "orchestral", "choral", "minimalism",
    # folk/country
    "bluegrass", "americana", "celtic", "neofolk", "freak folk",
    "indie folk", "singer-songwriter", "acoustic",
    # soul/funk/r&b
    "neo-soul", "motown", "northern soul", "contemporary r&b",
    "new jack swing", "quiet storm", "p-funk",
    # reggae/caribbean
    "dub", "dancehall", "rocksteady", "roots reggae", "ragga",
    "soca", "calypso",
    # african/world
    "afrobeat", "afropop", "highlife", "soukous", "mbalax",
    "fado", "flamenco", "ranchera", "cumbia", "salsa", "merengue",
    "bachata", "reggaeton", "mpb", "samba", "forró", "tango",
    # pop variants
    "indie pop", "dream pop", "shoegaze", "noise pop", "power pop",
    "baroque pop", "chamber pop", "electropop", "dance-pop", "synth-pop",
    "art pop", "teen pop", "k-pop", "j-pop", "c-pop", "europop",
    "britpop", "jangle pop",
    # other
    "experimental", "avant-garde", "spoken word", "soundtrack",
    "new age", "easy listening", "lounge", "exotica",
    "post-industrial", "martial industrial",
}

# Rate limiting: MusicBrainz allows 1 request per second
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 1.1  # slightly over 1s to be safe


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


@dataclass
class MBTrack:
    position: int
    title: str
    duration_ms: Optional[int] = None
    recording_id: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.duration_ms is not None:
            return self.duration_ms / 1000.0
        return None


@dataclass
class MBRelease:
    release_id: str
    title: str
    artist: str
    year: Optional[int] = None
    original_year: Optional[int] = None
    track_count: int = 0
    country: Optional[str] = None
    media: Optional[str] = None
    label: Optional[str] = None
    barcode: Optional[str] = None
    tracks: List[MBTrack] = field(default_factory=list)
    release_group_id: Optional[str] = None
    genres: List[str] = field(default_factory=list)


def search_releases(artist: str, album: str, limit: int = 20) -> List[MBRelease]:
    """Search MusicBrainz for releases matching artist + album text."""
    _rate_limit()

    try:
        query = f'artist:"{artist}" AND release:"{album}"'
        log.info(f"MusicBrainz search: {query}")

        result = musicbrainzngs.search_releases(
            query=query,
            limit=limit,
        )
    except Exception as e:
        log.error(f"MusicBrainz search error: {e}")
        return []

    releases = []
    for r in result.get("release-list", []):
        artist_name = ""
        if "artist-credit" in r:
            parts = []
            for ac in r["artist-credit"]:
                if isinstance(ac, dict) and "artist" in ac:
                    parts.append(ac["artist"].get("name", ""))
                    parts.append(ac.get("joinphrase", ""))
                elif isinstance(ac, str):
                    parts.append(ac)
            artist_name = "".join(parts).strip()

        year = None
        if "date" in r:
            try:
                year = int(r["date"][:4])
            except (ValueError, IndexError):
                pass

        track_count = 0
        media_type = None
        if "medium-list" in r:
            for medium in r["medium-list"]:
                track_count += int(medium.get("track-count", 0))
                if not media_type:
                    media_type = medium.get("format")

        label = None
        if "label-info-list" in r:
            for li in r["label-info-list"]:
                if "label" in li:
                    label = li["label"].get("name")
                    break

        releases.append(MBRelease(
            release_id=r["id"],
            title=r.get("title", ""),
            artist=artist_name,
            year=year,
            track_count=track_count,
            country=r.get("country"),
            media=media_type,
            label=label,
            barcode=r.get("barcode"),
            release_group_id=r.get("release-group", {}).get("id"),
        ))

    log.info(f"MusicBrainz found {len(releases)} releases for '{artist}' - '{album}'")
    return releases


def get_release_details(release_id: str) -> Optional[MBRelease]:
    """Get full release details including track list with durations."""
    _rate_limit()

    try:
        result = musicbrainzngs.get_release_by_id(
            release_id,
            includes=["recordings", "artist-credits", "labels", "release-groups", "genres", "tags"],
        )
    except Exception as e:
        log.error(f"MusicBrainz release lookup error for {release_id}: {e}")
        return None

    r = result.get("release", {})

    artist_name = ""
    if "artist-credit" in r:
        parts = []
        for ac in r["artist-credit"]:
            if isinstance(ac, dict) and "artist" in ac:
                parts.append(ac["artist"].get("name", ""))
                parts.append(ac.get("joinphrase", ""))
            elif isinstance(ac, str):
                parts.append(ac)
        artist_name = "".join(parts).strip()

    year = None
    if "date" in r:
        try:
            year = int(r["date"][:4])
        except (ValueError, IndexError):
            pass

    # Get original year from release group
    original_year = None
    rg = r.get("release-group", {})
    if "first-release-date" in rg:
        try:
            original_year = int(rg["first-release-date"][:4])
        except (ValueError, IndexError):
            pass

    tracks = []
    media_type = None
    label = None
    barcode = r.get("barcode")
    total_track_count = 0

    if "medium-list" in r:
        for medium in r["medium-list"]:
            if not media_type:
                media_type = medium.get("format")
            disc_offset = total_track_count
            for t in medium.get("track-list", []):
                rec = t.get("recording", {})
                duration_ms = None
                if "length" in t:
                    try:
                        duration_ms = int(t["length"])
                    except (ValueError, TypeError):
                        pass
                if duration_ms is None and "length" in rec:
                    try:
                        duration_ms = int(rec["length"])
                    except (ValueError, TypeError):
                        pass

                position = disc_offset + int(t.get("position", 0))
                tracks.append(MBTrack(
                    position=position,
                    title=rec.get("title", t.get("title", "")),
                    duration_ms=duration_ms,
                    recording_id=rec.get("id"),
                ))
            total_track_count += int(medium.get("track-count", 0))

    if "label-info-list" in r:
        for li in r["label-info-list"]:
            if "label" in li:
                label = li["label"].get("name")
                break

    # Collect genres: prefer official genre-list, fall back to tag-list filtered by known genres
    genre_map: dict[str, int] = {}
    for g in r.get("genre-list", []):
        name = g.get("name", "").strip()
        count = int(g.get("count", 0))
        if name:
            genre_map[name] = genre_map.get(name, 0) + count
    for g in rg.get("genre-list", []):
        name = g.get("name", "").strip()
        count = int(g.get("count", 0))
        if name:
            genre_map[name] = genre_map.get(name, 0) + count

    if not genre_map:
        # Fallback: use folksonomy tags but only those that are recognized genre names
        for tag in r.get("tag-list", []):
            name = tag.get("name", "").strip().lower()
            count = int(tag.get("count", 0))
            if name in _KNOWN_GENRES and count > 0:
                genre_map[name] = genre_map.get(name, 0) + count
        for tag in rg.get("tag-list", []):
            name = tag.get("name", "").strip().lower()
            count = int(tag.get("count", 0))
            if name in _KNOWN_GENRES and count > 0:
                genre_map[name] = genre_map.get(name, 0) + count

    genres = [g for g, _ in sorted(genre_map.items(), key=lambda x: -x[1])]

    return MBRelease(
        release_id=r["id"],
        title=r.get("title", ""),
        artist=artist_name,
        year=year,
        original_year=original_year,
        track_count=total_track_count,
        country=r.get("country"),
        media=media_type,
        label=label,
        barcode=barcode,
        tracks=tracks,
        release_group_id=rg.get("id"),
        genres=genres,
    )


def search_by_artist_album(artist: str, album: str, limit: int = 20) -> List[MBRelease]:
    """Search and return releases with full track details.

    This is the main entry point: searches by text, then fetches
    full details (including track durations) for each candidate.
    """
    candidates = search_releases(artist, album, limit=limit)

    detailed = []
    for candidate in candidates:
        release = get_release_details(candidate.release_id)
        if release:
            detailed.append(release)

    return detailed
