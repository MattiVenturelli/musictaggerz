import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.api import albums, settings, stats, websocket
from app.services.queue_manager import queue_manager
from app.services.file_watcher import FileWatcher
from app.utils.logger import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting MusicTaggerz...")
    init_db()
    log.info("Database initialized.")

    queue_manager.start()
    log.info("Queue manager started.")

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
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
