"""Settings panel: target size, format, output location, EXIF option."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as ttk

from ..core.utils import CUSTOM_OUTPUT, ORIGINAL_FORMAT
from ..i18n.strings import T
from .theme import FONT_DEFAULT, FONT_MONO


class SettingsPanel(ttk.Frame):
    def __init__(self, parent: ttk.Widget, ui_scale: float = 1.0, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self._scale = ui_scale

        self.size_var = ttk.StringVar(value="500KB")
        self.fmt_var = ttk.StringVar(value=ORIGINAL_FORMAT)
        self.out_var = ttk.StringVar(value="same_dir")
        self.custom_dir_var = ttk.StringVar()
        self.strip_exif_var = tk.BooleanVar(value=False)

        self._build()
        self._sync_output_controls()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(self, text=T("panel_settings"))
        card.grid(row=0, column=0, sticky="ew")

        # --- Target size row ---
        row_size = ttk.Frame(card)
        row_size.grid(row=0, column=0, sticky="w", pady=(2, 4), padx=6)

        ttk.Label(row_size, text=T("label_target_size")).pack(side="left")
        ttk.Entry(
            row_size, textvariable=self.size_var, width=14, font=FONT_MONO
        ).pack(side="left", padx=(4, 8))
        ttk.Label(row_size, text=T("size_hint"), bootstyle="secondary").pack(side="left")

        # --- Format row ---
        row_fmt = ttk.Frame(card)
        row_fmt.grid(row=1, column=0, sticky="w", pady=2, padx=6)

        ttk.Label(row_fmt, text=T("label_format")).pack(side="left")

        for label_key, value in (
            ("format_original", ORIGINAL_FORMAT),
            ("JPEG", ".jpg"),
            ("PNG", ".png"),
            ("WebP", ".webp"),
        ):
            display = label_key if label_key in ("JPEG", "PNG", "WebP") else T(label_key)
            ttk.Radiobutton(
                row_fmt, text=display, variable=self.fmt_var, value=value
            ).pack(side="left", padx=6)

        # --- Output row ---
        row_out = ttk.Frame(card)
        row_out.grid(row=2, column=0, sticky="w", pady=2, padx=6)

        ttk.Label(row_out, text=T("label_output")).pack(side="left")

        ttk.Radiobutton(
            row_out, text=T("output_same_dir"), variable=self.out_var,
            value="same_dir", command=self._sync_output_controls
        ).pack(side="left", padx=(0, 6))

        ttk.Radiobutton(
            row_out, text=T("output_custom_dir"), variable=self.out_var,
            value=CUSTOM_OUTPUT, command=self._sync_output_controls
        ).pack(side="left", padx=(0, 4))

        self._custom_entry = ttk.Entry(
            row_out, textvariable=self.custom_dir_var, width=22, font=FONT_MONO
        )
        self._custom_entry.pack(side="left", padx=(0, 4))

        self._browse_btn = ttk.Button(
            row_out, text=T("browse"), command=self._browse_output,
            bootstyle="secondary", width=6
        )
        self._browse_btn.pack(side="left")

        # --- EXIF row ---
        row_exif = ttk.Frame(card)
        row_exif.grid(row=3, column=0, sticky="w", pady=(4, 4), padx=6)

        ttk.Checkbutton(
            row_exif, text=T("strip_exif"), variable=self.strip_exif_var,
            bootstyle="round-toggle"
        ).pack(side="left")

    def _sync_output_controls(self) -> None:
        state = "normal" if self.out_var.get() == CUSTOM_OUTPUT else "disabled"
        self._custom_entry.configure(state=state)
        self._browse_btn.configure(state=state)

    def _browse_output(self) -> None:
        directory = filedialog.askdirectory(title=T("dlg_select_folder"))
        if directory:
            self.custom_dir_var.set(directory)
            self.out_var.set(CUSTOM_OUTPUT)
            self._sync_output_controls()

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._custom_entry.configure(state=state if self.out_var.get() == CUSTOM_OUTPUT else "disabled")
        self._browse_btn.configure(state=state if self.out_var.get() == CUSTOM_OUTPUT else "disabled")
