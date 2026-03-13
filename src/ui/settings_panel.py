"""Settings panel: target size, format, output location, EXIF option."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

import ttkbootstrap as ttk

from ..core.models import CompressionConfig
from ..core.utils import CUSTOM_OUTPUT, ORIGINAL_FORMAT
from ..i18n.strings import T, get_language
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
        self.engine_preference_var = ttk.StringVar(value="auto")
        self._engine_choices: list[tuple[str, str]] = [
            (T("engine_pref_auto"), "auto"),
            (T("engine_pref_pillow"), "pillow"),
        ]

        if self._has_vips():
            self._engine_choices.insert(1, (T("engine_pref_vips"), "vips"))

        self._engine_label_to_value = dict(self._engine_choices)
        self._engine_value_to_label = {value: label for label, value in self._engine_choices}
        self._engine_display_var = ttk.StringVar(
            value=self._engine_value_to_label.get("auto", self._engine_choices[0][0])
        )

        self.watch_enabled_var = tk.BooleanVar(value=False)
        self.watch_recursive_var = tk.BooleanVar(value=False)
        self.watch_dirs: list[str] = []

        self._build()
        self._sync_output_controls()
        self._sync_watch_controls()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(self, text=T("panel_settings"))
        card.grid(row=0, column=0, sticky="ew")

        # --- Target size row ---
        row_size = ttk.Frame(card)
        row_size.grid(row=0, column=0, sticky="w", pady=(2, 4), padx=6)

        ttk.Label(row_size, text=T("label_target_size")).pack(side="left")
        ttk.Entry(row_size, textvariable=self.size_var, width=14, font=FONT_MONO).pack(
            side="left", padx=(4, 8)
        )
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
            ("AVIF", ".avif"),
        ):
            display = label_key if label_key in ("JPEG", "PNG", "WebP", "AVIF") else T(label_key)
            ttk.Radiobutton(row_fmt, text=display, variable=self.fmt_var, value=value).pack(
                side="left", padx=6
            )

        # --- Output row ---
        row_out = ttk.Frame(card)
        row_out.grid(row=2, column=0, sticky="w", pady=2, padx=6)

        ttk.Label(row_out, text=T("label_output")).pack(side="left")

        ttk.Radiobutton(
            row_out,
            text=T("output_same_dir"),
            variable=self.out_var,
            value="same_dir",
            command=self._sync_output_controls,
        ).pack(side="left", padx=(0, 6))

        ttk.Radiobutton(
            row_out,
            text=T("output_custom_dir"),
            variable=self.out_var,
            value=CUSTOM_OUTPUT,
            command=self._sync_output_controls,
        ).pack(side="left", padx=(0, 4))

        self._custom_entry = ttk.Entry(
            row_out, textvariable=self.custom_dir_var, width=22, font=FONT_MONO
        )
        self._custom_entry.pack(side="left", padx=(0, 4))

        self._browse_btn = ttk.Button(
            row_out, text=T("browse"), command=self._browse_output, bootstyle="secondary", width=6
        )
        self._browse_btn.pack(side="left")

        # --- EXIF row ---
        row_exif = ttk.Frame(card)
        row_exif.grid(row=3, column=0, sticky="w", pady=(4, 4), padx=6)

        ttk.Checkbutton(
            row_exif, text=T("strip_exif"), variable=self.strip_exif_var, bootstyle="round-toggle"
        ).pack(side="left")

        # --- Engine preference row ---
        row_engine = ttk.Frame(card)
        row_engine.grid(row=4, column=0, sticky="w", pady=(4, 4), padx=6)
        ttk.Label(row_engine, text=T("label_engine_preference")).pack(side="left")
        self._engine_combo = ttk.Combobox(
            row_engine,
            textvariable=self._engine_display_var,
            values=[label for label, _ in self._engine_choices],
            state="readonly",
            width=20,
            font=FONT_DEFAULT,
        )
        self._engine_combo.pack(side="left", padx=(6, 0))
        self._engine_combo.bind("<<ComboboxSelected>>", self._on_engine_change)

        # --- Watch Mode row ---
        row_watch = ttk.Frame(card)
        row_watch.grid(row=5, column=0, sticky="w", pady=(4, 4), padx=6)
        
        ttk.Checkbutton(
            row_watch, text=T("watch_mode_enable"), variable=self.watch_enabled_var, 
            bootstyle="round-toggle", command=self._on_watch_toggle
        ).pack(side="left")
        
        self.watch_dirs_frame = ttk.Frame(card)
        self.watch_dirs_frame.grid(row=6, column=0, sticky="nsew", padx=24, pady=(0, 4))
        self.watch_dirs_frame.columnconfigure(0, weight=1)
        
        watch_top = ttk.Frame(self.watch_dirs_frame)
        watch_top.pack(fill="x", pady=(0, 4))
        
        ttk.Button(watch_top, text=T("watch_add_dir"), command=self._watch_add_dir, bootstyle="secondary-outline").pack(side="left")
        ttk.Button(watch_top, text=T("watch_clear_dirs"), command=self._watch_clear_dirs, bootstyle="secondary-outline").pack(side="left", padx=4)
        
        ttk.Checkbutton(
            watch_top, text=T("watch_recursive"), variable=self.watch_recursive_var, command=self._on_watch_config_change
        ).pack(side="right")
        
        self.watch_dirs_listbox = tk.Listbox(self.watch_dirs_frame, height=3, font=FONT_MONO)
        self.watch_dirs_listbox.pack(fill="x", expand=True)

    def _sync_watch_controls(self) -> None:
        if self.watch_enabled_var.get():
            self.watch_dirs_frame.grid()
        else:
            self.watch_dirs_frame.grid_remove()
            
    def _on_watch_toggle(self) -> None:
        self._sync_watch_controls()
        self._on_watch_config_change()
            
    def _watch_add_dir(self) -> None:
        directory = filedialog.askdirectory(title=T("watch_add_dir"))
        if directory and directory not in self.watch_dirs:
            self.watch_dirs.append(directory)
            self.watch_dirs_listbox.insert("end", directory)
            self._on_watch_config_change()

    def _watch_clear_dirs(self) -> None:
        self.watch_dirs.clear()
        self.watch_dirs_listbox.delete(0, "end")
        self._on_watch_config_change()

    def _on_watch_config_change(self) -> None:
        self.event_generate("<<WatchConfigChanged>>")

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
        self._custom_entry.configure(
            state=state if self.out_var.get() == CUSTOM_OUTPUT else "disabled"
        )
        self._browse_btn.configure(
            state=state if self.out_var.get() == CUSTOM_OUTPUT else "disabled"
        )
        self._engine_combo.configure(state="readonly" if enabled else "disabled")

    def apply_config(self, config: CompressionConfig) -> None:
        self.size_var.set(config.target_size_str)
        self.fmt_var.set(config.format_choice)
        self.out_var.set(config.output_mode)
        self.custom_dir_var.set(config.custom_dir)
        self.strip_exif_var.set(config.strip_exif)
        pref = (
            config.engine_preference
            if config.engine_preference in self._engine_value_to_label
            else "auto"
        )
        if pref == "vips" and not self._has_vips():
            pref = "auto"
        self.engine_preference_var.set(pref)
        self._engine_display_var.set(
            self._engine_value_to_label.get(pref, self._engine_choices[0][0])
        )
        self.watch_enabled_var.set(config.watch_enabled)
        self.watch_recursive_var.set(config.watch_recursive)
        
        self.watch_dirs.clear()
        self.watch_dirs.extend(config.watch_dirs)
        self.watch_dirs_listbox.delete(0, "end")
        for d in self.watch_dirs:
            self.watch_dirs_listbox.insert("end", d)
            
        self._sync_output_controls()
        self._sync_watch_controls()

    def get_config(self) -> CompressionConfig:
        return CompressionConfig(
            target_size_str=self.size_var.get().strip() or "500KB",
            format_choice=self.fmt_var.get(),
            output_mode=self.out_var.get(),
            custom_dir=self.custom_dir_var.get().strip(),
            strip_exif=bool(self.strip_exif_var.get()),
            language=get_language(),
            engine_preference=self.engine_preference_var.get() or "auto",
            watch_enabled=bool(self.watch_enabled_var.get()),
            watch_dirs=list(self.watch_dirs),
            watch_recursive=bool(self.watch_recursive_var.get()),
        )

    def _on_engine_change(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        label = self._engine_display_var.get()
        self.engine_preference_var.set(self._engine_label_to_value.get(label, "auto"))

    @staticmethod
    def _has_vips() -> bool:
        try:
            import pyvips  # noqa: F401

            return True
        except ImportError:
            return False
