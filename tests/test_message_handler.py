"""Tests for src.workers.message_handler – uses mock UI widgets."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pytest

from src.core.utils import format_eta
from src.workers.message_handler import MessageHandler


# ---------------------------------------------------------------------------
# Mock widgets (satisfy Protocol interfaces)
# ---------------------------------------------------------------------------


class MockLog:
    """Mock LogPanel that records calls."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []  # (method, message)
        self.cleared = False

    def append_ok(self, message: str) -> None:
        self.entries.append(("ok", message))

    def append_warn(self, message: str) -> None:
        self.entries.append(("warn", message))

    def append_error(self, message: str) -> None:
        self.entries.append(("error", message))

    def append_info(self, message: str) -> None:
        self.entries.append(("info", message))

    def append_sep(self) -> None:
        self.entries.append(("sep", ""))

    def clear(self) -> None:
        self.entries.clear()
        self.cleared = True


class MockProgress:
    """Mock Progressbar."""

    def __init__(self, maximum: int = 100) -> None:
        self.value: int = 0
        self._maximum = maximum

    def configure(self, **kw: object) -> None:
        if "value" in kw:
            self.value = kw["value"]  # type: ignore[assignment]

    def __getitem__(self, key: str) -> object:
        if key == "maximum":
            return self._maximum
        raise KeyError(key)


class MockStatus:
    """Mock status label."""

    def __init__(self) -> None:
        self.text: str = ""

    def configure(self, **kw: object) -> None:
        if "text" in kw:
            self.text = str(kw["text"])


@dataclass
class FakeResult:
    actual_size: int = 30_000
    format_name: str = "JPEG"
    quality_text: str = "quality=80"
    resized: bool = False
    scale: float = 1.0
    output_extension: str = ".jpg"
    warning: str | None = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler_parts():
    """Return (handler, log, progress, status, complete_args, cancel_called)."""
    log = MockLog()
    progress = MockProgress(maximum=5)
    status = MockStatus()
    complete_calls: list[tuple[int, int]] = []
    cancel_calls: list[bool] = []

    handler = MessageHandler(
        log=log,
        progress=progress,
        status=status,
        target_bytes=50_000,
        start_time=time.time() - 10.0,  # pretend started 10s ago
        on_complete=lambda ok, fail: complete_calls.append((ok, fail)),
        on_cancel=lambda: cancel_calls.append(True),
    )
    return handler, log, progress, status, complete_calls, cancel_calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressMessage:
    def test_updates_progress_and_status(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {"type": "progress", "index": 3, "total": 5, "name": "photo.jpg"}

        result = handler.handle(msg)

        assert result is False  # not terminal
        assert progress.value == 2  # index - 1
        assert "3/5" in status.text
        assert "photo.jpg" in status.text


class TestResultMessage:
    def test_target_met_logged_as_ok(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {
            "type": "result",
            "name": "photo.jpg",
            "output_path": "/out/photo_compressed.jpg",
            "original_size": 100_000,
            "result": FakeResult(actual_size=30_000),
        }

        result = handler.handle(msg)

        assert result is False
        assert len(log.entries) == 1
        assert log.entries[0][0] == "ok"
        assert "photo.jpg" in log.entries[0][1]

    def test_target_exceeded_logged_as_warn(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {
            "type": "result",
            "name": "huge.jpg",
            "output_path": "/out/huge_compressed.jpg",
            "original_size": 100_000,
            "result": FakeResult(actual_size=60_000),  # > target 50_000
        }

        result = handler.handle(msg)

        assert result is False
        assert len(log.entries) == 1
        assert log.entries[0][0] == "warn"

    def test_engine_name_in_message(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {
            "type": "result",
            "name": "photo.jpg",
            "output_path": "/out/photo_compressed.jpg",
            "original_size": 100_000,
            "result": FakeResult(actual_size=30_000),
            "engine_name": "vips",
        }

        handler.handle(msg)

        # Engine name is processed without error (logged internally)
        assert len(log.entries) == 1


class TestErrorMessage:
    def test_unrecognised_image_error(self, handler_parts):
        from PIL import UnidentifiedImageError

        handler, log, progress, status, _, _ = handler_parts
        msg = {
            "type": "error",
            "name": "bad_file.txt",
            "exc": UnidentifiedImageError("not an image"),
        }

        result = handler.handle(msg)

        assert result is False
        assert len(log.entries) == 1
        assert log.entries[0][0] == "error"
        assert "bad_file.txt" in log.entries[0][1]

    def test_generic_error(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {
            "type": "error",
            "name": "broken.jpg",
            "exc": RuntimeError("disk full"),
        }

        result = handler.handle(msg)

        assert result is False
        assert log.entries[0][0] == "error"
        assert "disk full" in log.entries[0][1]


class TestDoneMessage:
    def test_returns_true_and_calls_on_complete(self, handler_parts):
        handler, log, progress, status, complete_calls, _ = handler_parts
        msg = {"type": "done", "success": 4, "failure": 1}

        result = handler.handle(msg)

        assert result is True
        assert len(complete_calls) == 1
        assert complete_calls[0] == (4, 1)
        # Progress should be set to maximum
        assert progress.value == progress._maximum
        # Summary logged
        assert any(tag == "info" for tag, _ in log.entries)


class TestCancelledMessage:
    def test_returns_true_and_calls_on_cancel(self, handler_parts):
        handler, log, progress, status, _, cancel_calls = handler_parts
        msg = {"type": "cancelled"}

        result = handler.handle(msg)

        assert result is True
        assert len(cancel_calls) == 1
        assert any(tag == "warn" for tag, _ in log.entries)


class TestUnknownMessage:
    def test_unknown_type_returns_false(self, handler_parts):
        handler, log, progress, status, _, _ = handler_parts
        msg = {"type": "unknown_future_type"}

        result = handler.handle(msg)

        assert result is False
        assert len(log.entries) == 0


# ---------------------------------------------------------------------------
# format_eta tests
# ---------------------------------------------------------------------------


class TestFormatEta:
    def test_returns_empty_when_no_data(self):
        assert format_eta(0, 0, 0) == ""
        assert format_eta(0, 1, 5) == ""
        assert format_eta(5, 0, 5) == ""
        assert format_eta(5, 1, 0) == ""

    def test_returns_formatted_string(self):
        # 10 seconds elapsed, 5 of 10 done → speed=0.5/s, 10s remaining
        result = format_eta(10.0, 5, 10)
        assert "0.5" in result  # speed
        assert "10.0" in result  # remaining seconds

    def test_returns_string_starting_with_space(self):
        result = format_eta(2.0, 1, 5)
        assert result.startswith(" ")
