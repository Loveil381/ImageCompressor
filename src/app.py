"""Main application window – wires all panels and the worker together."""

from __future__ import annotations

import os
import time
import queue as _queue
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from PIL import Image

try:
    import pystray
except ImportError:
    pystray = None

from .core.models import CompressionTask
from .core.utils import (
    CUSTOM_OUTPUT,
    format_bytes,
    format_scale,
    parse_size,
    enable_high_dpi_awareness,
    get_window_dpi,
)
from .i18n.strings import T
from .ui.file_panel import FilePanel
from .ui.log_panel import LogPanel
from .ui.settings_panel import SettingsPanel
from .ui.theme import APP_TITLE, APP_VERSION, FONT_RUN, FONT_DEFAULT
from .workers.compress_worker import CompressWorker

_POLL_INTERVAL_MS = 50  # How often the UI checks the worker queue


def _create_tray_icon_image() -> Image.Image:
    icon_path = Path("assets/icon.ico")
    if icon_path.exists():
        try:
            return Image.open(icon_path)
        except Exception:
            pass
    # Fallback to creating a simple image
    return Image.new("RGB", (64, 64), color=(79, 156, 249))


class App(ttk.Window):
    """Root window of the image compression tool."""

    def __init__(self) -> None:
        enable_high_dpi_awareness()
        super().__init__(themename="darkly")

        self._apply_scaling()

        self.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.resizable(True, True)
        self.minsize(620, 560)

        self._worker = CompressWorker()
        self._running = False
        self._start_time = 0.0

        self._build_ui()
        self._center_window()

        self._tray_icon = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Catch minimize to hide window
        self.bind("<Unmap>", self._on_unmap)

    # ------------------------------------------------------------------
    # Tray Icon
    # ------------------------------------------------------------------

    def _on_unmap(self, event: ttk.Event) -> None:  # type: ignore[type-arg]
        # Check if the event happens to the main window
        if event.widget == self and self.state() == "iconic":
            self._hide_to_tray()

    def _on_close(self) -> None:
        if self._running:
            # Cancel before closing
            self._worker.cancel()
        self.destroy()

    def _hide_to_tray(self) -> None:
        if pystray is None:
            return
        
        self.withdraw()  # hide the window completely
        
        if self._tray_icon is None:
            image = _create_tray_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem("显示 (Show)", self._show_from_tray, default=True),
                pystray.MenuItem("退出 (Quit)", self._quit_from_tray)
            )
            self._tray_icon = pystray.Icon("name", image, APP_TITLE, menu)
            
        import threading
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon: object, item: object) -> None:
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self.deiconify)
        self.after(0, lambda: self.state("normal"))

    def _quit_from_tray(self, icon: object, item: object) -> None:
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self._on_close)

    # ------------------------------------------------------------------
    # Scaling
    # ------------------------------------------------------------------

    def _apply_scaling(self) -> None:
        dpi = get_window_dpi(self)
        self._scale = min(max(dpi / 96.0, 1.0), 1.35)
        try:
            self.tk.call("tk", "scaling", dpi / 72.0)
        except ttk.TclError:
            pass

    def _px(self, v: int) -> int:
        return max(1, round(v * self._scale))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        pad = {"padx": self._px(12), "pady": self._px(5)}

        # --- Title bar ---
        title_frame = ttk.Frame(self)
        title_frame.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Label(
            title_frame, text=APP_TITLE, font=("Microsoft YaHei UI", 16, "bold"), bootstyle="inverse-dark"
        ).pack(side="left")
        ttk.Label(
            title_frame, text=f"v{APP_VERSION}", font=FONT_DEFAULT, bootstyle="secondary"
        ).pack(side="left", padx=(8, 0), pady=(4, 0))

        # --- File panel ---
        self._file_panel = FilePanel(self, ui_scale=self._scale)
        self._file_panel.grid(row=1, column=0, sticky="ew", **pad)

        # --- Settings panel ---
        self._settings = SettingsPanel(self, ui_scale=self._scale)
        self._settings.grid(row=2, column=0, sticky="ew", **pad)

        # --- Action buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, pady=(self._px(6), self._px(4)))

        self._run_btn = ttk.Button(
            btn_frame, text=T("start"), command=self._on_start, bootstyle="success", width=14
        )
        self._run_btn.pack(side="left", padx=(0, self._px(8)))

        self._preview_btn = ttk.Button(
            btn_frame, text="对比预览 (选定)", command=self._on_preview, bootstyle="info", width=16
        )
        self._preview_btn.pack(side="left", padx=(0, self._px(8)))

        self._cancel_btn = ttk.Button(
            btn_frame, text=T("cancel"), command=self._on_cancel, bootstyle="danger", width=8
        )
        self._cancel_btn.configure(state="disabled")
        self._cancel_btn.pack(side="left")

        # --- Progress bar ---
        self._progress = ttk.Progressbar(self, mode="determinate")
        self._progress.grid(row=4, column=0, sticky="ew", padx=self._px(12), pady=(0, self._px(4)))

        # --- Log panel ---
        self._log = LogPanel(self, height=9)
        self._log.grid(row=5, column=0, sticky="ew", **pad)

        # --- Status bar ---
        self._status = ttk.Label(self, text=T("status_ready"), font=FONT_DEFAULT, bootstyle="inverse-dark")
        self._status.grid(row=6, column=0, sticky="ew", padx=self._px(12), pady=(0, self._px(6)))

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _center_window(self) -> None:
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 620)
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ------------------------------------------------------------------
    # Run / Cancel
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        files = self._file_panel.files
        if not files:
            Messagebox.show_warning(T("err_no_files"), T("dlg_title"))
            return

        size_str = self._settings.size_var.get()
        try:
            target_bytes = parse_size(size_str)
        except ValueError as exc:
            Messagebox.show_error(T("err_invalid_size", detail=str(exc)), T("dlg_title"))
            return

        if target_bytes <= 0:
            Messagebox.show_error(T("err_zero_size"), T("dlg_title"))
            return

        output_mode = self._settings.out_var.get()
        custom_dir = self._settings.custom_dir_var.get().strip()
        if output_mode == CUSTOM_OUTPUT and (not custom_dir or not os.path.isdir(custom_dir)):
            Messagebox.show_error(T("err_invalid_dir"), T("dlg_title"))
            return

        tasks = [CompressionTask(src_path=p, target_bytes=target_bytes, output_path="") for p in files]

        self._set_running(True)
        self._log.clear()
        self._progress.configure(maximum=len(tasks), value=0)
        self._log.append_info(T("log_sep"))
        self._log.append_info(T("log_target", sz=format_bytes(target_bytes)))
        self._log.append_info(T("log_count", n=len(tasks)))
        self._log.append_info(T("log_sep"))
        self._status.configure(text=T("status_compressing"))

        self._start_time = time.time()

        self._worker.start(
            tasks=tasks,
            fmt_choice=self._settings.fmt_var.get(),
            output_mode=output_mode,
            custom_dir=custom_dir,
            strip_exif=self._settings.strip_exif_var.get(),
        )
        self.after(_POLL_INTERVAL_MS, self._poll_worker)

    def _on_preview(self) -> None:
        sel = self._file_panel._listbox.curselection()
        if not sel:
            Messagebox.show_warning("请在上面的列表中选中一张要预览的图片。", T("dlg_title"))
            return
            
        src_path = self._file_panel.files[sel[0]]
        fmt_choice = self._settings.fmt_var.get()
        out_mode = self._settings.out_var.get()
        custom_dir = self._settings.custom_dir_var.get().strip()
        
        from .core.utils import resolve_output_extension, build_output_path
        ext, _ = resolve_output_extension(src_path, fmt_choice)
        out_path = build_output_path(src_path, ext, out_mode, custom_dir)
        
        if not os.path.exists(out_path):
            Messagebox.show_warning(
                f"尚未生成压缩后文件，或者已被删除。\n预期路径：\n{out_path}", 
                T("dlg_title")
            )
            return
            
        from .ui.preview_window import PreviewWindow
        PreviewWindow(self, src_path, out_path)

    def _on_cancel(self) -> None:
        self._worker.cancel()

    # ------------------------------------------------------------------
    # Worker polling
    # ------------------------------------------------------------------

    def _poll_worker(self) -> None:
        while True:
            try:
                msg = self._worker.result_queue.get_nowait()
            except _queue.Empty:
                break

            mtype = msg["type"]

            if mtype == "progress":
                idx = msg["index"]
                total = msg["total"]
                self._progress.configure(value=idx - 1)
                
                # Calculate ETA
                elapsed = time.time() - self._start_time
                if elapsed > 0 and idx > 1:
                    speed = (idx - 1) / elapsed
                    eta_s = (total - (idx - 1)) / speed
                    speed_str = f" ({speed:.1f} 文件/秒，预计剩余 {eta_s:.1f}秒)"
                else:
                    speed_str = ""

                self._status.configure(
                    text=f"{T('status_compressing')}  {idx}/{total}  —  {msg['name']}{speed_str}"
                )

            elif mtype == "result":
                r = msg["result"]
                orig = msg["original_size"]
                ratio = (r.actual_size / orig * 100) if orig else 0.0
                scale_note = T("scale_note", pct=format_scale(r.scale)) if r.resized else ""
                warn_note = f"；{r.warning}" if r.warning else ""
                
                out_name = Path(msg["output_path"]).name
                
                size_str = self._settings.size_var.get()
                tb = parse_size(size_str) if size_str else r.actual_size + 1
                target_met = r.actual_size <= tb
                
                text = T(
                    "log_ok" if target_met else "log_warn",
                    name=msg["name"],
                    orig=format_bytes(orig),
                    out=format_bytes(r.actual_size),
                    ratio=ratio,
                    scale=scale_note,
                    fmt=r.format_name,
                    quality=r.quality_text,
                    outname=out_name,
                    warn=warn_note,
                )
                if target_met:
                    self._log.append_ok(text)
                else:
                    self._log.append_warn(text)

            elif mtype == "error":
                from PIL import UnidentifiedImageError
                exc = msg["exc"]
                if isinstance(exc, UnidentifiedImageError):
                    self._log.append_error(T("log_error_unrecognised", name=msg["name"]))
                else:
                    self._log.append_error(T("log_error_generic", name=msg["name"], err=str(exc)))

            elif mtype == "done":
                self._progress.configure(value=self._progress["maximum"])
                ok = msg["success"]
                fail = msg["failure"]
                self._log.append_sep()
                self._log.append_info(T("log_summary", ok=ok, fail=fail))
                self._status.configure(text=T("status_done", ok=ok, fail=fail))
                self._set_running(False)
                Messagebox.show_info(T("status_done", ok=ok, fail=fail), T("dlg_done_title"))
                return

            elif mtype == "cancelled":
                self._log.append_warn(T("status_cancelled"))
                self._status.configure(text=T("status_cancelled"))
                self._set_running(False)
                return

        self.after(_POLL_INTERVAL_MS, self._poll_worker)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._running = running
        run_state = "disabled" if running else "normal"
        cancel_state = "normal" if running else "disabled"
        self._run_btn.configure(state=run_state)
        self._cancel_btn.configure(state=cancel_state)
        self._file_panel.set_enabled(not running)
        self._settings.set_enabled(not running)

