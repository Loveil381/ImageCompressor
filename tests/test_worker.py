"""Tests for src.workers.compress_worker."""

from __future__ import annotations

import queue
import time
from pathlib import Path

from PIL import Image

from src.core.models import CompressionTask
from src.workers.compress_worker import CompressWorker


def _make_image(path: Path, size: tuple[int, int] = (800, 600), color: tuple[int, int, int] = (120, 180, 230)) -> str:
    image = Image.new("RGB", size, color)
    image.save(path, format="JPEG", quality=95)
    return str(path)


def _make_noise_image(path: Path, size: tuple[int, int] = (1800, 1800)) -> str:
    image = Image.effect_noise(size, 120).convert("RGB")
    image.save(path, format="JPEG", quality=95)
    return str(path)


def _collect_messages(worker: CompressWorker, timeout: float = 10.0) -> list[dict]:
    messages: list[dict] = []
    deadline = time.time() + timeout

    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        try:
            msg = worker.result_queue.get(timeout=remaining)
        except queue.Empty as exc:
            raise AssertionError("Timed out waiting for worker messages") from exc

        messages.append(msg)
        if msg["type"] in {"done", "cancelled"}:
            break

    if worker._thread is not None:
        worker._thread.join(timeout=timeout)
    return messages


class TestCompressWorker:
    def test_normal_flow_emits_progress_result_pairs_then_done(self, tmp_path: Path) -> None:
        worker = CompressWorker()
        tasks = [
            CompressionTask(_make_image(tmp_path / f"image_{idx}.jpg"), 60_000, "")
            for idx in range(3)
        ]

        worker.start(
            tasks=tasks,
            fmt_choice=".jpg",
            output_mode="same_dir",
            custom_dir="",
            strip_exif=False,
        )

        messages = _collect_messages(worker)
        assert [msg["type"] for msg in messages] == [
            "progress",
            "result",
            "progress",
            "result",
            "progress",
            "result",
            "done",
        ]

        done = messages[-1]
        assert done["success"] == 3
        assert done["failure"] == 0

        result_messages = [msg for msg in messages if msg["type"] == "result"]
        assert len(result_messages) == 3
        assert all(msg["engine_name"] in {"pillow", "vips"} for msg in result_messages)

    def test_cancel_emits_cancelled_message(self, tmp_path: Path) -> None:
        worker = CompressWorker()
        tasks = [
            CompressionTask(_make_noise_image(tmp_path / f"large_{idx}.jpg"), 40_000, "")
            for idx in range(6)
        ]

        worker.start(
            tasks=tasks,
            fmt_choice=".jpg",
            output_mode="same_dir",
            custom_dir="",
            strip_exif=False,
        )
        worker.cancel()

        messages = _collect_messages(worker, timeout=15.0)
        message_types = [msg["type"] for msg in messages]

        assert "cancelled" in message_types
        assert "done" not in message_types

    def test_single_file_error_does_not_stop_following_tasks(self, tmp_path: Path) -> None:
        worker = CompressWorker()
        missing = str(tmp_path / "missing.jpg")
        valid = _make_image(tmp_path / "valid.jpg")
        tasks = [
            CompressionTask(missing, 50_000, ""),
            CompressionTask(valid, 50_000, ""),
        ]

        worker.start(
            tasks=tasks,
            fmt_choice=".jpg",
            output_mode="same_dir",
            custom_dir="",
            strip_exif=False,
        )

        messages = _collect_messages(worker)
        message_types = [msg["type"] for msg in messages]

        assert message_types == ["progress", "error", "progress", "result", "done"]
        done = messages[-1]
        assert done["success"] == 1
        assert done["failure"] == 1
