"""Pure utility functions – no UI dependencies."""

from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path
from typing import Any, cast

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXT_TO_FORMAT: dict[str, str] = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}

FALLBACK_EXTENSIONS: dict[str, str] = {
    ".bmp": ".png",
    ".gif": ".png",
    ".tif": ".png",
    ".tiff": ".png",
}

SUPPORTED_INPUT_TYPES = "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff"

ORIGINAL_FORMAT = "original"
CUSTOM_OUTPUT = "custom"


# ---------------------------------------------------------------------------
# Size helpers
# ---------------------------------------------------------------------------


def parse_size(size_str: str) -> int:
    """Parse values like '500KB', '1.5MB', '1048576' to bytes.

    Raises ValueError for unrecognised input.
    """
    normalized = size_str.strip().upper().replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(B|KB|MB|GB)?", normalized)
    if not match:
        raise ValueError(f"无效的目标大小：{size_str}")

    value = float(match.group(1))
    unit = match.group(2) or "B"
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return int(value * units[unit])


def format_bytes(size_in_bytes: int) -> str:
    """Return a human-readable string representation of a byte count."""
    if size_in_bytes >= 1024**3:
        return f"{size_in_bytes / 1024**3:.2f} GB"
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    if size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    return f"{size_in_bytes} B"


def format_scale(scale: float) -> str:
    """Return a percentage string for the given scale factor."""
    return f"{scale * 100:.0f}%"


def format_eta(elapsed: float, processed: int, total: int) -> str:
    """Return human-readable ETA string, or ``''`` if not enough data.

    Parameters
    ----------
    elapsed:
        Seconds since the batch started.
    processed:
        Number of items already completed.
    total:
        Total number of items in the batch.
    """
    if elapsed <= 0 or processed <= 0 or total <= 0:
        return ""
    speed = processed / elapsed
    remaining = (total - processed) / speed
    return f" ({speed:.1f} 文件/秒，预计剩余 {remaining:.1f}秒)"


# ---------------------------------------------------------------------------
# Extension / format resolution
# ---------------------------------------------------------------------------


def resolve_output_extension(src_path: str, fmt_choice: str) -> tuple[str, str | None]:
    """Return *(output_extension, warning_or_None)* for a given source path.

    If *fmt_choice* is ``ORIGINAL_FORMAT`` and the source format has no
    direct save support, a fallback extension is chosen and a warning is
    returned.
    """
    source_ext = Path(src_path).suffix.lower()
    if fmt_choice != ORIGINAL_FORMAT:
        return fmt_choice, None

    if source_ext in EXT_TO_FORMAT:
        return source_ext, None

    fallback_ext = FALLBACK_EXTENSIONS.get(source_ext, ".jpg")
    warning = f"原格式 {source_ext or '(无扩展名)'} 不支持直接输出，已自动改为 {fallback_ext}"
    return fallback_ext, warning


def build_output_path(
    src_path: str,
    output_ext: str,
    output_mode: str,
    custom_dir: str,
) -> str:
    """Build the full output file path from source and config."""
    src = Path(src_path)
    directory = custom_dir if output_mode == CUSTOM_OUTPUT else str(src.parent)
    target_dir = Path(directory).resolve()
    if ".." in src.stem:
        raise ValueError("Output path escapes target directory")
    safe_stem = sanitize_filename(src.stem)
    candidate = (target_dir / f"{safe_stem}_compressed{output_ext}").resolve()

    try:
        candidate.relative_to(target_dir)
    except ValueError as exc:
        raise ValueError("Output path escapes target directory") from exc

    return str(candidate)


def sanitize_filename(name: str) -> str:
    """Return *name* with traversal and separator characters neutralised."""
    sanitized = name.replace("..", "")
    sanitized = sanitized.replace("/", "_").replace("\\", "_").replace("\0", "_")
    return sanitized or "_"


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def write_bytes(output_path: str, payload: bytes) -> None:
    """Write *payload* to *output_path*, creating parent directories as needed."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        fh.write(payload)


def get_file_size(path: str) -> int | None:
    """Return the file size in bytes, or None if the file cannot be accessed."""
    try:
        return os.path.getsize(path)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Windows DPI helpers
# ---------------------------------------------------------------------------


def enable_high_dpi_awareness() -> None:
    """Opt into high-DPI rendering on Windows to avoid blurry/tiny Tk UI."""
    if os.name != "nt":
        return

    windll = cast(Any, ctypes.windll)
    for call in [
        lambda: windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)),
        lambda: windll.shcore.SetProcessDpiAwareness(2),
        lambda: windll.user32.SetProcessDPIAware(),
    ]:
        try:
            call()
            return
        except Exception:
            continue


def get_window_dpi(window: object) -> float:
    """Return the DPI of the monitor containing *window* (Windows only)."""
    if os.name != "nt":
        return 96.0
    try:
        import tkinter as tk

        assert isinstance(window, tk.Misc)
        windll = cast(Any, ctypes.windll)
        return float(windll.user32.GetDpiForWindow(window.winfo_id()))
    except Exception:
        return 96.0
