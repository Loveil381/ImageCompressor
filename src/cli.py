"""Command-line interface for batch image compression."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core.compressor import compress_image, get_engine_name
from .core.utils import (
    EXT_TO_FORMAT,
    FALLBACK_EXTENSIONS,
    format_bytes,
    parse_size,
    resolve_output_extension,
)

_FORMAT_MAP = {
    "original": "original",
    "jpg": ".jpg",
    "png": ".png",
    "webp": ".webp",
    "avif": ".avif",
}
_SUPPORTED_SUFFIXES = frozenset({*EXT_TO_FORMAT, *FALLBACK_EXTENSIONS})


@dataclass(frozen=True)
class InputItem:
    src_path: Path
    relative_dir: Path


def _parse_target_size(value: str) -> int:
    try:
        return parse_size(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imagecompressor")
    parser.add_argument("inputs", nargs="+", help="Files, directories, or glob patterns to compress")
    parser.add_argument(
        "-s",
        "--target-size",
        required=True,
        type=_parse_target_size,
        help="Target size such as 500KB or 1MB",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=sorted(_FORMAT_MAP),
        default="original",
        help="Output format",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Output directory. Defaults to the source file directory.",
    )
    parser.add_argument(
        "--strip-exif",
        action="store_true",
        help="Strip EXIF metadata from outputs",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively process files in directories",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print errors and a final summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output",
    )
    return parser


def _is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES


def _discover_directory(root: Path, recursive: bool) -> list[InputItem]:
    iterator = root.rglob("*") if recursive else root.glob("*")
    items: list[InputItem] = []
    for path in sorted(iterator):
        if _is_supported_file(path):
            relative_dir = path.parent.relative_to(root)
            items.append(InputItem(src_path=path.resolve(), relative_dir=relative_dir))
    return items


def discover_inputs(inputs: list[str], recursive: bool) -> tuple[list[InputItem], list[str]]:
    items: list[InputItem] = []
    errors: list[str] = []
    seen: set[Path] = set()

    for raw in inputs:
        matches = sorted(glob.glob(raw, recursive=recursive)) if glob.has_magic(raw) else [raw]
        if not matches:
            errors.append(f"No matches found for input: {raw}")
            continue

        for match in matches:
            path = Path(match)
            if path.is_dir():
                for item in _discover_directory(path, recursive):
                    if item.src_path not in seen:
                        seen.add(item.src_path)
                        items.append(item)
                continue

            if _is_supported_file(path):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    items.append(InputItem(src_path=resolved, relative_dir=Path()))
                continue

            if path.exists():
                errors.append(f"Unsupported input type: {path}")
            else:
                errors.append(f"Input path not found: {path}")

    return items, errors


def _build_output_path(item: InputItem, output_root: Path | None, output_ext: str) -> Path:
    filename = f"{item.src_path.stem}_compressed{output_ext}"
    if output_root is None:
        return item.src_path.with_name(filename)
    return (output_root / item.relative_dir / filename).resolve()


def _print_progress(index: int, total: int, path: Path, *, quiet: bool, json_mode: bool) -> None:
    if quiet or json_mode:
        return
    print(f"[{index}/{total}] Compressing {path}", file=sys.stderr)


def _emit_success(
    source: Path,
    output_path: Path,
    result: Any,
    *,
    quiet: bool,
    json_mode: bool,
) -> None:
    if quiet or json_mode:
        return
    print(
        f"OK  {source.name} -> {output_path}  "
        f"({format_bytes(result.actual_size)}, {result.format_name}, {result.quality_text})"
    )


def _emit_error(source: Path, exc: Exception, *, json_mode: bool) -> None:
    if json_mode:
        return
    print(f"ERROR {source}: {exc}", file=sys.stderr)


def _result_to_dict(source: Path, output_path: Path, result: Any) -> dict[str, Any]:
    return {
        "source": str(source),
        "output": str(output_path),
        "success": True,
        "actual_size": result.actual_size,
        "format_name": result.format_name,
        "quality_text": result.quality_text,
        "resized": result.resized,
        "scale": result.scale,
        "warning": result.warning,
    }


def _error_to_dict(source: Path, output_path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "source": str(source),
        "output": str(output_path),
        "success": False,
        "error": str(exc),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    fmt_choice = _FORMAT_MAP[args.format]
    output_root = Path(args.output_dir).resolve() if args.output_dir else None
    inputs, discovery_errors = discover_inputs(args.inputs, recursive=args.recursive)

    if discovery_errors:
        for error in discovery_errors:
            print(error, file=sys.stderr)
        return 2

    if not inputs:
        print("No supported input files found.", file=sys.stderr)
        return 2

    engine_name = get_engine_name()
    results: list[dict[str, Any]] = []
    success_count = 0
    failure_count = 0

    for index, item in enumerate(inputs, start=1):
        _print_progress(index, len(inputs), item.src_path, quiet=args.quiet, json_mode=args.json)
        output_ext, warning = resolve_output_extension(str(item.src_path), fmt_choice)
        output_path = _build_output_path(item, output_root, output_ext)

        try:
            result = compress_image(
                str(item.src_path),
                args.target_size,
                str(output_path),
                strip_exif=args.strip_exif,
            )
            if warning is not None:
                result.warning = warning if result.warning is None else f"{result.warning}; {warning}"
            success_count += 1
            results.append(_result_to_dict(item.src_path, output_path, result))
            _emit_success(item.src_path, output_path, result, quiet=args.quiet, json_mode=args.json)
        except Exception as exc:
            failure_count += 1
            results.append(_error_to_dict(item.src_path, output_path, exc))
            _emit_error(item.src_path, exc, json_mode=args.json)

    summary = {
        "engine": engine_name,
        "target_bytes": args.target_size,
        "requested_format": args.format,
        "output_dir": str(output_root) if output_root is not None else None,
        "total": len(inputs),
        "success": success_count,
        "failure": failure_count,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"Summary: {success_count} succeeded, {failure_count} failed, "
            f"engine={engine_name}, target={format_bytes(args.target_size)}"
        )

    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
