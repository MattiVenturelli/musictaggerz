import os
import time
import threading
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent, DirCreatedEvent, DirMovedEvent

from app.core.audio_reader import AUDIO_EXTENSIONS
from app.config import settings
from app.utils.logger import log


class _StabilizationTracker:
    """Tracks folders with recent activity and triggers callback after stabilization delay."""

    def __init__(self, delay: int, callback: Callable[[str], None]):
        self._delay = delay
        self._callback = callback
        self._pending: dict[str, float] = {}  # folder_path -> last_activity_time
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def notify(self, folder_path: str):
        """Record activity in a folder."""
        with self._lock:
            self._pending[folder_path] = time.time()

    def _monitor_loop(self):
        while self._running:
            time.sleep(2)  # check every 2 seconds
            now = time.time()
            ready = []

            with self._lock:
                for folder, last_time in list(self._pending.items()):
                    if now - last_time >= self._delay:
                        ready.append(folder)
                for folder in ready:
                    del self._pending[folder]

            for folder in ready:
                log.info(f"Folder stabilized after {self._delay}s: {folder}")
                try:
                    self._callback(folder)
                except Exception as e:
                    log.error(f"Error processing stabilized folder {folder}: {e}")


class MusicFolderHandler(FileSystemEventHandler):
    """Watches for new audio files and triggers processing after stabilization."""

    def __init__(self, tracker: _StabilizationTracker):
        super().__init__()
        self._tracker = tracker

    def _should_ignore(self, path: str) -> bool:
        basename = os.path.basename(path)
        if basename.startswith("."):
            return True
        if basename.startswith("~") or basename.endswith(".tmp") or basename.endswith(".part"):
            return True
        return False

    def _get_album_folder(self, filepath: str) -> Optional[str]:
        """Get the album folder containing an audio file."""
        folder = os.path.dirname(filepath)
        if self._should_ignore(folder):
            return None
        return folder

    def on_created(self, event):
        if self._should_ignore(event.src_path):
            return

        if isinstance(event, FileCreatedEvent):
            ext = os.path.splitext(event.src_path)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                folder = self._get_album_folder(event.src_path)
                if folder:
                    log.debug(f"New audio file detected: {event.src_path}")
                    self._tracker.notify(folder)

        elif isinstance(event, DirCreatedEvent):
            # New directory - might contain audio files soon
            log.debug(f"New directory detected: {event.src_path}")

    def on_moved(self, event):
        if self._should_ignore(event.dest_path):
            return

        if isinstance(event, FileMovedEvent):
            ext = os.path.splitext(event.dest_path)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                folder = self._get_album_folder(event.dest_path)
                if folder:
                    log.debug(f"Audio file moved: {event.dest_path}")
                    self._tracker.notify(folder)

        elif isinstance(event, DirMovedEvent):
            # Check if moved directory has audio
            if os.path.isdir(event.dest_path):
                has_audio = any(
                    os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
                    for f in os.listdir(event.dest_path)
                    if os.path.isfile(os.path.join(event.dest_path, f))
                )
                if has_audio:
                    self._tracker.notify(event.dest_path)


class FileWatcher:
    """Monitors music directory for new albums."""

    def __init__(self, on_new_folder: Callable[[str], None]):
        self._watch_path = settings.music_dir
        self._delay = settings.watch_stabilization_delay
        self._on_new_folder = on_new_folder
        self._tracker = _StabilizationTracker(self._delay, on_new_folder)
        self._observer: Optional[Observer] = None

    def start(self):
        if not os.path.isdir(self._watch_path):
            log.warning(f"Watch path does not exist: {self._watch_path}")
            return

        self._tracker.start()

        handler = MusicFolderHandler(self._tracker)
        self._observer = Observer()
        self._observer.schedule(handler, self._watch_path, recursive=True)
        self._observer.daemon = True
        self._observer.start()

        log.info(f"File watcher started on {self._watch_path} (stabilization: {self._delay}s)")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
        self._tracker.stop()
        log.info("File watcher stopped")
