# Contributing

Thanks for contributing to ImageCompressor.

## Development Setup

```bash
git clone https://github.com/Loveil381/ImageCompressor.git
cd ImageCompressor
pip install -r requirements.txt -r requirements-dev.txt
```

Optional high-performance engine (`pyvips`):

- Ubuntu / Debian:
```bash
sudo apt install libvips-dev && pip install pyvips
```
- macOS:
```bash
brew install vips && pip install pyvips
```
- Windows:
Install prebuilt `libvips` binaries, add `bin` to `PATH`, then run:
```bash
pip install pyvips
```

## Code Style

- Lint with Ruff:
```bash
python -m ruff check src/ tests/
```
- Format check:
```bash
python -m ruff format --check src/ tests/
```
- Type check:
```bash
python -m mypy src/ --ignore-missing-imports
```
- Run tests:
```bash
python -m pytest tests/ -v --cov=src
```

## Adding a New Engine

To add a new compression engine:

1. Implement the `CompressionEngine` interface in `src/core/engines/base.py`.
2. Add a new engine module under `src/core/engines/`.
3. Ensure `encode_lossy`, `encode_png`, `get_image_size`, and `name` are implemented.
4. Integrate selection logic in `src/core/compressor.py` without breaking Pillow fallback.
5. Add/extend tests in `tests/test_engines.py` and related integration tests.

## Pull Request Process

1. Create a feature branch from `main`.
2. Keep changes focused and include tests when behavior changes.
3. Run lint, type checks, and tests locally before opening a PR.
4. Open a PR with:
   - summary of changes
   - test results
   - any migration notes (if needed)
5. Address review feedback and keep commit history clean.
