"""Pillow-based compression engine – fallback when pyvips is unavailable.

This module wraps the original Pillow logic from ``compressor.py`` into the
``CompressionEngine`` interface.  The behaviour is identical to the legacy
implementation.
"""

from __future__ import annotations

import io
from functools import lru_cache

from PIL import Image, ImageOps

from .base import CompressionEngine

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

METADATA_KEYS = ("exif", "icc_profile", "xmp")


class PillowEngine(CompressionEngine):
    """Compression engine backed by Pillow."""

    # Cache the last opened image to avoid re-opening during binary search.
    _cache_path: str | None = None
    _cache_image: Image.Image | None = None

    @property
    def name(self) -> str:
        return "pillow"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode_lossy(
        self,
        image_path: str,
        scale: float,
        quality: int,
        save_format: str,
        *,
        strip_exif: bool = False,
    ) -> bytes:
        image = self._open_and_prepare(image_path, save_format, strip_exif=strip_exif)
        resized = self._resize(image, scale)
        return self._do_encode_lossy(resized, save_format, quality)

    def encode_png(
        self,
        image_path: str,
        scale: float,
        colors: int | None,
        *,
        strip_exif: bool = False,
    ) -> bytes:
        image = self._open_and_prepare(image_path, "PNG", strip_exif=strip_exif)
        resized = self._resize(image, scale)
        quantized = self._quantize(resized, colors)
        return self._do_encode_png(quantized)

    def get_image_size(self, image_path: str) -> tuple[int, int]:
        with Image.open(image_path) as img:
            return img.size

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_and_prepare(
        self, image_path: str, save_format: str, *, strip_exif: bool
    ) -> Image.Image:
        """Open, orient, and prepare *image_path* for *save_format*.

        Results are cached so repeated calls during one binary search loop
        do not re-read the file from disk.
        """
        cache_key = (image_path, save_format, strip_exif)
        if getattr(self, "_prep_cache_key", None) == cache_key:
            return self._prep_cache_image  # type: ignore[return-value]

        with Image.open(image_path) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()

        if strip_exif:
            image = self._strip_metadata(image)

        prepared = self._prepare_for_format(image, save_format)

        self._prep_cache_key = cache_key
        self._prep_cache_image = prepared
        return prepared

    def _prepare_for_format(
        self, image: Image.Image, save_format: str
    ) -> Image.Image:
        """Convert colour mode as required by *save_format*."""
        if save_format == "JPEG":
            if image.mode not in ("RGB", "L"):
                rgba = image.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                return self._copy_meta(image, bg)
            if image.mode == "L":
                return self._copy_meta(image, image.convert("RGB"))
            return self._copy_meta(image, image.copy())

        if save_format == "PNG":
            if image.mode in ("RGBA", "RGB", "L", "P"):
                return self._copy_meta(image, image.copy())
            if "A" in image.getbands():
                return self._copy_meta(image, image.convert("RGBA"))
            return self._copy_meta(image, image.convert("RGB"))

        # WEBP and others
        if image.mode in ("RGBA", "RGB", "L"):
            return self._copy_meta(image, image.copy())
        if "A" in image.getbands():
            return self._copy_meta(image, image.convert("RGBA"))
        return self._copy_meta(image, image.convert("RGB"))

    def _resize(self, image: Image.Image, scale: float) -> Image.Image:
        if scale >= 0.999:
            return self._copy_meta(image, image.copy())
        w, h = image.size
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        return self._copy_meta(image, image.resize(new_size, RESAMPLE_LANCZOS))

    @staticmethod
    def _do_encode_lossy(
        image: Image.Image, save_format: str, quality: int
    ) -> bytes:
        buf = io.BytesIO()
        kwargs: dict[str, object] = {"format": save_format}
        if save_format == "JPEG":
            kwargs.update({"quality": quality, "optimize": True, "progressive": True})
            kwargs.update(_metadata_kwargs(image, ("exif", "icc_profile")))
        elif save_format == "WEBP":
            kwargs.update({"quality": quality, "method": 6})
            kwargs.update(_metadata_kwargs(image, ("exif", "icc_profile", "xmp")))
        else:
            raise ValueError(f"不支持的有损格式：{save_format}")
        image.save(buf, **kwargs)
        return buf.getvalue()

    @staticmethod
    def _do_encode_png(image: Image.Image) -> bytes:
        buf = io.BytesIO()
        image.save(
            buf,
            format="PNG",
            optimize=True,
            compress_level=9,
            **_metadata_kwargs(image, ("exif", "icc_profile")),
        )
        return buf.getvalue()

    @staticmethod
    def _quantize(image: Image.Image, colors: int | None) -> Image.Image:
        if colors is None:
            return image
        rgba = image.convert("RGBA")
        kw: dict[str, object] = {"colors": colors, "dither": PNG_DITHER}
        if PNG_QUANTIZE_METHOD is not None:
            kw["method"] = PNG_QUANTIZE_METHOD
        return _copy_metadata(image, rgba.quantize(**kw))

    @staticmethod
    def _strip_metadata(image: Image.Image) -> Image.Image:
        stripped = image.copy()
        for key in METADATA_KEYS:
            stripped.info.pop(key, None)
        if hasattr(stripped, "_exif"):
            stripped._exif = None
        return stripped

    @staticmethod
    def _copy_meta(source: Image.Image, target: Image.Image) -> Image.Image:
        return _copy_metadata(source, target)


# ---------------------------------------------------------------------------
# Module-level helpers (shared between static methods)
# ---------------------------------------------------------------------------


def _copy_metadata(source: Image.Image, target: Image.Image) -> Image.Image:
    for key in METADATA_KEYS:
        value = source.info.get(key)
        if value is not None:
            target.info[key] = value
        else:
            target.info.pop(key, None)
    if hasattr(target, "_exif"):
        target._exif = getattr(source, "_exif", None)
    return target


def _metadata_kwargs(
    image: Image.Image,
    allowed_keys: tuple[str, ...],
) -> dict[str, object]:
    return {
        key: image.info[key]
        for key in allowed_keys
        if image.info.get(key) is not None
    }
