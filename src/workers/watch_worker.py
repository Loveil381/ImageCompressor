"""Watch worker for monitoring directories and triggering auto-compression."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import (
    FileCreatedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from ..core.utils import EXT_TO_FORMAT

logger = logging.getLogger(__name__)


class AutoCompressHandler(FileSystemEventHandler):
    """Handles watchdog events and filters for images to compress."""

    def __init__(self, on_image_found: Callable[[str], None], stabilization_seconds: float = 2.0) -> None:
        super().__init__()
        self.on_image_found = on_image_found
        self.stabilization_seconds = stabilization_seconds

        self._compressed_suffix = "_compressed"
        self._supported_exts = set(EXT_TO_FORMAT.keys())

    def _process_path(self, path_str: str | bytes) -> None:
        normalized_path = os.fsdecode(path_str)
        path = Path(normalized_path)

        if not path.is_file() and not path.exists():
            # Could be a slightly delayed write, but we only check extension first
            pass

        if path.suffix.lower() not in self._supported_exts:
            return

        # Infinite loop prevention
        if self._compressed_suffix in path.stem:
            return

        # Avoid blocking the observer thread
        threading.Thread(target=self._wait_and_emit, args=(normalized_path,), daemon=True).start()

    def _wait_and_emit(self, path_str: str) -> None:
        time.sleep(self.stabilization_seconds)

        path = Path(path_str)

        # Some file systems emit a create event before the writer has flushed data.
        for _ in range(10):
            try:
                if path.exists() and path.stat().st_size > 0:
                    self.on_image_found(path_str)
                    return
            except OSError:
                return
            threading.Event().wait(0.05)

        return

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if isinstance(event, FileCreatedEvent):
            self._process_path(event.src_path)
        else:
            # Fallback for some platforms where it's generically FileSystemEvent
            self._process_path(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if isinstance(event, FileMovedEvent):
            self._process_path(event.dest_path)


class WatchWorker:
    """Manages the watchdog Observer for Watch Mode."""

    def __init__(self, on_image_found: Callable[[str], None]) -> None:
        self.observer: Any = None
        self.on_image_found = on_image_found
        self.handler = AutoCompressHandler(on_image_found=self.on_image_found)

    def start(self, directories: list[str], recursive: bool = False) -> None:
        self.stop()
        if not directories:
            return

        self.observer = Observer()
        started_any = False
        for d in directories:
            p = Path(d)
            if p.is_dir():
                try:
                    self.observer.schedule(self.handler, str(p), recursive=recursive)
                    started_any = True
                except OSError as e:
                    logger.warning("Failed to schedule watch for %s: %s", d, e)

        if started_any:
            self.observer.start()
            for _ in range(20):
                if self.observer.is_alive():
                    break
                threading.Event().wait(0.01)
        else:
            self.observer = None

    def stop(self) -> None:
        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self.observer = None

    def is_running(self) -> bool:
        return self.observer is not None and self.observer.is_alive()
