import os
from typing import List

from sqlalchemy.orm import Session

from app.core.audio_reader import (
    scan_album_folder, scan_multi_disc_album, find_disc_subfolders,
    has_audio_files, is_disc_subfolder, AUDIO_EXTENSIONS, AlbumInfo,
)
from app.models import Album, Track, ActivityLog
from app.database import SessionLocal
from app.config import settings
from app.services.notification_service import notifications
from app.utils.logger import log


def scan_directory(path: str = None, force: bool = False) -> List[int]:
    """Scan a directory for albums.

    Args:
        path: Directory to scan (defaults to MUSIC_DIR)
        force: If True, re-scan albums already in the database (reset to pending)
    """
    scan_path = path or settings.music_dir
    log.info(f"Scanning directory: {scan_path} (force={force})")

    album_ids = []
    new_album_ids = []
    db = SessionLocal()
    try:
        for entry in sorted(os.listdir(scan_path)):
            folder_path = os.path.join(scan_path, entry)
            if not os.path.isdir(folder_path):
                continue
            if entry.startswith("."):
                continue

            if has_audio_files(folder_path):
                # Level 1: direct audio files → single album
                existing = db.query(Album).filter(Album.path == folder_path).first()
                is_new = existing is None or force
                album_id = _scan_album_folder(db, folder_path, force=force)
                if album_id:
                    album_ids.append(album_id)
                    if is_new:
                        new_album_ids.append(album_id)
            else:
                # Check if this folder has disc subfolders (e.g. Album/CD1/)
                disc_subs = find_disc_subfolders(folder_path)
                if disc_subs:
                    existing = db.query(Album).filter(Album.path == folder_path).first()
                    is_new = existing is None or force
                    album_id = _scan_multi_disc_folder(db, folder_path, disc_subs, force=force)
                    if album_id:
                        album_ids.append(album_id)
                        if is_new:
                            new_album_ids.append(album_id)
                else:
                    # Level 2: Artist/Album structure
                    for sub_entry in sorted(os.listdir(folder_path)):
                        sub_path = os.path.join(folder_path, sub_entry)
                        if not os.path.isdir(sub_path):
                            continue
                        if sub_entry.startswith("."):
                            continue

                        if has_audio_files(sub_path):
                            existing = db.query(Album).filter(Album.path == sub_path).first()
                            is_new = existing is None or force
                            album_id = _scan_album_folder(db, sub_path, force=force)
                            if album_id:
                                album_ids.append(album_id)
                                if is_new:
                                    new_album_ids.append(album_id)
                        else:
                            # Level 3: Artist/Album/CD1/ structure
                            disc_subs_2 = find_disc_subfolders(sub_path)
                            if disc_subs_2:
                                existing = db.query(Album).filter(Album.path == sub_path).first()
                                is_new = existing is None or force
                                album_id = _scan_multi_disc_folder(db, sub_path, disc_subs_2, force=force)
                                if album_id:
                                    album_ids.append(album_id)
                                    if is_new:
                                        new_album_ids.append(album_id)

        log.info(f"Scan complete. Found {len(album_ids)} albums ({len(new_album_ids)} new).")
        notifications.send_scan_update(len(album_ids), "Scan complete")
        notifications.send_notification("info", f"Scan complete: {len(album_ids)} albums found ({len(new_album_ids)} new)")

        # Always queue new albums for matching (matching never modifies files).
        # The tagging_service will decide whether to write tags based on
        # auto_tag_on_scan setting (auto mode) vs needs_review (manual mode).
        if new_album_ids:
            from app.services.queue_manager import queue_manager
            queued = 0
            for aid in new_album_ids:
                album = db.query(Album).filter(Album.id == aid).first()
                if album and album.status == "pending":
                    album.status = "matching"
                    queue_manager.enqueue_album(aid)  # user_initiated=False (default)
                    queued += 1
            db.commit()
            log.info(f"Auto-queued {queued} new albums for matching")
            notifications.send_notification("info", f"Matching {queued} new albums")
    finally:
        db.close()

    return album_ids


def _scan_album_folder(db: Session, folder_path: str, force: bool = False) -> int | None:
    existing = db.query(Album).filter(Album.path == folder_path).first()
    if existing:
        if not force:
            changed = _incremental_update(db, existing)
            if changed:
                log.info(f"Incremental update found changes: {folder_path}")
            return existing.id
        # Force rescan: delete old data and re-import
        log.info(f"Force rescan: {folder_path}")
        db.query(Track).filter(Track.album_id == existing.id).delete()
        db.delete(existing)
        db.flush()

    album_info = scan_album_folder(folder_path)
    if not album_info:
        return None

    log.info(f"New album: {album_info.artist} - {album_info.album} ({album_info.track_count} tracks)")

    album = Album(
        path=folder_path,
        artist=album_info.artist,
        album=album_info.album,
        year=album_info.year,
        status="pending",
        track_count=album_info.track_count,
    )
    db.add(album)
    db.flush()

    # Save MusicBrainz IDs from files if present (preserves data on DB recreate)
    # but do NOT change album status - that's decided by the tagging pipeline
    for track_info in album_info.tracks:
        track = Track(
            album_id=album.id,
            path=track_info.path,
            track_number=track_info.track_number,
            disc_number=track_info.disc_number or 1,
            title=track_info.title,
            artist=track_info.artist,
            duration=track_info.duration,
            musicbrainz_recording_id=track_info.musicbrainz_recording_id,
            status="pending",
        )
        db.add(track)
        if track_info.musicbrainz_release_id and not album.musicbrainz_release_id:
            album.musicbrainz_release_id = track_info.musicbrainz_release_id

    db.add(ActivityLog(
        album_id=album.id,
        action="scanned",
        details=f"{album_info.track_count} tracks",
    ))

    db.commit()
    return album.id


