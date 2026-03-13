# ImageCompressor

> 高质量桌面图片压缩工具，支持 JPEG / PNG / WebP。  
> A high-quality desktop image compression tool for JPEG / PNG / WebP.

[![CI](https://github.com/Loveil381/ImageCompressor/actions/workflows/ci.yml/badge.svg)](https://github.com/Loveil381/ImageCompressor/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

| Feature | Description |
|---|---|
| Target size compression | Compress images to a target size (for example `500KB`) |
| Batch processing | Compress multiple files in one run |
| Multiple formats | JPEG / PNG / WebP / BMP / GIF / TIFF input support |
| Output options | Save in original directory or custom directory |
| EXIF control | Optional metadata stripping via `strip_exif` |
| Drag-and-drop | File/folder drag-and-drop support |
| Preview | Before/after preview support |
| I18N | Chinese / English / Japanese |
| High-DPI | Better scaling on high-DPI displays |
| Dual engine architecture | `pyvips` (optional high-performance) + Pillow (default fallback) |

---

## Installation

```bash
# 1) Clone repository
git clone https://github.com/Loveil381/ImageCompressor.git
cd ImageCompressor

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run
python run.py
# or
python -m src.main
```

---

## Performance (Optional pyvips Engine)

Install `pyvips + libvips` to get roughly **3-5x faster** compression in many workloads.

- Ubuntu / Debian:
```bash
sudo apt install libvips-dev && pip install pyvips
```
- macOS:
```bash
brew install vips && pip install pyvips
```
- Windows:
Download and install prebuilt **libvips** binaries, add `bin` to `PATH`, then:
```bash
pip install pyvips
```

If `pyvips` is not installed, the app remains fully usable and automatically falls back to **Pillow**.

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Lint
python -m ruff check src/ tests/

# Format check
python -m ruff format --check src/ tests/

# Type check
python -m mypy src/ --ignore-missing-imports

# Tests
python -m pytest tests/ -v --cov=src
```

---

## Project Structure

```text
src/
  app.py
  main.py
  core/
    compressor.py
    models.py
    utils.py
    engines/
      base.py          # 压缩引擎抽象基类
      vips_engine.py   # pyvips 高性能引擎（可选）
      pillow_engine.py # Pillow 兼容引擎（默认）
  ui/
    file_panel.py
    settings_panel.py
    log_panel.py
    preview_window.py
    theme.py
    widgets.py
  workers/
    compress_worker.py
    message_handler.py
  i18n/
    strings.py

tests/
  test_compressor.py
  test_engines.py
  test_utils.py
  ...
```

---

## English Quick Intro

ImageCompressor is a Python desktop image compressor with target-size optimization, batch processing, and optional high-performance `pyvips` backend.  
Without `pyvips`, it automatically uses Pillow, so no extra setup is required for basic usage.

---

## License

MIT License
