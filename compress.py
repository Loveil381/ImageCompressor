from __future__ import annotations

import ctypes
import io
import os
import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

try:
    PNG_QUANTIZE_METHOD = Image.Quantize.FASTOCTREE
except AttributeError:
    PNG_QUANTIZE_METHOD = None

try:
    PNG_DITHER = Image.Dither.NONE
except AttributeError:
    PNG_DITHER = Image.NONE

APP_TITLE = "图片压缩工具"
BG_COLOR = "#f5f6f8"
PANEL_COLOR = "#ffffff"
ACCENT_COLOR = "#2f80ed"
SUCCESS_COLOR = "#27ae60"
DANGER_COLOR = "#d64545"
NEUTRAL_COLOR = "#5f6b7a"
TEXT_COLOR = "#22303c"
DEFAULT_FONT = ("Microsoft YaHei UI", 10)
TITLE_FONT = ("Microsoft YaHei UI", 16, "bold")
BUTTON_FONT = ("Microsoft YaHei UI", 10)
SUPPORTED_INPUT_TYPES = "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff"
EXT_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
FALLBACK_EXTENSIONS = {
    ".bmp": ".png",
    ".gif": ".png",
    ".tif": ".png",
    ".tiff": ".png",
}
ORIGINAL_FORMAT = "original"
CUSTOM_OUTPUT = "custom"


@dataclass
class CompressionResult:
    actual_size: int
    format_name: str
    quality_text: str
    resized: bool
    scale: float
    output_extension: str
    warning: str | None = None


def enable_high_dpi_awareness() -> None:
    """Opt into high-DPI rendering on Windows to avoid blurry/tiny Tk UI."""
    if os.name != "nt":
        return

    user32 = getattr(ctypes, "windll", None)
    if user32 is None:
        return

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_window_dpi(window: tk.Tk) -> float:
    if os.name != "nt":
        return 96.0

    try:
        return float(ctypes.windll.user32.GetDpiForWindow(window.winfo_id()))
    except Exception:
        return 96.0


def parse_size(size_str: str) -> int:
    """Parse values like 500KB, 1.5MB, 1048576 to bytes."""
    normalized = size_str.strip().upper().replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(B|KB|MB|GB)?", normalized)
    if not match:
        raise ValueError(f"无效的目标大小：{size_str}")

    value = float(match.group(1))
    unit = match.group(2) or "B"
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return int(value * units[unit])


def format_bytes(size_in_bytes: int) -> str:
    if size_in_bytes >= 1024**3:
        return f"{size_in_bytes / 1024**3:.2f} GB"
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    if size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    return f"{size_in_bytes} B"


def format_scale(scale: float) -> str:
    return f"{scale * 100:.0f}%"


def resolve_output_extension(src_path: str, fmt_choice: str) -> tuple[str, str | None]:
    source_ext = Path(src_path).suffix.lower()
    if fmt_choice != ORIGINAL_FORMAT:
        return fmt_choice, None

    if source_ext in EXT_TO_FORMAT:
        return source_ext, None

    fallback_ext = FALLBACK_EXTENSIONS.get(source_ext, ".jpg")
    warning = f"原格式 {source_ext or '(无扩展名)'} 不支持直接输出，已自动改为 {fallback_ext}"
    return fallback_ext, warning


