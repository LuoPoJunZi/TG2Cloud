from __future__ import annotations

import re
import unicodedata
from itertools import islice
from pathlib import Path

# Local, bounded heuristics, not a dictionary/model or a public-suffix download.
_TLDS = frozenset({
    "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "name", "pro", "aero", "museum",
    "coop", "travel", "mobi", "tel", "jobs", "cat", "asia", "io", "ai", "me", "co", "tv", "cc", "de",
    "cn", "uk", "us", "jp", "kr", "fr", "ru", "ca", "au", "nz", "ch", "it", "es", "nl", "eu", "hk",
    "tw", "in", "br", "sg", "vn", "th", "id", "app", "dev", "cloud", "online", "site", "website",
    "space", "xyz", "top", "club", "shop", "store", "link", "live", "vip", "win", "wiki", "tech",
    "media", "video", "download", "news", "digital", "solutions", "zone", "one", "fun", "lol", "art",
    "social", "today", "email", "click", "life", "work", "film", "movie", "world", "music", "network",
    "community", "agency", "games", "guide", "tools", "design", "test", "example", "中国", "中國", "公司",
    "网络", "網絡", "香港", "台湾", "台灣", "рф", "みんな", "世界",
})
_TECH_TITLES = {"node.js", "vue.js", "next.js", "react.js", "asp.net"}
_SHORT_WORDS = {"a", "an", "the", "of", "to", "in", "and", "or", "on", "by", "for", "is", "it",
                "my", "you", "we", "me", "be", "so", "as", "at", "do", "no", "up", "go", "old",
                "new", "now", "not", "our", "all", "one", "two", "fun", "out", "see", "day", "sun"}
_DOMAIN = re.compile(r"(?<![\w.-])(?:\*\.)?(?:[\w-]+\.)+([\w-]{2,63})(?::\d+)?(?:[/?#][^\s<>]*)?@?[\w-]*", re.IGNORECASE)
_NOISE = re.compile(
    r"^(?:[\W_]*)(?:广告|廣告|推广|推廣|广告合作|备用网址|備用網址|"
    r"(?:关注|關注|订阅|訂閱|加入|点击|點擊|欢迎|歡迎)(?:频道|頻道|群|链接|連結|获取|獲取|订阅|訂閱|关注|關注)|"
    r"下载链接|下載連結|资源链接|資源連結|资源来源|資源來源|资源来自|資源來自|"
    r"(?:更多资源|更多資源)(?:请|請)?(?:关注|關注|订阅|訂閱|点击|點擊)|"
    r"(?:精选资源|精選資源)(?:关注|關注|订阅|訂閱|频道|頻道)|"
    r"频道|頻道|交流群|提取码|提取碼|密码|密碼|口令|解压|解壓|文件大小|大小|时长|時長|分辨率|格式|来源|來源|搬运|版权|"
    r"(?:subscribe|follow|join)\s+(?:us\b|our\b|this\b|(?:to\s+)?(?:our|the|this)\s+channel\b|@)|"
    r"subscribe\s*$|download\s+link\b|password\b|size\b|"
    r"チャンネル登録|구독\s*(?:하기|해주세요)|팔로우\s*(?:하기|해주세요))", re.IGNORECASE,
)
_AD_TAIL = re.compile(
    r"(?:\s|[|｜])+(?:欢迎关注|歡迎關注|欢迎订阅|歡迎訂閱|加入频道|加入頻道|加入群组|"
    r"更多资源|更多資源|关注频道|關注頻道|订阅频道|訂閱頻道|资源分享|資源分享|"
    r"资源来源|资源来自|点击链接|點擊連結|广告合作|备用网址|"
    r"follow\s+us\b|subscribe\s+to\b|join\s+our\b)", re.IGNORECASE,
)
_QUALITY = re.compile(
    r"(?:(?:\d+(?:\.\d+)?\s*(?:[KMGT]i?B|[KM]|P|FPS|分钟|秒))|"
    r"[248]K|HDR|UHD|HD|FHD|HEVC|H\.?26[45]|AV1|1080i|WEB[- ]?DL|BDRip|BluRay|"
    r"高清|超清|蓝光|藍光|视频|視頻|完整版|完整|全集|中字|字幕版|画质|畫質|版|[\s|/+,-])", re.IGNORECASE,
)
_EPISODE = re.compile(r"第\s*[\d一二三四五六七八九十百]+\s*[集季话話期课課章]|\bS\d{1,3}E\d{1,4}\b|\b(?:episode|lesson|ep)\s*\d+\b", re.IGNORECASE)
_CAPTION_SUFFIX = re.compile(r"\.(?:mp4|mkv|avi|mov|webm|m4v|ts|flv|wmv|exe|bat|cmd|sh)\s*$", re.IGNORECASE)


def truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return encoded.decode("utf-8")
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def safe_file_name(name: str, fallback: str) -> str:
    def clean(value: str) -> str:
        if not isinstance(value, str):
            return ""
        value = unicodedata.normalize("NFC", value)
        value = "".join(c for c in value if unicodedata.category(c) not in {"Cf", "Cs"}
                        and (ord(c) < 128 or unicodedata.category(c) != "Cc"))
        # Retain the established basename/illegal-character policy, including
        # sanitizing the fallback itself. Never return a raw fallback path.
        return re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]+", "_", Path(value).name).strip(" .")

    candidate = clean(name) or clean(fallback) or "file"
    suffix = truncate_utf8(Path(candidate).suffix, 24)
    stem_budget = max(1, 180 - len(suffix.encode("utf-8")))
    stem = truncate_utf8(Path(candidate).stem, stem_budget)
    if not stem:
        stem = "file"
    return f"{stem}{suffix}"


def _random_identifier(stem: str) -> bool:
    """Conservative ASCII IDs; ordinary words, CJK, years and versions survive."""
    if not re.fullmatch(r"[A-Za-z\d_-]{8,96}", stem):
        return False
    if re.fullmatch(r"_{2,}[A-Z\d]{1,8}_{2,}", stem):
        return True
    token = stem.strip("_- ")
    if re.fullmatch(r"[a-f\d]{16,}", token, re.IGNORECASE):
        return True
    if re.fullmatch(r"s\d{1,3}e\d{1,4}(?:v\d+)?", token, re.IGNORECASE):
        return False
    runs = re.findall(r"[A-Za-z]+", token)
    digits = re.findall(r"\d+", token)
    if (len(digits) >= 2 and len(runs) >= 3 and max(map(len, runs)) <= 3
            and sum(map(len, digits)) >= len(token) / 5):
        return True
    # Many alternating short case runs are more characteristic of a generated
    # token than a title. Do not classify a single normal English word by entropy.
    if len(token) >= 16 and token.isalpha():
        pieces = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", token)
        if sum(piece.casefold() in _SHORT_WORDS for piece in pieces) >= max(3, len(pieces) / 2):
            return False
        return len(pieces) >= 6 and max(map(len, pieces), default=0) <= 3
    return False


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
    weak = not name or _promotional_name(name) or _random_identifier(stem) or bool(re.fullmatch(
        r"(?:[\d\W_]+|[a-f\d]{16,}|[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}"
        r"|(?:video|vid|file|telegram|document|clip)(?:[\W_]+[\da-f]+|\d+)*)",
        stem, re.IGNORECASE,
    ))
    if not weak or not caption:
        return original
    title = caption_title(caption, entities)
    title = _CAPTION_SUFFIX.sub("", title)
    if title and suffix and title.lower().endswith(suffix.lower()):
        title = title[:-len(suffix)]
    if not title:
        return original
    candidate = safe_file_name(title + suffix, original)
    # A hostile title ending in '/..' or '/.' must not collapse to a basename
    # such as 'mp4' during cleanup and lose the attachment's real extension.
    return candidate if not suffix or candidate.lower().endswith(suffix.lower()) else original


def caption_title(caption: str, entities=()) -> str:
    """Prefer substantive visible descriptions, including Telegram block quotes."""
    return caption_candidate(caption, entities)[0]


def caption_candidate(caption: str, entities=()) -> tuple[str, int]:
    """Shared selection score for one caption and safely associated album text."""
    if not isinstance(caption, str):
        return "", -1
    # Preserve code-unit offsets even for isolated invalid surrogates; decoding
    # replaces them with U+FFFD, which the existing symbol cleanup discards.
    encoded = caption[:8192].encode("utf-16-le", errors="surrogatepass")
    masked = bytearray(encoded)
    quote_ranges = []
    try:
        entries = iter(entities or ())
    except TypeError:
        entries = iter(())
    for entity in islice(entries, 256):
        kind = type(entity).__name__
        try:
            offset, length = int(entity.offset), int(entity.length)
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
        if offset < 0 or length <= 0:
            continue
        start = max(0, offset) * 2
        end = min(len(masked), (offset + length) * 2)
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
        return "", -1
    # Explicit titles and short episodes outrank prose/short fallback. Quotes
    # retain their existing priority; ties are refined by bounded readability.
    # Ties preserve source order; do not mistake the longest advertisement for a title.
    title, score = max(candidates, key=lambda candidate: candidate[1])
    return _title_fragment(title), score


def _without_domains(line: str) -> str:
    def replace(match):
        token, tld = match[0], match[1].casefold()
        if token.casefold() in _TECH_TITLES or tld in {"mp4", "mkv", "avi", "mov", "webm", "m4v", "flv", "wmv"}:
            return token
        obvious = (tld in _TLDS or tld.startswith("xn--") or token.startswith(("www.", "*."))
                   or any(c in token for c in "/?@#")
                   or (token.isascii() and token == token.casefold() and tld.isalpha())
                   or line.strip(" .") == token.casefold() == token)
        return " " if obvious else token
    line = _DOMAIN.sub(replace, line)
    # Broken promotional placeholders such as '*.com@', not ordinary 'com' words.
    return re.sub(r"\*+\.[\w-]+@?[\w-]*", " ", line)


