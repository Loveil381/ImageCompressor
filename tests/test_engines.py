"""Tests for engine implementations and selection."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

import src.core.compressor as compressor
from src.core.compressor import compress_image, get_engine_name
from src.core.engines.pillow_engine import PillowEngine

try:
    import pyvips  # noqa: F401

    HAS_VIPS = True
except ImportError:
    HAS_VIPS = False


def _save_image(tmp_path: Path, filename: str, image: Image.Image, *, format_name: str | None = None) -> str:
    path = tmp_path / filename
    image.save(path, format=format_name)
    return str(path)


def _make_gradient(size: tuple[int, int] = (640, 480)) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    for x in range(width):
        for y in range(height):
            image.putpixel((x, y), ((x * 5) % 256, (y * 3) % 256, (x + y) % 256))
    return image


class TestPillowEngine:
    def test_encode_lossy_jpeg_meets_target_constraints(self, tmp_path: Path) -> None:
        src = _save_image(tmp_path, "rgba.png", Image.new("RGBA", (400, 300), (10, 120, 240, 128)))
        engine = PillowEngine()

        data = engine.encode_lossy(src, 1.0, 75, "JPEG")

        out = tmp_path / "pillow_lossy.jpg"
        out.write_bytes(data)
        with Image.open(out) as encoded:
            assert encoded.mode == "RGB"
        assert data[:2] == b"\xff\xd8"

    def test_encode_lossy_webp_returns_bytes(self, tmp_path: Path) -> None:
        src = _save_image(tmp_path, "webp_source.png", _make_gradient((320, 240)))
        engine = PillowEngine()

        data = engine.encode_lossy(src, 0.8, 70, "WEBP")

        out = tmp_path / "pillow_lossy.webp"
        out.write_bytes(data)
        with Image.open(out) as encoded:
            assert encoded.format == "WEBP"

    def test_encode_png_preserves_png_output(self, tmp_path: Path) -> None:
        palette = Image.new("P", (256, 128))
        palette.putpalette([value for rgb in range(256) for value in (rgb, rgb, rgb)])
        for x in range(256):
            for y in range(128):
                palette.putpixel((x, y), x)
        src = _save_image(tmp_path, "palette.png", palette, format_name="PNG")
        engine = PillowEngine()

        data = engine.encode_png(src, 0.75, 32)

        out = tmp_path / "pillow_quantized.png"
        out.write_bytes(data)
        with Image.open(out) as encoded:
            assert encoded.format == "PNG"
            assert encoded.size[0] < 256

    def test_get_image_size_returns_dimensions(self, tmp_path: Path) -> None:
        src = _save_image(tmp_path, "size.jpg", Image.new("RGB", (123, 456), (20, 40, 60)))

        engine = PillowEngine()

        assert engine.get_image_size(src) == (123, 456)


class TestEngineSelection:
    def test_get_engine_returns_expected_type(self) -> None:
        compressor._engine_instance = None
        engine = compressor._get_engine()

        if HAS_VIPS:
            from src.core.engines.vips_engine import VipsEngine

            assert isinstance(engine, VipsEngine)
        else:
            assert isinstance(engine, PillowEngine)

        compressor._engine_instance = None

    def test_get_engine_name_returns_supported_name(self) -> None:
        compressor._engine_instance = None
        assert get_engine_name() in {"pillow", "vips"}
        compressor._engine_instance = None

    def test_pillow_preference_forces_pillow_engine(self) -> None:
        compressor._engine_instance = None
        engine = compressor._get_engine("pillow")
        assert isinstance(engine, PillowEngine)
        assert get_engine_name("pillow") == "pillow"
        compressor._engine_instance = None

    def test_vips_preference_falls_back_when_unavailable(self) -> None:
        compressor._engine_instance = None
        if HAS_VIPS:
            assert get_engine_name("vips") == "vips"
        else:
            assert get_engine_name("vips") == "pillow"
        compressor._engine_instance = None


@pytest.mark.skipif(not HAS_VIPS, reason="pyvips not installed")
class TestVipsEngine:
    def test_encode_lossy_returns_jpeg_bytes(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        src = _save_image(tmp_path, "source.png", Image.new("RGBA", (400, 300), (200, 100, 20, 180)))
        data = VipsEngine().encode_lossy(src, 1.0, 80, "JPEG")

        out = tmp_path / "vips_lossy.jpg"
        out.write_bytes(data)
        with Image.open(out) as encoded:
            assert encoded.mode == "RGB"

    def test_encode_png_returns_png_bytes(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        src = _save_image(tmp_path, "source.png", _make_gradient((320, 240)))
        data = VipsEngine().encode_png(src, 0.7, 64)

        out = tmp_path / "vips_quantized.png"
        out.write_bytes(data)
        with Image.open(out) as encoded:
            assert encoded.format == "PNG"

    def test_get_image_size_returns_dimensions(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        src = _save_image(tmp_path, "size.jpg", Image.new("RGB", (321, 654), (50, 80, 120)))
        assert VipsEngine().get_image_size(src) == (321, 654)

    def test_both_engines_meet_target_size_for_same_input(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        src = _save_image(tmp_path, "shared_source.jpg", _make_gradient((900, 700)), format_name="JPEG")
        target = 70_000
        original_engine = compressor._engine_instance

        try:
            compressor._engine_instance = PillowEngine()
            pillow_out = str(tmp_path / "shared_pillow.jpg")
            pillow_result = compress_image(src, target, pillow_out)

            compressor._engine_instance = VipsEngine()
            vips_out = str(tmp_path / "shared_vips.jpg")
            vips_result = compress_image(src, target, vips_out)
        finally:
            compressor._engine_instance = original_engine

        assert pillow_result.actual_size <= target
        assert vips_result.actual_size <= target
        assert Path(pillow_out).exists()
        assert Path(vips_out).exists()