def compress_image(src_path: str, target_bytes: int, output_path: str) -> CompressionResult:
    output_ext = Path(output_path).suffix.lower()
    save_format = EXT_TO_FORMAT.get(output_ext, "JPEG")

    with Image.open(src_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()

    if save_format == "PNG":
        return compress_png(image, target_bytes, output_path, output_ext)
    return compress_lossy(image, target_bytes, output_path, save_format, output_ext)


def compress_lossy(
    image: Image.Image,
    target_bytes: int,
    output_path: str,
    save_format: str,
    output_ext: str,
) -> CompressionResult:
    prepared = prepare_image_for_format(image, save_format)
    smallest_attempt: CompressionResult | None = None
    smallest_payload = b""

    for scale in iter_scales():
        candidate = resize_image(prepared, scale)
        fit_payload, fit_quality = find_best_lossy_payload(candidate, target_bytes, save_format)
        if fit_payload is not None and fit_quality is not None:
            write_bytes(output_path, fit_payload)
            return CompressionResult(
                actual_size=len(fit_payload),
                format_name=save_format,
                quality_text=f"quality={fit_quality}",
                resized=scale < 0.999,
                scale=scale,
                output_extension=output_ext,
            )

        payload = encode_lossy(candidate, save_format, quality=5)
        if smallest_attempt is None or len(payload) < smallest_attempt.actual_size:
            smallest_payload = payload
            smallest_attempt = CompressionResult(
                actual_size=len(payload),
                format_name=save_format,
                quality_text="quality=5",
                resized=scale < 0.999,
                scale=scale,
                output_extension=output_ext,
            )

    if smallest_attempt is None:
        raise RuntimeError("压缩失败，未生成任何输出结果。")

    write_bytes(output_path, smallest_payload)
    return smallest_attempt


def find_best_lossy_payload(
    image: Image.Image,
    target_bytes: int,
    save_format: str,
) -> tuple[bytes | None, int | None]:
    high_quality_payload = encode_lossy(image, save_format, quality=95)
    if len(high_quality_payload) <= target_bytes:
        return high_quality_payload, 95

    low_quality_payload = encode_lossy(image, save_format, quality=5)
    if len(low_quality_payload) > target_bytes:
        return None, None

    best_payload = low_quality_payload
    best_quality = 5
    low = 5
    high = 95

    while low <= high:
        middle = (low + high) // 2
        payload = encode_lossy(image, save_format, quality=middle)
        payload_size = len(payload)
        if payload_size <= target_bytes:
            best_payload = payload
            best_quality = middle
            low = middle + 1
        else:
            high = middle - 1

    return best_payload, best_quality


def compress_png(
    image: Image.Image,
    target_bytes: int,
    output_path: str,
    output_ext: str,
) -> CompressionResult:
    prepared = prepare_image_for_format(image, "PNG")
    smallest_attempt: tuple[bytes, int, float] | None = None

    for scale in iter_scales():
        scaled = resize_image(prepared, scale)
        for colors in (None, 256, 128, 64, 32, 16):
            candidate = quantize_png(scaled, colors)
            payload = encode_png(candidate)
            payload_size = len(payload)

            if payload_size <= target_bytes:
                write_bytes(output_path, payload)
                quality_text = "PNG optimize" if colors is None else f"palette={colors}"
                return CompressionResult(
                    actual_size=payload_size,
                    format_name="PNG",
                    quality_text=quality_text,
                    resized=scale < 0.999,
                    scale=scale,
                    output_extension=output_ext,
                )

            if smallest_attempt is None or payload_size < smallest_attempt[1]:
                smallest_attempt = (payload, payload_size, scale)

    if smallest_attempt is None:
        raise RuntimeError("PNG 压缩失败，未生成任何输出结果。")

    payload, payload_size, scale = smallest_attempt
    write_bytes(output_path, payload)
    return CompressionResult(
        actual_size=payload_size,
        format_name="PNG",
        quality_text="palette=16",
        resized=scale < 0.999,
        scale=scale,
        output_extension=output_ext,
    )


def prepare_image_for_format(image: Image.Image, save_format: str) -> Image.Image:
    if save_format == "JPEG":
        if image.mode not in ("RGB", "L"):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB") if image.mode == "L" else image.copy()

    if save_format == "PNG":
        if image.mode in ("RGBA", "RGB", "L", "P"):
            return image.copy()
        if "A" in image.getbands():
            return image.convert("RGBA")
        return image.convert("RGB")

    if image.mode in ("RGBA", "RGB", "L"):
        return image.copy()
    if "A" in image.getbands():
        return image.convert("RGBA")
    return image.convert("RGB")


def iter_scales() -> list[float]:
    scales = [1.0]
    current = 0.95
    while current >= 0.1:
        scales.append(round(current, 2))
        current -= 0.05
    return scales


def resize_image(image: Image.Image, scale: float) -> Image.Image:
    if scale >= 0.999:
        return image.copy()

    width, height = image.size
    new_size = (
        max(1, int(width * scale)),
        max(1, int(height * scale)),
    )
    return image.resize(new_size, RESAMPLE_LANCZOS)


def encode_lossy(image: Image.Image, save_format: str, quality: int) -> bytes:
    buffer = io.BytesIO()
    save_kwargs: dict[str, object] = {"format": save_format}

    if save_format == "JPEG":
        save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
    elif save_format == "WEBP":
        save_kwargs.update({"quality": quality, "method": 6})
    else:
        raise ValueError(f"不支持的有损格式：{save_format}")

    image.save(buffer, **save_kwargs)
    return buffer.getvalue()


def quantize_png(image: Image.Image, colors: int | None) -> Image.Image:
    if colors is None:
        return image

    rgba_image = image.convert("RGBA")
    quantize_kwargs = {"colors": colors, "dither": PNG_DITHER}
    if PNG_QUANTIZE_METHOD is not None:
        quantize_kwargs["method"] = PNG_QUANTIZE_METHOD
    return rgba_image.quantize(**quantize_kwargs)


def encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True, compress_level=9)
    return buffer.getvalue()


