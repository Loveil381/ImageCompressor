"""pyvips-based compression engine – preferred when pyvips is installed.

pyvips wraps the libvips C library and processes images via streaming
pipelines, avoiding full in-memory copies.  This yields 3–5× faster
encode and ~10× lower memory than Pillow for resize+encode workloads.

References
----------
- https://github.com/libvips/libvips/wiki/Speed-and-memory-use
- Crushee (sharp / libvips for Node.js) uses very similar parameters.
"""

from __future__ import annotations

from contextlib import suppress
from typing import cast

import pyvips  # will raise ImportError if not installed

from .base import CompressionEngine


class VipsEngine(CompressionEngine):
    """Compression engine backed by pyvips (libvips)."""

    @property
    def name(self) -> str:
        return "vips"

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
        image = self._load(image_path, strip_exif=strip_exif)
        image = self._prepare_for_lossy(image, save_format)
        image = self._resize(image, scale)

        if save_format == "JPEG":
            return cast(
                bytes,
                image.jpegsave_buffer(
                    Q=quality,
                    optimize_coding=True,
                    interlace=True,
                    strip=strip_exif,
                ),
            )
        if save_format == "WEBP":
            return cast(
                bytes,
                image.webpsave_buffer(
                    Q=quality,
                    effort=6,
                    strip=strip_exif,
                ),
            )
        raise ValueError(f"不支持的有损格式：{save_format}")

    def encode_png(
        self,
        image_path: str,
        scale: float,
        colors: int | None,
        *,
        strip_exif: bool = False,
    ) -> bytes:
        image = self._load(image_path, strip_exif=strip_exif)
        image = self._resize(image, scale)

        if colors is not None:
            return cast(
                bytes,
                image.pngsave_buffer(
                    compression=9,
                    effort=10,
                    palette=True,
                    colours=colors,
                    strip=strip_exif,
                ),
            )
        return cast(
            bytes,
            image.pngsave_buffer(
                compression=9,
                effort=10,
                strip=strip_exif,
            ),
        )

    def get_image_size(self, image_path: str) -> tuple[int, int]:
        image = pyvips.Image.new_from_file(image_path, access="sequential")
        return (image.width, image.height)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(image_path: str, *, strip_exif: bool) -> pyvips.Image:
        """Load image and optionally strip EXIF metadata."""
        image = pyvips.Image.new_from_file(image_path, access="random")

        # Auto-rotate according to EXIF orientation, then drop orientation tag
        image = image.autorot()

        if strip_exif:
            # Remove all metadata fields; pyvips mutate API
            image = image.copy()
            fields_to_remove = []
            for field in image.get_fields():
                if field.startswith("exif-") or field in (
                    "xmp-data",
                    "iptc-data",
                ):
                    fields_to_remove.append(field)
            for field in fields_to_remove:
                with suppress(pyvips.Error):
                    image = image.mutate(lambda m, f=field: m.remove(f))

        return image

    @staticmethod
    def _prepare_for_lossy(image: pyvips.Image, save_format: str) -> pyvips.Image:
        """Convert to sRGB and flatten alpha for JPEG."""
        # Ensure sRGB colourspace
        if image.interpretation != "srgb":
            image = image.colourspace("srgb")

        # Flatten RGBA → RGB with white background for JPEG
        if save_format == "JPEG" and image.hasalpha():
            image = image.flatten(background=[255, 255, 255])

        return image

    @staticmethod
    def _resize(image: pyvips.Image, scale: float) -> pyvips.Image:
        if scale >= 0.999:
            return image
        return image.resize(scale, kernel="lanczos3")
