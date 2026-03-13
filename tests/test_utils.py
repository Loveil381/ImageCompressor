"""Tests for src.core.utils"""

from __future__ import annotations

import pytest

from src.core.utils import (
    CUSTOM_OUTPUT,
    ORIGINAL_FORMAT,
    format_bytes,
    format_scale,
    parse_size,
    resolve_output_extension,
)


# ---------------------------------------------------------------------------
# parse_size
# ---------------------------------------------------------------------------


class TestParseSize:
    def test_kilobytes(self) -> None:
        assert parse_size("500KB") == 512_000

    def test_megabytes(self) -> None:
        assert parse_size("1MB") == 1_048_576

    def test_megabytes_fractional(self) -> None:
        assert parse_size("1.5MB") == 1_572_864

    def test_gigabytes(self) -> None:
        assert parse_size("1GB") == 1_073_741_824

    def test_bytes_no_unit(self) -> None:
        assert parse_size("800000") == 800_000

    def test_bytes_explicit(self) -> None:
        assert parse_size("1024B") == 1024

    def test_lowercase(self) -> None:
        assert parse_size("500kb") == 512_000

    def test_with_spaces(self) -> None:
        assert parse_size(" 500 KB ") == 512_000

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_size("notasize")

    def test_invalid_unit_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_size("500TB")


# ---------------------------------------------------------------------------
# format_bytes
# ---------------------------------------------------------------------------


class TestFormatBytes:
    def test_bytes(self) -> None:
        assert format_bytes(512) == "512 B"

    def test_kilobytes(self) -> None:
        assert format_bytes(1024) == "1.0 KB"

    def test_megabytes(self) -> None:
        assert "MB" in format_bytes(1024 * 1024)

    def test_gigabytes(self) -> None:
        assert "GB" in format_bytes(1024 ** 3)


# ---------------------------------------------------------------------------
# format_scale
# ---------------------------------------------------------------------------


class TestFormatScale:
    def test_full_scale(self) -> None:
        assert format_scale(1.0) == "100%"

    def test_half_scale(self) -> None:
        assert format_scale(0.5) == "50%"

    def test_decimal_scale(self) -> None:
        assert format_scale(0.75) == "75%"


# ---------------------------------------------------------------------------
# resolve_output_extension
# ---------------------------------------------------------------------------


class TestResolveOutputExtension:
    def test_explicit_jpg(self) -> None:
        ext, warn = resolve_output_extension("photo.png", ".jpg")
        assert ext == ".jpg"
        assert warn is None

    def test_original_jpg(self) -> None:
        ext, warn = resolve_output_extension("photo.jpg", ORIGINAL_FORMAT)
        assert ext == ".jpg"
        assert warn is None

    def test_original_jpeg(self) -> None:
        ext, warn = resolve_output_extension("img.jpeg", ORIGINAL_FORMAT)
        assert ext == ".jpeg"
        assert warn is None

    def test_original_webp(self) -> None:
        ext, warn = resolve_output_extension("img.webp", ORIGINAL_FORMAT)
        assert ext == ".webp"
        assert warn is None

    def test_original_bmp_fallback(self) -> None:
        ext, warn = resolve_output_extension("img.bmp", ORIGINAL_FORMAT)
        assert ext == ".png"
        assert warn is not None

    def test_original_gif_fallback(self) -> None:
        ext, warn = resolve_output_extension("img.gif", ORIGINAL_FORMAT)
        assert ext == ".png"
        assert warn is not None

    def test_original_tiff_fallback(self) -> None:
        ext, warn = resolve_output_extension("img.tiff", ORIGINAL_FORMAT)
        assert ext == ".png"
        assert warn is not None

    def test_original_no_extension_fallback(self) -> None:
        ext, warn = resolve_output_extension("imagefile", ORIGINAL_FORMAT)
        assert ext == ".jpg"
        assert warn is not None
