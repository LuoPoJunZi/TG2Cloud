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


def _promotional_name(name: str) -> bool:
    """Recognize contact/channel boilerplate, not ordinary descriptive titles."""
    stem = unicodedata.normalize("NFKC", Path(name).stem[:1024])
    if re.search(r"教程|教学|指南|解析|评测|攻略|tutorial|guide", stem, re.IGNORECASE):
        return False
    contact = re.search(r"@[A-Za-z\d_]{3,}|https?://|www\.|t\.me/|telegram\.me/", stem, re.IGNORECASE)
    promotion = re.search(r"关注|订阅|加入|频道|推广|精选资源|资源精选|follow\b|subscribe\b|join\b", stem, re.IGNORECASE)
    return bool(contact and promotion)


def video_file_name(name: str, caption: str, fallback: str, entities=()) -> str:
    """Use a visible caption for machine-generated or promotional video names.

    Do not infer content, follow URLs, or rename an already descriptive filename.
    Telegram entity offsets are UTF-16 code units, not Python character indexes.
    """
    original = safe_file_name(name, fallback)
    suffix = Path(original).suffix or Path(fallback).suffix
    stem = Path(original).stem
    weak = not name or _promotional_name(name) or bool(re.fullmatch(
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
    """Prefer substantive visible descriptions, including Telegram block quotes."""
    encoded = caption[:8192].encode("utf-16-le", errors="replace")
    masked = bytearray(encoded)
    quote_ranges = []
    for entity in entities or ():
        kind = type(entity).__name__
        start = max(0, int(entity.offset)) * 2
        end = min(len(masked), (int(entity.offset) + int(entity.length)) * 2)
        if not 0 <= start < end:
            continue
        if kind == "MessageEntityBlockquote":
            quote_ranges.append((start, end))
        elif kind in {
            "MessageEntityUrl", "MessageEntityTextUrl", "MessageEntityHashtag",
            "MessageEntityMention", "MessageEntityMentionName", "MessageEntityEmail",
            "MessageEntityPhone", "MessageEntityBotCommand", "MessageEntityCashtag",
            "MessageEntitySpoiler", "MessageEntityCode", "MessageEntityPre",
        }:
            masked[start:end] = b" \0" * ((end - start) // 2)
    candidates = _description_candidates(masked.decode("utf-16-le", errors="replace"))
    # Slice the already-masked UTF-16 data: hidden URLs must stay excluded even
    # when their visible labels occur inside a block quote after an emoji.
    for start, end in quote_ranges[:64]:
        candidates.extend(_description_candidates(
            masked[start:end].decode("utf-16-le", errors="replace"), quoted=True,
        ))
    if not candidates:
        return ""
    # Explicit title > substantive quote > substantive prose > short fallback.
    # Ties preserve source order; do not mistake the longest advertisement for a title.
    return max(candidates, key=lambda candidate: candidate[1])[0]


def _description_candidates(text: str, *, quoted: bool = False) -> list[tuple[str, int]]:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if c in "\n\r" or not unicodedata.category(c).startswith("C"))
    candidates: list[tuple[str, int]] = []
    paragraph: list[str] = []
    paragraph_quoted = quoted

    def flush() -> None:
        nonlocal paragraph_quoted
        if paragraph:
            description = " ".join(paragraph)
            substantial = len(re.findall(r"[^\W\d_]", description)) >= 12
            candidates.append((description, 2 if substantial and paragraph_quoted else int(substantial)))
            paragraph.clear()
        paragraph_quoted = quoted

    for raw_line in text.splitlines()[:64]:
        line = raw_line.strip().lstrip(">│┃ ").strip()
        if not line or re.match(
            r"^(?:[\W_]*)(?:广告|推广|关注|订阅|加入|点击|下载链接|资源链接|频道|交流群|"
            r"提取码|密码|口令|解压|文件大小|大小|时长|分辨率|格式|来源|搬运|版权|"
            r"subscribe\b|follow\b|join\b|download\s+link\b|password\b|size\b)",
            line, re.IGNORECASE,
        ) or _promotional_name(line):
            flush()
            continue
        line = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", line)
        line = re.sub(r"[a-z][a-z\d+.-]*://[^\s<>\u3000]+", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b[\w.+-]+@[\w.-]+\b", " ", line)
        line = re.sub(r"(?<![\w])(?:[\w-]+\.)+[a-z\u4e00-\u9fff]{2,}(?![\w-])(?::\d+)?(?:[/?#][^\s<>]*)?", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:[/?#][^\s<>]*)?", " ", line)
        line = re.sub(r"(?<![A-Za-z\d_])[@#$][\w\u200c\u200d]+", " ", line)
        line = re.sub(r"(?:提取码|密码|口令|解压码)\s*[:：=]?\s*\S+", " ", line)
        line = re.split(r"(?:\s|[|｜])+(?:欢迎关注|欢迎订阅|加入频道|加入群组|更多资源|关注频道|订阅频道)", line)[0]
        explicit = bool(re.match(r"^(?:标题|名称|文件名|视频标题|title)\s*[:：]\s*", line, re.IGNORECASE))
        line = re.sub(r"^(?:标题|名称|文件名|视频标题|title|视频说明|视频简介|内容简介|内容描述|描述|说明|简介)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        line = "".join(c for c in line if unicodedata.category(c) not in {"So", "Sk"} and c not in "\ufe0e\ufe0f\u20e3")
        line = re.sub(r"\s+", " ", line).strip(" \t-—_·|:：*~[]【】()（）“”「」『』\"" + chr(96))
        if (re.fullmatch(r"(?:(?:\d+(?:\.\d+)?\s*(?:[KMGT]i?B|[KM]|P|FPS|分钟|秒))|HDR|HEVC|H\.?26[45]|[\s|/+,-])+", line, re.IGNORECASE)
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", line, re.IGNORECASE)
                or len(re.findall(r"[^\W\d_]", line)) < 2 or line.lower() in {
                    "视频", "文件", "资源", "资源分享", "资源介绍", "精选资源", "每日精选", "本期推荐",
                    "视频介绍", "内容介绍", "链接", "下载",
                    "点击这里", "video", "download", "link",
                }):
            flush()
            continue
        if explicit:
            flush()
            candidates.append((line, 3))
        else:
            # A real paragraph can span manually wrapped caption lines. Never
            # cross blank, metadata, link-only or advertisement boundaries.
            paragraph.append(line)
            paragraph_quoted = paragraph_quoted or raw_line.lstrip().startswith((">", "“", "「", "『", "│"))
    flush()
    return candidates


def album_file_name(title: str, kind: str, number: int, extension: str) -> str:
    """Reserve the suffix budget so long album titles cannot erase numbering."""
    extension = truncate_utf8(extension, 24)
    if not re.fullmatch(r"\.[A-Za-z\d]{1,12}", extension):
        extension = ".bin"
    tail = f"-{kind}{number:02d}{extension}"
    clean = safe_file_name(title, "media")
    clean = truncate_utf8(clean, 180 - len(tail.encode("utf-8"))).rstrip(" .")
    return f"{clean}{tail}"
