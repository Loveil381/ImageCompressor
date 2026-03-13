"""Main application window – wires all panels and the worker together."""

from __future__ import annotations

import os
import queue as _queue
import threading
import time
from contextlib import suppress
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image
from ttkbootstrap.dialogs import Messagebox

try:
    import pystray
except ImportError:
    pystray = None

from .core.compressor import get_engine_name
from .core.config_manager import load_config, save_config
from .core.models import CompressionTask
from .core.utils import (
    CUSTOM_OUTPUT,
    enable_high_dpi_awareness,
    format_bytes,
    get_window_dpi,
    parse_size,
)
from .i18n.strings import T, set_language
from .ui.file_panel import FilePanel
from .ui.log_panel import LogPanel
from .ui.settings_panel import SettingsPanel
from .ui.theme import APP_TITLE, APP_VERSION, FONT_DEFAULT
from .workers.compress_worker import CompressWorker
from .workers.message_handler import MessageHandler
from .workers.watch_worker import WatchWorker

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
        self._watch_compress_worker = CompressWorker()
        self._watch_worker = WatchWorker(on_image_found=self._on_watch_image_found)
        self._running = False
        self._msg_handler: MessageHandler | None = None
        self._watch_msg_handler: MessageHandler | None = None
        self._config = load_config()
        try:
            set_language(self._config.language)
        except ValueError:
            set_language("zh")

        self._build_ui()
        self._settings.apply_config(self._config)
        self._settings.bind("<<WatchConfigChanged>>", self._on_watch_config_changed)
        self._center_window()
        self.apply_watch_config()

        self._tray_icon = None
        self._tray_running = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap)

    # ------------------------------------------------------------------
    # Tray Icon
    # ------------------------------------------------------------------

    def _on_unmap(self, event: ttk.Event) -> None:  # type: ignore[type-arg]
        if event.widget == self and self.state() == "iconic":
            self._hide_to_tray()

    def _on_close(self) -> None:
        if self._running:
            self._worker.cancel()
        self._watch_worker.stop()
        if self._watch_compress_worker.is_alive():
            self._watch_compress_worker.cancel()
            
        if self._tray_icon:
            self._tray_icon.stop()
        
        # Grab current UI settings and sync to config
        current_config = self._settings.get_config()
        self._config.target_size_str = current_config.target_size_str
        self._config.format_choice = current_config.format_choice
        self._config.output_mode = current_config.output_mode
        self._config.custom_dir = current_config.custom_dir
        self._config.strip_exif = current_config.strip_exif
        self._config.engine_preference = current_config.engine_preference
        save_config(self._config)
        self.destroy()

    def _hide_to_tray(self) -> None:
        if pystray is None:
            return
        self.withdraw()
        if self._tray_icon is None:
            image = _create_tray_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem("显示 (Show)", self._show_from_tray, default=True),
                pystray.MenuItem("退出 (Quit)", self._quit_from_tray),
            )
            self._tray_icon = pystray.Icon("name", image, APP_TITLE, menu)
        if self._tray_running:
            return
        self._tray_running = True
        threading.Thread(target=self._run_tray_icon, daemon=True).start()

    def _run_tray_icon(self) -> None:
        try:
            if self._tray_icon:
                self._tray_icon.run()
        finally:
            self._tray_running = False

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
        with suppress(ttk.TclError):
            self.tk.call("tk", "scaling", dpi / 72.0)

    def _px(self, v: int) -> int:
        return max(1, round(v * self._scale))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        pad = {"padx": self._px(12), "pady": self._px(5)}

        title_frame = ttk.Frame(self)
        title_frame.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Label(
            title_frame,
            text=APP_TITLE,
            font=("Microsoft YaHei UI", 16, "bold"),
            bootstyle="inverse-dark",
        ).pack(side="left")
        ttk.Label(
            title_frame, text=f"v{APP_VERSION}", font=FONT_DEFAULT, bootstyle="secondary"
        ).pack(side="left", padx=(8, 0), pady=(4, 0))

        self._file_panel = FilePanel(self, ui_scale=self._scale)
        self._file_panel.grid(row=1, column=0, sticky="ew", **pad)

        self._settings = SettingsPanel(self, ui_scale=self._scale)
        self._settings.grid(row=2, column=0, sticky="ew", **pad)

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

        self._progress = ttk.Progressbar(self, mode="determinate")
        self._progress.grid(row=4, column=0, sticky="ew", padx=self._px(12), pady=(0, self._px(4)))

        self._log = LogPanel(self, height=9)
        self._log.grid(row=5, column=0, sticky="ew", **pad)

        self._status = ttk.Label(
            self, text=T("status_ready"), font=FONT_DEFAULT, bootstyle="inverse-dark"
        )
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

        tasks = [
            CompressionTask(src_path=p, target_bytes=target_bytes, output_path="") for p in files
        ]

        self._set_running(True)
        self._log.clear()
        self._progress.configure(maximum=len(tasks), value=0)
        self._log.append_info(T("log_sep"))
        engine_preference = self._settings.engine_preference_var.get()
        self._log.append_info(f"[{T('log_engine', engine=get_engine_name(engine_preference))}]")
        self._log.append_info(T("log_target", sz=format_bytes(target_bytes)))
        self._log.append_info(T("log_count", n=len(tasks)))
        self._log.append_info(T("log_sep"))
        self._status.configure(text=T("status_compressing"))

        self._msg_handler = MessageHandler(
            log=self._log,
            progress=self._progress,
            status=self._status,
            target_bytes=target_bytes,
            start_time=time.time(),
            on_complete=self._on_batch_complete,
            on_cancel=self._on_batch_cancel,
        )

        self._worker.start(
            tasks=tasks,
            fmt_choice=self._settings.fmt_var.get(),
            output_mode=output_mode,
            custom_dir=custom_dir,
            strip_exif=self._settings.strip_exif_var.get(),
            engine_preference=engine_preference,
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
        from .core.utils import build_output_path, resolve_output_extension

        ext, _ = resolve_output_extension(src_path, fmt_choice)
        out_path = build_output_path(src_path, ext, out_mode, custom_dir)
        if not os.path.exists(out_path):
            Messagebox.show_warning(
                f"尚未生成压缩后文件，或者已被删除。\n预期路径：\n{out_path}", T("dlg_title")
            )
            return
        from .ui.preview_window import PreviewWindow

        PreviewWindow(self, src_path, out_path)

    def _on_cancel(self) -> None:
        self._worker.cancel()

    # ------------------------------------------------------------------
    # Worker polling  (< 15 lines – routing delegated to MessageHandler)
    # ------------------------------------------------------------------

    def _poll_worker(self) -> None:
        while True:
            try:
                msg = self._worker.result_queue.get_nowait()
            except _queue.Empty:
                break
            if self._msg_handler and self._msg_handler.handle(msg):
                return  # terminal message (done / cancelled)
        self.after(_POLL_INTERVAL_MS, self._poll_worker)

    def _poll_watch_worker(self) -> None:
        while True:
            try:
                msg = self._watch_compress_worker.result_queue.get_nowait()
            except _queue.Empty:
                break
            if self._watch_msg_handler and self._watch_msg_handler.handle(msg):
                return
        if self._watch_compress_worker.is_alive():
            self.after(_POLL_INTERVAL_MS, self._poll_watch_worker)

    def apply_watch_config(self) -> None:
        if self._config.watch_enabled:
            self._watch_worker.start(
                directories=self._config.watch_dirs,
                recursive=self._config.watch_recursive
            )
            self._log.append_info(T("watch_started") + f": {len(self._config.watch_dirs)} dirs")
        else:
            if self._watch_worker.is_running():
                self._watch_worker.stop()
                self._log.append_info(T("watch_stopped"))

    def _on_watch_config_changed(self, event: tk.Event) -> None:  # type: ignore[type-arg, unused-ignore]
        current_config = self._settings.get_config()
        self._config.watch_enabled = current_config.watch_enabled
        self._config.watch_dirs = current_config.watch_dirs
        self._config.watch_recursive = current_config.watch_recursive
        self.apply_watch_config()

    def _on_watch_image_found(self, path: str) -> None:
        try:
            target_bytes = parse_size(self._settings.size_var.get())
        except ValueError:
            target_bytes = 500 * 1024

        task = CompressionTask(src_path=path, target_bytes=target_bytes, output_path="")
        
        if not self._watch_compress_worker.is_alive():
            self._watch_msg_handler = MessageHandler(
                log=self._log,
                progress=None,
                status=None,
                target_bytes=target_bytes,
                start_time=time.time(),
                on_complete=lambda ok, fail: None,
                on_cancel=lambda: None,
            )
            
            self._log.append_info(T("auto_compressing").format(name=Path(path).name))
            
            self._watch_compress_worker.start(
                tasks=[task],
                fmt_choice=self._settings.fmt_var.get(),
                output_mode=self._settings.out_var.get(),
                custom_dir=self._settings.custom_dir_var.get().strip(),
                strip_exif=self._settings.strip_exif_var.get(),
                engine_preference=self._settings.engine_preference_var.get(),
                continuous=True,
            )
            self.after(_POLL_INTERVAL_MS, self._poll_watch_worker)
        else:
            self._log.append_info(T("auto_compressing").format(name=Path(path).name))
            self._watch_compress_worker.append_task(task)

    # ------------------------------------------------------------------
    # Batch callbacks (invoked by MessageHandler)
    # ------------------------------------------------------------------

    def _on_batch_complete(self, ok: int, fail: int) -> None:
        self._set_running(False)
        Messagebox.show_info(T("status_done", ok=ok, fail=fail), T("dlg_done_title"))

    def _on_batch_cancel(self) -> None:
        self._set_running(False)

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
