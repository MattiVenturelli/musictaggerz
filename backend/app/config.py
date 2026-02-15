import json
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    music_dir: str = "/music"
    database_url: str = "sqlite:////data/autotagger.db"
    log_level: str = "INFO"

    auto_tag_on_scan: bool = False
    confidence_auto_threshold: float = 85.0
    confidence_review_threshold: float = 50.0

    artwork_min_size: int = 500
    artwork_max_size: int = 1400
    artwork_sources: List[str] = [
        "coverart", "filesystem", "fanarttv", "itunes", "spotify"
    ]

    watch_stabilization_delay: int = 30

    fanarttv_api_key: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    preferred_countries: List[str] = ["US", "GB", "DE", "IT"]
    preferred_media: List[str] = ["Digital Media", "CD"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def apply_from_db(self, key: str, value: str) -> None:
        """Update a runtime setting from a DB value."""
        if not hasattr(self, key):
            return
        field = self.model_fields.get(key)
        if not field:
            return

        origin = field.annotation
        try:
            if origin is bool:
                object.__setattr__(self, key, value.lower() not in ("false", "0", "no", ""))
            elif origin is float or (hasattr(origin, '__origin__') and origin is float):
                object.__setattr__(self, key, float(value))
            elif origin is int:
                object.__setattr__(self, key, int(value))
            elif origin == List[str] or str(origin) == "typing.List[str]":
                # Accept both JSON array and comma-separated
                if value.startswith("["):
                    object.__setattr__(self, key, json.loads(value))
                else:
                    object.__setattr__(self, key, [v.strip() for v in value.split(",") if v.strip()])
            else:
                object.__setattr__(self, key, value)
        except (ValueError, json.JSONDecodeError):
            pass

    def load_from_db(self) -> None:
        """Load all settings from DB into runtime config."""
        from app.database import SessionLocal
        from app.models import Setting
        db = SessionLocal()
        try:
            for s in db.query(Setting).all():
                if s.value is not None:
                    self.apply_from_db(s.key, s.value)
        finally:
            db.close()


settings = Settings()
