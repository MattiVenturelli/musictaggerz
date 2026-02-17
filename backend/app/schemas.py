from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TrackBase(BaseModel):
    track_number: Optional[int] = None
    disc_number: Optional[int] = 1
    title: Optional[str] = None
    artist: Optional[str] = None
    duration: Optional[float] = None
    path: str


class TrackResponse(TrackBase):
    id: int
    album_id: int
    musicbrainz_recording_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    has_lyrics: Optional[bool] = False
    lyrics_synced: Optional[bool] = False
    replaygain_track_gain: Optional[str] = None
    replaygain_track_peak: Optional[str] = None

    class Config:
        from_attributes = True


class MatchCandidateResponse(BaseModel):
    id: int
    musicbrainz_release_id: str
    confidence: float
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    original_year: Optional[int] = None
    track_count: Optional[int] = None
    country: Optional[str] = None
    media: Optional[str] = None
    label: Optional[str] = None
    is_selected: bool

    class Config:
        from_attributes = True


class AlbumSummary(BaseModel):
    id: int
    path: str
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    status: str
    match_confidence: Optional[float] = None
    cover_path: Optional[str] = None
    track_count: Optional[int] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlbumDetail(AlbumSummary):
    musicbrainz_release_id: Optional[str] = None
    cover_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    replaygain_album_gain: Optional[str] = None
    replaygain_album_peak: Optional[str] = None
    tracks: List[TrackResponse] = []
    match_candidates: List[MatchCandidateResponse] = []


class AlbumListResponse(BaseModel):
    items: List[AlbumSummary]
    total: int
    limit: int
    offset: int


class TagRequest(BaseModel):
    release_id: Optional[str] = None


class ScanRequest(BaseModel):
    path: Optional[str] = None
    force: bool = False


class BatchActionRequest(BaseModel):
    album_ids: List[int]


class StatsResponse(BaseModel):
    total_albums: int
    tagged_count: int
    pending_count: int
    matching_count: int
    needs_review_count: int
    failed_count: int
    skipped_count: int
    queue_size: int = 0
    is_processing: bool = False
    recent_activity: List["ActivityLogResponse"] = []


class SettingResponse(BaseModel):
    key: str
    value: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SettingsUpdateRequest(BaseModel):
    settings: dict


class ActivityLogResponse(BaseModel):
    id: int
    album_id: Optional[int] = None
    action: str
    details: Optional[str] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


StatsResponse.model_rebuild()


class ArtworkOptionResponse(BaseModel):
    source: str
    thumbnail_url: str
    full_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    label: str


class ArtworkDiscoveryResponse(BaseModel):
    album_id: int
    options: List[ArtworkOptionResponse]


class ApplyArtworkRequest(BaseModel):
    source: str
    full_url: str
    file: Optional[str] = None


# ─── Tag Backup schemas ──────────────────────────────────────────

class TagBackupResponse(BaseModel):
    id: int
    album_id: int
    action: str
    created_at: Optional[datetime] = None
    track_count: int = 0

    class Config:
        from_attributes = True


# ─── Manual Tag Editing schemas ──────────────────────────────────

class ManualTagEditRequest(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    album_artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None


class BulkManualTagEditRequest(BaseModel):
    album: Optional[str] = None
    album_artist: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None
