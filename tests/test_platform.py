"""Tests for path sanitisation and platform helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.platform import open_directory, open_file
from src.core.utils import CUSTOM_OUTPUT, build_output_path, sanitize_filename


class TestSanitizeFilename:
    def test_removes_traversal_and_separators(self) -> None:
        assert sanitize_filename("../../../etc/passwd") == "___etc_passwd"


class TestBuildOutputPath:
    def test_rejects_source_stem_with_dot_dot(self, tmp_path: Path) -> None:
        src = tmp_path / "safe..name.jpg"
        src.write_bytes(b"test")

        with pytest.raises(ValueError, match="Output path escapes target directory"):
            build_output_path(str(src), ".jpg", CUSTOM_OUTPUT, str(tmp_path))

    def test_raises_when_resolved_output_escapes_target_directory(self, tmp_path: Path) -> None:
        src = tmp_path / "photo.jpg"
        src.write_bytes(b"test")

        original_resolve = Path.resolve

        def fake_resolve(path_obj: Path, *args, **kwargs) -> Path:
            if path_obj == tmp_path / "safe":
                return original_resolve(path_obj, *args, **kwargs)
            if path_obj == tmp_path / "safe" / "photo_compressed.jpg":
                return original_resolve(
                    tmp_path / "escaped" / "photo_compressed.jpg", *args, **kwargs
                )
            return original_resolve(path_obj, *args, **kwargs)

        with (
            patch("src.core.utils.Path.resolve", autospec=True, side_effect=fake_resolve),
            pytest.raises(ValueError, match="Output path escapes target directory"),
        ):
            build_output_path(str(src), ".jpg", CUSTOM_OUTPUT, str(tmp_path / "safe"))


class TestPlatformOpeners:
    def test_windows_uses_startfile(self) -> None:
        with (
            patch("src.core.platform.sys.platform", "win32"),
            patch("src.core.platform.os.startfile", create=True) as startfile_mock,
        ):
            open_file("C:/tmp/file.jpg")
        startfile_mock.assert_called_once_with("C:/tmp/file.jpg")

    def test_windows_startfile_failure_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch("src.core.platform.sys.platform", "win32"),
            patch("src.core.platform.os.startfile", create=True, side_effect=OSError("boom")),
            caplog.at_level(logging.WARNING),
        ):
            open_file("C:/tmp/file.jpg")
        assert "Failed to open path on Windows" in caplog.text

    def test_macos_uses_open(self) -> None:
        with (
            patch("src.core.platform.sys.platform", "darwin"),
            patch("src.core.platform.subprocess.run") as run_mock,
        ):
            open_directory("/tmp")
        run_mock.assert_called_once_with(["open", "/tmp"], check=False)

    def test_linux_uses_xdg_open(self) -> None:
        with (
            patch("src.core.platform.sys.platform", "linux"),
            patch("src.core.platform.subprocess.run") as run_mock,
        ):
            open_file("/tmp/file.jpg")
        run_mock.assert_called_once_with(["xdg-open", "/tmp/file.jpg"], check=False)

    def test_unknown_platform_logs_warning_without_raising(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            patch("src.core.platform.sys.platform", "plan9"),
            caplog.at_level(logging.WARNING),
        ):
            open_file("/tmp/file.jpg")
        assert "Unsupported platform" in caplog.text

    def test_missing_open_command_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch("src.core.platform.sys.platform", "linux"),
            patch("src.core.platform.subprocess.run", side_effect=FileNotFoundError),
            caplog.at_level(logging.WARNING),
        ):
            open_directory("/tmp")
        assert "Open command not found" in caplog.text
