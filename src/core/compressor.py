"""Image compression engine – pure logic, no UI dependencies.

All public functions are stateless and thread-safe.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: F401

from .models import CompressionResult
from .utils import EXT_TO_FORMAT, write_bytes

# ---------------------------------------------------------------------------
# Pillow compatibility shims
# ---------------------------------------------------------------------------

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9
    RESAMPLE_LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]

try:
    PNG_QUANTIZE_METHOD = Image.Quantize.FASTOCTREE
except AttributeError:
    PNG_QUANTIZE_METHOD = None

try:
    PNG_DITHER = Image.Dither.NONE
except AttributeError:
    PNG_DITHER = Image.NONE  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compress_image(
    src_path: str,
    target_bytes: int,
    output_path: str,
    strip_exif: bool = False,
    progress_cb: Callable[[str], None] | None = None,
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
    PIL.UnidentifiedImageError
        If *src_path* is not a recognised image.
    RuntimeError
        If no output could be produced at all.
    """
    output_ext = Path(output_path).suffix.lower()
    save_format = EXT_TO_FORMAT.get(output_ext, "JPEG")

    with Image.open(src_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()

    if strip_exif:
        # Re-create without any info dict to drop ALL metadata
        stripped = Image.new(image.mode, image.size)
        stripped.putdata(list(image.getdata()))
        image = stripped

    if save_format == "PNG":
        return _compress_png(image, target_bytes, output_path, output_ext)
    return _compress_lossy(image, target_bytes, output_path, save_format, output_ext)


# ---------------------------------------------------------------------------
# Lossy compression (JPEG / WebP)
# ---------------------------------------------------------------------------


def _compress_lossy(
    image: Image.Image,
    target_bytes: int,
    output_path: str,
    save_format: str,
    output_ext: str,
) -> CompressionResult:
    prepared = _prepare_image_for_format(image, save_format)
    smallest_attempt: CompressionResult | None = None
    smallest_payload = b""

    for scale in _iter_scales():
        candidate = _resize_image(prepared, scale)
        fit_payload, fit_quality = _find_best_lossy_payload(
            candidate, target_bytes, save_format
        )
        if fit_payload is not None and fit_quality is not None:
            write_bytes(output_path, fit_payload)
            return CompressionResult(
                actual_size=len(fit_payload),
                format_name=save_format,
                quality_text=f"quality={fit_quality}",
                resized=scale < 0.999,
                scale=scale,
                output_extension=output_ext,
            )

        payload = _encode_lossy(candidate, save_format, quality=5)
        if smallest_attempt is None or len(payload) < smallest_attempt.actual_size:
            smallest_payload = payload
            smallest_attempt = CompressionResult(
                actual_size=len(payload),
                format_name=save_format,
                quality_text="quality=5",
                resized=scale < 0.999,
                scale=scale,
                output_extension=output_ext,
            )

    if smallest_attempt is None:
        raise RuntimeError("压缩失败，未生成任何输出结果。")

    write_bytes(output_path, smallest_payload)
    return smallest_attempt


def _find_best_lossy_payload(
    image: Image.Image,
    target_bytes: int,
    save_format: str,
) -> tuple[bytes | None, int | None]:
    high_payload = _encode_lossy(image, save_format, quality=95)
    if len(high_payload) <= target_bytes:
        return high_payload, 95

    low_payload = _encode_lossy(image, save_format, quality=5)
    if len(low_payload) > target_bytes:
        return None, None

    best_payload = low_payload
    best_quality = 5
    lo, hi = 5, 95

    while lo <= hi:
        mid = (lo + hi) // 2
        payload = _encode_lossy(image, save_format, quality=mid)
        if len(payload) <= target_bytes:
            best_payload = payload
            best_quality = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best_payload, best_quality


# ---------------------------------------------------------------------------
# PNG compression
# ---------------------------------------------------------------------------


def _compress_png(
    image: Image.Image,
    target_bytes: int,
    output_path: str,
    output_ext: str,
) -> CompressionResult:
    prepared = _prepare_image_for_format(image, "PNG")
    smallest_attempt: tuple[bytes, int, float] | None = None

    for scale in _iter_scales():
        scaled = _resize_image(prepared, scale)
        for colors in (None, 256, 128, 64, 32, 16):
            candidate = _quantize_png(scaled, colors)
            payload = _encode_png(candidate)
            size = len(payload)

            if size <= target_bytes:
                write_bytes(output_path, payload)
                quality_text = "PNG optimize" if colors is None else f"palette={colors}"
                return CompressionResult(
                    actual_size=size,
                    format_name="PNG",
                    quality_text=quality_text,
                    resized=scale < 0.999,
                    scale=scale,
                    output_extension=output_ext,
                )

            if smallest_attempt is None or size < smallest_attempt[1]:
                smallest_attempt = (payload, size, scale)

    if smallest_attempt is None:
        raise RuntimeError("PNG 压缩失败，未生成任何输出结果。")

    payload, size, scale = smallest_attempt
    write_bytes(output_path, payload)
    return CompressionResult(
        actual_size=size,
        format_name="PNG",
        quality_text="palette=16",
        resized=scale < 0.999,
        scale=scale,
        output_extension=output_ext,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _prepare_image_for_format(image: Image.Image, save_format: str) -> Image.Image:
    if save_format == "JPEG":
        if image.mode not in ("RGB", "L"):
            rgba = image.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            return bg
        return image.convert("RGB") if image.mode == "L" else image.copy()

    if save_format == "PNG":
        if image.mode in ("RGBA", "RGB", "L", "P"):
            return image.copy()
        if "A" in image.getbands():
            return image.convert("RGBA")
        return image.convert("RGB")

    # WEBP and others
    if image.mode in ("RGBA", "RGB", "L"):
        return image.copy()
    if "A" in image.getbands():
        return image.convert("RGBA")
    return image.convert("RGB")


def _iter_scales() -> list[float]:
    scales = [1.0]
    current = 0.95
    while current >= 0.1:
        scales.append(round(current, 2))
        current -= 0.05
    return scales


def _resize_image(image: Image.Image, scale: float) -> Image.Image:
    if scale >= 0.999:
        return image.copy()
    w, h = image.size
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(new_size, RESAMPLE_LANCZOS)


def _encode_lossy(image: Image.Image, save_format: str, quality: int) -> bytes:
    buf = io.BytesIO()
    kwargs: dict[str, object] = {"format": save_format}
    if save_format == "JPEG":
        kwargs.update({"quality": quality, "optimize": True, "progressive": True})
    elif save_format == "WEBP":
        kwargs.update({"quality": quality, "method": 6})
    else:
        raise ValueError(f"不支持的有损格式：{save_format}")
    image.save(buf, **kwargs)
    return buf.getvalue()


def _quantize_png(image: Image.Image, colors: int | None) -> Image.Image:
    if colors is None:
        return image
    rgba = image.convert("RGBA")
    kw: dict[str, object] = {"colors": colors, "dither": PNG_DITHER}
    if PNG_QUANTIZE_METHOD is not None:
        kw["method"] = PNG_QUANTIZE_METHOD
    return rgba.quantize(**kw)


def _encode_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True, compress_level=9)
    return buf.getvalue()
