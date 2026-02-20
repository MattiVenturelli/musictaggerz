import json
import os
import base64
from typing import Optional

from sqlalchemy.orm import Session

from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture

from app.core.tagger import TagData, write_tags
from app.models import TagBackup, TrackTagSnapshot, Track
from app.config import settings
from app.utils.logger import log


BACKUP_DIR = "/data/backups"


def _parse_number_total(value: str) -> tuple[Optional[int], Optional[int]]:
    """Parse '3/12' or '3' into (number, total)."""
    if not value:
        return None, None
    parts = value.split("/")
    try:
        num = int(parts[0].strip()) if parts[0].strip() else None
    except (ValueError, TypeError):
        num = None
    total = None
    if len(parts) > 1:
        try:
            total = int(parts[1].strip()) if parts[1].strip() else None
        except (ValueError, TypeError):
            pass
    return num, total


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    return str(value).strip() or None


def read_full_tags(filepath: str) -> Optional[TagData]:
    """Read ALL tags from an audio file and return a TagData.

    This is the mirror of tagger.py's write functions — it reads every field
    that write_tags() can write, including track_total, disc_total, label,
    country, cover_data, and cover_mime.
    """
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _read_flac_full(filepath)
        elif ext == ".mp3":
            return _read_mp3_full(filepath)
        elif ext in (".m4a", ".mp4"):
            return _read_mp4_full(filepath)
        elif ext in (".ogg", ".opus"):
            return _read_ogg_full(filepath)
        else:
            log.warning(f"read_full_tags: unsupported format {filepath}")
            return None
    except Exception as e:
        log.error(f"read_full_tags error for {filepath}: {e}")
        return None


def _read_flac_full(filepath: str) -> TagData:
    audio = FLAC(filepath)
    tn_str = _safe_str(audio.get("tracknumber"))
    dn_str = _safe_str(audio.get("discnumber"))
    track_number, track_total = _parse_number_total(tn_str) if tn_str else (None, None)
    disc_number, disc_total = _parse_number_total(dn_str) if dn_str else (None, None)
    year_str = _safe_str(audio.get("date"))
    year = None
    if year_str:
        try:
            year = int(year_str[:4])
        except (ValueError, TypeError):
            pass

    cover_data = None
    cover_mime = "image/jpeg"
    if audio.pictures:
        pic = audio.pictures[0]
        cover_data = pic.data
        cover_mime = pic.mime or "image/jpeg"

    return TagData(
        title=_safe_str(audio.get("title")),
        artist=_safe_str(audio.get("artist")),
        album_artist=_safe_str(audio.get("albumartist")),
        album=_safe_str(audio.get("album")),
        track_number=track_number,
        track_total=track_total,
        disc_number=disc_number,
        disc_total=disc_total,
        year=year,
        genre=_safe_str(audio.get("genre")),
        label=_safe_str(audio.get("label")) or _safe_str(audio.get("organization")),
        country=_safe_str(audio.get("releasecountry")),
        musicbrainz_release_id=_safe_str(audio.get("musicbrainz_albumid")),
        musicbrainz_recording_id=_safe_str(audio.get("musicbrainz_trackid")),
        cover_data=cover_data,
        cover_mime=cover_mime,
    )


def _read_mp3_full(filepath: str) -> TagData:
    audio = MP3(filepath)
    tags = audio.tags

    td = TagData()
    if not tags:
        return td

    td.title = _safe_str(tags.get("TIT2"))
    td.artist = _safe_str(tags.get("TPE1"))
    td.album_artist = _safe_str(tags.get("TPE2"))
    td.album = _safe_str(tags.get("TALB"))
    td.genre = _safe_str(tags.get("TCON"))

    trck = _safe_str(tags.get("TRCK"))
    if trck:
        td.track_number, td.track_total = _parse_number_total(trck)
    tpos = _safe_str(tags.get("TPOS"))
    if tpos:
        td.disc_number, td.disc_total = _parse_number_total(tpos)

    year_str = _safe_str(tags.get("TDRC"))
    if year_str:
        try:
            td.year = int(str(year_str)[:4])
        except (ValueError, TypeError):
            pass

    tpub = tags.get("TPUB")
    if tpub:
        td.label = _safe_str(tpub)

    txxx_country = tags.get("TXXX:MusicBrainz Album Release Country")
    if txxx_country:
        td.country = _safe_str(txxx_country)
    txxx_album_id = tags.get("TXXX:MusicBrainz Album Id")
    if txxx_album_id:
        td.musicbrainz_release_id = _safe_str(txxx_album_id)
    txxx_rec_id = tags.get("TXXX:MusicBrainz Recording Id")
    if txxx_rec_id:
        td.musicbrainz_recording_id = _safe_str(txxx_rec_id)

    apic_frames = tags.getall("APIC")
    if apic_frames:
        td.cover_data = apic_frames[0].data
        td.cover_mime = apic_frames[0].mime or "image/jpeg"

    return td


