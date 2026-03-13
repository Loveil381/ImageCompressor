"""Tests for src.core.config_manager."""

from __future__ import annotations

import json
from pathlib import Path

from src.core import config_manager
from src.core.models import CompressionConfig


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".imagecompressor" / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", config_path)

    original = CompressionConfig(
        target_size_str="1MB",
        format_choice=".webp",
        output_mode="custom",
        custom_dir=str(tmp_path / "out"),
        strip_exif=True,
        language="en",
        engine_preference="pillow",
    )
    config_manager.save_config(original)

    loaded = config_manager.load_config()

    assert loaded == original


def test_load_returns_default_when_file_missing(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".imagecompressor" / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", config_path)

    loaded = config_manager.load_config()

    assert loaded == CompressionConfig()


def test_load_fills_defaults_for_missing_fields(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".imagecompressor" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "target_size_str": "900KB",
                "format_choice": ".png",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_manager, "CONFIG_PATH", config_path)

    loaded = config_manager.load_config()

    assert loaded.target_size_str == "900KB"
    assert loaded.format_choice == ".png"
    assert loaded.output_mode == "same_dir"
    assert loaded.engine_preference == "auto"
    assert loaded.language == "zh"


def test_load_gracefully_handles_corrupt_json(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".imagecompressor" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(config_manager, "CONFIG_PATH", config_path)

    loaded = config_manager.load_config()

    assert loaded == CompressionConfig()
