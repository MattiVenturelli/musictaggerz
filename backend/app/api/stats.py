from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Album
from app.schemas import StatsResponse

router = APIRouter()


@router.get("", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    counts = (
        db.query(Album.status, func.count(Album.id))
        .group_by(Album.status)
        .all()
    )
    status_map = dict(counts)

    return StatsResponse(
        total_albums=sum(status_map.values()),
        tagged_count=status_map.get("tagged", 0),
        pending_count=status_map.get("pending", 0),
        matching_count=status_map.get("matching", 0),
        needs_review_count=status_map.get("needs_review", 0),
        failed_count=status_map.get("failed", 0),
        skipped_count=status_map.get("skipped", 0),
    )
