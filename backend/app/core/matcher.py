import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.audio_reader import AlbumInfo
from app.core.musicbrainz_client import MBRelease, search_releases, get_release_details
from app.core.fingerprint import (
    FingerprintMatch, fingerprint_album, aggregate_release_candidates,
    compute_fingerprint_score,
)
from app.config import settings
from app.utils.logger import log


@dataclass
class MatchScore:
    release: MBRelease
    total_score: float = 0.0
    text_score: float = 0.0
    track_count_score: float = 0.0
    duration_score: float = 0.0
    media_score: float = 0.0
    country_score: float = 0.0
    year_score: float = 0.0
    fingerprint_score: float = 0.0
    penalty: float = 0.0
    details: List[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    if not text:
        return ""
    # Unicode normalize
    text = unicodedata.normalize("NFKD", text)
    # Lowercase
    text = text.lower()
    # Remove accents
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Remove special characters, keep alphanumeric and spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _text_similarity(a: str, b: str) -> float:
    """Simple text similarity: ratio of matching words."""
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _score_text_match(local: AlbumInfo, release: MBRelease) -> tuple[float, list[str]]:
    """Score text match for artist + album (max 30 points)."""
    score = 0.0
    details = []

    artist_sim = _text_similarity(local.artist or "", release.artist)

    # Compare album names: try both raw and cleaned versions, take best
    local_album = local.album or ""
    album_sim = _text_similarity(local_album, release.title)
    cleaned_album = _clean_album_name(local_album)
    if cleaned_album != local_album:
        cleaned_sim = _text_similarity(cleaned_album, release.title)
        album_sim = max(album_sim, cleaned_sim)

    # Artist: up to 15 points
    artist_pts = artist_sim * 15.0
    score += artist_pts
    details.append(f"Artist similarity: {artist_sim:.0%} ({artist_pts:.1f}/15)")

    # Album: up to 15 points
    album_pts = album_sim * 15.0
    score += album_pts
    details.append(f"Album similarity: {album_sim:.0%} ({album_pts:.1f}/15)")

    return score, details


def _score_track_count(local: AlbumInfo, release: MBRelease) -> tuple[float, list[str]]:
    """Score track count match (max 20 points)."""
    local_count = local.track_count
    mb_count = release.track_count

    if local_count == 0 or mb_count == 0:
        return 0.0, ["Track count unknown"]

    diff = abs(local_count - mb_count)

    if diff == 0:
        return 20.0, [f"Track count exact match: {local_count}"]
    elif diff == 1:
        return 15.0, [f"Track count off by 1: local={local_count} vs MB={mb_count}"]
    elif diff == 2:
        return 10.0, [f"Track count off by 2: local={local_count} vs MB={mb_count}"]
    elif diff <= 4:
        return 5.0, [f"Track count off by {diff}: local={local_count} vs MB={mb_count}"]
    else:
        return 0.0, [f"Track count mismatch: local={local_count} vs MB={mb_count}"]


def _score_durations(local: AlbumInfo, release: MBRelease) -> tuple[float, list[str]]:
    """Score duration match (max 20 points). Compare per-track durations.

    For multi-disc albums, matches by (disc_number, track_number) first,
    falling back to flat index order.
    """
    local_tracks = sorted(
        [t for t in local.tracks if t.duration],
        key=lambda t: (t.disc_number or 1, t.track_number or 0),
    )

    if not local_tracks or not release.tracks:
        return 0.0, ["No duration data available"]

    # Build MB lookup by (disc_number, disc_position)
    mb_by_disc: dict[tuple[int, int], 'MBTrack'] = {}
    for mt in release.tracks:
        if mt.disc_position > 0:
            mb_by_disc[(mt.disc_number, mt.disc_position)] = mt

    mb_flat = sorted(release.tracks, key=lambda t: t.position)

    total_deviation = 0.0
    matched = 0

    for i, lt in enumerate(local_tracks):
        mb_track = None
        # Try disc-aware lookup first
        disc = lt.disc_number or 1
        trk = lt.track_number or 0
        if trk > 0 and (disc, trk) in mb_by_disc:
            mb_track = mb_by_disc[(disc, trk)]
        elif i < len(mb_flat):
            mb_track = mb_flat[i]

        if mb_track is None:
            continue

        local_dur = lt.duration
        mb_dur = mb_track.duration_seconds

        if local_dur and mb_dur and mb_dur > 0:
            deviation = abs(local_dur - mb_dur) / mb_dur
            total_deviation += deviation
            matched += 1

    if matched == 0:
        return 0.0, ["No duration comparisons possible"]

    avg_deviation = total_deviation / matched

    if avg_deviation <= 0.02:  # within 2%
        score = 20.0
    elif avg_deviation <= 0.05:  # within 5%
        score = 16.0
    elif avg_deviation <= 0.10:  # within 10%
        score = 10.0
    elif avg_deviation <= 0.20:  # within 20%
        score = 5.0
    else:
        score = 0.0

    details = [f"Avg duration deviation: {avg_deviation:.1%} over {matched} tracks ({score:.0f}/20)"]
    return score, details


def _score_media(release: MBRelease) -> tuple[float, list[str]]:
    """Score preferred media type (max 10 points)."""
    if not release.media:
        return 5.0, ["Media format unknown, neutral score"]

    if release.media in settings.preferred_media:
        idx = settings.preferred_media.index(release.media)
        pts = 10.0 - (idx * 2)  # first preferred = 10, second = 8, etc.
        pts = max(pts, 6.0)
        return pts, [f"Preferred media: {release.media} ({pts:.0f}/10)"]

    return 2.0, [f"Non-preferred media: {release.media} (2/10)"]


def _score_country(release: MBRelease) -> tuple[float, list[str]]:
    """Score preferred country (max 10 points)."""
    if not release.country:
        return 5.0, ["Country unknown, neutral score"]

    if release.country in settings.preferred_countries:
        idx = settings.preferred_countries.index(release.country)
        pts = 10.0 - (idx * 1.5)
        pts = max(pts, 5.0)
        return pts, [f"Preferred country: {release.country} ({pts:.0f}/10)"]

    return 2.0, [f"Non-preferred country: {release.country} (2/10)"]


def _score_year(local: AlbumInfo, release: MBRelease) -> tuple[float, list[str]]:
    """Score year match (max 10 points)."""
    local_year = local.year
    mb_year = release.original_year or release.year

    if not local_year or not mb_year:
        return 5.0, ["Year unknown, neutral score"]

    diff = abs(local_year - mb_year)
    if diff == 0:
        return 10.0, [f"Year exact match: {mb_year}"]
    elif diff <= 1:
        return 8.0, [f"Year off by 1: local={local_year} vs MB={mb_year}"]
    elif diff <= 3:
        return 5.0, [f"Year off by {diff}: local={local_year} vs MB={mb_year}"]
    else:
        return 2.0, [f"Year mismatch: local={local_year} vs MB={mb_year}"]


def _calculate_penalties(local: AlbumInfo, release: MBRelease) -> tuple[float, list[str]]:
    """Calculate penalties."""
    penalty = 0.0
    details = []

    local_discs = set(t.disc_number or 1 for t in local.tracks)
    local_is_single = len(local_discs) <= 1
    mb_is_multi = release.disc_count > 1

    # Penalize only when local is single-disc but MB is multi-disc with many more tracks
    if local_is_single and mb_is_multi and release.track_count > local.track_count + 5:
        penalty += 15.0
        details.append(f"Multi-disc penalty: MB has {release.track_count} tracks ({release.disc_count} discs) vs local {local.track_count} (-15)")

    # Penalize when local is multi-disc but MB is single-disc
    if not local_is_single and not mb_is_multi:
        penalty += 10.0
        details.append(f"Disc mismatch: local has {len(local_discs)} discs but MB is single-disc (-10)")

    return penalty, details


def score_release(
    local: AlbumInfo,
    release: MBRelease,
    fingerprint_matches: Optional[List[FingerprintMatch]] = None,
) -> MatchScore:
    """Score a single release against local album data."""
    match = MatchScore(release=release)

    text_score, text_details = _score_text_match(local, release)
    match.text_score = text_score
    match.details.extend(text_details)

    tc_score, tc_details = _score_track_count(local, release)
    match.track_count_score = tc_score
    match.details.extend(tc_details)

    dur_score, dur_details = _score_durations(local, release)
    match.duration_score = dur_score
    match.details.extend(dur_details)

    media_score, media_details = _score_media(release)
    match.media_score = media_score
    match.details.extend(media_details)

    country_score, country_details = _score_country(release)
    match.country_score = country_score
    match.details.extend(country_details)

    year_score, year_details = _score_year(local, release)
    match.year_score = year_score
    match.details.extend(year_details)

    # Fingerprint bonus (max 15 points)
    if fingerprint_matches:
        for fp_match in fingerprint_matches:
            if fp_match.release_id == release.release_id:
                match.fingerprint_score = compute_fingerprint_score(fp_match, local.track_count)
                match.details.append(
                    f"Fingerprint: {fp_match.matched_tracks}/{fp_match.total_tracks} tracks, "
                    f"avg score {fp_match.avg_score:.0%} ({match.fingerprint_score:.1f}/15)"
                )
                break

    penalty, penalty_details = _calculate_penalties(local, release)
    match.penalty = penalty
    match.details.extend(penalty_details)

    match.total_score = (
        match.text_score
        + match.track_count_score
        + match.duration_score
        + match.media_score
        + match.country_score
        + match.year_score
        + match.fingerprint_score
        - match.penalty
    )
    # Clamp to 0-100
    match.total_score = max(0.0, min(100.0, match.total_score))

    return match


def _clean_album_name(name: str) -> str:
    """Strip disc indicators, edition suffixes, and brackets from album name."""
    if not name:
        return name
    # Remove "- CD 1", "- Disc 2", "(CD1)", "[Disc 1]", etc.
    cleaned = re.sub(r"\s*[-–]\s*(CD|Disc|Disk)\s*\d+\s*$", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[\(\[](CD|Disc|Disk)\s*\d+[\)\]]", "", cleaned, flags=re.IGNORECASE)
    # Remove edition suffixes like "(Legacy Edition)", "(Deluxe)", "(Remastered)"
    cleaned = re.sub(r"\s*[\(\[](Legacy|Deluxe|Special|Limited|Remastered|Expanded|Anniversary|Bonus|Premium)\s*(Edition|Version|Remaster)?[\)\]]", "", cleaned, flags=re.IGNORECASE)
    # Remove trailing " - " artifacts
    cleaned = re.sub(r"\s*[-–]\s*$", "", cleaned)
    return cleaned.strip()


def _generate_search_variants(artist: str, album: str) -> List[tuple[str, str]]:
    """Generate search query variants, from most specific to most generic."""
    variants = [(artist, album)]

    cleaned = _clean_album_name(album)
    if cleaned != album:
        variants.append((artist, cleaned))

    # Try without anything in brackets
    no_brackets = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", album).strip()
    no_brackets = re.sub(r"\s*[-–]\s*$", "", no_brackets).strip()
    if no_brackets and no_brackets != album and no_brackets != cleaned:
        variants.append((artist, no_brackets))

    return variants


def find_matches(local: AlbumInfo, limit: int = 10) -> List[MatchScore]:
    """Find and score MusicBrainz matches for a local album.

    Returns scored candidates sorted by confidence (highest first).
    Tries multiple search variants if initial search returns no results.
    """
    if not local.artist and not local.album:
        log.warning(f"No artist/album metadata for {local.path}, skipping match")
        return []

    artist = local.artist or "Unknown"
    album = local.album or "Unknown"

    log.info(f"Matching: {artist} - {album} ({local.track_count} tracks)")

    # Try search variants until we get results
    variants = _generate_search_variants(artist, album)
    search_results = []

    for search_artist, search_album in variants:
        search_results = search_releases(search_artist, search_album, limit=15)
        if search_results:
            if search_album != album:
                log.info(f"Found results with cleaned name: '{search_album}'")
            break
        log.info(f"No results for '{search_artist}' - '{search_album}', trying next variant...")

    if not search_results:
        log.warning(f"No MusicBrainz results for {artist} - {album} (tried {len(variants)} variants)")
        return []

    # Pre-filter: skip releases with wildly different track counts
    filtered = []
    for release in search_results:
        if release.track_count > 0:
            diff = abs(release.track_count - local.track_count)
            if diff > local.track_count:  # more than 2x difference
                log.debug(f"Skipping {release.release_id}: track count {release.track_count} vs {local.track_count}")
                continue
        filtered.append(release)

    # Pre-score using search data (no detail fetch needed) to pick top candidates
    pre_scored = [score_release(local, release) for release in filtered]
    pre_scored.sort(key=lambda m: m.total_score, reverse=True)

    # Fetch full details only for the top 5 candidates (saves ~10s per album)
    top_n = 5
    top_candidates = pre_scored[:top_n]
    log.info(f"Fetching details for top {len(top_candidates)} of {len(filtered)} candidates")

    detailed_scored = []
    for match in top_candidates:
        detailed = get_release_details(match.release.release_id)
        if detailed:
            detailed_scored.append(score_release(local, detailed))

    # Sort final scores
    detailed_scored.sort(key=lambda m: m.total_score, reverse=True)

    # Return top results
    return detailed_scored[:limit]


def find_matches_by_fingerprint(
    local: AlbumInfo,
    api_key: str,
    limit: int = 10,
) -> List[MatchScore]:
    """Fallback path: find matches using audio fingerprinting when text search fails.

    Fingerprints tracks → aggregates release candidates → fetches MB details → scores.
    """
    log.info(f"Fingerprint fallback for {local.path}")

    fingerprints = fingerprint_album(api_key, local.tracks)
    if not fingerprints:
        log.warning("Fingerprint fallback: no fingerprints generated")
        return []

    fp_matches = aggregate_release_candidates(fingerprints)
    if not fp_matches:
        log.warning("Fingerprint fallback: no release candidates from AcoustID")
        return []

    log.info(f"Fingerprint found {len(fp_matches)} candidate releases, fetching details...")

    scored = []
    for fp_match in fp_matches[:5]:  # fetch details for top 5
        release = get_release_details(fp_match.release_id)
        if release:
            scored.append(score_release(local, release, fingerprint_matches=fp_matches))

    scored.sort(key=lambda m: m.total_score, reverse=True)
    return scored[:limit]


def decide_action(score: float) -> str:
    """Decide what to do based on confidence score.

    Returns: 'auto_tag', 'needs_review', or 'skip'
    """
    if score >= settings.confidence_auto_threshold:
        return "auto_tag"
    elif score >= settings.confidence_review_threshold:
        return "needs_review"
    else:
        return "skip"
