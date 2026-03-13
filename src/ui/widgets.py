"""No longer needed, as we use native ttkbootstrap widgets instead.
This file is kept for module structure parity or minimal helpers.
"""

from __future__ import annotations

import ttkbootstrap as ttk


class StatusBar(ttk.Label):
    """A status label anchored to the bottom of the window."""

    def __init__(self, parent: ttk.Widget, **kwargs: object) -> None:
        super().__init__(parent, text="", anchor="w", bootstyle="inverse-dark", **kwargs)

    def set(self, text: str) -> None:
        self.configure(text=text)
