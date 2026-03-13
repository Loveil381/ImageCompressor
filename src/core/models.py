"""Data models for the image compression tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompressionResult:
    """Result of a single image compression operation."""

    actual_size: int
    format_name: str
    quality_text: str
    resized: bool
    scale: float
    output_extension: str
    warning: str | None = None


@dataclass
class CompressionTask:
    """Describes a single pending compression job."""

    src_path: str
    target_bytes: int
    output_path: str

    @property
    def src_name(self) -> str:
        return Path(self.src_path).name


@dataclass
class CompressionConfig:
    """User-configured settings for a compression batch."""

    target_size_str: str = "500KB"
    format_choice: str = "original"   # "original" | ".jpg" | ".png" | ".webp"
    output_mode: str = "same_dir"     # "same_dir" | "custom"
    custom_dir: str = ""
    strip_exif: bool = False
    language: str = "zh"
    engine_preference: str = "auto"  # "auto" | "vips" | "pillow"


@dataclass
class BatchResult:
    """Aggregated result of a full batch compression run."""

    success_count: int = 0
    failure_count: int = 0
    results: list[tuple[CompressionTask, CompressionResult | Exception]] = field(
        default_factory=list
    )

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count
