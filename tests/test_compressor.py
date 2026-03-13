"""Tests for src.core.compressor – uses in-memory synthetic images."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.core.compressor import compress_image
from src.core.utils import format_bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(
    width: int = 800,
    height: int = 600,
    mode: str = "RGB",
    color: tuple = (120, 180, 230),
) -> Image.Image:
    """Return a solid-colour PIL Image for testing."""
    return Image.new(mode, (width, height), color)


def _save_test_image(tmp_path: Path, filename: str, image: Image.Image) -> str:
    """Save *image* to *tmp_path/filename* and return the absolute path."""
    p = tmp_path / filename
    image.save(str(p))
    return str(p)


# ---------------------------------------------------------------------------
# JPEG compression
# ---------------------------------------------------------------------------


class TestJpegCompression:
    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(1200, 900)
        src = _save_test_image(tmp_path, "test.jpg", img)
        out = str(tmp_path / "out.jpg")
        target = 50_000  # 50 KB

        result = compress_image(src, target, out)

        assert result.actual_size <= target, (
            f"Output {format_bytes(result.actual_size)} exceeded target {format_bytes(target)}"
        )
        assert Path(out).exists()
        assert result.format_name == "JPEG"

    def test_small_image_not_unnecessarily_degraded(self, tmp_path: Path) -> None:
        # A tiny image should already be < 500 KB, quality should stay high
        img = _make_test_image(100, 100)
        src = _save_test_image(tmp_path, "small.jpg", img)
        out = str(tmp_path / "small_out.jpg")
        target = 500_000  # 500 KB

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        # Should use high quality since it fits easily
        assert "95" in result.quality_text

    def test_rgba_input_converted_to_rgb_for_jpeg(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300, mode="RGBA", color=(0, 128, 255, 200))
        src = _save_test_image(tmp_path, "rgba.png", img)
        out = str(tmp_path / "rgba_out.jpg")

        result = compress_image(src, 100_000, out)

        assert Path(out).exists()
        with Image.open(out) as saved:
            assert saved.mode == "RGB"


# ---------------------------------------------------------------------------
# PNG compression
# ---------------------------------------------------------------------------


class TestPngCompression:
    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(800, 600)
        src = _save_test_image(tmp_path, "test.png", img)
        out = str(tmp_path / "out.png")
        target = 30_000  # 30 KB – forces quantization

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        assert Path(out).exists()
        assert result.format_name == "PNG"

    def test_png_with_alpha(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300, mode="RGBA", color=(100, 150, 200, 128))
        src = _save_test_image(tmp_path, "alpha.png", img)
        out = str(tmp_path / "alpha_out.png")

        result = compress_image(src, 200_000, out)

        assert Path(out).exists()
        assert result.format_name == "PNG"


# ---------------------------------------------------------------------------
# WebP compression
# ---------------------------------------------------------------------------


class TestWebpCompression:
    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(800, 600)
        src = _save_test_image(tmp_path, "test.jpg", img)
        out = str(tmp_path / "out.webp")
        target = 40_000

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        assert result.format_name == "WEBP"


# ---------------------------------------------------------------------------
# EXIF strip
# ---------------------------------------------------------------------------


class TestExifStrip:
    def test_strip_exif_produces_valid_output(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300)
        src = _save_test_image(tmp_path, "exif.jpg", img)
        out = str(tmp_path / "exif_out.jpg")

        result = compress_image(src, 200_000, out, strip_exif=True)

        assert Path(out).exists()
        assert result.actual_size > 0


# ---------------------------------------------------------------------------
# Format fallback (BMP → PNG)
# ---------------------------------------------------------------------------


class TestFormatFallback:
    def test_bmp_written_as_png(self, tmp_path: Path) -> None:
        img = _make_test_image(200, 150, mode="RGB")
        src = _save_test_image(tmp_path, "test.bmp", img)
        # Output extension is .png (as resolved by utils.resolve_output_extension)
        out = str(tmp_path / "test_compressed.png")

        result = compress_image(src, 500_000, out)

        assert Path(out).exists()
        assert result.format_name == "PNG"
