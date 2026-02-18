import os
import time
import threading
from typing import Callable, Optional

from app.core.audio_reader import AUDIO_EXTENSIONS, is_disc_subfolder, find_disc_subfolders
from app.config import settings
from app.utils.logger import log


class _PollingScanner:
    """Periodically scans for new album folders not yet in the database.

    Needed because inotify events from the host don't propagate into
    Docker containers through bind mounts.
    """

    _POLL_INTERVAL = 60  # seconds between scans

    def __init__(self, watch_path: str, callback: Callable[[str], None]):
        self._watch_path = watch_path
        self._callback = callback
        self._known_folders: set[str] = set()
        self._folder_file_counts: dict[str, int] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        try:
            self._known_folders = self._load_known_folders()
            self._folder_file_counts = {
                folder: self._count_audio_files(folder)
                for folder in self._known_folders
            }
            log.info(f"Polling scanner: {len(self._known_folders)} known folders in DB")
        except Exception as e:
            log.error(f"Failed to load known folders: {e}")
            self._known_folders = set()
            self._folder_file_counts = {}
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _load_known_folders(self) -> set[str]:
        from app.database import SessionLocal
        from app.models import Album
        db = SessionLocal()
        try:
            return {a.path for a in db.query(Album.path).all()}
        finally:
            db.close()

    def _poll_loop(self):
        log.info("Polling scanner thread started")
        while self._running:
            for _ in range(self._POLL_INTERVAL):
                if not self._running:
                    return
                time.sleep(1)

            log.debug("Polling scan cycle...")
            try:
                self._scan_for_new()
            except Exception as e:
                log.error(f"Polling scan error: {e}")

    def _has_audio_files(self, path: str) -> bool:
        """Check if a directory directly contains audio files."""
        return any(
            os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        )

    def _count_audio_files(self, folder: str) -> int:
        """Count audio files in a folder, including disc subfolders."""
        count = 0
        try:
            disc_subs = find_disc_subfolders(folder)
            dirs_to_check = [folder]
            if disc_subs:
                dirs_to_check.extend(disc_subs.values())
            for d in dirs_to_check:
                if not os.path.isdir(d):
                    continue
                for f in os.listdir(d):
                    if os.path.isfile(os.path.join(d, f)) and os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                        count += 1
        except OSError:
            pass
        return count

    def _scan_for_new(self):
        if not os.path.isdir(self._watch_path):
            return

        # Check known folders for file count changes (added/removed tracks)
        for folder in list(self._known_folders):
            if not os.path.isdir(folder):
                continue
            current_count = self._count_audio_files(folder)
            prev_count = self._folder_file_counts.get(folder, 0)
            if current_count != prev_count:
                log.info(f"Audio file count changed in {folder}: {prev_count} -> {current_count}")
                self._folder_file_counts[folder] = current_count
                self._callback(folder)

        for entry in os.listdir(self._watch_path):
            if entry.startswith("."):
                continue
            entry_path = os.path.join(self._watch_path, entry)
            if not os.path.isdir(entry_path):
                continue

            for root, dirs, files in os.walk(entry_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                if root in self._known_folders:
                    continue

                has_audio = any(
                    os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
                    for f in files
                    if not f.startswith(".")
                )
                if has_audio:
                    # Check if this is a disc subfolder — register parent instead
                    folder_name = os.path.basename(root)
                    if is_disc_subfolder(folder_name):
                        parent_path = os.path.dirname(root)
                        if parent_path not in self._known_folders:
                            disc_subs = find_disc_subfolders(parent_path)
                            if disc_subs:
                                log.info(f"New multi-disc album detected: {parent_path}")
                                self._known_folders.add(parent_path)
                                self._folder_file_counts[parent_path] = self._count_audio_files(parent_path)
                                # Mark all disc subfolders as known
                                for disc_path in disc_subs.values():
                                    self._known_folders.add(disc_path)
                                self._callback(parent_path)
                                continue
                    log.info(f"New album folder detected: {root}")
                    self._known_folders.add(root)
                    self._folder_file_counts[root] = self._count_audio_files(root)
                    self._callback(root)


class FileWatcher:
    """Monitors music directory for new albums via polling."""

    def __init__(self, on_new_folder: Callable[[str], None]):
        self._watch_path = settings.music_dir
        self._on_new_folder = on_new_folder
        self._poller = _PollingScanner(self._watch_path, on_new_folder)

    def start(self):
        if not os.path.isdir(self._watch_path):
            log.warning(f"Watch path does not exist: {self._watch_path}")
            return

        self._poller.start()
        log.info(f"File watcher started on {self._watch_path} (polling every {_PollingScanner._POLL_INTERVAL}s)")

    def stop(self):
        self._poller.stop()
        log.info("File watcher stopped")
