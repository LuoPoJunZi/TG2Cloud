from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def safe_file_name(name: str, fallback: str) -> str:
    candidate = Path(name or fallback).name
    candidate = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", candidate)
    candidate = candidate.strip(" .")
    if not candidate:
        candidate = fallback
    suffix = truncate_utf8(Path(candidate).suffix, 24)
    stem_budget = max(1, 180 - len(suffix.encode("utf-8")))
    stem = truncate_utf8(Path(candidate).stem, stem_budget)
    if not stem:
        stem = "file"
    return f"{stem}{suffix}"


def video_file_name(name: str, caption: str, fallback: str, entities=()) -> str:
    """Use local caption text only for machine-generated video names.

    Do not infer content, follow URLs, or rename an already descriptive filename.
    Telegram entity offsets are UTF-16 code units, not Python character indexes.
    """
    original = safe_file_name(name, fallback)
    suffix = Path(original).suffix or Path(fallback).suffix
    stem = Path(original).stem
    weak = not name or bool(re.fullmatch(
        r"(?:[\d\W_]+|[a-f\d]{16,}|[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}"
        r"|(?:video|vid|file|telegram|document|clip)(?:[\W_]+[\da-f]+|\d+)*)",
        stem, re.IGNORECASE,
    ))
    if not weak or not caption:
        return original
    title = caption_title(caption, entities)
    if title and suffix and title.lower().endswith(suffix.lower()):
        title = title[:-len(suffix)]
    return safe_file_name(title + suffix, original) if title else original


def caption_title(caption: str, entities=()) -> str:
    """Extract a bounded title from caption text; never fetch remote context."""
    encoded = caption[:8192].encode("utf-16-le", errors="replace")
    masked = bytearray(encoded)
    for entity in entities or ():
        if type(entity).__name__ not in {
            "MessageEntityUrl", "MessageEntityTextUrl", "MessageEntityHashtag",
            "MessageEntityMention", "MessageEntityMentionName", "MessageEntityEmail",
            "MessageEntityPhone", "MessageEntityBotCommand", "MessageEntityCashtag",
            "MessageEntitySpoiler", "MessageEntityCode", "MessageEntityPre",
        }:
            continue
        start = max(0, int(entity.offset)) * 2
        end = min(len(masked), (int(entity.offset) + int(entity.length)) * 2)
        if 0 <= start < end:
            masked[start:end] = b" \0" * ((end - start) // 2)
    text = unicodedata.normalize("NFKC", masked.decode("utf-16-le", errors="replace"))
    # Remove format/control characters but keep line boundaries for title selection.
    text = "".join(c for c in text if c in "\n\r" or not unicodedata.category(c).startswith("C"))
    for raw_line in text.splitlines()[:64]:
        line = raw_line.strip()
        # Discard promotion/credential/metadata lines, rather than turning their labels into titles.
        if re.match(
            r"^(?:[\W_]*)(?:广告|推广|关注|订阅|加入|点击|下载链接|资源链接|频道|交流群|"
            r"提取码|密码|口令|解压|文件大小|大小|时长|分辨率|格式|来源|搬运|版权|"
            r"subscribe\b|follow\b|join\b|download\s+link\b|password\b|size\b)",
            line, re.IGNORECASE,
        ):
            continue
        # Hidden-link labels and markdown link labels are not reliable descriptions.
        line = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", line)
        line = re.sub(r"[a-z][a-z\d+.-]*://[^\s<>\u3000]+", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b[\w.+-]+@[\w.-]+\b", " ", line)
        line = re.sub(r"(?<![\w])(?:[\w-]+\.)+[a-z\u4e00-\u9fff]{2,}(?![\w-])(?::\d+)?(?:[/?#][^\s<>]*)?", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:[/?#][^\s<>]*)?", " ", line)
        line = re.sub(r"(?<![A-Za-z\d_])[@#$][\w\u200c\u200d]+", " ", line)
        line = re.sub(r"(?:提取码|密码|口令|解压码)\s*[:：=]?\s*\S+", " ", line)
        line = re.split(r"(?:\s|[|｜])+(?:欢迎关注|欢迎订阅|加入频道|加入群组|更多资源|关注频道|订阅频道)", line)[0]
        line = re.sub(r"^(?:标题|名称|文件名|视频标题|title)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        line = "".join(c for c in line if unicodedata.category(c) not in {"So", "Sk"} and c not in "\ufe0e\ufe0f\u20e3")
        line = re.sub(r"\s+", " ", line).strip(" \t-—_·|:：*`~[]【】()（）")
        if re.fullmatch(r"(?:(?:\d+(?:\.\d+)?\s*(?:[KMGT]i?B|[KM]|P|FPS|分钟|秒))|HDR|HEVC|H\.?26[45]|[\s|/+,-])+", line, re.IGNORECASE):
            continue
        if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", line, re.IGNORECASE):
            continue
        # Keep episode numbers inside titles, but reject numeric-only and generic remnants.
        if len(re.findall(r"[^\W\d_]", line)) < 2 or line.lower() in {
            "视频", "文件", "资源", "资源分享", "链接", "下载", "点击这里", "video", "download", "link",
        }:
            continue
        if line:
            return line
    return ""


def album_file_name(title: str, kind: str, number: int, extension: str) -> str:
    """Reserve the suffix budget so long album titles cannot erase numbering."""
    extension = truncate_utf8(extension, 24)
    if not re.fullmatch(r"\.[A-Za-z\d]{1,12}", extension):
        extension = ".bin"
    tail = f"-{kind}{number:02d}{extension}"
    clean = safe_file_name(title, "media")
    clean = truncate_utf8(clean, 180 - len(tail.encode("utf-8"))).rstrip(" .")
    return f"{clean}{tail}"
