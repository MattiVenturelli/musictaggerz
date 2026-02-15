from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    music_dir: str = "/music"
    database_url: str = "sqlite:////data/autotagger.db"
    log_level: str = "INFO"

    confidence_auto_threshold: float = 85.0
    confidence_review_threshold: float = 50.0

    artwork_min_size: int = 500
    artwork_max_size: int = 1400
    artwork_sources: List[str] = [
        "filesystem", "itunes", "fanarttv", "spotify", "coverart"
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


settings = Settings()
