from typing import Optional

from sqlalchemy.orm import Session

from app.core.audio_reader import scan_album_folder
from app.core.matcher import find_matches, decide_action, MatchScore
from app.core.musicbrainz_client import MBRelease, get_release_details
from app.core.tagger import write_tags, TagData
from app.core.artwork_fetcher import fetch_artwork, save_artwork_to_folder
from app.models import Album, Track, MatchCandidate, ActivityLog
from app.database import SessionLocal
from app.utils.logger import log


def process_album(album_id: int, release_id: Optional[str] = None) -> bool:
    """Full tagging workflow for an album.

    1. Read local files
    2. Match on MusicBrainz (or use provided release_id)
    3. Score candidates, store in DB
    4. If auto_tag or release_id provided: write tags + fetch artwork
    5. Update DB status

    Returns True if tags were written.
    """
    db = SessionLocal()
    try:
        album = db.query(Album).filter(Album.id == album_id).first()
        if not album:
            log.error(f"Album {album_id} not found")
            return False

        log.info(f"Processing album {album_id}: {album.artist} - {album.album}")

        # Update status to matching
        album.status = "matching"
        db.commit()

        # Step 1: Read local files
        album_info = scan_album_folder(album.path)
        if not album_info:
            album.status = "failed"
            album.error_message = "Could not read audio files"
            db.commit()
            return False

        # Step 2: Match on MusicBrainz
        if release_id:
            # User selected a specific release
            selected_release = get_release_details(release_id)
            if not selected_release:
                album.status = "failed"
                album.error_message = f"Could not fetch release {release_id}"
                db.commit()
                return False
            matches = []
            action = "auto_tag"
        else:
            # Automatic matching
            matches = find_matches(album_info, limit=10)
            if not matches:
                album.status = "failed"
                album.error_message = "No MusicBrainz matches found"
                db.add(ActivityLog(album_id=album_id, action="match_failed", details="No results"))
                db.commit()
                return False

            # Step 3: Store candidates in DB
            _store_candidates(db, album_id, matches)

            best = matches[0]
            action = decide_action(best.total_score)
            selected_release = best.release

            log.info(f"Best match: {selected_release.artist} - {selected_release.title} "
                      f"({best.total_score:.1f}/100) -> {action}")

        # Step 4: Decide action
        if action == "needs_review":
            album.status = "needs_review"
            album.match_confidence = matches[0].total_score if matches else None
            db.add(ActivityLog(
                album_id=album_id, action="needs_review",
                details=f"Best: {selected_release.title} ({matches[0].total_score:.0f}%)" if matches else None,
            ))
            db.commit()
            log.info(f"Album {album_id} queued for review")
            return False

        elif action == "skip":
            album.status = "skipped"
            album.match_confidence = matches[0].total_score if matches else None
            db.add(ActivityLog(
                album_id=album_id, action="skipped",
                details=f"Low confidence ({matches[0].total_score:.0f}%)" if matches else None,
            ))
            db.commit()
            log.info(f"Album {album_id} skipped (low confidence)")
            return False

        # auto_tag: write tags and fetch artwork
        album.match_confidence = matches[0].total_score if matches else 100.0

        # Mark selected candidate
        if release_id:
            _mark_selected_candidate(db, album_id, release_id)

        # Step 5: Write tags to files
        success = _write_album_tags(db, album, selected_release)
        if not success:
            album.status = "failed"
            album.error_message = "Failed to write tags"
            db.commit()
            return False

        # Step 6: Fetch and save artwork
        _fetch_and_save_artwork(db, album, selected_release)

        # Update album metadata from MusicBrainz
        album.artist = selected_release.artist
        album.album = selected_release.title
        album.year = selected_release.original_year or selected_release.year
        album.musicbrainz_release_id = selected_release.release_id
        album.status = "tagged"
        album.error_message = None

        db.add(ActivityLog(
            album_id=album_id, action="tagged",
            details=f"{selected_release.artist} - {selected_release.title}",
        ))
        db.commit()

        log.info(f"Album {album_id} tagged successfully: {selected_release.artist} - {selected_release.title}")
        return True

    except Exception as e:
        log.error(f"Error processing album {album_id}: {e}")
        try:
            album = db.query(Album).filter(Album.id == album_id).first()
            if album:
                album.status = "failed"
                album.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
        return False
    finally:
        db.close()


