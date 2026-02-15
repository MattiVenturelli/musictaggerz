import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import Album, Track, MatchCandidate, ActivityLog
from app.schemas import (
    AlbumSummary, AlbumDetail, AlbumListResponse,
    TagRequest, ScanRequest, TrackResponse, MatchCandidateResponse,
    BatchActionRequest,
)
from app.core.audio_reader import read_track
from app.services.album_scanner import scan_directory
from app.services.queue_manager import queue_manager

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
def get_album_cover(album_id: int, db: Session = Depends(get_db)):
    """Serve album cover art image from filesystem."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

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


@router.post("/scan")
def trigger_scan(
    request: ScanRequest = ScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    background_tasks.add_task(scan_directory, request.path, request.force)
    return {"message": "Scan started", "path": request.path, "force": request.force}
