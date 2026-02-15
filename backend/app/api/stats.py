from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import Album, ActivityLog
from app.schemas import StatsResponse, ActivityLogResponse
from app.services.queue_manager import queue_manager

router = APIRouter()


@router.get("", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    counts = (
        db.query(Album.status, func.count(Album.id))
        .group_by(Album.status)
        .all()
    )
    status_map = dict(counts)

    # Recent activity (last 20 entries)
    recent = (
        db.query(ActivityLog)
        .order_by(ActivityLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return StatsResponse(
        total_albums=sum(status_map.values()),
        tagged_count=status_map.get("tagged", 0),
        pending_count=status_map.get("pending", 0),
        matching_count=status_map.get("matching", 0),
        needs_review_count=status_map.get("needs_review", 0),
        failed_count=status_map.get("failed", 0),
        skipped_count=status_map.get("skipped", 0),
        queue_size=queue_manager.queue_size,
        is_processing=queue_manager.is_processing,
        recent_activity=[ActivityLogResponse.model_validate(a) for a in recent],
    )


@router.get("/activity", response_model=List[ActivityLogResponse])
def get_activity(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get activity log entries."""
    activities = (
        db.query(ActivityLog)
        .order_by(ActivityLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [ActivityLogResponse.model_validate(a) for a in activities]
