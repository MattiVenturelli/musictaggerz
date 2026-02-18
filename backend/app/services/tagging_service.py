import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.core.audio_reader import scan_album_folder, scan_multi_disc_album, find_disc_subfolders
from app.core.matcher import find_matches, find_matches_by_fingerprint, decide_action, score_release, MatchScore
from app.core.musicbrainz_client import MBRelease, get_release_details
from app.core.fingerprint import fingerprint_album, aggregate_release_candidates
from app.core.tagger import write_tags, TagData
from app.core.artwork_fetcher import fetch_artwork, save_artwork_to_folder
from app.core.tag_backup import create_backup, read_full_tags
from app.models import Album, Track, MatchCandidate, ActivityLog
from app.database import SessionLocal
from app.config import settings
from app.services.notification_service import notifications
from app.utils.logger import log


def _progress(album_id: int, progress: float, message: str):
    """Send progress update with a small delay to let the event loop flush."""
    notifications.send_progress(album_id, progress, message)
    time.sleep(0.08)  # give the async event loop time to deliver the WS message


def process_album(album_id: int, release_id: Optional[str] = None, user_initiated: bool = False) -> bool:
    """Full tagging workflow for an album.

    1. Read local files
    2. Match on MusicBrainz (or use provided release_id)
    3. Score candidates, store in DB
    4. Decide action: write tags only if user_initiated OR auto mode is on
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
        notifications.send_album_update(album_id, "matching")
        _progress(album_id, 0.05, "Reading local files...")

        # Step 1: Read local files (detect multi-disc)
        disc_subs = find_disc_subfolders(album.path)
        if disc_subs:
            album_info = scan_multi_disc_album(album.path, disc_subs)
        else:
            album_info = scan_album_folder(album.path)
        if not album_info:
            album.status = "failed"
            album.error_message = "Could not read audio files"
            db.commit()
            return False

        # Step 2: Match on MusicBrainz
        _progress(album_id, 0.1, "Searching MusicBrainz...")
        if release_id:
            # User selected a specific release
            _progress(album_id, 0.15, f"Fetching release {release_id[:8]}...")
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

            acoustid_key = settings.acoustid_api_key
            fp_enabled = settings.fingerprint_enabled and bool(acoustid_key)
            best_text = matches[0].total_score if matches else 0

            if fp_enabled and not matches:
                # FALLBACK: text search failed, fingerprint is primary discovery
                _progress(album_id, 0.15, "Text search failed, fingerprinting tracks...")
                matches = find_matches_by_fingerprint(album_info, acoustid_key, limit=10)
            elif fp_enabled and best_text < settings.confidence_auto_threshold:
                # SUPPLEMENTARY: refine scores with fingerprint data
                _progress(album_id, 0.15, "Fingerprinting tracks for better matching...")
                fp_data = fingerprint_album(acoustid_key, album_info.tracks)
                if fp_data:
                    fp_matches = aggregate_release_candidates(fp_data)
                    if fp_matches:
                        matches = [
                            score_release(album_info, m.release, fingerprint_matches=fp_matches)
                            for m in matches
                        ]
                        matches.sort(key=lambda m: m.total_score, reverse=True)
            # else: score already high enough or fingerprinting disabled, skip

            if not matches:
                album.status = "failed"
                album.error_message = "No MusicBrainz matches found"
                db.add(ActivityLog(album_id=album_id, action="match_failed", details="No results"))
                db.commit()
                return False

            _progress(album_id, 0.25, f"Found {len(matches)} candidates, scoring...")

            # Step 3: Store candidates in DB
            _store_candidates(db, album_id, matches)

            best = matches[0]
            action = decide_action(best.total_score)
            selected_release = best.release

            # Manual mode: never auto-tag unless user explicitly triggered it
            if action == "auto_tag" and not user_initiated and not settings.auto_tag_on_scan:
                action = "needs_review"
                log.info(f"Manual mode: downgrading auto_tag to needs_review for album {album_id}")

            _progress(
                album_id, 0.3,
                f"Best: {selected_release.artist} - {selected_release.title} ({best.total_score:.0f}%)"
            )
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
            notifications.send_album_update(
                album_id, "needs_review",
                confidence=matches[0].total_score if matches else None,
                artist=selected_release.artist,
                album=selected_release.title,
            )
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
            notifications.send_album_update(album_id, "skipped")
            log.info(f"Album {album_id} skipped (low confidence)")
            return False

        # auto_tag: write tags and fetch artwork
        album.match_confidence = matches[0].total_score if matches else 100.0

        # Mark selected candidate
        if release_id:
            _mark_selected_candidate(db, album_id, release_id)

        # Step 5: Backup current tags before writing
        _progress(album_id, 0.35, "Backing up current tags...")
        create_backup(db, album.id, "musicbrainz_tag")

        # Step 5b: Write tags to files
        _progress(album_id, 0.4, "Writing tags to files...")
        success = _write_album_tags(db, album, selected_release, album_id)
        if not success:
            album.status = "failed"
            album.error_message = "Failed to write tags"
            db.commit()
            notifications.send_album_update(album_id, "failed", error="Failed to write tags")
            return False

        # Step 6: Backup before artwork, then fetch and save
        _progress(album_id, 0.75, "Fetching artwork...")
        create_backup(db, album.id, "artwork")
        _fetch_and_save_artwork(db, album, selected_release)

        # Step 7: Auto-fetch lyrics if enabled
        if settings.lyrics_enabled and settings.lyrics_auto_fetch:
            _progress(album_id, 0.88, "Fetching lyrics...")
            _fetch_lyrics_for_album(db, album)

        # Step 8: Auto-calculate ReplayGain if enabled
        if settings.replaygain_enabled and settings.replaygain_auto_calculate:
            _progress(album_id, 0.92, "Calculating ReplayGain...")
            _calculate_replaygain_for_album(db, album)

        _progress(album_id, 0.95, "Finalizing...")

        # Update album metadata from MusicBrainz
        album.artist = selected_release.artist
        album.album = selected_release.title
        album.year = selected_release.original_year or selected_release.year
        album.musicbrainz_release_id = selected_release.release_id
        album.musicbrainz_release_group_id = selected_release.release_group_id
        album.status = "tagged"
        album.error_message = None

        db.add(ActivityLog(
            album_id=album_id, action="tagged",
            details=f"{selected_release.artist} - {selected_release.title}",
        ))
        db.commit()

        log.info(f"Album {album_id} tagged successfully: {selected_release.artist} - {selected_release.title}")
        notifications.send_album_update(
            album_id, "tagged",
            artist=selected_release.artist,
            album=selected_release.title,
            confidence=album.match_confidence,
        )
        notifications.send_notification(
            "success",
            f"Tagged: {selected_release.artist} - {selected_release.title}",
        )
        return True

    except Exception as e:
        log.error(f"Error processing album {album_id}: {e}")
        try:
            album = db.query(Album).filter(Album.id == album_id).first()
            if album:
                album.status = "failed"
                album.error_message = str(e)[:500]
                db.commit()
                notifications.send_album_update(album_id, "failed", error=str(e)[:200])
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


def _write_album_tags(db: Session, album: Album, release: MBRelease, album_id: int = 0) -> bool:
    """Write tags to all tracks in the album."""
    tracks = db.query(Track).filter(Track.album_id == album.id).order_by(
        Track.disc_number, Track.track_number
    ).all()

    # Build MB lookup by (disc_number, disc_position)
    mb_by_disc: dict[tuple[int, int], 'MBTrack'] = {}
    for mt in release.tracks:
        if mt.disc_position > 0:
            mb_by_disc[(mt.disc_number, mt.disc_position)] = mt
    mb_flat = sorted(release.tracks, key=lambda t: t.position)

    year = release.original_year or release.year

    # Detect if local album is single-disc but MB release is multi-disc
    local_discs = set(t.disc_number or 1 for t in tracks)
    local_is_single_disc = len(local_discs) == 1
    mb_is_multi_disc = release.disc_count > 1

    # When local is single-disc but MB is multi-disc, local track numbers
    # can't be trusted (they may reflect a previous multi-disc tagging).
    # Use flat sequential matching sorted by file path.
    use_flat_only = local_is_single_disc and mb_is_multi_disc
    if use_flat_only:
        tracks = sorted(tracks, key=lambda t: t.path)

    disc_total = release.disc_count if mb_is_multi_disc and not local_is_single_disc else None
    total = len(tracks)

    success_count = 0
    for i, track in enumerate(tracks):
        disc_num = track.disc_number or 1

        # Match local track to MB track
        mb_track = None
        if use_flat_only:
            # Flat sequential matching by file path order
            if i < len(mb_flat):
                mb_track = mb_flat[i]
        else:
            # Disc-aware lookup, then flat fallback
            trk_num = track.track_number or 0
            if trk_num > 0 and (disc_num, trk_num) in mb_by_disc:
                mb_track = mb_by_disc[(disc_num, trk_num)]
            elif i < len(mb_flat):
                mb_track = mb_flat[i]

        if album_id and total > 0:
            pct = 0.4 + (i / total) * 0.3  # progress 0.4 -> 0.7
            title_preview = mb_track.title if mb_track else track.title
            _progress(album_id, pct, f"Writing track {i+1}/{total}: {title_preview}")

        # Per-disc track_total
        if use_flat_only:
            track_total = release.track_count
        else:
            track_total = release.disc_track_counts.get(disc_num, release.track_count)

        tag_data = TagData(
            artist=release.artist,
            album_artist=release.artist,
            album=release.title,
            year=year,
            genre=release.genres[0].title() if release.genres else None,
            label=release.label,
            country=release.country,
            track_total=track_total,
            disc_number=1 if use_flat_only else disc_num,
            disc_total=disc_total,
            musicbrainz_release_id=release.release_id,
        )

        if mb_track:
            tag_data.title = mb_track.title
            tag_data.musicbrainz_recording_id = mb_track.recording_id
            if use_flat_only:
                tag_data.track_number = i + 1
            else:
                tag_data.track_number = mb_track.disc_position if mb_track.disc_position > 0 else mb_track.position

        if write_tags(track.path, tag_data):
            if mb_track:
                track.title = mb_track.title
                track.musicbrainz_recording_id = mb_track.recording_id
            track.artist = release.artist
            track.track_number = tag_data.track_number
            track.disc_number = tag_data.disc_number
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

    # Embed in all tracks (read-merge-write to preserve existing tags)
    tracks = db.query(Track).filter(Track.album_id == album.id).all()
    embedded = 0
    for track in tracks:
        existing = read_full_tags(track.path)
        if existing:
            existing.cover_data = image_data
            existing.cover_mime = mime
            if write_tags(track.path, existing):
                embedded += 1
        else:
            # Fallback: write cover only (will clear other tags)
            tag_data = TagData(cover_data=image_data, cover_mime=mime)
            if write_tags(track.path, tag_data):
                embedded += 1

    log.info(f"Artwork embedded in {embedded}/{len(tracks)} tracks")


def _fetch_lyrics_for_album(db: Session, album: Album):
    """Auto-fetch lyrics for all tracks during tagging pipeline."""
    try:
        from app.core.lyrics_client import fetch_lyrics
        from app.core.lyrics_tagger import write_lyrics

        tracks = db.query(Track).filter(Track.album_id == album.id).all()
        found = 0
        for track in tracks:
            if not os.path.isfile(track.path):
                continue
            duration = track.duration or 0
            lr = fetch_lyrics(
                artist=track.artist or album.artist or "",
                title=track.title or "",
                album=album.album or "",
                duration=int(duration),
            )
            if lr and (lr.plain_lyrics or lr.synced_lyrics):
                if write_lyrics(track.path, lr.plain_lyrics, lr.synced_lyrics):
                    track.has_lyrics = True
                    track.lyrics_synced = bool(lr.synced_lyrics)
                    found += 1
        db.flush()
        log.info(f"Auto-lyrics: found {found}/{len(tracks)} for album {album.id}")
    except Exception as e:
        log.error(f"Auto-lyrics failed for album {album.id}: {e}")


def _calculate_replaygain_for_album(db: Session, album: Album):
    """Auto-calculate ReplayGain for all tracks during tagging pipeline."""
    try:
        from app.core.replaygain import analyze_album
        from app.core.replaygain_tagger import write_replaygain

        tracks = db.query(Track).filter(Track.album_id == album.id).all()
        filepaths = [t.path for t in tracks if os.path.isfile(t.path)]
        if not filepaths:
            return

        rg = analyze_album(filepaths)
        if not rg:
            log.warning(f"ReplayGain analysis returned no data for album {album.id}")
            return

        path_to_track = {t.path: t for t in tracks}
        for filepath in filepaths:
            track_rg = rg.tracks.get(filepath)
            if not track_rg:
                continue
            if write_replaygain(filepath, track_rg.gain, track_rg.peak, rg.album_gain, rg.album_peak):
                track = path_to_track.get(filepath)
                if track:
                    track.replaygain_track_gain = track_rg.gain
                    track.replaygain_track_peak = track_rg.peak

        album.replaygain_album_gain = rg.album_gain
        album.replaygain_album_peak = rg.album_peak
        db.flush()
        log.info(f"Auto-ReplayGain: album gain={rg.album_gain} for album {album.id}")
    except Exception as e:
        log.error(f"Auto-ReplayGain failed for album {album.id}: {e}")
