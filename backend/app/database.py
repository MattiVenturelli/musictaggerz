import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import settings


db_path = settings.database_url.replace("sqlite:///", "")
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    from app.models import Album, Track, MatchCandidate, Setting, ActivityLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()
    _seed_default_settings()
    _migrate_json_list_settings()
    _migrate_disc_patterns_to_json()


def _migrate_add_columns():
    """Add columns that were introduced after initial schema creation."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Check existing columns in albums table
        result = conn.execute(text("PRAGMA table_info(albums)"))
        existing = {row[1] for row in result}
        if "musicbrainz_release_group_id" not in existing:
            conn.execute(text("ALTER TABLE albums ADD COLUMN musicbrainz_release_group_id TEXT"))
            conn.commit()


def _seed_default_settings():
    import json as _json
    from app.models import Setting
    db = SessionLocal()
    try:
        defaults = [
            Setting(key="confidence_auto_threshold", value="85", value_type="float",
                    description="Auto-tag if confidence >= this"),
            Setting(key="confidence_review_threshold", value="50", value_type="float",
                    description="Queue for review if confidence >= this"),
            Setting(key="artwork_min_size", value="500", value_type="int",
                    description="Minimum artwork dimension in pixels"),
            Setting(key="artwork_max_size", value="1400", value_type="int",
                    description="Maximum artwork dimension in pixels"),
            Setting(key="watch_stabilization_delay", value="30", value_type="int",
                    description="Seconds to wait for file copy completion"),
            Setting(key="acoustid_api_key", value="", value_type="string",
                    description="AcoustID API key for audio fingerprinting"),
            Setting(key="fingerprint_enabled", value="false", value_type="bool",
                    description="Enable audio fingerprint matching via AcoustID"),
            Setting(key="fanarttv_api_key", value="", value_type="string",
                    description="fanart.tv API key"),
            Setting(key="spotify_client_id", value="", value_type="string",
                    description="Spotify client ID"),
            Setting(key="spotify_client_secret", value="", value_type="string",
                    description="Spotify client secret"),
            Setting(key="preferred_countries", value="US,GB,DE,IT",
                    value_type="list", description="Preferred release countries"),
            Setting(key="preferred_media", value="Digital Media,CD",
                    value_type="list", description="Preferred media types"),
            Setting(key="disc_subfolder_patterns",
                    value=_json.dumps([
                        r"^(?:cd|disc|disk)\s*(\d+)$",
                        r"^(?:(?:7|10|12)\s*(?:inch\s*)?)?vinyl\s*(\d+)$",
                        r"^side\s*([A-Da-d\d])$",
                        r"^cassette\s*(\d+)$",
                    ]),
                    value_type="list",
                    description="Regex patterns to detect disc subfolders (one capture group each)"),
        ]
        for d in defaults:
            existing = db.query(Setting).filter(Setting.key == d.key).first()
            if not existing:
                db.add(d)
        db.commit()
    finally:
        db.close()


def _migrate_json_list_settings():
    """Convert list settings from JSON array format to comma-separated."""
    import json as _json
    from app.models import Setting
    db = SessionLocal()
    try:
        for key in ("preferred_countries", "preferred_media", "artwork_sources"):
            s = db.query(Setting).filter(Setting.key == key).first()
            if s and s.value and s.value.startswith("["):
                try:
                    parsed = _json.loads(s.value)
                    if isinstance(parsed, list):
                        s.value = ",".join(str(v) for v in parsed)
                except _json.JSONDecodeError:
                    pass
        db.commit()
    finally:
        db.close()


def _migrate_disc_patterns_to_json():
    """Convert disc_subfolder_patterns from comma-separated to JSON array."""
    import json as _json
    from app.models import Setting
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == "disc_subfolder_patterns").first()
        if s and s.value and not s.value.startswith("["):
            patterns = [p.strip() for p in s.value.split(",") if p.strip()]
            s.value = _json.dumps(patterns)
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
