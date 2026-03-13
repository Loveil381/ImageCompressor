"""Decouples worker message processing from the App window.

The ``MessageHandler`` class receives messages from the ``CompressWorker``
queue and dispatches them to the UI widgets (log panel, progress bar,
status label).  This makes the message-processing logic independently
testable and keeps ``App._poll_worker`` under 15 lines.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PIL import UnidentifiedImageError

from ..core.utils import format_bytes, format_eta, format_scale
from ..i18n.strings import T

# ---------------------------------------------------------------------------
# Protocols for the UI widgets we depend on (makes mocking easy)
# ---------------------------------------------------------------------------


class LogSink(Protocol):
    """Minimal interface for a log panel."""

    def append_ok(self, message: str) -> None: ...
    def append_warn(self, message: str) -> None: ...
    def append_error(self, message: str) -> None: ...
    def append_info(self, message: str) -> None: ...
    def append_sep(self) -> None: ...
    def clear(self) -> None: ...


class ProgressSink(Protocol):
    """Minimal interface for a progress bar."""

    def configure(self, **kw: object) -> None: ...

    def __getitem__(self, key: str) -> object: ...


class StatusSink(Protocol):
    """Minimal interface for a status label."""

    def configure(self, **kw: object) -> None: ...


# ---------------------------------------------------------------------------
# MessageHandler
# ---------------------------------------------------------------------------


class MessageHandler:
    """Process worker messages and route them to UI widgets.

    Parameters
    ----------
    log:
        Log panel (or any object satisfying ``LogSink``).
    progress:
        Progress bar widget.
    status:
        Status label widget.
    target_bytes:
        Cached target size – avoids re-parsing every message.
    start_time:
        ``time.time()`` captured when the batch started.
    on_complete:
        Called when a ``done`` message arrives.  Signature:
        ``on_complete(success: int, failure: int) -> None``.
    on_cancel:
        Called when a ``cancelled`` message arrives.  No arguments.
    """

    def __init__(
        self,
        log: LogSink,
        progress: ProgressSink,
        status: StatusSink,
        target_bytes: int,
        start_time: float,
        on_complete: Callable[[int, int], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._log = log
        self._progress = progress
        self._status = status
        self._target_bytes = target_bytes
        self._start_time = start_time
        self._on_complete = on_complete
        self._on_cancel = on_cancel

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, msg: dict) -> bool:
        """Process one worker message.

        Returns ``True`` if the message is terminal (``done`` or
        ``cancelled``), meaning the poll loop should stop.
        """
        mtype = msg["type"]
        handler = self._DISPATCH.get(mtype)
        if handler is not None:
            return handler(self, msg)
        return False

    # ------------------------------------------------------------------
    # Per-type handlers
    # ------------------------------------------------------------------

    def _handle_progress(self, msg: dict) -> bool:
        idx = msg["index"]
        total = msg["total"]
        self._progress.configure(value=idx - 1)

        elapsed = time.time() - self._start_time
        eta_str = format_eta(elapsed, idx - 1, total)

        self._status.configure(
            text=f"{T('status_compressing')}  {idx}/{total}  —  {msg['name']}{eta_str}"
        )
        return False

    def _handle_result(self, msg: dict) -> bool:
        r = msg["result"]
        orig = msg["original_size"]
        ratio = (r.actual_size / orig * 100) if orig else 0.0
        scale_note = T("scale_note", pct=format_scale(r.scale)) if r.resized else ""
        warn_note = f"；{r.warning}" if r.warning else ""

        out_name = Path(msg["output_path"]).name
        target_met = r.actual_size <= self._target_bytes

        text = T(
            "log_ok" if target_met else "log_warn",
            name=msg["name"],
            orig=format_bytes(orig),
            out=format_bytes(r.actual_size),
            ratio=ratio,
            scale=scale_note,
            fmt=r.format_name,
            quality=r.quality_text,
            outname=out_name,
            warn=warn_note,
        )
        if target_met:
            self._log.append_ok(text)
        else:
            self._log.append_warn(text)
        return False

    def _handle_error(self, msg: dict) -> bool:
        exc = msg["exc"]
        if isinstance(exc, UnidentifiedImageError):
            self._log.append_error(T("log_error_unrecognised", name=msg["name"]))
        else:
            self._log.append_error(T("log_error_generic", name=msg["name"], err=str(exc)))
        return False

    def _handle_done(self, msg: dict) -> bool:
        ok = msg["success"]
        fail = msg["failure"]
        self._progress.configure(value=self._progress["maximum"])
        self._log.append_sep()
        self._log.append_info(T("log_summary", ok=ok, fail=fail))
        self._status.configure(text=T("status_done", ok=ok, fail=fail))
        self._on_complete(ok, fail)
        return True

    def _handle_cancelled(self, msg: dict) -> bool:
        self._log.append_warn(T("status_cancelled"))
        self._status.configure(text=T("status_cancelled"))
        self._on_cancel()
        return True

    # Dispatch table
    _DISPATCH: dict[str, Callable[[MessageHandler, dict], bool]] = {
        "progress": _handle_progress,
        "result": _handle_result,
        "error": _handle_error,
        "done": _handle_done,
        "cancelled": _handle_cancelled,
    }
