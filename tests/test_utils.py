"""Tests for src.core.utils"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.utils import (
    CUSTOM_OUTPUT,
    ORIGINAL_FORMAT,
    build_output_path,
    enable_high_dpi_awareness,
    format_bytes,
    format_eta,
    format_scale,
    get_file_size,
    get_window_dpi,
    parse_size,
    resolve_output_extension,
    sanitize_filename,
)


# ---------------------------------------------------------------------------
# parse_size
# ---------------------------------------------------------------------------


class TestParseSize:
    def test_zero_kilobytes(self) -> None:
        assert parse_size("0KB") == 0

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
    def test_zero_bytes(self) -> None:
        assert format_bytes(0) == "0 B"

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
# format_eta
# ---------------------------------------------------------------------------


class TestFormatEta:
    def test_returns_empty_when_not_enough_progress(self) -> None:
        assert format_eta(0, 1, 5) == ""
        assert format_eta(5, 0, 5) == ""
        assert format_eta(5, 1, 0) == ""

    def test_returns_estimated_speed_and_remaining_time(self) -> None:
        result = format_eta(10.0, 5, 10)
        assert "0.5" in result
        assert "10.0" in result


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


# ---------------------------------------------------------------------------
# build_output_path / sanitize_filename
# ---------------------------------------------------------------------------


class TestOutputPathHelpers:
    def test_sanitize_filename_replaces_separators(self) -> None:
        assert sanitize_filename(r"..\..\folder/name") == "__folder_name"

    def test_build_output_path_uses_custom_output_directory(self, tmp_path: Path) -> None:
        src = tmp_path / "photo.jpg"
        src.write_bytes(b"data")
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        output_path = build_output_path(str(src), ".jpg", CUSTOM_OUTPUT, str(out_dir))

        assert Path(output_path).parent == out_dir.resolve()
        assert Path(output_path).name == "photo_compressed.jpg"

    def test_build_output_path_rejects_traversal_stem(self, tmp_path: Path) -> None:
        src = tmp_path / "unsafe..name.jpg"
        src.write_bytes(b"data")

        with pytest.raises(ValueError, match="Output path escapes target directory"):
            build_output_path(str(src), ".jpg", CUSTOM_OUTPUT, str(tmp_path))


class TestFileAndDpiHelpers:
    def test_get_file_size_returns_none_for_missing_file(self) -> None:
        assert get_file_size("missing-file.jpg") is None

    def test_enable_high_dpi_awareness_noops_on_non_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.utils.os.name", "posix")
        enable_high_dpi_awareness()

    def test_get_window_dpi_returns_default_on_non_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.utils.os.name", "posix")
        assert get_window_dpi(object()) == 96.0