def _read_mp4_full(filepath: str) -> TagData:
    audio = MP4(filepath)
    td = TagData()

    td.title = _safe_str(audio.get("\xa9nam"))
    td.artist = _safe_str(audio.get("\xa9ART"))
    td.album_artist = _safe_str(audio.get("aART"))
    td.album = _safe_str(audio.get("\xa9alb"))
    td.genre = _safe_str(audio.get("\xa9gen"))

    if audio.get("trkn"):
        vals = audio["trkn"][0]
        td.track_number = vals[0] if vals[0] else None
        td.track_total = vals[1] if len(vals) > 1 and vals[1] else None
    if audio.get("disk"):
        vals = audio["disk"][0]
        td.disc_number = vals[0] if vals[0] else None
        td.disc_total = vals[1] if len(vals) > 1 and vals[1] else None

    year_str = _safe_str(audio.get("\xa9day"))
    if year_str:
        try:
            td.year = int(str(year_str)[:4])
        except (ValueError, TypeError):
            pass

    label_raw = audio.get("----:com.apple.iTunes:LABEL")
    if label_raw:
        td.label = label_raw[0].decode("utf-8", errors="ignore") if isinstance(label_raw[0], bytes) else str(label_raw[0])

    country_raw = audio.get("----:com.apple.iTunes:MusicBrainz Album Release Country")
    if country_raw:
        td.country = country_raw[0].decode("utf-8", errors="ignore") if isinstance(country_raw[0], bytes) else str(country_raw[0])
    rel_raw = audio.get("----:com.apple.iTunes:MusicBrainz Album Id")
    if rel_raw:
        td.musicbrainz_release_id = rel_raw[0].decode("utf-8", errors="ignore") if isinstance(rel_raw[0], bytes) else str(rel_raw[0])
    rec_raw = audio.get("----:com.apple.iTunes:MusicBrainz Track Id")
    if rec_raw:
        td.musicbrainz_recording_id = rec_raw[0].decode("utf-8", errors="ignore") if isinstance(rec_raw[0], bytes) else str(rec_raw[0])

    covr = audio.get("covr")
    if covr:
        td.cover_data = bytes(covr[0])
        fmt = covr[0].imageformat if hasattr(covr[0], 'imageformat') else None
        td.cover_mime = "image/png" if fmt == 14 else "image/jpeg"  # MP4Cover.FORMAT_PNG = 14

    return td


def _read_ogg_full(filepath: str) -> TagData:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".opus":
        audio = OggOpus(filepath)
    else:
        audio = OggVorbis(filepath)

    tn_str = _safe_str(audio.get("tracknumber"))
    dn_str = _safe_str(audio.get("discnumber"))
    track_number, track_total = _parse_number_total(tn_str) if tn_str else (None, None)
    disc_number, disc_total = _parse_number_total(dn_str) if dn_str else (None, None)

    year_str = _safe_str(audio.get("date"))
    year = None
    if year_str:
        try:
            year = int(year_str[:4])
        except (ValueError, TypeError):
            pass

    cover_data = None
    cover_mime = "image/jpeg"
    mbp = audio.get("metadata_block_picture")
    if mbp:
        try:
            pic = Picture(base64.b64decode(mbp[0]))
            cover_data = pic.data
            cover_mime = pic.mime or "image/jpeg"
        except Exception:
            pass

    return TagData(
        title=_safe_str(audio.get("title")),
        artist=_safe_str(audio.get("artist")),
        album_artist=_safe_str(audio.get("albumartist")),
        album=_safe_str(audio.get("album")),
        track_number=track_number,
        track_total=track_total,
        disc_number=disc_number,
        disc_total=disc_total,
        year=year,
        genre=_safe_str(audio.get("genre")),
        label=_safe_str(audio.get("label")) or _safe_str(audio.get("organization")),
        country=_safe_str(audio.get("releasecountry")),
        musicbrainz_release_id=_safe_str(audio.get("musicbrainz_albumid")),
        musicbrainz_recording_id=_safe_str(audio.get("musicbrainz_trackid")),
        cover_data=cover_data,
        cover_mime=cover_mime,
    )


def _tag_data_to_dict(td: TagData) -> dict:
    """Serialize TagData to JSON-safe dict (excluding cover_data)."""
    return {
        "title": td.title,
        "artist": td.artist,
        "album_artist": td.album_artist,
        "album": td.album,
        "track_number": td.track_number,
        "track_total": td.track_total,
        "disc_number": td.disc_number,
        "disc_total": td.disc_total,
        "year": td.year,
        "genre": td.genre,
        "label": td.label,
        "country": td.country,
        "musicbrainz_release_id": td.musicbrainz_release_id,
        "musicbrainz_recording_id": td.musicbrainz_recording_id,
        "cover_mime": td.cover_mime,
    }


def _dict_to_tag_data(d: dict) -> TagData:
    """Deserialize dict back to TagData (without cover_data)."""
    return TagData(
        title=d.get("title"),
        artist=d.get("artist"),
        album_artist=d.get("album_artist"),
        album=d.get("album"),
        track_number=d.get("track_number"),
        track_total=d.get("track_total"),
        disc_number=d.get("disc_number"),
        disc_total=d.get("disc_total"),
        year=d.get("year"),
        genre=d.get("genre"),
        label=d.get("label"),
        country=d.get("country"),
        musicbrainz_release_id=d.get("musicbrainz_release_id"),
        musicbrainz_recording_id=d.get("musicbrainz_recording_id"),
        cover_mime=d.get("cover_mime", "image/jpeg"),
    )