def write_bytes(output_path: str, payload: bytes) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as output_file:
        output_file.write(payload)


class App(tk.Tk):
    def __init__(self) -> None:
        enable_high_dpi_awareness()
        super().__init__()
        self.ui_scale = 1.0
        self.default_font = DEFAULT_FONT
        self.title_font = TITLE_FONT
        self.button_font = BUTTON_FONT
        self.run_font = ("Microsoft YaHei UI", 12, "bold")
        self.mono_font = ("Consolas", 10)
        self.small_mono_font = ("Consolas", 9)
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.configure(bg=BG_COLOR)
        self._configure_scaling()

        self.files: list[str] = []
        self.size_var = tk.StringVar(value="500KB")
        self.fmt_var = tk.StringVar(value=ORIGINAL_FORMAT)
        self.out_var = tk.StringVar(value="same_dir")
        self.custom_dir_var = tk.StringVar()

        self._build_ui()
        self._sync_output_controls()
        self._finalize_window()

    def _configure_scaling(self) -> None:
        dpi = get_window_dpi(self)
        self.ui_scale = min(max(dpi / 96.0, 1.0), 1.35)
        try:
            self.tk.call("tk", "scaling", dpi / 72.0)
        except tk.TclError:
            pass

        self.default_font = DEFAULT_FONT
        self.title_font = TITLE_FONT
        self.button_font = BUTTON_FONT
        self.run_font = ("Microsoft YaHei UI", 12, "bold")
        self.mono_font = ("Consolas", 10)
        self.small_mono_font = ("Consolas", 9)

    def _px(self, value: int) -> int:
        return max(1, round(value * self.ui_scale))

    def _finalize_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        compact_layout = self.winfo_screenheight() <= 1100 or self.ui_scale > 1.2
        pad_x = self._px(10 if compact_layout else 12)
        pad_y = self._px(4 if compact_layout else 6)
        pad = {"padx": pad_x, "pady": pad_y}
        listbox_width = 56 if self.winfo_screenwidth() <= 1536 else 72
        listbox_height = 5 if compact_layout else 8
        log_height = 6 if compact_layout else 10
        custom_dir_width = 20 if self.winfo_screenwidth() <= 1536 else 24

        tk.Label(
            self,
            text=APP_TITLE,
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=pad_x,
            pady=(self._px(10 if compact_layout else 14), pad_y),
        )

        frame_files = tk.LabelFrame(
            self,
            text="待压缩图片",
            font=self.default_font,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            padx=self._px(8),
            pady=self._px(8),
        )
        frame_files.grid(row=1, column=0, **pad, sticky="ew")
        frame_files.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            frame_files,
            width=listbox_width,
            height=listbox_height,
            selectmode=tk.EXTENDED,
            font=self.small_mono_font,
        )
        file_scroll = tk.Scrollbar(frame_files, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=file_scroll.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        file_scroll.grid(row=0, column=1, sticky="ns")

        button_row = tk.Frame(self, bg=BG_COLOR)
        button_row.grid(
            row=2,
            column=0,
            padx=pad_x,
            pady=(0, pad_y),
            sticky="w",
        )
        self.add_button = tk.Button(
            button_row,
            text="添加图片",
            command=self._add_files,
            width=10,
            bg=ACCENT_COLOR,
            fg="white",
            relief="flat",
            font=self.button_font,
        )
        self.add_button.pack(side="left", padx=(0, self._px(8)))

        self.remove_button = tk.Button(
            button_row,
            text="删除选中",
            command=self._remove_selected,
            width=10,
            bg=NEUTRAL_COLOR,
            fg="white",
            relief="flat",
            font=self.button_font,
        )
        self.remove_button.pack(side="left", padx=(0, self._px(8)))

        self.clear_button = tk.Button(
            button_row,
            text="清空列表",
            command=self._clear_files,
            width=10,
            bg=DANGER_COLOR,
            fg="white",
            relief="flat",
            font=self.button_font,
        )
        self.clear_button.pack(side="left")

        frame_size = tk.LabelFrame(
            self,
            text="目标大小",
            font=self.default_font,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            padx=self._px(8),
            pady=self._px(8),
        )
        frame_size.grid(row=3, column=0, **pad, sticky="ew")

        tk.Label(
            frame_size,
            text="输入目标大小：",
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            font=self.default_font,
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )
        tk.Entry(frame_size, textvariable=self.size_var, width=16, font=self.mono_font).grid(
            row=0,
            column=1,
            padx=(self._px(6), self._px(12)),
        )
        tk.Label(
            frame_size,
            text="示例：500KB / 1.5MB / 800000B",
            bg=PANEL_COLOR,
            fg="#6b7280",
            font=self.default_font,
        ).grid(row=0, column=2, sticky="w")

        frame_format = tk.LabelFrame(
            self,
            text="输出格式",
            font=self.default_font,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            padx=self._px(8),
            pady=self._px(8),
        )
        frame_format.grid(row=4, column=0, **pad, sticky="ew")

        for text, value in (
            ("原格式", ORIGINAL_FORMAT),
            ("JPEG", ".jpg"),
            ("PNG", ".png"),
            ("WebP", ".webp"),
        ):
            tk.Radiobutton(
                frame_format,
                text=text,
                variable=self.fmt_var,
                value=value,
                bg=PANEL_COLOR,
                fg=TEXT_COLOR,
                font=self.default_font,
                selectcolor=PANEL_COLOR,
                activebackground=PANEL_COLOR,
            ).pack(side="left", padx=self._px(8))

        frame_output = tk.LabelFrame(
            self,
            text="输出位置",
            font=self.default_font,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            padx=self._px(8),
            pady=self._px(8),
        )
        frame_output.grid(row=5, column=0, **pad, sticky="ew")

        tk.Radiobutton(
            frame_output,
            text="原目录（文件名追加 _compressed）",
            variable=self.out_var,
            value="same_dir",
            command=self._sync_output_controls,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            font=self.default_font,
            selectcolor=PANEL_COLOR,
            activebackground=PANEL_COLOR,
        ).pack(side="left", padx=(0, self._px(8)))

        tk.Radiobutton(
            frame_output,
            text="自定义目录",
            variable=self.out_var,
            value=CUSTOM_OUTPUT,
            command=self._sync_output_controls,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            font=self.default_font,
            selectcolor=PANEL_COLOR,
            activebackground=PANEL_COLOR,
        ).pack(side="left", padx=(0, self._px(8)))

        self.custom_dir_entry = tk.Entry(
            frame_output,
            textvariable=self.custom_dir_var,
            width=custom_dir_width,
            font=self.small_mono_font,
        )
        self.custom_dir_entry.pack(side="left", padx=(0, self._px(6)))

        self.browse_button = tk.Button(
            frame_output,
            text="浏览",
            command=self._browse_out,
            bg=NEUTRAL_COLOR,
            fg="white",
            relief="flat",
            font=self.button_font,
        )
        self.browse_button.pack(side="left")

        self.run_button = tk.Button(
            self,
            text="开始压缩",
            command=self._run,
            font=self.run_font,
            bg=SUCCESS_COLOR,
            fg="white",
            relief="flat",
            padx=self._px(20),
            pady=self._px(7),
        )
        self.run_button.grid(row=6, column=0, pady=(self._px(4), self._px(8 if compact_layout else 10)))

        self.progress = ttk.Progressbar(self, length=self._px(560), mode="determinate")
        self.progress.grid(
            row=7,
            column=0,
            padx=pad_x,
            pady=(0, pad_y),
            sticky="ew",
        )

        frame_log = tk.LabelFrame(
            self,
            text="运行日志",
            font=self.default_font,
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            padx=self._px(8),
            pady=self._px(8),
        )
        frame_log.grid(row=8, column=0, **pad, sticky="ew")
        frame_log.columnconfigure(0, weight=1)

        self.log = tk.Text(
            frame_log,
            width=listbox_width,
            height=log_height,
            font=self.small_mono_font,
            state="disabled",
            bg="#111827",
            fg="#e5e7eb",
        )
        log_scroll = tk.Scrollbar(frame_log, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

    def _sync_output_controls(self) -> None:
        state = "normal" if self.out_var.get() == CUSTOM_OUTPUT else "disabled"
        self.custom_dir_entry.configure(state=state)
        self.browse_button.configure(state=state)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", SUPPORTED_INPUT_TYPES), ("所有文件", "*.*")],
        )
        changed = False
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                changed = True

        if changed:
            self._refresh_file_list()

    def _remove_selected(self) -> None:
        selected_indices = list(self.listbox.curselection())
        if not selected_indices:
            return

        for index in reversed(selected_indices):
            del self.files[index]
        self._refresh_file_list()

    def _clear_files(self) -> None:
        self.files.clear()
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        self.listbox.delete(0, "end")
        for path in self.files:
            file_name = Path(path).name
            try:
                file_size = format_bytes(os.path.getsize(path))
            except OSError:
                file_size = "未知大小"
            self.listbox.insert("end", f"{file_name}    ({file_size})")

    def _browse_out(self) -> None:
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.custom_dir_var.set(directory)
            self.out_var.set(CUSTOM_OUTPUT)
            self._sync_output_controls()

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.add_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.run_button.configure(state=state)

        self._sync_output_controls()
        if not running and self.out_var.get() == CUSTOM_OUTPUT:
            self.custom_dir_entry.configure(state="normal")
            self.browse_button.configure(state="normal")
        elif running:
            self.custom_dir_entry.configure(state="disabled")
            self.browse_button.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def _run(self) -> None:
        if not self.files:
            messagebox.showwarning("提示", "请先添加要压缩的图片。")
            return

        try:
            target_bytes = parse_size(self.size_var.get())
        except ValueError as error:
            messagebox.showerror("错误", str(error))
            return

        if target_bytes <= 0:
            messagebox.showerror("错误", "目标大小必须大于 0。")
            return

        output_mode = self.out_var.get()
        custom_dir = self.custom_dir_var.get().strip()
        if output_mode == CUSTOM_OUTPUT and (not custom_dir or not os.path.isdir(custom_dir)):
            messagebox.showerror("错误", "请选择一个有效的输出目录。")
            return

        self._set_running_state(True)
        self._clear_log()
        self.progress.configure(maximum=len(self.files), value=0)

        self._log("=" * 60)
        self._log(f"目标大小：{format_bytes(target_bytes)}")
        self._log(f"待处理文件：{len(self.files)}")
        self._log("=" * 60)

        success_count = 0
        failure_count = 0

        try:
            for index, src_path in enumerate(self.files, start=1):
                file_name = Path(src_path).name
                try:
                    output_ext, warning = resolve_output_extension(src_path, self.fmt_var.get())
                    output_dir = custom_dir if output_mode == CUSTOM_OUTPUT else str(Path(src_path).parent)
                    output_path = str(Path(output_dir) / f"{Path(src_path).stem}_compressed{output_ext}")
                    original_size = os.path.getsize(src_path)

                    result = compress_image(src_path, target_bytes, output_path)
                    compression_ratio = (
                        (result.actual_size / original_size) * 100 if original_size else 0
                    )
                    status = "OK" if result.actual_size <= target_bytes else "WARN"
                    resized_note = (
                        f"，缩放至 {format_scale(result.scale)}"
                        if result.resized
                        else ""
                    )
                    warning_note = f"；{warning}" if warning else ""

                    self._log(
                        f"[{status}] {file_name}\n"
                        f"  原始大小：{format_bytes(original_size)} -> 输出大小：{format_bytes(result.actual_size)}"
                        f" ({compression_ratio:.1f}%){resized_note}\n"
                        f"  输出格式：{result.format_name}，压缩参数：{result.quality_text}\n"
                        f"  输出文件：{Path(output_path).name}{warning_note}"
                    )
                    success_count += 1
                except UnidentifiedImageError:
                    self._log(f"[ERROR] {file_name} 不是可识别的图片文件。")
                    failure_count += 1
                except Exception as error:
                    self._log(f"[ERROR] {file_name} 压缩失败：{error}")
                    failure_count += 1

                self.progress.configure(value=index)
                self.update()
        finally:
            self._set_running_state(False)

        self._log("=" * 60)
        self._log(f"完成：成功 {success_count}，失败 {failure_count}")
        messagebox.showinfo("完成", f"处理结束：成功 {success_count}，失败 {failure_count}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
