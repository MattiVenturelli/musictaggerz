import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, SessionLocal
from app.models import Album
from app.config import settings as app_settings
from app.api import albums, settings, stats, websocket
from app.services.queue_manager import queue_manager
from app.services.file_watcher import FileWatcher
from app.services.notification_service import notifications
from app.utils.logger import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting MusicTaggerz...")
    init_db()
    app_settings.load_from_db()
    log.info("Database initialized.")

    # Give the notification service access to the event loop for thread-safe broadcast
    notifications.set_loop(asyncio.get_running_loop())

    queue_manager.start()
    log.info("Queue manager started.")

    # Recovery: re-queue albums stuck in "matching" status from a previous run
    db = SessionLocal()
    try:
        stuck = db.query(Album).filter(Album.status == "matching").all()
        if stuck:
            for album in stuck:
                queue_manager.enqueue_album(album.id)
            log.info(f"Recovery: re-queued {len(stuck)} albums stuck in 'matching' status")
    finally:
        db.close()

    watcher = FileWatcher(on_new_folder=queue_manager.enqueue_folder)
    watcher.start()

    yield

    watcher.stop()
    queue_manager.stop()
    log.info("Shutting down MusicTaggerz.")


app = FastAPI(
    title="MusicTaggerz",
    version="1.0.0",
    description="Automatic music tagger with MusicBrainz integration",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(albums.router, prefix="/api/albums", tags=["albums"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all non-API routes (SPA client-side routing)."""
        return FileResponse(os.path.join(static_dir, "index.html"))
