"""Before/after image preview window."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageTk, ImageOps

from ..core.utils import format_bytes, get_file_size


class PreviewWindow(ttk.Toplevel):
    def __init__(self, parent: ttk.Widget, original_path: str, compressed_path: str) -> None:
        super().__init__(parent)
        self.title("预览对比 Preview")
        self.geometry("900x600")
        self.minsize(600, 400)

        self.original_path = original_path
        self.compressed_path = compressed_path

        try:
            with Image.open(original_path) as img:
                self.img_orig = ImageOps.exif_transpose(img).convert("RGB")
            with Image.open(compressed_path) as img:
                self.img_comp = ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            ttk.Label(self, text=f"加载图片失败: {e}", bootstyle="danger").pack(padx=20, pady=20)
            return

        orig_size = get_file_size(original_path) or 0
        comp_size = get_file_size(compressed_path) or 0
        ratio = (comp_size / orig_size * 100) if orig_size else 0

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Headers
        orig_header = ttk.Label(self, text=f"原图 Original - {Path(original_path).name} ({format_bytes(orig_size)})", font=("", 10, "bold"))
        orig_header.grid(row=0, column=0, pady=10)

        comp_header = ttk.Label(self, text=f"压缩后 Compressed - {Path(compressed_path).name} ({format_bytes(comp_size)} | {ratio:.1f}%)", font=("", 10, "bold"), bootstyle="success")
        comp_header.grid(row=0, column=1, pady=10)

        # Canvases for images
        self.canvas_orig = tk.Canvas(self, bg="#1a1d24", highlightthickness=0)
        self.canvas_orig.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.canvas_comp = tk.Canvas(self, bg="#1a1d24", highlightthickness=0)
        self.canvas_comp.grid(row=1, column=1, sticky="nsew", padx=10, pady=(0, 10))

        self.bind("<Configure>", self._on_resize)
        self._photo_orig = None
        self._photo_comp = None

    def _on_resize(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        # Avoid redrawing too often
        self.after_cancel(getattr(self, "_resize_job", " "))
        self._resize_job = self.after(100, self._redraw_images)

    def _redraw_images(self) -> None:
        w = max(10, self.canvas_orig.winfo_width())
        h = max(10, self.canvas_orig.winfo_height())

        img_w, img_h = self.img_orig.size
        # scale to fit
        scale = min(w / img_w, h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        resized_orig = self.img_orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_comp = self.img_comp.resize((new_w, new_h), Image.Resampling.LANCZOS)

        self._photo_orig = ImageTk.PhotoImage(resized_orig)
        self._photo_comp = ImageTk.PhotoImage(resized_comp)

        self.canvas_orig.delete("all")
        self.canvas_comp.delete("all")

        self.canvas_orig.create_image(w // 2, h // 2, image=self._photo_orig, anchor="center")
        self.canvas_comp.create_image(w // 2, h // 2, image=self._photo_comp, anchor="center")

