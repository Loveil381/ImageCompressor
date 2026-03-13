"""Tests for the Watch Worker."""

import queue
import time
from pathlib import Path

from src.workers.watch_worker import WatchWorker


def test_watch_worker_detects_new_image(tmp_path: Path, monkeypatch) -> None:
    # Disable the sleep to speed up the test
    monkeypatch.setattr("src.workers.watch_worker.time.sleep", lambda x: None)

    found_files = queue.Queue()

    def on_found(path: str) -> None:
        found_files.put(path)

    worker = WatchWorker(on_image_found=on_found)
    test_dir = tmp_path / "watch_dir"
    test_dir.mkdir()

    worker.start([str(test_dir)], recursive=False)
    assert worker.is_running()

    try:
        # Create a valid image file
        test_img = test_dir / "test.jpg"
        test_img.touch()
        test_img.write_bytes(b"dummy")

        # Create an invalid file
        test_txt = test_dir / "test.txt"
        test_txt.touch()

        # Create a file that looks like it was already compressed
        test_compressed = test_dir / "test_compressed.png"
        test_compressed.touch()
        test_compressed.write_bytes(b"dummy")

        # Wait for the filesystem event to be observed without relying on a fixed sleep.
        deadline = time.time() + 2.0
        while found_files.empty() and time.time() < deadline:
            time.sleep(0.05)

        # Retrieve all events
        paths = []
        while not found_files.empty():
            paths.append(found_files.get_nowait())

        assert len(paths) == 1
        assert "test.jpg" in paths[0]
        assert "test.txt" not in paths[0]
        assert "test_compressed.png" not in paths[0]

    finally:
        worker.stop()
        assert not worker.is_running()
