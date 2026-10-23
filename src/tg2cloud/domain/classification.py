"""Deterministic subdirectories; never change naming or accept arbitrary paths."""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from tg2cloud.persistence.features import MODES

EXTENSIONS = {
    "视频": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".flv"},
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".avif", ".bmp"},
    "音频": {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aac"},
    "文档": {".pdf", ".txt", ".md", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".csv"},
    "压缩包": {".zip", ".rar", ".7z", ".gz", ".bz2", ".xz", ".tar", ".zst"},
}


def media_type(kind: str, mime: str, extension: str) -> str:
    if kind in {"视频", "图片", "音频"}:
        return kind
    for prefix, label in (("video/", "视频"), ("image/", "图片"), ("audio/", "音频")):
        if mime.startswith(prefix):
            return label
    if mime in {"application/pdf", "text/plain", "application/epub+zip"}:
        return "文档"
    if mime in {"application/zip", "application/x-7z-compressed", "application/vnd.rar", "application/gzip"}:
        return "压缩包"
    for label, extensions in EXTENSIONS.items():
        if extension.lower() in extensions:
            return label
    return "其他文件"


def safe_directory(path: str) -> str:
    if (not isinstance(path, str) or unicodedata.normalize("NFC", path) != path or len(path.encode("utf-8")) > 128
            or "\\" in path or ":" in path or "%" in path or path.startswith("/")
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or path and any(part in {"", ".", ".."} for part in path.split("/"))):
        raise ValueError("分类目录不是安全的受管相对路径")
    return path


def directory(preferences: dict, created_at: float, *, kind="", mime="", extension="") -> str:
    mode = preferences["classification"]
    if mode not in MODES:
        raise ValueError("未知分类规则")
    if mode == "off":
        return ""
    parts = []
    if mode in {"type", "type_month"}:
        parts.append(media_type(kind, mime, extension))
    if mode in {"year", "month", "type_month"}:
        zone = timezone.utc if preferences["timezone"] == "UTC" else ZoneInfo(preferences["timezone"])
        date = datetime.fromtimestamp(created_at, zone)
        parts.append(date.strftime("%Y"))
        if mode != "year":
            parts.append(date.strftime("%m"))
    return safe_directory(str(PurePosixPath(*parts)))


def check_scope(task: dict, settings) -> None:
    safe_directory(task.get("target_directory", ""))
    base = task.get("target_base")
    if base is not None and base != settings.cd2_target:
        raise ValueError("任务接收后 WebDAV 基础目录发生变化；停止自动上传，请核对配置")
