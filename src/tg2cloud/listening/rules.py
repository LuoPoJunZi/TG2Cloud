"""Finite OR-of-AND rules over original metadata; never execute user code."""

from __future__ import annotations

import fnmatch
import json
import unicodedata
from pathlib import Path

from tg2cloud.domain.classification import media_type
from tg2cloud.domain.planning import PlanningError

TYPES = {"视频", "图片", "音频", "文档", "压缩包", "其他文件"}


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def strings(value, limit=20):
    if (
        not isinstance(value, list)
        or len(value) > limit
        or any(
            not isinstance(s, str)
            or not 1 <= len(s) <= 100
            or any(ord(c) < 32 for c in s)
            for s in value
        )
    ):
        raise PlanningError("规则列表应包含有界非空文本")
    return value


def validate(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {
        "groups",
        "exclude",
        "min_bytes",
        "max_bytes",
        "scope",
        "all_attachments",
    }:
        raise PlanningError("未知筛选规则字段")
    if len(json.dumps(value, ensure_ascii=False)) > 8192:
        raise PlanningError("规则总长度不能超过 8192 字符")
    result = {
        "groups": [],
        "exclude": [],
        "min_bytes": 0,
        "max_bytes": 0,
        "scope": "both",
        "all_attachments": False,
        **value,
    }
    if (
        result["scope"] not in {"name", "caption", "both"}
        or type(result["all_attachments"]) is not bool
    ):
        raise PlanningError("匹配范围或全部附件确认无效")
    for key in ("min_bytes", "max_bytes"):
        if type(result[key]) is not int or not 0 <= result[key] <= 100 * 1024**4:
            raise PlanningError("大小必须是有效字节数")
    if result["max_bytes"] and result["min_bytes"] > result["max_bytes"]:
        raise PlanningError("最小大小不能超过最大大小")
    strings(result["exclude"])
    if not isinstance(result["groups"], list) or len(result["groups"]) > 8:
        raise PlanningError("最多允许 8 个 OR 规则组")
    groups = []
    for group in result["groups"]:
        if not isinstance(group, dict) or set(group) - {
            "types",
            "extensions",
            "names",
            "name_mode",
            "keywords",
            "keyword_mode",
        }:
            raise PlanningError("包含组字段无效")
        g = {
            "types": [],
            "extensions": [],
            "names": [],
            "name_mode": "contains",
            "keywords": [],
            "keyword_mode": "any",
            **group,
        }
        for key in ("types", "extensions", "names", "keywords"):
            strings(g[key])
        if (
            set(g["types"]) - TYPES
            or g["name_mode"] not in {"exact", "contains", "glob"}
            or g["keyword_mode"] not in {"any", "all"}
        ):
            raise PlanningError("类型或匹配方式无效")
        if g["name_mode"] == "glob" and any("[" in s or "]" in s for s in g["names"]):
            raise PlanningError("通配符仅支持 * 和 ?")
        g["extensions"] = [norm(s).lstrip(".") for s in g["extensions"]]
        if any(
            not s or len(s) > 24 or any(not (c.isalnum() or c == ".") for c in s)
            for s in g["extensions"]
        ):
            raise PlanningError("扩展名无效")
        if not any(g[key] for key in ("types", "extensions", "names", "keywords")):
            raise PlanningError("包含组不能为空")
        groups.append(g)
    if not groups and not result["all_attachments"]:
        raise PlanningError("空规则不会匹配全部附件；请明确设置 all_attachments=true")
    result["groups"] = groups
    return result


def facts(message, caption: str | None = None) -> dict:
    file = getattr(message, "file", None)
    document = getattr(message, "document", None)
    photo = getattr(message, "photo", None)
    kind = (
        "视频"
        if getattr(message, "video", None)
        else "图片"
        if photo
        else "音频"
        if getattr(message, "audio", None) or getattr(message, "voice", None)
        else ""
    )
    name = getattr(file, "name", "") or ""
    ext = getattr(file, "ext", "") or Path(name).suffix
    mime = getattr(file, "mime_type", "") or ""
    return {
        "message_id": int(message.id),
        "chat_id": int(message.chat_id),
        "original": name[:1024],
        "caption": (
            caption
            if caption is not None
            else getattr(message, "raw_text", "")
            or getattr(message, "message", "")
            or ""
        )[:8192],
        "size": getattr(file, "size", None),
        "extension": ext,
        "kind": media_type(kind, mime, ext),
        "mime": mime,
        "media_key": f"document:{document.id}"
        if document
        else f"photo:{photo.id}"
        if photo
        else None,
        "attachment": bool(file and getattr(message, "media", None)),
        "protected": getattr(message, "noforwards", None) is not False,
        "group": str(getattr(message, "grouped_id", None) or ""),
    }


def evaluate(config: dict, item: dict, *, source_allowed: bool) -> tuple[bool, str]:
    config = validate(config)
    if not source_allowed:
        return False, "来源读取权限未通过"
    if not item.get("attachment"):
        return False, "无附件"
    size = item.get("size")
    if type(size) is not int or size <= 0:
        return False, "无法确认文件大小"
    name = norm(item["original"])
    text = (
        name
        if config["scope"] == "name"
        else norm(item["caption"])
        if config["scope"] == "caption"
        else name + "\n" + norm(item["caption"])
    )
    if any(norm(s) in text for s in config["exclude"]):
        return False, "排除关键词命中"
    if size < config["min_bytes"] or config["max_bytes"] and size > config["max_bytes"]:
        return False, "大小不符"
    for group in config["groups"]:
        if group["types"] and item["kind"] not in group["types"]:
            continue
        if group["extensions"] and not any(
            name.endswith("." + s) or norm(item["extension"]).lstrip(".") == s
            for s in group["extensions"]
        ):
            continue
        if group["names"] and not any(
            name == norm(s)
            if group["name_mode"] == "exact"
            else fnmatch.fnmatchcase(name, norm(s))
            if group["name_mode"] == "glob"
            else norm(s) in name
            for s in group["names"]
        ):
            continue
        hits = [norm(s) in text for s in group["keywords"]]
        if hits and not (all(hits) if group["keyword_mode"] == "all" else any(hits)):
            continue
        return True, "包含规则组命中"
    return (
        (True, "已明确选择全部附件")
        if config["all_attachments"] and not config["groups"]
        else (False, "类型、名称或关键词不符")
    )
