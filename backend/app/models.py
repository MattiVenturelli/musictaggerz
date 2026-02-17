from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, Index
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String, nullable=False, unique=True)
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    status = Column(String, nullable=False, default="pending")
    match_confidence = Column(Float)
    musicbrainz_release_id = Column(String)
    musicbrainz_release_group_id = Column(String)
    cover_path = Column(String)
    cover_url = Column(String)
    track_count = Column(Integer)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    replaygain_album_gain = Column(String)
    replaygain_album_peak = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tracks = relationship("Track", back_populates="album", cascade="all, delete-orphan")
    match_candidates = relationship("MatchCandidate", back_populates="album_obj", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_albums_status", "status"),
        Index("idx_albums_updated", "updated_at"),
    )


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    path = Column(String, nullable=False, unique=True)
    track_number = Column(Integer)
    disc_number = Column(Integer, default=1)
    title = Column(String)
    artist = Column(String)
    duration = Column(Float)
    musicbrainz_recording_id = Column(String)
    status = Column(String, default="pending")
    error_message = Column(Text)
    has_lyrics = Column(Boolean, default=False)
    lyrics_synced = Column(Boolean, default=False)
    replaygain_track_gain = Column(String)
    replaygain_track_peak = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    album = relationship("Album", back_populates="tracks")

    __table_args__ = (
        Index("idx_tracks_album", "album_id"),
    )


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    musicbrainz_release_id = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    original_year = Column(Integer)
    track_count = Column(Integer)
    country = Column(String)
    media = Column(String)
    label = Column(String)
    barcode = Column(String)
    is_selected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    album_obj = relationship("Album", back_populates="match_candidates")

    __table_args__ = (
        Index("idx_candidates_album", "album_id"),
    )


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text)
    value_type = Column(String)
    description = Column(Text)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="SET NULL"))
    action = Column(String, nullable=False)
    details = Column(Text)
    timestamp = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("idx_activity_timestamp", "timestamp"),
    )


class TagBackup(Base):
    __tablename__ = "tag_backups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)  # musicbrainz_tag, manual_edit, artwork, lyrics, replaygain, pre_restore
    created_at = Column(DateTime, default=utcnow)

    snapshots = relationship("TrackTagSnapshot", back_populates="backup", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_backups_album", "album_id"),
    )


class TrackTagSnapshot(Base):
    __tablename__ = "track_tag_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backup_id = Column(Integer, ForeignKey("tag_backups.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    path = Column(String, nullable=False)
    tags_json = Column(Text, nullable=False)  # JSON serialized tag data
    has_cover = Column(Boolean, default=False)
    cover_path = Column(String)  # path to saved cover file on disk

    backup = relationship("TagBackup", back_populates="snapshots")

    __table_args__ = (
        Index("idx_snapshots_backup", "backup_id"),
    )
