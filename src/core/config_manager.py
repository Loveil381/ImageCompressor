"""Configuration persistence for the image compressor app."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path

from .models import CompressionConfig

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".imagecompressor" / "config.json"


def load_config() -> CompressionConfig:
    """Load persisted config from disk, falling back to defaults on failure."""
    default_config = CompressionConfig()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return default_config
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default_config

    defaults = asdict(default_config)
    merged: dict[str, object] = {}
    for field in fields(CompressionConfig):
        merged[field.name] = raw.get(field.name, defaults[field.name])

    try:
        watch_dirs_raw = merged["watch_dirs"]
        watch_dirs = [str(x) for x in watch_dirs_raw] if isinstance(watch_dirs_raw, list) else []
        return CompressionConfig(
            target_size_str=str(merged["target_size_str"]),
            format_choice=str(merged["format_choice"]),
            output_mode=str(merged["output_mode"]),
            custom_dir=str(merged["custom_dir"]),
            strip_exif=bool(merged["strip_exif"]),
            language=str(merged["language"]),
            engine_preference=str(merged["engine_preference"]),
            watch_enabled=bool(merged["watch_enabled"]),
            watch_dirs=watch_dirs,
            watch_recursive=bool(merged["watch_recursive"]),
        )
    except (TypeError, KeyError):
        return default_config


def save_config(config: CompressionConfig) -> None:
    """Persist *config* to disk as UTF-8 JSON."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as fh:
            json.dump(asdict(config), fh, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Failed to save config file: %s", exc)
