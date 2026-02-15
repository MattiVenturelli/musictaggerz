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
    ArtworkOptionResponse, ArtworkDiscoveryResponse, ApplyArtworkRequest,
)
from app.core.audio_reader import read_track
from app.core.artwork_discovery import (
    discover_caa, discover_itunes, discover_fanarttv, discover_filesystem,
)
from app.core.artwork_fetcher import _download_image, save_artwork_to_folder
from app.core.tagger import write_tags, TagData
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

    # Embed in all audio files
    tracks = db.query(Track).filter(Track.album_id == album_id).all()
    embedded = 0
    for track in tracks:
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


@router.post("/scan")
def trigger_scan(
    request: ScanRequest = ScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    background_tasks.add_task(scan_directory, request.path, request.force)
    return {"message": "Scan started", "path": request.path, "force": request.force}
