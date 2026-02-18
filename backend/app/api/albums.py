import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import Album, Track, MatchCandidate, ActivityLog, TagBackup, TrackTagSnapshot
from app.schemas import (
    AlbumSummary, AlbumDetail, AlbumListResponse,
    TagRequest, ScanRequest, TrackResponse, MatchCandidateResponse,
    BatchActionRequest,
    ArtworkOptionResponse, ArtworkDiscoveryResponse, ApplyArtworkRequest,
    TagBackupResponse, ManualTagEditRequest, BulkManualTagEditRequest,
)
from app.core.audio_reader import read_track
from app.core.artwork_discovery import (
    discover_caa, discover_itunes, discover_fanarttv, discover_filesystem,
)
from app.core.artwork_fetcher import _download_image, save_artwork_to_folder
from app.core.tagger import write_tags, TagData
from app.core.tag_backup import read_full_tags, create_backup, restore_backup, delete_backup
from app.services.album_scanner import scan_directory
from app.services.queue_manager import queue_manager
from app.utils.logger import log

router = APIRouter()


@router.get("", response_model=AlbumListResponse)
def list_albums(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "updated_desc",
    db: Session = Depends(get_db),
):
    query = db.query(Album)

    if status:
        query = query.filter(Album.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Album.artist.ilike(pattern)) | (Album.album.ilike(pattern))
        )

    total = query.count()

    sort_map = {
        "updated_desc": Album.updated_at.desc(),
        "updated_asc": Album.updated_at.asc(),
        "created_desc": Album.created_at.desc(),
        "created_asc": Album.created_at.asc(),
        "artist": Album.artist.asc(),
        "album": Album.album.asc(),
        "confidence_desc": Album.match_confidence.desc(),
        "confidence_asc": Album.match_confidence.asc(),
    }
    query = query.order_by(sort_map.get(sort, Album.updated_at.desc()))

    albums = query.offset(offset).limit(limit).all()

    return AlbumListResponse(
        items=[AlbumSummary.model_validate(a) for a in albums],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{album_id}/artwork-options", response_model=ArtworkDiscoveryResponse)
def get_artwork_options(album_id: int, db: Session = Depends(get_db)):
    """Discover available artwork from all sources (thumbnails only, no download)."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    options: list[ArtworkOptionResponse] = []

    # Filesystem
    if album.path:
        for opt in discover_filesystem(album.path, album.id):
            options.append(ArtworkOptionResponse(
                source=opt.source, thumbnail_url=opt.thumbnail_url,
                full_url=opt.full_url, width=opt.width, height=opt.height,
                label=opt.label,
            ))

    # CAA for the current release
    if album.musicbrainz_release_id:
        for opt in discover_caa(album.musicbrainz_release_id):
            options.append(ArtworkOptionResponse(
                source=opt.source, thumbnail_url=opt.thumbnail_url,
                full_url=opt.full_url, width=opt.width, height=opt.height,
                label=opt.label,
            ))

    # CAA for all match candidates (different releases)
    candidate_ids = {
        c.musicbrainz_release_id
        for c in db.query(MatchCandidate).filter(MatchCandidate.album_id == album_id).all()
        if c.musicbrainz_release_id != album.musicbrainz_release_id
    }
    for rid in candidate_ids:
        for opt in discover_caa(rid):
            opt.label = f"{opt.label} (candidate)"
            options.append(ArtworkOptionResponse(
                source=opt.source, thumbnail_url=opt.thumbnail_url,
                full_url=opt.full_url, width=opt.width, height=opt.height,
                label=opt.label,
            ))

    # iTunes
    if album.artist or album.album:
        for opt in discover_itunes(album.artist or "", album.album or ""):
            options.append(ArtworkOptionResponse(
                source=opt.source, thumbnail_url=opt.thumbnail_url,
                full_url=opt.full_url, width=opt.width, height=opt.height,
                label=opt.label,
            ))

    # fanart.tv
    if album.musicbrainz_release_group_id:
        for opt in discover_fanarttv(album.musicbrainz_release_group_id):
            options.append(ArtworkOptionResponse(
                source=opt.source, thumbnail_url=opt.thumbnail_url,
                full_url=opt.full_url, width=opt.width, height=opt.height,
                label=opt.label,
            ))

    return ArtworkDiscoveryResponse(album_id=album_id, options=options)


@router.post("/{album_id}/artwork")
def apply_artwork(album_id: int, request: ApplyArtworkRequest, db: Session = Depends(get_db)):
    """Download selected artwork, save to folder, and embed in audio files."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Get image data
    if request.source == "filesystem":
        # Read from local file
        filename = request.file or os.path.basename(request.full_url.split("file=")[-1])
        filename = os.path.basename(filename)  # sanitize
        filepath = os.path.join(album.path, filename)
        if not os.path.isfile(filepath):
            raise HTTPException(status_code=404, detail="Local file not found")
        with open(filepath, "rb") as f:
            image_data = f.read()
        mime = "image/png" if filepath.lower().endswith(".png") else "image/jpeg"
    else:
        # Download from external URL
        image_data = _download_image(request.full_url)
        if not image_data:
            raise HTTPException(status_code=502, detail="Failed to download artwork")
        mime = "image/png" if image_data[:4] == b'\x89PNG' else "image/jpeg"

    # Save to album folder
    saved_path = save_artwork_to_folder(album.path, image_data, mime)
    if saved_path:
        album.cover_path = saved_path

    # Embed in all audio files (read-merge-write to preserve existing tags)
    create_backup(db, album_id, "artwork")
    tracks = db.query(Track).filter(Track.album_id == album_id).all()
    embedded = 0
    for track in tracks:
        existing = read_full_tags(track.path)
        if existing:
            existing.cover_data = image_data
            existing.cover_mime = mime
            if write_tags(track.path, existing):
                embedded += 1
        else:
            tag_data = TagData(cover_data=image_data, cover_mime=mime)
            if write_tags(track.path, tag_data):
                embedded += 1

    db.add(ActivityLog(
        album_id=album_id, action="artwork_applied",
        details=f"Source: {request.source}, embedded in {embedded}/{len(tracks)} tracks",
    ))
    db.commit()

    log.info(f"Artwork applied to album {album_id}: source={request.source}, embedded={embedded}/{len(tracks)}")
    return {"message": "Artwork applied", "album_id": album_id, "embedded": embedded}


@router.get("/{album_id}/tracks/{track_id}/tags")
def get_track_tags(album_id: int, track_id: int, db: Session = Depends(get_db)):
    """Read current metadata tags directly from the audio file."""
    track = (
        db.query(Track)
        .filter(Track.id == track_id, Track.album_id == album_id)
        .first()
    )
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not os.path.isfile(track.path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    info = read_track(track.path)
    if not info:
        raise HTTPException(status_code=500, detail="Could not read file tags")

    return {
        "track_id": track.id,
        "path": track.path,
        "title": info.title,
        "artist": info.artist,
        "album": info.album,
        "album_artist": info.album_artist,
        "track_number": info.track_number,
        "disc_number": info.disc_number,
        "year": info.year,
        "genre": info.genre,
        "duration": info.duration,
        "format": info.format,
        "has_cover": info.has_cover,
        "musicbrainz_recording_id": info.musicbrainz_recording_id,
        "musicbrainz_release_id": info.musicbrainz_release_id,
    }


@router.get("/{album_id}/cover")
def get_album_cover(album_id: int, file: Optional[str] = None, db: Session = Depends(get_db)):
    """Serve album cover art image from filesystem.

    If `file` is provided, serve that specific image file from the album folder.
    """
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Serve specific file if requested (used by filesystem artwork thumbnails)
    if file:
        safe_name = os.path.basename(file)
        if album.path:
            filepath = os.path.join(album.path, safe_name)
            if os.path.isfile(filepath):
                return FileResponse(filepath, media_type=_guess_image_type(filepath))
        raise HTTPException(status_code=404, detail="File not found")

    # Try the stored cover_path first
    if album.cover_path and os.path.isfile(album.cover_path):
        return FileResponse(album.cover_path, media_type=_guess_image_type(album.cover_path))

    # Fallback: look for common cover filenames in the album directory
    if album.path and os.path.isdir(album.path):
        candidates = [
            "cover.jpg", "Cover.jpg", "cover.png", "Cover.png",
            "albumart.jpg", "AlbumArt.jpg", "folder.jpg", "Folder.jpg",
            "front.jpg", "Front.jpg", "front.png", "Front.png",
        ]
        for name in candidates:
            filepath = os.path.join(album.path, name)
            if os.path.isfile(filepath):
                return FileResponse(filepath, media_type=_guess_image_type(filepath))

    raise HTTPException(status_code=404, detail="Cover art not found")


def _guess_image_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")


@router.get("/{album_id}", response_model=AlbumDetail)
def get_album(album_id: int, db: Session = Depends(get_db)):
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    return AlbumDetail(
        **{c.name: getattr(album, c.name) for c in Album.__table__.columns},
        tracks=[TrackResponse.model_validate(t) for t in album.tracks],
        match_candidates=[
            MatchCandidateResponse.model_validate(m) for m in album.match_candidates
        ],
    )


@router.post("/{album_id}/tag")
def tag_album(
    album_id: int,
    request: TagRequest = TagRequest(),
    db: Session = Depends(get_db),
):
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    album.status = "matching"
    db.commit()

    queue_manager.enqueue_album(album_id, release_id=request.release_id, user_initiated=True)

    return {"message": "Tagging queued", "album_id": album_id}


@router.post("/{album_id}/retag")
def retag_album(
    album_id: int,
    request: TagRequest = TagRequest(),
    db: Session = Depends(get_db),
):
    """Re-tag an album (reset status and re-match)."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Clear old match candidates
    db.query(MatchCandidate).filter(MatchCandidate.album_id == album_id).delete()
    album.status = "matching"
    album.match_confidence = None
    album.musicbrainz_release_id = None
    album.error_message = None
    db.add(ActivityLog(album_id=album_id, action="retag_requested"))
    db.commit()

    queue_manager.enqueue_album(album_id, release_id=request.release_id, user_initiated=True)

    return {"message": "Retag queued", "album_id": album_id}


@router.post("/{album_id}/skip")
def skip_album(album_id: int, db: Session = Depends(get_db)):
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    album.status = "skipped"
    db.add(ActivityLog(album_id=album_id, action="skipped"))
    db.commit()

    return {"message": "Album skipped", "album_id": album_id}


@router.delete("/{album_id}")
def delete_album(album_id: int, db: Session = Depends(get_db)):
    """Remove album from database (does NOT delete files)."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    db.delete(album)
    db.commit()

    return {"message": "Album removed from database", "album_id": album_id}


@router.post("/batch/tag")
def batch_tag(request: BatchActionRequest, db: Session = Depends(get_db)):
    """Queue multiple albums for tagging."""
    queued = []
    for album_id in request.album_ids:
        album = db.query(Album).filter(Album.id == album_id).first()
        if album:
            album.status = "matching"
            queue_manager.enqueue_album(album_id, user_initiated=True)
            queued.append(album_id)
    db.commit()
    return {"message": f"Queued {len(queued)} albums", "album_ids": queued}


@router.post("/batch/tag-pending")
def batch_tag_pending(db: Session = Depends(get_db)):
    """Queue all untagged albums (pending + needs_review) for tagging."""
    albums = db.query(Album).filter(Album.status.in_(["pending", "needs_review"])).all()
    queued = []
    for album in albums:
        album.status = "matching"
        queue_manager.enqueue_album(album.id, user_initiated=True)
        queued.append(album.id)
    db.commit()
    return {"message": f"Queued {len(queued)} albums for tagging", "album_ids": queued}


@router.post("/batch/skip")
def batch_skip(request: BatchActionRequest, db: Session = Depends(get_db)):
    """Skip multiple albums."""
    skipped = []
    for album_id in request.album_ids:
        album = db.query(Album).filter(Album.id == album_id).first()
        if album:
            album.status = "skipped"
            db.add(ActivityLog(album_id=album_id, action="skipped"))
            skipped.append(album_id)
    db.commit()
    return {"message": f"Skipped {len(skipped)} albums", "album_ids": skipped}


# ─── Tag Backup & Restore ─────────────────────────────────────────

@router.get("/{album_id}/backups", response_model=List[TagBackupResponse])
def list_backups(album_id: int, db: Session = Depends(get_db)):
    """List all tag backups for an album."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    backups = (
        db.query(TagBackup)
        .filter(TagBackup.album_id == album_id)
        .order_by(TagBackup.created_at.desc())
        .all()
    )
    result = []
    for b in backups:
        count = db.query(TrackTagSnapshot).filter(TrackTagSnapshot.backup_id == b.id).count()
        result.append(TagBackupResponse(
            id=b.id, album_id=b.album_id, action=b.action,
            created_at=b.created_at, track_count=count,
        ))
    return result


@router.post("/{album_id}/backups/{backup_id}/restore")
def restore_album_backup(album_id: int, backup_id: int, db: Session = Depends(get_db)):
    """Restore tags from a backup. Creates a pre-restore backup first."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    backup = db.query(TagBackup).filter(
        TagBackup.id == backup_id, TagBackup.album_id == album_id
    ).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Create a safety backup of current state before restoring
    create_backup(db, album_id, "pre_restore")

    success, total = restore_backup(db, backup_id)
    db.add(ActivityLog(
        album_id=album_id, action="backup_restored",
        details=f"Backup {backup_id} restored: {success}/{total} tracks",
    ))
    db.commit()
    return {"message": "Backup restored", "success": success, "total": total}


@router.delete("/{album_id}/backups/{backup_id}")
def delete_album_backup(album_id: int, backup_id: int, db: Session = Depends(get_db)):
    """Delete a specific backup."""
    backup = db.query(TagBackup).filter(
        TagBackup.id == backup_id, TagBackup.album_id == album_id
    ).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    delete_backup(db, backup_id)
    db.commit()
    return {"message": "Backup deleted"}


# ─── Manual Tag Editing ──────────────────────────────────────────

@router.put("/{album_id}/tracks/{track_id}/tags")
def edit_track_tags(
    album_id: int, track_id: int,
    request: ManualTagEditRequest,
    db: Session = Depends(get_db),
):
    """Edit tags for a single track."""
    track = db.query(Track).filter(
        Track.id == track_id, Track.album_id == album_id
    ).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.isfile(track.path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    # Backup before editing
    create_backup(db, album_id, "manual_edit", track_ids=[track_id])

    # Read current tags, merge with changes
    current = read_full_tags(track.path)
    if not current:
        raise HTTPException(status_code=500, detail="Could not read file tags")

    changes = request.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(current, field, value)

    if not write_tags(track.path, current):
        raise HTTPException(status_code=500, detail="Failed to write tags")

    # Update DB record
    if request.title is not None:
        track.title = request.title
    if request.artist is not None:
        track.artist = request.artist
    if request.track_number is not None:
        track.track_number = request.track_number
    if request.disc_number is not None:
        track.disc_number = request.disc_number
    if request.musicbrainz_recording_id is not None:
        track.musicbrainz_recording_id = request.musicbrainz_recording_id

    db.add(ActivityLog(
        album_id=album_id, action="manual_edit",
        details=f"Track {track_id}: edited {list(changes.keys())}",
    ))
    db.commit()
    return {"message": "Track tags updated", "fields": list(changes.keys())}


@router.put("/{album_id}/tags")
def edit_album_tags(
    album_id: int,
    request: BulkManualTagEditRequest,
    db: Session = Depends(get_db),
):
    """Edit album-level tags applied to all tracks."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    changes = request.model_dump(exclude_none=True)
    if not changes:
        return {"message": "No changes"}

    # Backup before editing
    create_backup(db, album_id, "manual_edit")

    tracks = db.query(Track).filter(Track.album_id == album_id).all()
    success = 0
    for track in tracks:
        if not os.path.isfile(track.path):
            continue
        current = read_full_tags(track.path)
        if not current:
            continue
        for field, value in changes.items():
            setattr(current, field, value)
        if write_tags(track.path, current):
            success += 1

    # Update album DB record
    if request.album is not None:
        album.album = request.album
    if request.album_artist is not None:
        album.artist = request.album_artist
    if request.year is not None:
        album.year = request.year

    db.add(ActivityLog(
        album_id=album_id, action="manual_edit",
        details=f"Album-level: edited {list(changes.keys())} on {success}/{len(tracks)} tracks",
    ))
    db.commit()
    return {"message": "Album tags updated", "success": success, "total": len(tracks)}


# ─── Lyrics ──────────────────────────────────────────────────────

@router.post("/{album_id}/lyrics")
def fetch_album_lyrics(album_id: int, db: Session = Depends(get_db)):
    """Fetch and embed lyrics for all tracks in an album."""
    from app.core.lyrics_client import fetch_lyrics
    from app.core.lyrics_tagger import write_lyrics

    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    create_backup(db, album_id, "lyrics")

    tracks = db.query(Track).filter(Track.album_id == album_id).all()
    results = {"found": 0, "not_found": 0, "errors": 0}

    for track in tracks:
        if not os.path.isfile(track.path):
            results["errors"] += 1
            continue

        duration = track.duration or 0
        lr = fetch_lyrics(
            artist=track.artist or album.artist or "",
            title=track.title or "",
            album=album.album or "",
            duration=int(duration),
        )
        if not lr or (not lr.plain_lyrics and not lr.synced_lyrics):
            if lr and lr.instrumental:
                track.has_lyrics = False
                track.lyrics_synced = False
            results["not_found"] += 1
            continue

        if write_lyrics(track.path, lr.plain_lyrics, lr.synced_lyrics):
            track.has_lyrics = True
            track.lyrics_synced = bool(lr.synced_lyrics)
            results["found"] += 1
        else:
            results["errors"] += 1

    db.add(ActivityLog(
        album_id=album_id, action="lyrics_fetched",
        details=f"Found: {results['found']}, Not found: {results['not_found']}, Errors: {results['errors']}",
    ))
    db.commit()
    return {"message": "Lyrics fetched", **results}


@router.post("/{album_id}/tracks/{track_id}/lyrics")
def fetch_track_lyrics(album_id: int, track_id: int, db: Session = Depends(get_db)):
    """Fetch and embed lyrics for a single track."""
    from app.core.lyrics_client import fetch_lyrics
    from app.core.lyrics_tagger import write_lyrics

    track = db.query(Track).filter(
        Track.id == track_id, Track.album_id == album_id
    ).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    if not os.path.isfile(track.path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    duration = track.duration or 0
    lr = fetch_lyrics(
        artist=track.artist or album.artist or "",
        title=track.title or "",
        album=album.album or "",
        duration=int(duration),
    )

    if not lr or (not lr.plain_lyrics and not lr.synced_lyrics):
        return {"message": "No lyrics found", "found": False, "instrumental": lr.instrumental if lr else False}

    if not write_lyrics(track.path, lr.plain_lyrics, lr.synced_lyrics):
        raise HTTPException(status_code=500, detail="Failed to write lyrics")

    track.has_lyrics = True
    track.lyrics_synced = bool(lr.synced_lyrics)
    db.commit()
    return {"message": "Lyrics written", "found": True, "synced": bool(lr.synced_lyrics)}


@router.get("/{album_id}/tracks/{track_id}/lyrics")
def get_track_lyrics(album_id: int, track_id: int, db: Session = Depends(get_db)):
    """Read lyrics from the audio file."""
    from app.core.lyrics_tagger import read_lyrics

    track = db.query(Track).filter(
        Track.id == track_id, Track.album_id == album_id
    ).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.isfile(track.path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    plain, synced = read_lyrics(track.path)
    return {"plain": plain, "synced": synced}


# ─── ReplayGain ──────────────────────────────────────────────────

@router.post("/{album_id}/replaygain")
def calculate_replaygain(
    album_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Launch ReplayGain calculation as a background task."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    background_tasks.add_task(_replaygain_task, album_id)
    return {"message": "ReplayGain calculation started", "album_id": album_id}


def _replaygain_task(album_id: int):
    """Background task for ReplayGain analysis + tag writing."""
    from app.core.replaygain import analyze_album
    from app.core.replaygain_tagger import write_replaygain
    from app.database import SessionLocal
    from app.services.notification_service import notifications

    db = SessionLocal()
    try:
        album = db.query(Album).filter(Album.id == album_id).first()
        if not album:
            return

        tracks = db.query(Track).filter(Track.album_id == album_id).all()
        filepaths = [t.path for t in tracks if os.path.isfile(t.path)]
        if not filepaths:
            return

        notifications.send_progress(album_id, 0.1, "Creating backup...")
        create_backup(db, album_id, "replaygain")
        db.commit()

        notifications.send_progress(album_id, 0.2, "Analyzing loudness...")
        rg = analyze_album(filepaths)
        if not rg:
            notifications.send_notification("error", f"ReplayGain analysis failed for album {album_id}")
            return

        notifications.send_progress(album_id, 0.7, "Writing ReplayGain tags...")
        path_to_track = {t.path: t for t in tracks}
        success = 0
        for i, filepath in enumerate(filepaths):
            track_rg = rg.tracks.get(filepath)
            if not track_rg:
                continue
            if write_replaygain(filepath, track_rg.gain, track_rg.peak, rg.album_gain, rg.album_peak):
                track = path_to_track.get(filepath)
                if track:
                    track.replaygain_track_gain = track_rg.gain
                    track.replaygain_track_peak = track_rg.peak
                success += 1

        album.replaygain_album_gain = rg.album_gain
        album.replaygain_album_peak = rg.album_peak

        db.add(ActivityLog(
            album_id=album_id, action="replaygain_calculated",
            details=f"Album gain: {rg.album_gain}, written to {success}/{len(filepaths)} tracks",
        ))
        db.commit()

        notifications.send_progress(album_id, 1.0, "ReplayGain complete")
        notifications.send_notification("success", f"ReplayGain calculated for album {album_id}")
        # Trigger a refresh of the album detail
        notifications.send_album_update(album_id, album.status)

    except Exception as e:
        log.error(f"ReplayGain task failed for album {album_id}: {e}")
        notifications.send_notification("error", f"ReplayGain failed: {str(e)[:100]}")
    finally:
        db.close()


@router.post("/scan")
def trigger_scan(
    request: ScanRequest = ScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    background_tasks.add_task(scan_directory, request.path, request.force)
    return {"message": "Scan started", "path": request.path, "force": request.force}
