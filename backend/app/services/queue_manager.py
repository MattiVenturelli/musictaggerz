import threading
import queue
from dataclasses import dataclass
from typing import Optional

from app.services.album_scanner import scan_single_folder
from app.services.tagging_service import process_album
from app.models import Album
from app.database import SessionLocal
from app.utils.logger import log

MAX_RETRIES = 3


@dataclass
class QueueItem:
    folder_path: Optional[str] = None  # for new folder scan + tag
    album_id: Optional[int] = None     # for direct album tag
    release_id: Optional[str] = None   # optional: specific MusicBrainz release
    retry_count: int = 0


class QueueManager:
    """FIFO processing queue for sequential album tagging."""

    def __init__(self):
        self._queue: queue.Queue[QueueItem] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._current_item: Optional[QueueItem] = None

    def start(self):
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        log.info("Queue manager started")

    def stop(self):
        self._running = False
        # Put a sentinel to unblock the worker
        self._queue.put(None)
        if self._worker:
            self._worker.join(timeout=10)
        log.info("Queue manager stopped")

    def enqueue_folder(self, folder_path: str):
        """Add a new folder to scan and tag."""
        item = QueueItem(folder_path=folder_path)
        self._queue.put(item)
        log.info(f"Queued folder: {folder_path} (queue size: {self._queue.qsize()})")

    def enqueue_album(self, album_id: int, release_id: Optional[str] = None):
        """Add an album to the tagging queue."""
        item = QueueItem(album_id=album_id, release_id=release_id)
        self._queue.put(item)
        log.info(f"Queued album {album_id} (queue size: {self._queue.qsize()})")

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        return self._current_item is not None

    def _worker_loop(self):
        while self._running:
            try:
                item = self._queue.get(timeout=2)
            except queue.Empty:
                continue

            if item is None:  # sentinel
                break

            self._current_item = item
            try:
                self._process_item(item)
            except Exception as e:
                log.error(f"Queue worker error: {e}")
                self._handle_retry(item)
            finally:
                self._current_item = None
                self._queue.task_done()

    def _process_item(self, item: QueueItem):
        album_id = item.album_id

        # If it's a folder, scan it first
        if item.folder_path and not album_id:
            log.info(f"Processing folder: {item.folder_path}")
            album_id = scan_single_folder(item.folder_path)
            if not album_id:
                log.warning(f"No album found in folder: {item.folder_path}")
                return

        if not album_id:
            return

        log.info(f"Processing album {album_id} (attempt {item.retry_count + 1})")
        success = process_album(album_id, release_id=item.release_id)

        if not success and item.retry_count < MAX_RETRIES - 1:
            # Check if it needs review (don't retry those)
            db = SessionLocal()
            try:
                album = db.query(Album).filter(Album.id == album_id).first()
                if album and album.status in ("needs_review", "skipped"):
                    log.info(f"Album {album_id} status is '{album.status}', not retrying")
                    return
            finally:
                db.close()

            self._handle_retry(QueueItem(
                album_id=album_id,
                release_id=item.release_id,
                retry_count=item.retry_count,
            ))

    def _handle_retry(self, item: QueueItem):
        if item.retry_count < MAX_RETRIES - 1:
            item.retry_count += 1
            self._queue.put(item)
            log.info(f"Re-queued album {item.album_id} (retry {item.retry_count}/{MAX_RETRIES})")

            # Update retry count in DB
            if item.album_id:
                db = SessionLocal()
                try:
                    album = db.query(Album).filter(Album.id == item.album_id).first()
                    if album:
                        album.retry_count = item.retry_count
                        db.commit()
                finally:
                    db.close()
        else:
            log.warning(f"Max retries reached for album {item.album_id}")


# Singleton instance
queue_manager = QueueManager()
