"""Internationalisation strings.

Usage::

    from src.i18n.strings import T, set_language
    set_language("zh")
    print(T("add_files"))  # → "添加图片"
"""

from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    # -----------------------------------------------------------------------
    # App chrome
    # -----------------------------------------------------------------------
    "app_title": {
        "zh": "图片压缩工具",
        "en": "Image Compressor",
        "ja": "画像圧縮ツール",
    },
    # -----------------------------------------------------------------------
    # File panel
    # -----------------------------------------------------------------------
    "panel_files": {"zh": "待压缩图片", "en": "Images to Compress", "ja": "圧縮する画像"},
    "add_files": {"zh": "添加图片", "en": "Add Images", "ja": "追加"},
    "add_folder": {"zh": "添加文件夹", "en": "Add Folder", "ja": "フォルダ追加"},
    "remove_selected": {"zh": "删除选中", "en": "Remove", "ja": "選択削除"},
    "clear_list": {"zh": "清空列表", "en": "Clear All", "ja": "全削除"},
    "drop_hint": {
        "zh": "拖入图片或文件夹",
        "en": "Drop images or folders here",
        "ja": "画像・フォルダをドロップ",
    },
    "file_size_unknown": {"zh": "未知大小", "en": "Unknown size", "ja": "不明"},
    # -----------------------------------------------------------------------
    # Settings panel
    # -----------------------------------------------------------------------
    "panel_settings": {"zh": "压缩设置", "en": "Settings", "ja": "設定"},
    "label_target_size": {
        "zh": "目标大小：",
        "en": "Target size:",
        "ja": "目標サイズ：",
    },
    "size_hint": {
        "zh": "示例：500KB / 1.5MB / 800000B",
        "en": "e.g. 500KB / 1.5MB / 800000B",
        "ja": "例：500KB / 1.5MB",
    },
    "label_format": {"zh": "输出格式：", "en": "Output format:", "ja": "出力形式："},
    "format_original": {"zh": "原格式", "en": "Original", "ja": "元の形式"},
    "label_output": {"zh": "输出位置：", "en": "Output location:", "ja": "出力先："},
    "output_same_dir": {
        "zh": "原目录（追加 _compressed）",
        "en": "Source folder (_compressed suffix)",
        "ja": "元のフォルダ（_compressed）",
    },
    "output_custom_dir": {"zh": "自定义目录", "en": "Custom folder", "ja": "カスタムフォルダ"},
    "browse": {"zh": "浏览…", "en": "Browse…", "ja": "参照…"},
    "strip_exif": {
        "zh": "移除 EXIF 元数据（GPS / 相机信息）",
        "en": "Strip EXIF metadata (GPS / camera info)",
        "ja": "EXIF メタデータを削除（GPS / カメラ情報）",
    },
    "label_engine_preference": {
        "zh": "引擎偏好:",
        "en": "Engine preference:",
        "ja": "エンジン設定:",
    },
    "engine_pref_auto": {
        "zh": "自动",
        "en": "Auto",
        "ja": "自動",
    },
    "engine_pref_vips": {
        "zh": "pyvips (高性能)",
        "en": "pyvips (High performance)",
        "ja": "pyvips (高性能)",
    },
    "engine_pref_pillow": {
        "zh": "Pillow (兼容)",
        "en": "Pillow (Compatible)",
        "ja": "Pillow (互換)",
    },
    # -----------------------------------------------------------------------
    # Action buttons
    # -----------------------------------------------------------------------
    "start": {"zh": "开始压缩", "en": "Compress", "ja": "圧縮開始"},
    "cancel": {"zh": "取消", "en": "Cancel", "ja": "キャンセル"},
    # -----------------------------------------------------------------------
    # Log panel
    # -----------------------------------------------------------------------
    "panel_log": {"zh": "运行日志", "en": "Log", "ja": "ログ"},
    # -----------------------------------------------------------------------
    # Status / progress messages
    # -----------------------------------------------------------------------
    "status_ready": {"zh": "就绪", "en": "Ready", "ja": "準備完了"},
    "status_compressing": {
        "zh": "正在压缩…",
        "en": "Compressing…",
        "ja": "圧縮中…",
    },
    "status_done": {
        "zh": "完成：成功 {ok}，失败 {fail}",
        "en": "Done: {ok} succeeded, {fail} failed",
        "ja": "完了：成功 {ok}，失敗 {fail}",
    },
    "status_cancelled": {"zh": "已取消", "en": "Cancelled", "ja": "キャンセル済み"},
    # -----------------------------------------------------------------------
    # Log line templates
    # -----------------------------------------------------------------------
    "log_sep": {"zh": "=" * 60, "en": "=" * 60, "ja": "=" * 60},
    "log_target": {"zh": "目标大小：{sz}", "en": "Target size: {sz}", "ja": "目標サイズ：{sz}"},
    "log_count": {
        "zh": "待处理文件：{n}",
        "en": "Files to process: {n}",
        "ja": "処理ファイル数：{n}",
    },
    "log_engine": {
        "zh": "压缩引擎：{engine}",
        "en": "Engine: {engine}",
        "ja": "圧縮エンジン：{engine}",
    },
    "log_ok": {
        "zh": "[OK] {name}\n  {orig} → {out} ({ratio:.1f}%){scale}\n  格式：{fmt}，参数：{quality}\n  输出：{outname}{warn}",
        "en": "[OK] {name}\n  {orig} → {out} ({ratio:.1f}%){scale}\n  Format: {fmt}, params: {quality}\n  Saved: {outname}{warn}",
        "ja": "[OK] {name}\n  {orig} → {out} ({ratio:.1f}%){scale}\n  形式：{fmt}, パラメータ：{quality}\n  保存先：{outname}{warn}",
    },
    "log_warn": {
        "zh": "[WARN] {name}\n  {orig} → {out} ({ratio:.1f}%){scale} ※目标未达到\n  格式：{fmt}，参数：{quality}\n  输出：{outname}{warn}",
        "en": "[WARN] {name}\n  {orig} → {out} ({ratio:.1f}%){scale} ※target not met\n  Format: {fmt}, params: {quality}\n  Saved: {outname}{warn}",
        "ja": "[WARN] {name}\n  {orig} → {out} ({ratio:.1f}%){scale} ※目標未達\n  形式：{fmt}, パラメータ：{quality}\n  保存先：{outname}{warn}",
    },
    "log_error_unrecognised": {
        "zh": "[ERROR] {name} 不是可识别的图片文件。",
        "en": "[ERROR] {name}: not a recognised image file.",
        "ja": "[ERROR] {name}：認識できない画像ファイルです。",
    },
    "log_error_generic": {
        "zh": "[ERROR] {name} 压缩失败：{err}",
        "en": "[ERROR] {name}: compression failed: {err}",
        "ja": "[ERROR] {name}：圧縮失敗：{err}",
    },
    "log_summary": {
        "zh": "完成：成功 {ok}，失败 {fail}",
        "en": "Done: {ok} succeeded, {fail} failed",
        "ja": "完了：成功 {ok}，失敗 {fail}",
    },
    # -----------------------------------------------------------------------
    # Scale note
    # -----------------------------------------------------------------------
    "scale_note": {
        "zh": "，缩放至 {pct}",
        "en": ", resized to {pct}",
        "ja": ", {pct} にリサイズ",
    },
    # -----------------------------------------------------------------------
    # Watch Mode
    # -----------------------------------------------------------------------
    "watch_mode_enable": {
        "zh": "开启监控模式 (自动压缩新图片)",
        "en": "Enable Watch Mode (Auto-compress new images)",
        "ja": "監視モードを有効にする（新しい画像を自動圧縮）",
    },
    "watch_recursive": {
        "zh": "包含子目录",
        "en": "Include Sub-directories",
        "ja": "サブディレクトリを含める",
    },
    "watch_add_dir": {
        "zh": "添加监控目录...",
        "en": "Add Watch Directory...",
        "ja": "監視ディレクトリを追加...",
    },
    "watch_clear_dirs": {
        "zh": "清空目录",
        "en": "Clear Directories",
        "ja": "ディレクトリをクリア",
    },
    "watch_started": {
        "zh": "已启动监控",
        "en": "Watch mode started",
        "ja": "監視モードを開始しました",
    },
    "watch_stopped": {
        "zh": "已停止监控",
        "en": "Watch mode stopped",
        "ja": "監視モードを停止しました",
    },
    "auto_compressing": {
        "zh": "自动压缩新文件: {name}",
        "en": "Auto-compressing new file: {name}",
        "ja": "新しいファイルを自動圧縮中: {name}",
    },
    # -----------------------------------------------------------------------
    # Dialogs / error messages
    # -----------------------------------------------------------------------
    "dlg_title": {"zh": "图片压缩工具", "en": "Image Compressor", "ja": "画像圧縮ツール"},
    "err_no_files": {
        "zh": "请先添加要压缩的图片。",
        "en": "Please add at least one image first.",
        "ja": "画像を追加してください。",
    },
    "err_invalid_size": {
        "zh": "无效的目标大小：{detail}",
        "en": "Invalid target size: {detail}",
        "ja": "無効な目標サイズ：{detail}",
    },
    "err_zero_size": {
        "zh": "目标大小必须大于 0。",
        "en": "Target size must be greater than 0.",
        "ja": "目標サイズは 0 より大きくしてください。",
    },
    "err_invalid_dir": {
        "zh": "请选择一个有效的输出目录。",
        "en": "Please select a valid output directory.",
        "ja": "有効な出力フォルダを選択してください。",
    },
    "dlg_done_title": {"zh": "完成", "en": "Done", "ja": "完了"},
    "dlg_select_images": {
        "zh": "选择图片",
        "en": "Select images",
        "ja": "画像を選択",
    },
    "dlg_select_folder": {
        "zh": "选择输出目录",
        "en": "Select output folder",
        "ja": "出力フォルダを選択",
    },
    "file_type_images": {"zh": "图片文件", "en": "Image files", "ja": "画像ファイル"},
    "file_type_all": {"zh": "所有文件", "en": "All files", "ja": "すべてのファイル"},
}

_LANGUAGE: str = "zh"
_FALLBACK: str = "en"


def set_language(lang: str) -> None:
    """Set the active language. Accepted values: 'zh', 'en', 'ja'."""
    global _LANGUAGE
    if lang not in ("zh", "en", "ja"):
        raise ValueError(f"Unsupported language: {lang!r}")
    _LANGUAGE = lang


def get_language() -> str:
    return _LANGUAGE


def T(key: str, **kwargs: object) -> str:  # noqa: N802
    """Translate *key* using the current language, with optional format args."""
    entry = _STRINGS.get(key)
    if entry is None:
        return key  # graceful fallback

    text = entry.get(_LANGUAGE) or entry.get(_FALLBACK) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text


def supported_languages() -> list[str]:
    return ["zh", "en", "ja"]
