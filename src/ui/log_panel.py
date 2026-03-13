"""Log output panel."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk

from ..i18n.strings import T
from .theme import FONT_MONO_SM


class LogPanel(ttk.Frame):
    """Scrollable read-only log panel."""

    def __init__(self, parent: ttk.Widget, height: int = 10, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(self, text=T("panel_log"))
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)

        self._text = tk.Text(
            card,
            height=height,
            font=FONT_MONO_SM,
            state="disabled",
            wrap="none",
        )
        _scroll_y = ttk.Scrollbar(card, orient="vertical", command=self._text.yview)
        _scroll_x = ttk.Scrollbar(card, orient="horizontal", command=self._text.xview)
        self._text.configure(
            yscrollcommand=_scroll_y.set,
            xscrollcommand=_scroll_x.set,
        )
        self._text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        _scroll_y.grid(row=0, column=1, sticky="ns", pady=4)
        _scroll_x.grid(row=1, column=0, sticky="ew", padx=4)

        # Match darkly theme roughly for Text inside frame if needed
        # We can just leave it to default Tk Text style or style it manually
        self._text.configure(bg="#222", fg="#ddd", insertbackground="white")

        self._text.tag_configure("ok", foreground="#2ce079")
        self._text.tag_configure("warn", foreground="#f39c12")
        self._text.tag_configure("error", foreground="#e74c3c")
        self._text.tag_configure("info", foreground="#3498db")
        self._text.tag_configure("sep", foreground="#555")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def append(self, message: str, tag: str = "") -> None:
        self._text.configure(state="normal")
        if tag:
            self._text.insert("end", message + "\n", tag)
        else:
            self._text.insert("end", message + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def append_ok(self, message: str) -> None:
        self.append(message, "ok")

    def append_warn(self, message: str) -> None:
        self.append(message, "warn")

    def append_error(self, message: str) -> None:
        self.append(message, "error")

    def append_info(self, message: str) -> None:
        self.append(message, "info")

    def append_sep(self) -> None:
        self.append("─" * 64, "sep")