def _scan_multi_disc_folder(db: Session, parent_path: str, disc_subs: dict[int, str], force: bool = False) -> int | None:
    """Scan a multi-disc album and create a single Album record."""
    existing = db.query(Album).filter(Album.path == parent_path).first()
    if existing:
        if not force:
            changed = _incremental_update(db, existing)
            if changed:
                log.info(f"Incremental update found changes (multi-disc): {parent_path}")
            return existing.id
        log.info(f"Force rescan multi-disc: {parent_path}")
        db.query(Track).filter(Track.album_id == existing.id).delete()
        db.delete(existing)
        db.flush()

    # Cleanup: remove any old Album records that pointed to individual disc subfolders
    for disc_path in disc_subs.values():
        old = db.query(Album).filter(Album.path == disc_path).first()
        if old:
            log.info(f"Removing old per-disc record: {disc_path}")
            db.query(Track).filter(Track.album_id == old.id).delete()
            db.delete(old)
    db.flush()

    album_info = scan_multi_disc_album(parent_path, disc_subs)
    if not album_info:
        return None

    log.info(f"New multi-disc album: {album_info.artist} - {album_info.album} "
             f"({album_info.track_count} tracks, {album_info.disc_count} discs)")

    album = Album(
        path=parent_path,
        artist=album_info.artist,
        album=album_info.album,
        year=album_info.year,
        status="pending",
        track_count=album_info.track_count,
    )
    db.add(album)
    db.flush()

    for track_info in album_info.tracks:
        track = Track(
            album_id=album.id,
            path=track_info.path,
            track_number=track_info.track_number,
            disc_number=track_info.disc_number or 1,
            title=track_info.title,
            artist=track_info.artist,
            duration=track_info.duration,
            musicbrainz_recording_id=track_info.musicbrainz_recording_id,
            status="pending",
        )
        db.add(track)
        if track_info.musicbrainz_release_id and not album.musicbrainz_release_id:
            album.musicbrainz_release_id = track_info.musicbrainz_release_id

    db.add(ActivityLog(
        album_id=album.id,
        action="scanned",
        details=f"{album_info.track_count} tracks, {album_info.disc_count} discs",
    ))

    db.commit()
    return album.id


def _incremental_update(db: Session, album: Album) -> bool:
    """Compare disk files vs DB tracks for an existing album.

    Adds new tracks, removes deleted tracks, and resets album to pending
    if any changes are found. Returns True if changes were made.
    """
    disc_subs = find_disc_subfolders(album.path)
    if disc_subs:
        album_info = scan_multi_disc_album(album.path, disc_subs)
    else:
        album_info = scan_album_folder(album.path)

    if not album_info:
        return False

    disk_paths = {t.path for t in album_info.tracks}
    db_tracks = db.query(Track).filter(Track.album_id == album.id).all()
    db_paths = {t.path for t in db_tracks}

    added = disk_paths - db_paths
    removed = db_paths - disk_paths

    if not added and not removed:
        return False

    # Build a lookup for quick access to scanned track info
    track_info_map = {t.path: t for t in album_info.tracks}

    for path in added:
        ti = track_info_map[path]
        track = Track(
            album_id=album.id,
            path=ti.path,
            track_number=ti.track_number,
            disc_number=ti.disc_number or 1,
            title=ti.title,
            artist=ti.artist,
            duration=ti.duration,
            musicbrainz_recording_id=ti.musicbrainz_recording_id,
            status="pending",
        )
        db.add(track)

    if removed:
        db.query(Track).filter(Track.path.in_(removed)).delete(synchronize_session=False)

    album.track_count = len(disk_paths)
    album.status = "pending"

    changes = []
    if added:
        changes.append(f"+{len(added)} tracks")
    if removed:
        changes.append(f"-{len(removed)} tracks")
    detail = ", ".join(changes)

    db.add(ActivityLog(
        album_id=album.id,
        action="incremental_update",
        details=detail,
    ))

    db.commit()
    log.info(f"Incremental update for '{album.artist} - {album.album}': {detail}")
    return True


def scan_single_folder(folder_path: str) -> int | None:
    db = SessionLocal()
    try:
        # If this folder is a disc subfolder, scan the parent as multi-disc
        folder_name = os.path.basename(folder_path)
        if is_disc_subfolder(folder_name):
            parent_path = os.path.dirname(folder_path)
            disc_subs = find_disc_subfolders(parent_path)
            if disc_subs:
                return _scan_multi_disc_folder(db, parent_path, disc_subs)

        # Check if the folder itself has disc subfolders
        disc_subs = find_disc_subfolders(folder_path)
        if disc_subs:
            return _scan_multi_disc_folder(db, folder_path, disc_subs)

        album_id = _scan_album_folder(db, folder_path)
        return album_id
    finally:
        db.close()
