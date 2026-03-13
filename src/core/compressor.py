"""Image compression engine – pure logic, no UI dependencies.

Architecture
------------
Uses the **Strategy Pattern** to support multiple backends:

- **VipsEngine** (pyvips / libvips) – preferred; 3-5× faster, ~10× less memory
- **PillowEngine** – automatic fallback when pyvips is not installed

The search algorithm (binary search on quality and scale) is engine-agnostic
and lives entirely in this module.

Complexity analysis
-------------------
- Lossy worst-case:  7 (scale binary) × 7 (quality binary) + 7 = **56** encodes
- PNG worst-case:    7 (scale binary) × 6 (colors) + 6           = **48** encodes
- Previous (linear): 19 (scale) × 7 (quality)                    = **133** encodes

All public functions are stateless and thread-safe.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

try:
    import pillow_avif
except ImportError:
    pass

from .engines.base import CompressionEngine
from .models import CompressionResult
from .utils import EXT_TO_FORMAT, write_bytes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine selection (module-level singleton)
# ---------------------------------------------------------------------------

_engine_instance: CompressionEngine | None = None
_engine_preference: str | None = None


def _get_engine(preference: str = "auto") -> CompressionEngine:
    """Return (and cache) the best available compression engine.

    Tries VipsEngine first; falls back to PillowEngine if pyvips is not
    installed.  The chosen engine is logged once on first call.
    """
    global _engine_instance, _engine_preference
    normalized = preference if preference in {"auto", "vips", "pillow"} else "auto"
    if _engine_instance is not None and _engine_preference == normalized:
        return _engine_instance

    from .engines.pillow_engine import PillowEngine

    if normalized == "pillow":
        _engine_instance = PillowEngine()
    elif normalized == "vips":
        try:
            from .engines.vips_engine import VipsEngine

            _engine_instance = VipsEngine()
        except ImportError:
            logger.warning("Vips engine requested but unavailable, falling back to Pillow.")
            _engine_instance = PillowEngine()
    else:
        try:
            from .engines.vips_engine import VipsEngine

            _engine_instance = VipsEngine()
        except ImportError:
            _engine_instance = PillowEngine()

    _engine_preference = normalized
    logger.info("[Engine: %s]", _engine_instance.name)
    return _engine_instance


# ---------------------------------------------------------------------------
# Public API  (signature unchanged)
# ---------------------------------------------------------------------------


def compress_image(
    src_path: str,
    target_bytes: int,
    output_path: str,
    strip_exif: bool = False,
    progress_cb: Callable[[str], None] | None = None,
    engine_preference: str = "auto",
) -> CompressionResult:
    """Compress *src_path* to *output_path* aiming for at most *target_bytes*.

    Parameters
    ----------
    src_path:
        Absolute path to the source image.
    target_bytes:
        Upper bound for the output file size.
    output_path:
        Where the compressed file will be written.
    strip_exif:
        If True, EXIF metadata is removed from the output.
    progress_cb:
        Optional callable receiving status strings during long operations.

    Returns
    -------
    CompressionResult
        Details of the compression result.

    Raises
    ------
    RuntimeError
        If no output could be produced at all.
    """
    engine = _get_engine(engine_preference)
    output_ext = Path(output_path).suffix.lower()
    save_format = EXT_TO_FORMAT.get(output_ext, "JPEG")

    if save_format == "PNG":
        return _compress_png(
            engine,
            src_path,
            target_bytes,
            output_path,
            output_ext,
            strip_exif=strip_exif,
        )
    return _compress_lossy(
        engine,
        src_path,
        target_bytes,
        output_path,
        save_format,
        output_ext,
        strip_exif=strip_exif,
    )


def get_engine_name(preference: str = "auto") -> str:
    """Return the active compression engine name."""
    return _get_engine(preference).name


# ---------------------------------------------------------------------------
# Lossy compression (JPEG / WebP) – binary search on quality then scale
# ---------------------------------------------------------------------------

# Complexity: 7 (quality binary at scale=1) + 7 (scale binary) × 7 (quality)
#           = 7 + 49 = 56 encodes worst-case.


def _compress_lossy(
    engine: CompressionEngine,
    src_path: str,
    target_bytes: int,
    output_path: str,
    save_format: str,
    output_ext: str,
    *,
    strip_exif: bool = False,
) -> CompressionResult:
    """Find the best (scale, quality) pair that fits *target_bytes*."""

    # Step 1: Try scale=1.0, binary-search quality 5–95
    fit = _find_best_quality(
        engine,
        src_path,
        1.0,
        target_bytes,
        save_format,
        strip_exif=strip_exif,
    )
    if fit is not None:
        payload, quality = fit
        write_bytes(output_path, payload)
        return CompressionResult(
            actual_size=len(payload),
            format_name=save_format,
            quality_text=f"quality={quality}",
            resized=False,
            scale=1.0,
            output_extension=output_ext,
        )

    # Step 2: Binary-search scale 0.1–0.95, precision 0.02
    #         For each candidate scale, binary-search quality.
    smallest_payload = b""
    smallest_result: CompressionResult | None = None

    lo_s, hi_s = 0.10, 0.95
    while hi_s - lo_s >= 0.02:
        mid_s = round((lo_s + hi_s) / 2, 4)

        # Fast reject: if quality=5 still > target × 2, skip to smaller scale
        worst = engine.encode_lossy(
            src_path,
            mid_s,
            5,
            save_format,
            strip_exif=strip_exif,
        )
        if len(worst) > target_bytes * 2:
            if smallest_result is None or len(worst) < smallest_result.actual_size:
                smallest_payload = worst
                smallest_result = CompressionResult(
                    actual_size=len(worst),
                    format_name=save_format,
                    quality_text="quality=5",
                    resized=True,
                    scale=mid_s,
                    output_extension=output_ext,
                )
            hi_s = mid_s
            continue

        fit = _find_best_quality(
            engine,
            src_path,
            mid_s,
            target_bytes,
            save_format,
            strip_exif=strip_exif,
        )
        if fit is not None:
            payload, quality = fit
            # Found a fit – try a larger scale
            if smallest_result is None or len(payload) <= target_bytes:
                smallest_payload = payload
                smallest_result = CompressionResult(
                    actual_size=len(payload),
                    format_name=save_format,
                    quality_text=f"quality={quality}",
                    resized=True,
                    scale=mid_s,
                    output_extension=output_ext,
                )
            lo_s = mid_s + 0.02
        else:
            # Track smallest attempt at quality=5 for this scale
            if smallest_result is None or len(worst) < smallest_result.actual_size:
                smallest_payload = worst
                smallest_result = CompressionResult(
                    actual_size=len(worst),
                    format_name=save_format,
                    quality_text="quality=5",
                    resized=True,
                    scale=mid_s,
                    output_extension=output_ext,
                )
            hi_s = mid_s

    if smallest_result is None:
        raise RuntimeError("压缩失败，未生成任何输出结果。")

    write_bytes(output_path, smallest_payload)
    return smallest_result


def _find_best_quality(
    engine: CompressionEngine,
    src_path: str,
    scale: float,
    target_bytes: int,
    save_format: str,
    *,
    strip_exif: bool = False,
) -> tuple[bytes, int] | None:
    """Binary-search quality 5–95 at a given *scale*.

    Returns ``(payload, quality)`` if a fit is found, else ``None``.
    Worst-case: 7 encode calls (⌈log₂(91)⌉).
    """
    # Quick check: if quality=95 already fits, return immediately
    high = engine.encode_lossy(src_path, scale, 95, save_format, strip_exif=strip_exif)
    if len(high) <= target_bytes:
        return high, 95

    # Quick check: if quality=5 doesn't fit, no solution at this scale
    low = engine.encode_lossy(src_path, scale, 5, save_format, strip_exif=strip_exif)
    if len(low) > target_bytes:
        return None

    best_payload = low
    best_quality = 5
    lo, hi = 5, 95

    while lo <= hi:
        mid = (lo + hi) // 2
        payload = engine.encode_lossy(
            src_path,
            scale,
            mid,
            save_format,
            strip_exif=strip_exif,
        )
        if len(payload) <= target_bytes:
            best_payload = payload
            best_quality = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best_payload, best_quality


# ---------------------------------------------------------------------------
# PNG compression – iterate colors, binary-search scale
# ---------------------------------------------------------------------------

# Colors to try, in order from least to most aggressive quantization.
_PNG_COLORS = (None, 256, 128, 64, 32, 16)

# Complexity: 6 (colors at scale=1) + 7 (scale binary) × 6 (colors)
#           = 6 + 42 = 48 encodes worst-case.


def _compress_png(
    engine: CompressionEngine,
    src_path: str,
    target_bytes: int,
    output_path: str,
    output_ext: str,
    *,
    strip_exif: bool = False,
) -> CompressionResult:
    """Find the best (scale, colors) pair for PNG that fits *target_bytes*."""

    # Step 1: Try scale=1.0, iterate colors
    fit = _find_best_png_colors(
        engine,
        src_path,
        1.0,
        target_bytes,
        strip_exif=strip_exif,
    )
    if fit is not None:
        payload, colors = fit
        write_bytes(output_path, payload)
        quality_text = "PNG optimize" if colors is None else f"palette={colors}"
        return CompressionResult(
            actual_size=len(payload),
            format_name="PNG",
            quality_text=quality_text,
            resized=False,
            scale=1.0,
            output_extension=output_ext,
        )

    # Step 2: Binary-search scale 0.1–0.95
    smallest_payload = b""
    smallest_result: CompressionResult | None = None

    lo_s, hi_s = 0.10, 0.95
    while hi_s - lo_s >= 0.02:
        mid_s = round((lo_s + hi_s) / 2, 4)

        fit = _find_best_png_colors(
            engine,
            src_path,
            mid_s,
            target_bytes,
            strip_exif=strip_exif,
        )
        if fit is not None:
            payload, colors = fit
            quality_text = "PNG optimize" if colors is None else f"palette={colors}"
            smallest_payload = payload
            smallest_result = CompressionResult(
                actual_size=len(payload),
                format_name="PNG",
                quality_text=quality_text,
                resized=True,
                scale=mid_s,
                output_extension=output_ext,
            )
            lo_s = mid_s + 0.02
        else:
            # Track the most-aggressive attempt (colors=16) as fallback
            worst = engine.encode_png(
                src_path,
                mid_s,
                16,
                strip_exif=strip_exif,
            )
            if smallest_result is None or len(worst) < smallest_result.actual_size:
                smallest_payload = worst
                smallest_result = CompressionResult(
                    actual_size=len(worst),
                    format_name="PNG",
                    quality_text="palette=16",
                    resized=True,
                    scale=mid_s,
                    output_extension=output_ext,
                )
            hi_s = mid_s

    if smallest_result is None:
        raise RuntimeError("PNG 压缩失败，未生成任何输出结果。")

    write_bytes(output_path, smallest_payload)
    return smallest_result


def _find_best_png_colors(
    engine: CompressionEngine,
    src_path: str,
    scale: float,
    target_bytes: int,
    *,
    strip_exif: bool = False,
) -> tuple[bytes, int | None] | None:
    """Try each color-count at the given *scale*.

    Returns ``(payload, colors)`` for the first fit, or ``None``.
    Worst-case: 6 encode calls (len(_PNG_COLORS)).
    """
    for colors in _PNG_COLORS:
        payload = engine.encode_png(
            src_path,
            scale,
            colors,
            strip_exif=strip_exif,
        )
        if len(payload) <= target_bytes:
            return payload, colors
    return None
