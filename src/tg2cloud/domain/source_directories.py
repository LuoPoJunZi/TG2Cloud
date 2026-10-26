"""Bounded source names and a listener-only, media-type directory policy."""

from __future__ import annotations

import re
import unicodedata

from tg2cloud.domain.classification import media_type, safe_directory

MAX_COLUMNS = 60  # Thirty full-width characters, including a collision suffix.
MAX_BYTES = 112  # Leave room for /其他文件 within safe_directory's 128 bytes.
CATEGORIES = ("视频", "图片", "音频", "文档", "压缩包", "其他文件")


def columns(value: str) -> int:
    return sum(
        0
        if unicodedata.category(c).startswith("M")
        else 2
        if unicodedata.east_asian_width(c) in {"W", "F"}
        else 1
        for c in value
    )


def folder_name(title: str, chat: int, suffix: str = "") -> str:
    text = unicodedata.normalize("NFC", title)
    text = re.sub(r"[0-9#*]\ufe0f?\u20e3", "", text)
    cleaned = []
    for c in text:
        code = ord(c)
        category = unicodedata.category(c)
        if (
            0x1F000 <= code <= 0x1FAFF
            or 0x2600 <= code <= 0x27BF
            or 0xFE00 <= code <= 0xFE0F
            or 0xE0000 <= code <= 0xE01EF
            or c
            in "©®™↔↕↖↗↘↙↩↪⌚⌛⌨⏏⏩⏪⏫⏬⏭⏮⏯⏰⏱⏲⏳⏸⏹⏺▪▫▶◀◻◼◽◾⤴⤵⬅⬆⬇⬛⬜⭐⭕〰〽㊗㊙"
            or category in {"Cf", "Cs", "Co", "Cn"}
        ):
            continue
        cleaned.append(
            " " if c.isspace() or category == "Cc" or c in '/\\:%<>|"*?' else c
        )
    text = " ".join("".join(cleaned).split()).strip(" .") or f"来源-{abs(chat)}"
    # Keep combining marks with their preceding character when truncating.
    clusters = []
    for c in text:
        if unicodedata.category(c).startswith("M"):
            if clusters:
                clusters[-1] += c
        else:
            clusters.append(c)
    result = ""
    for cluster in clusters:
        candidate = result + cluster + suffix
        if (
            columns(candidate) > MAX_COLUMNS
            or len(candidate.encode("utf-8")) > MAX_BYTES
        ):
            break
        result += cluster
    return safe_directory((result.rstrip(" .") or "来源") + suffix)


def media_directory(
    config: dict, *, kind="", mime="", extension="", base=None
) -> str | None:
    if config.get("directory_mode", "legacy") != "source_type":
        return None
    folder = config.get("source_folder", "")
    if not folder or config.get("source_base") != base:
        raise ValueError("监听目录未准备好或 Bot 保存根目录已变化；请核对来源保存目录")
    return safe_directory(folder + "/" + media_type(kind, mime, extension))


def description(config: dict) -> str:
    if config.get("directory_mode", "legacy") == "source_type":
        return (
            config.get("source_folder") or "按来源名称创建"
        ) + "/文件类型（相对于 Bot 保存目录）"
    return (
        config.get("directory")
        or config.get("profile", {}).get("directory")
        or "沿用分类或默认目录"
    )
