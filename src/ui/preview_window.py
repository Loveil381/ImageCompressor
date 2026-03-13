"""Before/after image preview window."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageOps, ImageTk

from ..core.utils import format_bytes, get_file_size


class PreviewWindow(ttk.Toplevel):
    def __init__(
        self,
        parent: ttk.Widget,
        original_path: str,
        compressed_path: str,
        engine_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("预览对比 Preview")
        self.geometry("900x600")
        self.minsize(600, 400)

        self.original_path = original_path
        self.compressed_path = compressed_path
        self.engine_name = engine_name
        self.mode_var = tk.StringVar(value="slider")  # "slider" or "side_by_side"
        self.slider_pos = 0.5  # 0.0 to 1.0

        # Load and scale images to max 1920x1080 immediately
        MAX_W, MAX_H = 1920, 1080
        try:
            with Image.open(original_path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img_w, img_h = img.size
                scale = min(1.0, MAX_W / img_w, MAX_H / img_h)
                if scale < 1.0:
                    new_w, new_h = max(1, int(img_w * scale)), max(1, int(img_h * scale))
                    self._display_orig = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                else:
                    self._display_orig = img.copy()

            with Image.open(compressed_path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img_w, img_h = img.size
                scale = min(1.0, MAX_W / img_w, MAX_H / img_h)
                if scale < 1.0:
                    new_w, new_h = max(1, int(img_w * scale)), max(1, int(img_h * scale))
                    self._display_comp = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                else:
                    self._display_comp = img.copy()
        except Exception as e:
            ttk.Label(self, text=f"加载图片失败: {e}", bootstyle="danger").pack(padx=20, pady=20)
            return

        orig_size = get_file_size(original_path) or 0
        comp_size = get_file_size(compressed_path) or 0
        ratio = (comp_size / orig_size * 100) if orig_size else 0

        # Top panel for headers and mode switch
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        # Mode switch
        mode_frame = ttk.Frame(top_frame)
        mode_frame.pack(side="top", pady=(0, 10))
        ttk.Radiobutton(
            mode_frame,
            text="滑动对比",
            variable=self.mode_var,
            value="slider",
            command=self._on_mode_change,
            bootstyle="toolbutton",
        ).pack(side="left", padx=5)
        ttk.Radiobutton(
            mode_frame,
            text="并排对比",
            variable=self.mode_var,
            value="side_by_side",
            command=self._on_mode_change,
            bootstyle="toolbutton",
        ).pack(side="left", padx=5)

        # Headers frame
        header_frame = ttk.Frame(top_frame)
        header_frame.pack(fill="x")
        header_frame.columnconfigure(0, weight=1)
        header_frame.columnconfigure(1, weight=1)

        orig_header = ttk.Label(
            header_frame,
            text=f"原图 Original - {Path(self.original_path).name} ({format_bytes(orig_size)})",
            font=("", 10, "bold"),
        )
        orig_header.grid(row=0, column=0)

        comp_text = f"压缩后 Compressed - {Path(self.compressed_path).name} ({format_bytes(comp_size)} | {ratio:.1f}%)"
        if self.engine_name:
            comp_text += f" [{self.engine_name}]"
        comp_header = ttk.Label(
            header_frame, text=comp_text, font=("", 10, "bold"), bootstyle="success"
        )
        comp_header.grid(row=0, column=1)

        # Main canvas frame
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Canvases
        self.canvas_slider = tk.Canvas(self.canvas_frame, bg="#1a1d24", highlightthickness=0)
        self.canvas_slider.bind("<B1-Motion>", self._on_drag)
        self.canvas_slider.bind("<ButtonRelease-1>", self._on_drag)
        self.canvas_slider.bind("<Button-1>", self._on_drag)

        self.canvas_orig = tk.Canvas(self.canvas_frame, bg="#1a1d24", highlightthickness=0)
        self.canvas_comp = tk.Canvas(self.canvas_frame, bg="#1a1d24", highlightthickness=0)

        self.bind("<Configure>", self._on_resize)
        self._photo_slider = None
        self._photo_orig = None
        self._photo_comp = None

        self._on_mode_change()

    def _on_mode_change(self) -> None:
        if self.mode_var.get() == "slider":
            self.canvas_orig.pack_forget()
            self.canvas_comp.pack_forget()
            self.canvas_slider.pack(fill="both", expand=True)
            self.canvas_slider.config(cursor="sb_h_double_arrow")
        else:
            self.canvas_slider.pack_forget()
            self.canvas_orig.pack(side="left", fill="both", expand=True, padx=(0, 5))
            self.canvas_comp.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Trigger redraw
        if hasattr(self, "_resize_job"):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._redraw_images)

    def _on_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self.mode_var.get() == "slider":
            w = self.canvas_slider.winfo_width()
            h = self.canvas_slider.winfo_height()
            if w <= 0 or h <= 0 or not hasattr(self, "_display_orig"):
                return

            img_w, img_h = self._get_scaled_size(self._display_orig, w, h)
            img_x_start = w // 2 - img_w // 2

            # Map event X to image coordinates
            if img_w > 0:
                slider_pos = (event.x - img_x_start) / img_w
                self.slider_pos = max(0.0, min(1.0, slider_pos))
                self._draw_slider()

    def _on_resize(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        # Ignore resize events not triggering from main toplevel bounds if needed,
        # but typical to debounce all
        if hasattr(self, "_resize_job"):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._redraw_images)

    def _get_scaled_size(self, img: Image.Image, max_w: int, max_h: int) -> tuple[int, int]:
        img_w, img_h = img.size
        if img_w == 0 or img_h == 0:
            return 1, 1
        scale = min(max_w / img_w, max_h / img_h)
        return max(1, int(img_w * scale)), max(1, int(img_h * scale))

    def _redraw_images(self) -> None:
        if not hasattr(self, "_display_orig") or not hasattr(self, "_display_comp"):
            return

        if self.mode_var.get() == "slider":
            self._draw_slider()
        else:
            self._draw_side_by_side()

    def _draw_slider(self) -> None:
        w = max(10, self.canvas_slider.winfo_width())
        h = max(10, self.canvas_slider.winfo_height())

        new_w, new_h = self._get_scaled_size(self._display_orig, w, h)

        # Resize display images to canvas fit
        resized_orig = self._display_orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_comp = self._display_comp.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Calculate crop based on slider
        separator_x = int(new_w * self.slider_pos)

        # Base image
        base_img = Image.new("RGB", (new_w, new_h), color="#1a1d24")

        # Left part (Original)
        if separator_x > 0:
            crop_orig = resized_orig.crop((0, 0, separator_x, new_h))
            base_img.paste(crop_orig, (0, 0))

        # Right part (Compressed)
        if separator_x < new_w:
            crop_comp = resized_comp.crop((separator_x, 0, new_w, new_h))
            base_img.paste(crop_comp, (separator_x, 0))

        self._photo_slider = ImageTk.PhotoImage(base_img)
        self.canvas_slider.delete("all")

        # Center the image on canvas
        img_x = w // 2
        img_y = h // 2

        self.canvas_slider.create_image(img_x, img_y, image=self._photo_slider, anchor="center")

        # Draw separator line
        # The line x coordinate relative to canvas
        line_x = img_x - new_w // 2 + separator_x
        line_top = img_y - new_h // 2
        line_bottom = img_y + new_h // 2

        self.canvas_slider.create_line(line_x, line_top, line_x, line_bottom, fill="white", width=2)

        # Draw central handle
        handle_y = h // 2
        r = 6
        self.canvas_slider.create_oval(
            line_x - r, handle_y - r, line_x + r, handle_y + r, fill="white", outline="#333333"
        )
        # Left arrow
        self.canvas_slider.create_polygon(
            line_x - 3,
            handle_y,
            line_x - 1,
            handle_y - 3,
            line_x - 1,
            handle_y + 3,
            fill="#333333",
            outline="",
        )
        # Right arrow
        self.canvas_slider.create_polygon(
            line_x + 3,
            handle_y,
            line_x + 1,
            handle_y - 3,
            line_x + 1,
            handle_y + 3,
            fill="#333333",
            outline="",
        )

    def _draw_side_by_side(self) -> None:
        w_orig = max(10, self.canvas_orig.winfo_width())
        h_orig = max(10, self.canvas_orig.winfo_height())

        w_comp = max(10, self.canvas_comp.winfo_width())
        h_comp = max(10, self.canvas_comp.winfo_height())

        new_w_orig, new_h_orig = self._get_scaled_size(self._display_orig, w_orig, h_orig)
        new_w_comp, new_h_comp = self._get_scaled_size(self._display_comp, w_comp, h_comp)

        resized_orig = self._display_orig.resize((new_w_orig, new_h_orig), Image.Resampling.LANCZOS)
        resized_comp = self._display_comp.resize((new_w_comp, new_h_comp), Image.Resampling.LANCZOS)

        self._photo_orig = ImageTk.PhotoImage(resized_orig)
        self._photo_comp = ImageTk.PhotoImage(resized_comp)

        self.canvas_orig.delete("all")
        self.canvas_comp.delete("all")

        self.canvas_orig.create_image(
            w_orig // 2, h_orig // 2, image=self._photo_orig, anchor="center"
        )
        self.canvas_comp.create_image(
            w_comp // 2, h_comp // 2, image=self._photo_comp, anchor="center"
        )
