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
    _seed_default_settings()


def _seed_default_settings():
    from app.models import Setting
    db = SessionLocal()
    try:
        existing = db.query(Setting).count()
        if existing > 0:
            return

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
            Setting(key="fanarttv_api_key", value="", value_type="string",
                    description="fanart.tv API key"),
            Setting(key="spotify_client_id", value="", value_type="string",
                    description="Spotify client ID"),
            Setting(key="spotify_client_secret", value="", value_type="string",
                    description="Spotify client secret"),
            Setting(key="preferred_countries", value='["US","GB","DE","IT"]',
                    value_type="json", description="Preferred release countries"),
            Setting(key="preferred_media", value='["Digital Media","CD"]',
                    value_type="json", description="Preferred media types"),
        ]
        db.add_all(defaults)
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