def _store_candidates(db: Session, album_id: int, matches: list[MatchScore]):
    """Store match candidates in the database."""
    # Remove old candidates
    db.query(MatchCandidate).filter(MatchCandidate.album_id == album_id).delete()

    for i, match in enumerate(matches):
        r = match.release
        candidate = MatchCandidate(
            album_id=album_id,
            musicbrainz_release_id=r.release_id,
            confidence=match.total_score,
            artist=r.artist,
            album=r.title,
            year=r.year,
            original_year=r.original_year,
            track_count=r.track_count,
            country=r.country,
            media=r.media,
            label=r.label,
            barcode=r.barcode,
            is_selected=(i == 0),
        )
        db.add(candidate)
    db.flush()


def _mark_selected_candidate(db: Session, album_id: int, release_id: str):
    """Mark a specific candidate as selected."""
    db.query(MatchCandidate).filter(
        MatchCandidate.album_id == album_id
    ).update({"is_selected": False})

    db.query(MatchCandidate).filter(
        MatchCandidate.album_id == album_id,
        MatchCandidate.musicbrainz_release_id == release_id,
    ).update({"is_selected": True})
    db.flush()


def _write_album_tags(db: Session, album: Album, release: MBRelease) -> bool:
    """Write tags to all tracks in the album."""
    tracks = db.query(Track).filter(Track.album_id == album.id).order_by(
        Track.disc_number, Track.track_number
    ).all()

    mb_tracks = sorted(release.tracks, key=lambda t: t.position)
    track_total = release.track_count
    year = release.original_year or release.year

    success_count = 0
    for i, track in enumerate(tracks):
        # Match local track to MB track by position
        mb_track = mb_tracks[i] if i < len(mb_tracks) else None

        tag_data = TagData(
            artist=release.artist,
            album_artist=release.artist,
            album=release.title,
            year=year,
            track_total=track_total,
            disc_number=track.disc_number or 1,
            musicbrainz_release_id=release.release_id,
        )

        if mb_track:
            tag_data.title = mb_track.title
            tag_data.track_number = mb_track.position
            tag_data.musicbrainz_recording_id = mb_track.recording_id

        if write_tags(track.path, tag_data):
            # Update track in DB
            if mb_track:
                track.title = mb_track.title
                track.musicbrainz_recording_id = mb_track.recording_id
            track.artist = release.artist
            track.status = "tagged"
            success_count += 1
        else:
            track.status = "failed"
            track.error_message = "Failed to write tags"

    db.flush()
    log.info(f"Tags written to {success_count}/{len(tracks)} tracks")
    return success_count > 0


def _fetch_and_save_artwork(db: Session, album: Album, release: MBRelease):
    """Fetch artwork and embed in files + save to folder."""
    result = fetch_artwork(
        folder_path=album.path,
        artist=release.artist,
        album=release.title,
        musicbrainz_release_id=release.release_id,
        musicbrainz_release_group_id=release.release_group_id or "",
    )

    if not result:
        log.warning(f"No artwork found for album {album.id}")
        return

    image_data, mime = result

    # Save to folder
    saved_path = save_artwork_to_folder(album.path, image_data, mime)
    if saved_path:
        album.cover_path = saved_path

    # Embed in all tracks
    tracks = db.query(Track).filter(Track.album_id == album.id).all()
    embedded = 0
    for track in tracks:
        tag_data = TagData(cover_data=image_data, cover_mime=mime)
        if write_tags(track.path, tag_data):
            embedded += 1

    log.info(f"Artwork embedded in {embedded}/{len(tracks)} tracks")
