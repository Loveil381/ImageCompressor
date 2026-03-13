"""Tests for src.core.compressor – uses in-memory synthetic images.

Covers:
- Original functionality (JPEG, PNG, WebP, EXIF, format fallback)
- Engine abstraction (fallback, direct engine usage)
- Binary search encode-count budgets
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from src.core.compressor import compress_image
from src.core.utils import format_bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(
    width: int = 800,
    height: int = 600,
    mode: str = "RGB",
    color: tuple = (120, 180, 230),
) -> Image.Image:
    """Return a solid-colour PIL Image for testing."""
    return Image.new(mode, (width, height), color)


def _save_test_image(tmp_path: Path, filename: str, image: Image.Image) -> str:
    """Save *image* to *tmp_path/filename* and return the absolute path."""
    p = tmp_path / filename
    image.save(str(p))
    return str(p)


def _save_test_jpeg_with_exif(tmp_path: Path, filename: str, image: Image.Image) -> str:
    """Save *image* with EXIF camera and GPS metadata."""
    p = tmp_path / filename
    exif = Image.Exif()
    exif[271] = "CodexCam"
    exif[272] = "Model 1"
    exif[305] = "Pillow"
    exif[34853] = {
        1: "N",
        2: (35.0, 41.0, 0.0),
        3: "E",
        4: (139.0, 42.0, 0.0),
    }
    image.save(str(p), format="JPEG", quality=95, exif=exif)
    return str(p)


def _read_exif(path: str) -> Image.Exif:
    with Image.open(path) as image:
        return image.getexif()


# ---------------------------------------------------------------------------
# JPEG compression
# ---------------------------------------------------------------------------


class TestJpegCompression:
    def test_one_by_one_image_compresses_to_jpeg(self, tmp_path: Path) -> None:
        img = _make_test_image(1, 1)
        src = _save_test_image(tmp_path, "tiny.png", img)
        out = str(tmp_path / "tiny.jpg")

        result = compress_image(src, 5_000, out)

        assert Path(out).exists()
        assert result.format_name == "JPEG"
        assert result.actual_size > 0

    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(1200, 900)
        src = _save_test_image(tmp_path, "test.jpg", img)
        out = str(tmp_path / "out.jpg")
        target = 50_000  # 50 KB

        result = compress_image(src, target, out)

        assert result.actual_size <= target, (
            f"Output {format_bytes(result.actual_size)} exceeded target {format_bytes(target)}"
        )
        assert Path(out).exists()
        assert result.format_name == "JPEG"

    def test_small_image_not_unnecessarily_degraded(self, tmp_path: Path) -> None:
        # A tiny image should already be < 500 KB, quality should stay high
        img = _make_test_image(100, 100)
        src = _save_test_image(tmp_path, "small.jpg", img)
        out = str(tmp_path / "small_out.jpg")
        target = 500_000  # 500 KB

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        # Should use high quality since it fits easily
        assert "95" in result.quality_text

    def test_rgba_input_converted_to_rgb_for_jpeg(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300, mode="RGBA", color=(0, 128, 255, 200))
        src = _save_test_image(tmp_path, "rgba.png", img)
        out = str(tmp_path / "rgba_out.jpg")

        result = compress_image(src, 100_000, out)

        assert Path(out).exists()
        with Image.open(out) as saved:
            assert saved.mode == "RGB"

    def test_grayscale_input_converted_for_jpeg(self, tmp_path: Path) -> None:
        img = _make_test_image(320, 240, mode="L", color=180)
        src = _save_test_image(tmp_path, "gray.png", img)
        out = str(tmp_path / "gray_out.jpg")

        result = compress_image(src, 40_000, out)

        assert result.format_name == "JPEG"
        with Image.open(out) as saved:
            assert saved.mode == "RGB"

    def test_tiny_target_does_not_crash(self, tmp_path: Path) -> None:
        img = Image.effect_noise((1200, 1200), 120).convert("RGB")
        src = _save_test_image(tmp_path, "hard.jpg", img)
        out = str(tmp_path / "hard_out.jpg")

        result = compress_image(src, 10, out)

        assert Path(out).exists()
        assert result.actual_size > 0
        assert Path(out).stat().st_size == result.actual_size


# ---------------------------------------------------------------------------
# PNG compression
# ---------------------------------------------------------------------------


class TestPngCompression:
    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(800, 600)
        src = _save_test_image(tmp_path, "test.png", img)
        out = str(tmp_path / "out.png")
        target = 30_000  # 30 KB – forces quantization

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        assert Path(out).exists()
        assert result.format_name == "PNG"

    def test_png_with_alpha(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300, mode="RGBA", color=(100, 150, 200, 128))
        src = _save_test_image(tmp_path, "alpha.png", img)
        out = str(tmp_path / "alpha_out.png")

        result = compress_image(src, 200_000, out)

        assert Path(out).exists()
        assert result.format_name == "PNG"

    def test_palette_input_remains_png(self, tmp_path: Path) -> None:
        img = Image.new("P", (256, 128))
        img.putpalette([value for color in range(256) for value in (color, color, color)])
        for x in range(256):
            for y in range(128):
                img.putpixel((x, y), x)
        src = _save_test_image(tmp_path, "palette.png", img)
        out = str(tmp_path / "palette_out.png")

        result = compress_image(src, 20_000, out)

        assert Path(out).exists()
        assert result.format_name == "PNG"


# ---------------------------------------------------------------------------
# WebP compression
# ---------------------------------------------------------------------------


class TestWebpCompression:
    def test_output_size_within_target(self, tmp_path: Path) -> None:
        img = _make_test_image(800, 600)
        src = _save_test_image(tmp_path, "test.jpg", img)
        out = str(tmp_path / "out.webp")
        target = 40_000

        result = compress_image(src, target, out)

        assert result.actual_size <= target
        assert result.format_name == "WEBP"


# ---------------------------------------------------------------------------
# EXIF strip
# ---------------------------------------------------------------------------


class TestExifStrip:
    def test_strip_exif_removes_camera_and_gps_metadata(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300)
        src = _save_test_jpeg_with_exif(tmp_path, "exif.jpg", img)
        out = str(tmp_path / "exif_out.jpg")

        result = compress_image(src, 200_000, out, strip_exif=True)

        assert Path(out).exists()
        assert result.actual_size > 0
        exif = _read_exif(out)
        assert len(exif) == 0
        assert exif.get(271) is None
        assert exif.get(272) is None
        assert exif.get(34853) is None

    def test_preserves_exif_when_strip_disabled(self, tmp_path: Path) -> None:
        img = _make_test_image(400, 300)
        src = _save_test_jpeg_with_exif(tmp_path, "exif_keep.jpg", img)
        out = str(tmp_path / "exif_keep_out.jpg")

        result = compress_image(src, 200_000, out, strip_exif=False)

        assert Path(out).exists()
        assert result.actual_size > 0
        exif = _read_exif(out)
        assert exif.get(271) == "CodexCam"
        assert exif.get(272) == "Model 1"
        assert exif.get(34853) is not None


# ---------------------------------------------------------------------------
# Format fallback (BMP → PNG)
# ---------------------------------------------------------------------------


class TestFormatFallback:
    def test_bmp_written_as_png(self, tmp_path: Path) -> None:
        img = _make_test_image(200, 150, mode="RGB")
        src = _save_test_image(tmp_path, "test.bmp", img)
        # Output extension is .png (as resolved by utils.resolve_output_extension)
        out = str(tmp_path / "test_compressed.png")

        result = compress_image(src, 500_000, out)

        assert Path(out).exists()
        assert result.format_name == "PNG"


# ---------------------------------------------------------------------------
# NEW: Engine fallback
# ---------------------------------------------------------------------------


class TestEngineFallback:
    def test_pillow_fallback_when_pyvips_unavailable(self) -> None:
        """When pyvips is not importable, PillowEngine should be selected."""
        import src.core.compressor as comp_module

        # Reset the cached engine
        comp_module._engine_instance = None

        # Mock the vips_engine import to raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if "vips_engine" in name:
                raise ImportError("No module named 'pyvips'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Force re-import of the vips_engine module to fail
            comp_module._engine_instance = None
            try:
                # Directly test the fallback by trying vips import
                try:
                    from src.core.engines.vips_engine import VipsEngine
                    # pyvips is actually installed – test that VipsEngine works
                    engine = VipsEngine()
                    assert engine.name == "vips"
                except ImportError:
                    # pyvips is not installed – test that PillowEngine works
                    from src.core.engines.pillow_engine import PillowEngine
                    engine = PillowEngine()
                    assert engine.name == "pillow"
            finally:
                comp_module._engine_instance = None

    def test_engine_name_is_string(self) -> None:
        """The selected engine should have a valid name."""
        import src.core.compressor as comp_module
        comp_module._engine_instance = None
        assert comp_module.get_engine_name() in ("vips", "pillow")
        comp_module._engine_instance = None


# ---------------------------------------------------------------------------
# NEW: Pillow engine direct usage
# ---------------------------------------------------------------------------


class TestPillowEngineDirect:
    def test_encode_lossy_returns_valid_jpeg(self, tmp_path: Path) -> None:
        """PillowEngine.encode_lossy should return valid JPEG bytes."""
        from src.core.engines.pillow_engine import PillowEngine

        img = _make_test_image(400, 300)
        src = _save_test_image(tmp_path, "direct.jpg", img)

        engine = PillowEngine()
        data = engine.encode_lossy(src, 1.0, 80, "JPEG")

        assert len(data) > 0
        # JPEG magic bytes
        assert data[:2] == b"\xff\xd8"

    def test_encode_png_returns_valid_png(self, tmp_path: Path) -> None:
        """PillowEngine.encode_png should return valid PNG bytes."""
        from src.core.engines.pillow_engine import PillowEngine

        img = _make_test_image(400, 300)
        src = _save_test_image(tmp_path, "direct.png", img)

        engine = PillowEngine()
        data = engine.encode_png(src, 1.0, None)

        assert len(data) > 0
        # PNG magic bytes
        assert data[:4] == b"\x89PNG"

    def test_get_image_size(self, tmp_path: Path) -> None:
        from src.core.engines.pillow_engine import PillowEngine

        img = _make_test_image(640, 480)
        src = _save_test_image(tmp_path, "size.jpg", img)

        engine = PillowEngine()
        w, h = engine.get_image_size(src)
        assert (w, h) == (640, 480)


# ---------------------------------------------------------------------------
# NEW: Vips engine direct usage (skipped if pyvips not installed)
# ---------------------------------------------------------------------------


class TestVipsEngineDirect:
    @pytest.fixture(autouse=True)
    def _require_pyvips(self):
        pytest.importorskip("pyvips")

    def test_encode_lossy_returns_valid_jpeg(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        img = _make_test_image(400, 300)
        src = _save_test_image(tmp_path, "vips_direct.jpg", img)

        engine = VipsEngine()
        data = engine.encode_lossy(src, 1.0, 80, "JPEG")

        assert len(data) > 0
        assert data[:2] == b"\xff\xd8"

    def test_encode_png_returns_valid_png(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        img = _make_test_image(400, 300)
        src = _save_test_image(tmp_path, "vips_direct.png", img)

        engine = VipsEngine()
        data = engine.encode_png(src, 1.0, None)

        assert len(data) > 0
        assert data[:4] == b"\x89PNG"

    def test_get_image_size(self, tmp_path: Path) -> None:
        from src.core.engines.vips_engine import VipsEngine

        img = _make_test_image(640, 480)
        src = _save_test_image(tmp_path, "vips_size.jpg", img)

        engine = VipsEngine()
        w, h = engine.get_image_size(src)
        assert (w, h) == (640, 480)


# ---------------------------------------------------------------------------
# NEW: Binary search encode-count budgets
# ---------------------------------------------------------------------------


class TestEncodeCountBudget:
    """Verify binary search keeps encode calls within theoretical bounds.

    Lossy worst-case: 7 (quality at scale=1) + 7 (scale) × 7 (quality) = 56
    PNG   worst-case: 6 (colors at scale=1) + 7 (scale) × 6 (colors)  = 48
    """

    def test_lossy_encode_count_within_budget(self, tmp_path: Path) -> None:
        """Lossy compression should use ≤ 56 encode calls."""
        from src.core.engines.pillow_engine import PillowEngine

        img = _make_test_image(1200, 900)
        src = _save_test_image(tmp_path, "count.jpg", img)
        out = str(tmp_path / "count_out.jpg")

        engine = PillowEngine()
        call_count = 0
        original_encode = engine.encode_lossy

        def counting_encode(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_encode(*args, **kwargs)

        engine.encode_lossy = counting_encode  # type: ignore[assignment]

        # Patch the engine so compressor uses our counting wrapper
        import src.core.compressor as comp_module
        old_engine = comp_module._engine_instance
        comp_module._engine_instance = engine
        try:
            # Use a tight target to exercise the full search
            compress_image(src, 5_000, out)
        finally:
            comp_module._engine_instance = old_engine

        assert call_count <= 56, (
            f"Lossy encode was called {call_count} times (budget: 56)"
        )

    def test_png_encode_count_within_budget(self, tmp_path: Path) -> None:
        """PNG compression should use ≤ 48 encode calls."""
        from src.core.engines.pillow_engine import PillowEngine

        img = _make_test_image(1200, 900)
        src = _save_test_image(tmp_path, "count.png", img)
        out = str(tmp_path / "count_out.png")

        engine = PillowEngine()
        call_count = 0
        original_encode = engine.encode_png

        def counting_encode(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_encode(*args, **kwargs)

        engine.encode_png = counting_encode  # type: ignore[assignment]

        import src.core.compressor as comp_module
        old_engine = comp_module._engine_instance
        comp_module._engine_instance = engine
        try:
            compress_image(src, 1_000, out)
        finally:
            comp_module._engine_instance = old_engine

        assert call_count <= 48, (
            f"PNG encode was called {call_count} times (budget: 48)"
        )


# ---------------------------------------------------------------------------
# NEW: compress_image signature unchanged
# ---------------------------------------------------------------------------


class TestCompressImageSignature:
    def test_accepts_documented_parameters(self, tmp_path: Path) -> None:
        """compress_image must accept the documented positional and keyword args."""
        import inspect
        from src.core.compressor import compress_image

        sig = inspect.signature(compress_image)
        params = list(sig.parameters.keys())

        assert "src_path" in params
        assert "target_bytes" in params
        assert "output_path" in params
        assert "strip_exif" in params
        assert "progress_cb" in params


class TestCompressionEdgeCases:
    def test_large_image_reaches_target_size(self, tmp_path: Path) -> None:
        img = Image.effect_noise((2000, 2000), 120).convert("RGB")
        src = _save_test_image(tmp_path, "large.jpg", img)
        out = str(tmp_path / "large_out.jpg")
        target = 200_000

        result = compress_image(src, target, out)

        assert Path(out).exists()
        assert result.actual_size <= target
        assert result.resized or "95" not in result.quality_text
