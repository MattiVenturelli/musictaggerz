import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.utils.logger import log


@dataclass
class TrackFingerprint:
    path: str
    duration: float
    fingerprint: str
    acoustid_results: List["AcoustIDResult"] = field(default_factory=list)


@dataclass
class AcoustIDResult:
    recording_id: str
    score: float
    title: str = ""
    artist: str = ""
    release_ids: List[str] = field(default_factory=list)


@dataclass
class FingerprintMatch:
    release_id: str
    matched_tracks: int = 0
    total_tracks: int = 0
    avg_score: float = 0.0
    recording_ids: List[str] = field(default_factory=list)


# Rate limiting for AcoustID (separate from MusicBrainz)
_last_acoustid_request: float = 0.0
_ACOUSTID_MIN_INTERVAL: float = 0.35  # AcoustID allows 3 req/s


def _acoustid_rate_limit():
    global _last_acoustid_request
    now = time.time()
    elapsed = now - _last_acoustid_request
    if elapsed < _ACOUSTID_MIN_INTERVAL:
        time.sleep(_ACOUSTID_MIN_INTERVAL - elapsed)
    _last_acoustid_request = time.time()


def fingerprint_file(path: str) -> Optional[TrackFingerprint]:
    """Generate a Chromaprint fingerprint for an audio file.

    Uses fpcalc via the acoustid library. Returns None on failure.
    """
    try:
        import acoustid
        duration, fingerprint = acoustid.fingerprint_file(path, force_fpcalc=True)
        return TrackFingerprint(path=path, duration=duration, fingerprint=fingerprint)
    except Exception as e:
        log.warning(f"Fingerprint failed for {path}: {e}")
        return None


def lookup_fingerprint(api_key: str, fp: TrackFingerprint) -> TrackFingerprint:
    """Look up a fingerprint on AcoustID. Populates fp.acoustid_results in place.

    Calls the AcoustID web service with meta=['recordings','releases'].
    """
    import acoustid

    _acoustid_rate_limit()

    try:
        results = acoustid.lookup(
            api_key,
            fp.fingerprint,
            fp.duration,
            meta=["recordings", "releases"],
        )
    except acoustid.WebServiceError as e:
        log.warning(f"AcoustID lookup failed for {fp.path}: {e}")
        return fp

    for result in results.get("results", []):
        score = float(result.get("score", 0))
        for recording in result.get("recordings", []):
            rec_id = recording.get("id", "")
            if not rec_id:
                continue

            title = recording.get("title", "")
            artist = ""
            for ac in recording.get("artists", []):
                if artist:
                    artist += ac.get("joinphrase", "")
                artist += ac.get("name", "")

            release_ids = []
            for rel in recording.get("releases", []):
                rid = rel.get("id", "")
                if rid:
                    release_ids.append(rid)

            fp.acoustid_results.append(AcoustIDResult(
                recording_id=rec_id,
                score=score,
                title=title,
                artist=artist,
                release_ids=release_ids,
            ))

    return fp


def _select_tracks(tracks: list, max_tracks: int = 5) -> list:
    """Select tracks distributed evenly across the album, skipping short tracks (<30s)."""
    eligible = [(i, t) for i, t in enumerate(tracks) if t.duration and t.duration >= 30.0]
    if not eligible:
        return []
    if len(eligible) <= max_tracks:
        return [t for _, t in eligible]

    # Pick equidistant indices
    step = len(eligible) / max_tracks
    selected = []
    for j in range(max_tracks):
        idx = int(j * step)
        selected.append(eligible[idx][1])
    return selected


def fingerprint_album(
    api_key: str,
    tracks: list,
    max_tracks: int = 5,
) -> List[TrackFingerprint]:
    """Fingerprint a selection of tracks from an album and look them up on AcoustID.

    Args:
        api_key: AcoustID API key
        tracks: list of TrackInfo objects (from audio_reader)
        max_tracks: maximum number of tracks to fingerprint

    Returns list of TrackFingerprint with populated acoustid_results.
    """
    selected = _select_tracks(tracks, max_tracks)
    if not selected:
        log.warning("No eligible tracks for fingerprinting (all too short?)")
        return []

    fingerprints = []
    for track in selected:
        fp = fingerprint_file(track.path)
        if fp:
            fingerprints.append(fp)

    if not fingerprints:
        log.warning("All fingerprint attempts failed")
        return []

    log.info(f"Fingerprinted {len(fingerprints)}/{len(selected)} tracks, looking up on AcoustID...")

    for fp in fingerprints:
        lookup_fingerprint(api_key, fp)

    return fingerprints


def aggregate_release_candidates(fingerprints: List[TrackFingerprint]) -> List[FingerprintMatch]:
    """Aggregate AcoustID results across multiple tracks to find the most likely release.

    Groups results by release_id, counts how many tracks matched each release,
    and computes average score. Returns top 10 sorted by matched_tracks then avg_score.
    """
    # release_id -> {scores: [], recording_ids: set()}
    release_data: dict[str, dict] = {}

    for fp in fingerprints:
        # Track which releases this particular track matched (avoid double-counting)
        seen_releases_for_track: set[str] = set()

        for result in fp.acoustid_results:
            for release_id in result.release_ids:
                if release_id in seen_releases_for_track:
                    continue
                seen_releases_for_track.add(release_id)

                if release_id not in release_data:
                    release_data[release_id] = {"scores": [], "recording_ids": set()}

                release_data[release_id]["scores"].append(result.score)
                release_data[release_id]["recording_ids"].add(result.recording_id)

    matches = []
    total_tracks = len(fingerprints)

    for release_id, data in release_data.items():
        scores = data["scores"]
        matches.append(FingerprintMatch(
            release_id=release_id,
            matched_tracks=len(scores),
            total_tracks=total_tracks,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            recording_ids=list(data["recording_ids"]),
        ))

    # Sort: most matched tracks first, then highest avg score
    matches.sort(key=lambda m: (m.matched_tracks, m.avg_score), reverse=True)
    return matches[:10]


def compute_fingerprint_score(fp_match: FingerprintMatch, local_track_count: int) -> float:
    """Convert a FingerprintMatch into a score (0-15 points).

    Scoring:
    - Base: proportion of fingerprinted tracks that matched this release (0-10 pts)
    - Bonus: average AcoustID confidence score (0-5 pts)

    A perfect match (all tracks matched with score 1.0) = 15 points.
    """
    if fp_match.matched_tracks == 0 or fp_match.total_tracks == 0:
        return 0.0

    match_ratio = fp_match.matched_tracks / fp_match.total_tracks
    base_score = match_ratio * 10.0

    confidence_bonus = fp_match.avg_score * 5.0

    total = base_score + confidence_bonus
    return min(15.0, max(0.0, total))
