"""Background worker thread for image compression.

Design notes
------------
* The worker runs in a daemon thread so it is automatically killed when the
  main window closes.
* It communicates back to the UI thread *exclusively* via a thread-safe
  ``queue.Queue`` so the UI never needs to acquire any lock.
* Cancellation is cooperative: the worker checks ``_cancel_event`` between
  each file; it never interrupts Pillow mid-save.

Message protocol (dict payloads placed on the ``result_queue``)
---------------------------------------------------------------
``{"type": "progress", "index": int, "total": int, "name": str}``
    Emitted *before* each file is processed so the progress bar can advance.

``{"type": "result", "index": int, "name": str, "src_path": str,
    "output_path": str, "original_size": int, "result": CompressionResult}``
    Emitted on successful compression.

``{"type": "error", "index": int, "name": str, "exc": Exception}``
    Emitted when a single file fails (other files still continue).

``{"type": "done", "success": int, "failure": int}``
    Final message; always emitted even after cancellation.

``{"type": "cancelled"}``
    Emitted *instead of* ``done`` when the worker is cancelled.
"""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path

from PIL import UnidentifiedImageError

from ..core.compressor import compress_image, get_engine_name
from ..core.models import CompressionResult, CompressionTask
from ..core.utils import build_output_path, get_file_size, resolve_output_extension


class CompressWorker:
    """Manages a single compression batch in a background thread."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self.result_queue: queue.Queue[dict] = queue.Queue()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        tasks: list[CompressionTask],
        fmt_choice: str,
        output_mode: str,
        custom_dir: str,
        strip_exif: bool,
        engine_preference: str = "auto",
    ) -> None:
        """Start the compression batch in a daemon thread.

        This method is *not* re-entrant; call :meth:`cancel` first if a batch
        is already running.
        """
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(tasks, fmt_choice, output_mode, custom_dir, strip_exif, engine_preference),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation.  The worker will stop before the next file."""
        self._cancel_event.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(
        self,
        tasks: list[CompressionTask],
        fmt_choice: str,
        output_mode: str,
        custom_dir: str,
        strip_exif: bool,
        engine_preference: str,
    ) -> None:
        success = 0
        failure = 0
        total = len(tasks)
        _engine_name = get_engine_name(engine_preference)

        for index, task in enumerate(tasks, start=1):
            if self._cancel_event.is_set():
                self.result_queue.put({"type": "cancelled"})
                return

            self.result_queue.put(
                {
                    "type": "progress",
                    "index": index,
                    "total": total,
                    "name": task.src_name,
                }
            )

            try:
                output_ext, warning = resolve_output_extension(
                    task.src_path, fmt_choice
                )
                output_path = build_output_path(
                    task.src_path, output_ext, output_mode, custom_dir
                )
                original_size = get_file_size(task.src_path) or 0

                result: CompressionResult = compress_image(
                    task.src_path,
                    task.target_bytes,
                    output_path,
                    strip_exif=strip_exif,
                    engine_preference=engine_preference,
                )
                if warning:
                    result.warning = warning

                self.result_queue.put(
                    {
                        "type": "result",
                        "index": index,
                        "name": task.src_name,
                        "src_path": task.src_path,
                        "output_path": output_path,
                        "original_size": original_size,
                        "result": result,
                        "engine_name": _engine_name,
                    }
                )
                success += 1

            except UnidentifiedImageError as exc:
                self.result_queue.put(
                    {"type": "error", "index": index, "name": task.src_name, "exc": exc}
                )
                failure += 1
            except Exception as exc:  # noqa: BLE001
                self.result_queue.put(
                    {"type": "error", "index": index, "name": task.src_name, "exc": exc}
                )
                failure += 1

        self.result_queue.put({"type": "done", "success": success, "failure": failure})
