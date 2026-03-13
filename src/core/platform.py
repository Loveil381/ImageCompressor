"""Cross-platform helpers for opening files and directories."""

from __future__ import annotations

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def open_file(path: str) -> None:
    """Open *path* with the platform default application."""
    _open_path(path)


def open_directory(path: str) -> None:
    """Open *path* in the platform file manager."""
    _open_path(path)


def _open_path(path: str) -> None:
    if sys.platform.startswith("win"):
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except (AttributeError, OSError) as exc:
            logger.warning("Failed to open path on Windows: %s", exc)
        return

    command = _platform_command()
    if command is None:
        logger.warning("Unsupported platform for opening path: %s", sys.platform)
        return

    try:
        subprocess.run([command, path], check=False)
    except FileNotFoundError:
        logger.warning("Open command not found: %s", command)
    except OSError as exc:
        logger.warning("Failed to open path with %s: %s", command, exc)


def _platform_command() -> str | None:
    if sys.platform == "darwin":
        return "open"
    if sys.platform.startswith("linux"):
        return "xdg-open"
    return None
