"""Tests for the CLI entrypoint."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        cwd=str(cwd or REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def _create_image(
    path: Path,
    size: tuple[int, int] = (640, 480),
    color: tuple[int, int, int] = (80, 120, 180),
) -> None:
    Image.new("RGB", size, color).save(path)


class TestCliEntrypoint:
    def test_single_file_compression_returns_zero(self, tmp_path: Path) -> None:
        src = tmp_path / "input.jpg"
        _create_image(src)

        result = _run_cli(str(src), "-s", "500KB")

        assert result.returncode == 0
        assert (tmp_path / "input_compressed.jpg").exists()
        assert "Summary: 1 succeeded, 0 failed" in result.stdout

    def test_recursive_directory_output_dir_uses_requested_format(self, tmp_path: Path) -> None:
        photos = tmp_path / "photos"
        nested = photos / "nested"
        nested.mkdir(parents=True)
        _create_image(photos / "one.jpg")
        _create_image(nested / "two.png")
        output_dir = tmp_path / "compressed"

        result = _run_cli(str(photos), "-s", "1MB", "-r", "-f", "webp", "-o", str(output_dir))

        assert result.returncode == 0
        assert (output_dir / "one_compressed.webp").exists()
        assert (output_dir / "nested" / "two_compressed.webp").exists()

    def test_json_output_is_valid_json(self, tmp_path: Path) -> None:
        src = tmp_path / "input.jpg"
        _create_image(src)

        result = _run_cli(str(src), "-s", "500KB", "--json")

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["success"] == 1
        assert payload["failure"] == 0
        assert payload["results"][0]["success"] is True

    def test_partial_failure_returns_one(self, tmp_path: Path) -> None:
        ok_file = tmp_path / "ok.jpg"
        bad_file = tmp_path / "bad.jpg"
        _create_image(ok_file)
        bad_file.write_bytes(b"not a real image")

        result = _run_cli(str(ok_file), str(bad_file), "-s", "500KB", "-q")

        assert result.returncode == 1
        assert "Summary: 1 succeeded, 1 failed" in result.stdout
        assert "ERROR" in result.stderr

    def test_missing_required_target_size_returns_two(self, tmp_path: Path) -> None:
        src = tmp_path / "input.jpg"
        _create_image(src)

        result = _run_cli(str(src))

        assert result.returncode == 2

    def test_cli_import_does_not_pull_tkinter(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "import src.cli; "
                    "raise SystemExit(0 if 'tkinter' not in sys.modules and 'ttkbootstrap' not in sys.modules else 1)"
                ),
            ],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0
