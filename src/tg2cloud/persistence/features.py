"""Versioned optional settings and durable incidents in the existing metadata DB."""
from __future__ import annotations

import json
import os
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KEY = "optional-features.v1"
MODES = {"off": "不分类", "type": "按类型", "year": "按年份", "month": "按年月", "type_month": "按类型/年月"}


def defaults() -> dict:
    return {"schema": 1, "revision": "initial", "classification": "off",
            "timezone": os.environ.get("TZ", "Asia/Shanghai"), "notifications": False,
            "recovery_notifications": True, "cooldown_seconds": 1800,
            "disk_threshold_bytes": 0, "sustained_seconds": 300, "blocked_seconds": 1800}


def validate(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != set(defaults()):
        raise ValueError("可选功能配置结构不受支持")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["classification"] not in MODES:
        raise ValueError("可选功能配置版本或分类规则无效")
    if not isinstance(value["revision"], str) or len(value["revision"]) > 64:
        raise ValueError("可选功能配置修订号无效")
    for key in ("notifications", "recovery_notifications"):
        if type(value[key]) is not bool:
            raise ValueError("通知开关必须是布尔值")
    for key, low, high in (("cooldown_seconds", 60, 86400), ("sustained_seconds", 30, 86400),
                           ("blocked_seconds", 60, 604800), ("disk_threshold_bytes", 0, 2**60)):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("通知阈值超出支持范围")
    if value["timezone"] != "UTC":
        try:
            ZoneInfo(value["timezone"])
        except (ValueError, TypeError, ZoneInfoNotFoundError):
            raise ValueError("时区不可用；请核对系统 IANA 时区数据") from None
    return value


def read(connection) -> dict:
    row = connection.execute("SELECT value FROM service_meta WHERE key=?", (KEY,)).fetchone()
    if row and len(row[0]) > 4096:
        raise ValueError("可选功能配置过大")
    return validate(json.loads(row[0])) if row else defaults()


def change(connection, revision: str, updates: dict) -> dict:
    if not isinstance(updates, dict) or set(updates) - (set(defaults()) - {"schema", "revision"}):
        raise ValueError("未知可选功能配置")
    connection.execute("BEGIN IMMEDIATE")
    try:
        value = read(connection)
        if value["revision"] != revision:
            raise ValueError("配置已变化，请刷新后重试")
        value.update(updates, revision=secrets.token_hex(16))
        validate(value)
        connection.execute("INSERT INTO service_meta(key,value) VALUES(?,?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (KEY, json.dumps(value)))
        connection.execute("COMMIT")
        return value
    except BaseException:
        connection.execute("ROLLBACK")
        raise
