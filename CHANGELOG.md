# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.2.0] - 2026-03-13

### Added
- Dual-engine architecture with optional `pyvips` engine and default Pillow fallback.
- Engine abstraction layer under `src/core/engines/`.
- Engine-aware tests for both `pillow-only` and `with-vips` environments.
- Configuration persistence support.

### Changed
- Compression search strategy optimized with binary search for quality/scale combinations.
- Project documentation updated for engine architecture and development workflow.

### Fixed
- `strip_exif` behavior improvements for metadata handling consistency.
- Security hardening in file/output path handling.

## [2.1.0] - 2026-03-12

### Added
- `ttkbootstrap` dark theme UI refresh.
- Image preview window and preview-related workflow.
- Internationalization (i18n) support.

## [2.0.0] - 2026-03-11

### Changed
- Refactored to a modular architecture with clearer separation of core/ui/worker layers.
