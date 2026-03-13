"""Tests for src.core.models (dataclasses)."""

from __future__ import annotations

from src.core.models import BatchResult, CompressionConfig, CompressionResult, CompressionTask


class TestCompressionTask:
    def test_src_name(self) -> None:
        task = CompressionTask(
            src_path="/some/dir/photo.jpg",
            target_bytes=500_000,
            output_path="",
        )
        assert task.src_name == "photo.jpg"


class TestCompressionResult:
    def test_default_warning_is_none(self) -> None:
        r = CompressionResult(
            actual_size=100,
            format_name="JPEG",
            quality_text="quality=80",
            resized=False,
            scale=1.0,
            output_extension=".jpg",
        )
        assert r.warning is None


class TestBatchResult:
    def test_total(self) -> None:
        b = BatchResult(success_count=3, failure_count=1)
        assert b.total == 4

    def test_empty(self) -> None:
        b = BatchResult()
        assert b.total == 0
        assert b.results == []