def create_backup(db: Session, album_id: int, action: str, track_ids: list[int] | None = None) -> Optional[int]:
    """Create a backup of current tags for an album's tracks.

    Returns the backup_id, or None if backups are disabled.
    """
    if not settings.backup_enabled:
        return None

    tracks = db.query(Track).filter(Track.album_id == album_id)
    if track_ids:
        tracks = tracks.filter(Track.id.in_(track_ids))
    tracks = tracks.all()

    if not tracks:
        return None

    backup = TagBackup(album_id=album_id, action=action)
    db.add(backup)
    db.flush()  # get backup.id

    backup_dir = os.path.join(BACKUP_DIR, str(backup.id))
    album_cover_file = None

    for track in tracks:
        if not os.path.isfile(track.path):
            continue

        tag_data = read_full_tags(track.path)
        if not tag_data:
            continue

        # Save one cover per backup (all tracks in an album share the same cover)
        has_cover = tag_data.cover_data is not None
        if has_cover and tag_data.cover_data and album_cover_file is None:
            os.makedirs(backup_dir, exist_ok=True)
            ext = ".png" if tag_data.cover_mime == "image/png" else ".jpg"
            album_cover_file = os.path.join(backup_dir, f"cover{ext}")
            try:
                with open(album_cover_file, "wb") as f:
                    f.write(tag_data.cover_data)
            except Exception as e:
                log.warning(f"Failed to save backup cover for album {album_id}: {e}")
                album_cover_file = None

        snapshot = TrackTagSnapshot(
            backup_id=backup.id,
            track_id=track.id,
            path=track.path,
            tags_json=json.dumps(_tag_data_to_dict(tag_data)),
            has_cover=has_cover,
            cover_path=album_cover_file if has_cover else None,
        )
        db.add(snapshot)

    db.flush()
    _prune_old_backups(db, album_id)
    log.info(f"Backup {backup.id} created for album {album_id} (action={action}, tracks={len(tracks)})")
    return backup.id


def restore_backup(db: Session, backup_id: int) -> tuple[int, int]:
    """Restore tags from a backup. Returns (success_count, total_count)."""
    backup = db.query(TagBackup).filter(TagBackup.id == backup_id).first()
    if not backup:
        return 0, 0

    snapshots = db.query(TrackTagSnapshot).filter(TrackTagSnapshot.backup_id == backup_id).all()
    total = len(snapshots)
    success = 0

    for snap in snapshots:
        if not os.path.isfile(snap.path):
            log.warning(f"Restore: file not found {snap.path}")
            continue

        tag_data = _dict_to_tag_data(json.loads(snap.tags_json))

        # Restore cover from saved file
        if snap.has_cover and snap.cover_path and os.path.isfile(snap.cover_path):
            try:
                with open(snap.cover_path, "rb") as f:
                    tag_data.cover_data = f.read()
            except Exception as e:
                log.warning(f"Failed to read backup cover {snap.cover_path}: {e}")

        if write_tags(snap.path, tag_data):
            # Update track DB record from restored tags
            track = db.query(Track).filter(Track.id == snap.track_id).first()
            if track:
                track.title = tag_data.title
                track.artist = tag_data.artist
                if tag_data.track_number is not None:
                    track.track_number = tag_data.track_number
                if tag_data.disc_number is not None:
                    track.disc_number = tag_data.disc_number
            success += 1

    db.flush()
    log.info(f"Backup {backup_id} restored: {success}/{total} tracks")
    return success, total


def _prune_old_backups(db: Session, album_id: int):
    """Keep only the N most recent backups per album."""
    max_count = settings.backup_max_per_album
    backups = (
        db.query(TagBackup)
        .filter(TagBackup.album_id == album_id)
        .order_by(TagBackup.created_at.desc())
        .all()
    )

    if len(backups) <= max_count:
        return

    to_delete = backups[max_count:]
    for b in to_delete:
        # Clean up cover files on disk
        backup_dir = os.path.join(BACKUP_DIR, str(b.id))
        if os.path.isdir(backup_dir):
            import shutil
            try:
                shutil.rmtree(backup_dir)
            except Exception as e:
                log.warning(f"Failed to remove backup dir {backup_dir}: {e}")
        db.delete(b)

    db.flush()
    log.debug(f"Pruned {len(to_delete)} old backups for album {album_id}")


def delete_backup(db: Session, backup_id: int) -> bool:
    """Delete a specific backup and its cover files."""
    backup = db.query(TagBackup).filter(TagBackup.id == backup_id).first()
    if not backup:
        return False

    backup_dir = os.path.join(BACKUP_DIR, str(backup_id))
    if os.path.isdir(backup_dir):
        import shutil
        try:
            shutil.rmtree(backup_dir)
        except Exception as e:
            log.warning(f"Failed to remove backup dir {backup_dir}: {e}")

    db.delete(backup)
    db.flush()
    return True
