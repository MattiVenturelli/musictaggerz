from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import Album, Track, ActivityLog
from app.schemas import (
    AlbumSummary, AlbumDetail, AlbumListResponse,
    TagRequest, ScanRequest, TrackResponse, MatchCandidateResponse,
)
from app.services.album_scanner import scan_directory

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
    }
    query = query.order_by(sort_map.get(sort, Album.updated_at.desc()))

    albums = query.offset(offset).limit(limit).all()

    return AlbumListResponse(
        items=[AlbumSummary.model_validate(a) for a in albums],
        total=total,
        limit=limit,
        offset=offset,
    )


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
async def tag_album(
    album_id: int,
    request: TagRequest = TagRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    album.status = "matching"
    db.commit()

    # Tagging will be implemented in Phase 3-4
    # background_tasks.add_task(tagging_service.tag_album, album_id, request.release_id)

    return {"message": "Tagging queued", "album_id": album_id}


@router.post("/{album_id}/skip")
def skip_album(album_id: int, db: Session = Depends(get_db)):
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    album.status = "skipped"
    db.add(ActivityLog(album_id=album_id, action="skipped"))
    db.commit()

    return {"message": "Album skipped", "album_id": album_id}


@router.post("/scan")
async def trigger_scan(
    request: ScanRequest = ScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    background_tasks.add_task(scan_directory, request.path)
    return {"message": "Scan started", "path": request.path}
