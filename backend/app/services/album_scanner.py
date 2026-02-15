import os
from typing import List

from sqlalchemy.orm import Session

from app.core.audio_reader import scan_album_folder, AUDIO_EXTENSIONS, AlbumInfo
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
    db = SessionLocal()
    try:
        for entry in sorted(os.listdir(scan_path)):
            folder_path = os.path.join(scan_path, entry)
            if not os.path.isdir(folder_path):
                continue
            if entry.startswith("."):
                continue

            has_audio = any(
                os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            )

            if has_audio:
                album_id = _scan_album_folder(db, folder_path, force=force)
                if album_id:
                    album_ids.append(album_id)
            else:
                for sub_entry in sorted(os.listdir(folder_path)):
                    sub_path = os.path.join(folder_path, sub_entry)
                    if not os.path.isdir(sub_path):
                        continue
                    if sub_entry.startswith("."):
                        continue
                    has_sub_audio = any(
                        os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
                        for f in os.listdir(sub_path)
                        if os.path.isfile(os.path.join(sub_path, f))
                    )
                    if has_sub_audio:
                        album_id = _scan_album_folder(db, sub_path, force=force)
                        if album_id:
                            album_ids.append(album_id)

        log.info(f"Scan complete. Found {len(album_ids)} albums.")
        notifications.send_scan_update(len(album_ids), "Scan complete")
        notifications.send_notification("info", f"Scan complete: {len(album_ids)} albums found")
    finally:
        db.close()

    return album_ids


def _scan_album_folder(db: Session, folder_path: str, force: bool = False) -> int | None:
    existing = db.query(Album).filter(Album.path == folder_path).first()
    if existing:
        if not force:
            log.debug(f"Album already in database: {folder_path}")
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

    for track_info in album_info.tracks:
        track = Track(
            album_id=album.id,
            path=track_info.path,
            track_number=track_info.track_number,
            disc_number=track_info.disc_number or 1,
            title=track_info.title,
            artist=track_info.artist,
            duration=track_info.duration,
            status="pending",
        )
        db.add(track)

    db.add(ActivityLog(
        album_id=album.id,
        action="scanned",
        details=f"{album_info.track_count} tracks",
    ))

    db.commit()
    return album.id


def scan_single_folder(folder_path: str) -> int | None:
    db = SessionLocal()
    try:
        album_id = _scan_album_folder(db, folder_path)
        return album_id
    finally:
        db.close()
