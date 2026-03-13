"""File list panel with drag-and-drop support and right-click menu."""

from __future__ import annotations

import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, Menu

import ttkbootstrap as ttk

from ..core.utils import SUPPORTED_INPUT_TYPES, format_bytes, get_file_size
from ..i18n.strings import T
from .theme import FONT_DEFAULT, FONT_MONO_SM

_IMAGE_EXTS = frozenset(".jpg .jpeg .png .webp .bmp .gif .tif .tiff".split())


def _collect_images_from_path(path: str) -> list[str]:
    p = Path(path)
    if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
        return [str(p)]
    if p.is_dir():
        found = []
        for item in sorted(p.rglob("*")):
            if item.is_file() and item.suffix.lower() in _IMAGE_EXTS:
                found.append(str(item))
        return found
    return []


class FilePanel(ttk.Frame):
    """Panel containing the file list, drag-drop zone, file management, right click menu."""

    def __init__(self, parent: ttk.Widget, ui_scale: float = 1.0, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self._scale = ui_scale
        self.files: list[str] = []
        self._build()
        self._setup_right_click()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(self, text=T("panel_files"))
        card.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        card.columnconfigure(0, weight=1)

        # Drop hint label
        self._drop_label = ttk.Label(
            card,
            text=T("drop_hint"),
            font=FONT_DEFAULT,
            bootstyle="secondary",
        )
        self._drop_label.grid(row=0, column=0, columnspan=2, pady=6)

        # Listbox + scrollbar
        self._listbox = tk.Listbox(
            card,
            width=60,
            height=7,
            selectmode=tk.EXTENDED,
            font=FONT_MONO_SM,
        )
        _scroll = ttk.Scrollbar(card, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=_scroll.set)
        self._listbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        _scroll.grid(row=1, column=1, sticky="ns", pady=4)
        self._listbox.grid_remove()

        # Button row
        btn_row = ttk.Frame(self)
        btn_row.grid(row=1, column=0, sticky="w", pady=(4, 0))

        px = self._px(6)
        ttk.Button(
            btn_row, text=T("add_files"), command=self._add_files, bootstyle="primary"
        ).pack(side="left", padx=(0, px))
        ttk.Button(
            btn_row, text=T("add_folder"), command=self._add_folder, bootstyle="secondary"
        ).pack(side="left", padx=(0, px))
        
        self._remove_btn = ttk.Button(
            btn_row, text=T("remove_selected"), command=self._remove_selected, bootstyle="secondary"
        )
        self._remove_btn.pack(side="left", padx=(0, px))
        
        self._clear_btn = ttk.Button(
            btn_row, text=T("clear_list"), command=self._clear_files, bootstyle="danger"
        )
        self._clear_btn.pack(side="left")

        self._setup_dnd(card)

    def _setup_dnd(self, target: ttk.Widget) -> None:
        try:
            from tkinterdnd2 import DND_FILES  # type: ignore[import]
            for widget in (target, self._listbox, self._drop_label):
                widget.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
                widget.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _setup_right_click(self) -> None:
        self._menu = Menu(self._listbox, tearoff=0)
        self._menu.add_command(label="打开所在目录", command=self._open_location)
        self._menu.add_command(label="预览原图", command=self._preview_original)
        self._menu.add_separator()
        self._menu.add_command(label="从列表中移除", command=self._remove_selected)

        # Right click bind
        bind_seq = "<Button-2>" if self.tk.call("tk", "windowingsystem") == "aqua" else "<Button-3>"
        self._listbox.bind(bind_seq, self._on_right_click)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._remove_btn.configure(state=state)
        self._clear_btn.configure(state=state)
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                for btn in child.winfo_children():
                    try:
                        btn.configure(state=state)  # type: ignore[call-arg]
                    except tk.TclError:
                        pass

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _open_location(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        path = self.files[sel[0]]
        parent = os.path.dirname(path)
        if os.name == "nt":
            os.startfile(parent)
        elif os.name == "posix":
            subprocess.run(["open", parent])

    def _preview_original(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        path = self.files[sel[0]]
        if os.name == "nt":
            os.startfile(path)
        elif os.name == "posix":
            subprocess.run(["open", path])

    def _on_right_click(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        # Select the item under cursor if not already selected
        idx = self._listbox.nearest(event.y)
        if getattr(self._listbox, "size")() == 0:
            return
        if getattr(self._listbox, "bbox")(idx):
            if idx not in self._listbox.curselection():
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(idx)
            self._menu.tk_popup(event.x_root, event.y_root)

    def _on_drop(self, event: object) -> None:
        try:
            data = str(getattr(event, "data", ""))
            raw_paths: list[str] = []
            current = ""
            in_braces = False
            for ch in data:
                if ch == "{":
                    in_braces = True
                elif ch == "}":
                    in_braces = False
                    raw_paths.append(current.strip())
                    current = ""
                elif ch == " " and not in_braces:
                    if current:
                        raw_paths.append(current.strip())
                        current = ""
                else:
                    current += ch
            if current.strip():
                raw_paths.append(current.strip())

            changed = False
            for raw in raw_paths:
                for img_path in _collect_images_from_path(raw):
                    if img_path not in self.files:
                        self.files.append(img_path)
                        changed = True
            if changed:
                self._refresh()
        except Exception:
            pass

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title=T("dlg_select_images"),
            filetypes=[
                (T("file_type_images"), SUPPORTED_INPUT_TYPES),
                (T("file_type_all"), "*.*"),
            ],
        )
        changed = False
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                changed = True
        if changed:
            self._refresh()

    def _add_folder(self) -> None:
        directory = filedialog.askdirectory(title=T("dlg_select_images"))
        if not directory:
            return
        changed = False
        for img_path in _collect_images_from_path(directory):
            if img_path not in self.files:
                self.files.append(img_path)
                changed = True
        if changed:
            self._refresh()

    def _remove_selected(self) -> None:
        indices = list(self._listbox.curselection())
        if not indices:
            return
        for idx in reversed(indices):
            del self.files[idx]
        self._refresh()

    def _clear_files(self) -> None:
        self.files.clear()
        self._refresh()

    def _refresh(self) -> None:
        self._listbox.delete(0, "end")
        if self.files:
            self._drop_label.grid_remove()
            self._listbox.grid()
            for path in self.files:
                name = Path(path).name
                size = get_file_size(path)
                size_str = format_bytes(size) if size else T("file_size_unknown")
                self._listbox.insert("end", f"{name}    ({size_str})")
        else:
            self._listbox.grid_remove()
            self._drop_label.grid()

    def _px(self, v: int) -> int:
        return max(1, round(v * self._scale))
