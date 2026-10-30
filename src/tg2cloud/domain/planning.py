"""Bounded naming plans shared by manual delivery and monitored sources."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from tg2cloud.domain.classification import safe_directory
from tg2cloud.domain.naming import (
    caption_title,
    clean_promotional_affixes,
    media_file_name,
    safe_file_name,
    video_file_name,
)


class PlanningError(ValueError):
    """A fixed local validation message safe to show without Telegram exception details."""


DEFAULT_PROFILE = {
    "mode": "compatible",
    "template": "{title} {episode}",
    "prefixes": [],
    "suffixes": [],
    "label": "",
    "directory": "",
}
FIELDS = {
    "title",
    "episode",
    "season",
    "chapter",
    "year",
    "resolution",
    "language",
    "version",
}


def profile(value: dict | None = None) -> dict:
    if value is not None and not isinstance(value, dict):
        raise PlanningError("命名配置必须是 JSON 对象")
    result = {**DEFAULT_PROFILE, **(value or {})}
    if not isinstance(value or {}, dict) or set(result) != set(DEFAULT_PROFILE):
        raise PlanningError("未知命名配置")
    if result["mode"] not in {"compatible", "caption", "template"}:
        raise PlanningError("命名模式应为 compatible、caption 或 template")
    for key in ("template", "label"):
        if (
            not isinstance(result[key], str)
            or len(result[key]) > 200
            or any(ord(c) < 32 for c in result[key])
        ):
            raise PlanningError("命名模板或标签无效")
    tokens = re.findall(r"\{([^{}]*)\}", result["template"])
    if (
        set(tokens) - FIELDS
        or re.sub(r"\{[^{}]*\}", "", result["template"]).count("{")
        or "}" in re.sub(r"\{[^{}]*\}", "", result["template"])
    ):
        raise PlanningError("模板只能使用已支持字段")
    for key in ("prefixes", "suffixes"):
        items = result[key]
        if (
            not isinstance(items, list)
            or len(items) > 12
            or any(
                not isinstance(s, str)
                or not 1 <= len(s) <= 80
                or any(ord(c) < 32 for c in s)
                for s in items
            )
        ):
            raise PlanningError("清理规则长度无效")
    result["directory"] = safe_directory(result["directory"])
    return result


def fields(text: str) -> dict[str, str]:
    text = unicodedata.normalize("NFC", text[:8192])
    found = {key: "" for key in FIELDS}
    season = re.search(r"第\s*(\d{1,3})\s*季|\bS(\d{1,3})(?=E|\b)", text, re.IGNORECASE)
    episode = re.search(
        r"第\s*(\d{1,4})\s*[集话話]|\b(?:S\d{1,3})?E(?:P)?[ .]?(\d{1,4})\b",
        text,
        re.IGNORECASE,
    )
    chapter = re.search(r"第\s*\d{1,4}\s*[讲講章课課]", text)
    if season:
        found["season"] = "S" + str(int(next(s for s in season.groups() if s))).zfill(2)
    if episode:
        found["episode"] = (
            (found["season"] or "")
            + "E"
            + str(int(next(s for s in episode.groups() if s))).zfill(2)
        )
    for key, pattern in (
        ("year", r"(?<!\d)(?:19|20)\d{2}(?!\d)"),
        ("resolution", r"\b(?:720p|1080p|2160p|4K|8K)\b"),
        ("language", r"(?:中文字幕|简体中字|繁体中字|双语字幕|日本語|English|한국어)"),
        ("version", r"\bv\d+(?:\.\d+){0,3}\b"),
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        found[key] = match[0] if match else ""
    found["chapter"] = chapter[0] if chapter else ""
    return found


def name_plan(
    original: str,
    caption: str,
    fallback: str,
    *,
    kind: str = "",
    extension: str = "",
    entities=(),
    options=None,
) -> dict:
    options = profile(options)
    compatible = (video_file_name if kind == "视频" else media_file_name)(
        original, caption, fallback, entities, media_extension=extension
    )
    cleaned = caption[:8192]
    if options["label"]:
        lines = [
            line.split(options["label"], 1)[1]
            for line in cleaned.splitlines()
            if options["label"] in line
        ]
        cleaned = "\n".join(lines) if lines else cleaned
    for prefix in options["prefixes"]:
        cleaned = "\n".join(line.removeprefix(prefix) for line in cleaned.splitlines())
    for suffix in options["suffixes"]:
        cleaned = "\n".join(line.removesuffix(suffix) for line in cleaned.splitlines())
    clean_original = clean_promotional_affixes(original)
    for prefix in options["prefixes"]:
        clean_original = clean_original.removeprefix(prefix)
    for suffix in options["suffixes"]:
        stem, ext = Path(clean_original).stem, Path(clean_original).suffix
        clean_original = stem.removesuffix(suffix) + ext
    if clean_original != original or cleaned != caption:
        compatible = (video_file_name if kind == "视频" else media_file_name)(
            clean_original, cleaned, fallback, entities if cleaned == caption else (), media_extension=extension
        )
    title = caption_title(cleaned, entities if cleaned == caption else ())
    data = fields((original or "") + "\n" + cleaned)
    data["title"] = title
    proposed, basis = compatible, "兼容命名（有效原名优先，说明与默认名兜底）"
    own, description = fields(original), fields(cleaned)
    ambiguous = any(
        own[key] and description[key] and own[key] != description[key]
        for key in ("episode", "chapter")
    )
    if options["mode"] == "caption" and ambiguous:
        title = ""  # Conflicting episode/chapter facts must not replace a meaningful original.
        basis = "说明与原名季集冲突，保留兼容命名"
    if options["mode"] != "compatible" and title:
        if options["mode"] == "template":
            # Strip only explicit episode/chapter tokens already extracted, never infer from sequence.
            stem = re.sub(
                r"第\s*\d+\s*[季集话話讲講章课課]|\bS\d+E\d+\b|\bE\d+\b",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()
            data["title"] = stem or title
            stem = re.sub(r"\{([^{}]+)\}", lambda m: data[m[1]], options["template"])
            stem = re.sub(r"([|·_-])\s+(?:[|·_-]\s*)+", r"\1 ", stem)
            stem = re.sub(r"\s+", " ", stem).strip(" -_·|")
            # A missing template slot may omit optional metadata, never a member's chapter.
            for key in ("episode", "chapter"):
                if data[key] and not fields(stem)[key]:
                    stem += " " + data[key]
        else:
            stem = title
            # A shared description must not erase a member's explicit episode/chapter.
            for token in (data["episode"], data["chapter"]):
                if (
                    token
                    and token not in stem
                    and not fields(stem)["episode"]
                    and not fields(stem)["chapter"]
                ):
                    stem += " " + token
        if stem:
            proposed = safe_file_name(stem + Path(compatible).suffix, compatible)
            basis = (
                "说明标题"
                if options["mode"] == "caption"
                else "已识别字段模板（缺项省略）"
            )
    return {"file_name": proposed, "basis": basis, "fields": data, "profile": options}


def corrected_name(value: str, current: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 1024
        or any(ord(c) < 32 for c in value)
        or "/" in value
        or "\\" in value
    ):
        raise PlanningError("请输入不含路径和控制字符的文件名")
    suffix = Path(current).suffix
    stem = value.strip()
    if stem.lower().endswith(suffix.lower()) and suffix:
        stem = stem[: -len(suffix)]
    return safe_file_name(stem + suffix, current)
