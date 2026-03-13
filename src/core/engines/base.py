"""Abstract base class for compression engines.

Each engine implements resize + encode as an atomic operation, returning raw
bytes.  The search algorithm in ``compressor.py`` is engine-agnostic and calls
these methods repeatedly to find the optimal parameters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CompressionEngine(ABC):
    """Strategy interface for image compression backends."""

    @abstractmethod
    def encode_lossy(
        self,
        image_path: str,
        scale: float,
        quality: int,
        save_format: str,
        *,
        strip_exif: bool = False,
    ) -> bytes:
        """Resize to *scale* and encode as JPEG or WebP, returning raw bytes.

        Parameters
        ----------
        image_path:
            Absolute path to the source image.
        scale:
            Resize factor in (0, 1].  1.0 means no resize.
        quality:
            Encoder quality parameter (typically 5–95).
        save_format:
            ``"JPEG"`` or ``"WEBP"``.
        strip_exif:
            If True, strip EXIF metadata from the output.
        """

    @abstractmethod
    def encode_png(
        self,
        image_path: str,
        scale: float,
        colors: int | None,
        *,
        strip_exif: bool = False,
    ) -> bytes:
        """Resize to *scale* and encode as PNG, returning raw bytes.

        Parameters
        ----------
        image_path:
            Absolute path to the source image.
        scale:
            Resize factor in (0, 1].
        colors:
            If not None, quantize to this many colours (palette mode).
        strip_exif:
            If True, strip EXIF metadata from the output.
        """

    @abstractmethod
    def get_image_size(self, image_path: str) -> tuple[int, int]:
        """Return ``(width, height)`` of the image at *image_path*."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name, e.g. ``"vips"`` or ``"pillow"``."""