def _deduplicate_title(line: str) -> str:
    words = line.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        middle = len(words) // 2
        left, right = " ".join(words[:middle]), " ".join(words[middle:])
        if left.rstrip("。.!！") == right.rstrip("。.!！") and (
            middle >= 2 or any(ord(c) > 127 for c in left) or left.endswith(("。", ".", "!", "！"))
        ):
            return left.rstrip("。.!！")
    repeated = re.fullmatch(r"(.{2,80}?)[。!！]+\s*\1[。!！]*", line)
    return repeated[1] if repeated else line


def _title_fragment(title: str) -> str:
    if len(title.encode("utf-8")) <= 150:
        return title
    prefix = truncate_utf8(title, 150)
    # Prefer complete clauses, then a word boundary; byte truncation is the
    # existing last resort for very long unbroken text, not an invented summary.
    boundaries = list(re.finditer(r"[。！？!?;；,，]|\s+", prefix))
    for boundary in reversed(boundaries):
        if boundary.start() >= len(prefix) / 2:
            return prefix[:boundary.start()].rstrip(" ,，;；")
    return prefix


def _candidate_score(text: str, priority: int) -> int:
    letters = sum(c.isalpha() or unicodedata.category(c).startswith("M") for c in text)
    if _EPISODE.search(text) and len(text) <= 80:
        priority = max(priority, 3)
    words = re.findall(r"[^\W\d_]+", text)
    if 2 <= len(words) <= 10 and all(w[0].isupper() or w.lower() in {"a", "an", "the", "of", "to", "and", "in"} for w in words):
        priority = max(priority, 2)
    return priority * 100 + min(letters, 40) + min(len(words), 8)


def _continues_paragraph(previous: str, line: str) -> bool:
    # Keep existing wrapped descriptions, but do not merge a title with an
    # unrelated next line merely because the author omitted a blank line.
    return previous.endswith((",", "，", ";", "；")) or bool(re.match(
        r"^(?:以及|并且|並且|并记录|和|及|与|與|还有|還有|and\b|or\b|with\b)", line, re.IGNORECASE,
    ))


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
            priority = 2 if substantial and paragraph_quoted else int(substantial)
            candidates.append((description, _candidate_score(description, priority)))
            paragraph.clear()
        paragraph_quoted = quoted

    for raw_line in text.splitlines()[:64]:
        line = raw_line.strip().lstrip(">│┃ ").strip()
        if not line or _NOISE.match(line):
            flush()
            continue
        line = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", line)
        line = re.sub(r"[a-z][a-z\d+.-]{0,31}://[^\s<>\u3000]+", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b[\w.+-]+@(?:[\w-]+\.)+[\w-]+\b", " ", line)
        line = _without_domains(line)
        line = re.sub(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:[/?#][^\s<>]*)?", " ", line)
        line = re.sub(r"@[\w\u200c\u200d]+|(?<![A-Za-z\d_])[#$][\w\u200c\u200d]+", " ", line)
        line = re.sub(r"(?:提取码|密码|口令|解压码)\s*[:：=]?\s*\S+", " ", line)
        line = _AD_TAIL.split(line)[0]
        labels = r"标题|標題|名称|名稱|文件名|檔名|视频标题|視頻標題|title|filename|題名|作品名|제목"
        explicit = bool(re.match(rf"^(?:{labels})\s*[:：]\s*", line, re.IGNORECASE))
        line = re.sub(rf"^(?:{labels}|视频说明|视频简介|内容简介|内容描述|描述|说明|简介)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        # A numeric work title requires visible title context. Arbitrary numeric
        # captions remain the established fallback rather than a guessed name.
        numeric_title = bool(re.fullmatch(r"\d{1,8}", line.strip("《》「」\" "))) and (
            explicit or line.startswith(("《", "「"))
        )
        machine_title = _random_identifier(line)
        line = "".join(c for c in line if unicodedata.category(c) not in {"So", "Sk"} and c not in "\ufe0e\ufe0f\u20e3")
        line = re.sub(r"\s+", " ", line).strip(" \t-—_·|:：*~[]【】()（）“”「」『』\"" + chr(96))
        line = _deduplicate_title(line)
        if numeric_title:
            line = line.strip("《》")
        if (not _QUALITY.sub("", line) or machine_title or _random_identifier(line)
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", line, re.IGNORECASE)
                or (len(re.findall(r"[^\W\d_]", line)) < 2 and not numeric_title) or line.lower() in {
                    "视频", "文件", "资源", "资源分享", "资源介绍", "精选资源", "每日精选", "本期推荐",
                    "视频介绍", "内容介绍", "链接", "下载",
                    "点击这里", "video", "download", "link",
                }):
            flush()
            continue
        if explicit or numeric_title:
            flush()
            candidates.append((line, _candidate_score(line, 4)))
        else:
            # A real paragraph can span manually wrapped caption lines. Never
            # cross blank, metadata, link-only or advertisement boundaries.
            if paragraph and not _continues_paragraph(paragraph[-1], line):
                flush()
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
