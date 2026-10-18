"""Family grants in existing service_meta; no DDL, credentials or task deletion."""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

KEY = "family-users.v1"
MAX_MEMBERS = 32


def user_id(value) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,14}", str(value)):
        raise ValueError("请输入一个有效的 Telegram 用户 ID")
    return int(value)


def validate(item: dict, admin_id: int) -> dict:
    if (not isinstance(item, dict) or set(item) != {"schema", "admin_id", "revision", "users", "events"}
            or type(item["schema"]) is not int or item["schema"] != 1
            or type(item["admin_id"]) is not int or item["admin_id"] != admin_id
            or not isinstance(item["revision"], str) or not re.fullmatch(r"[a-f0-9]{32}|initial", item["revision"])
            or not isinstance(item["users"], list) or len(item["users"]) > MAX_MEMBERS
            or not isinstance(item["events"], list) or len(item["events"]) > 100):
        raise ValueError("家庭授权记录不受支持或管理员已变化；请人工核对，不自动接管")
    seen = {admin_id}
    for member in item["users"]:
        if (not isinstance(member, dict) or set(member) != {"id", "name", "enabled"}
                or type(member["enabled"]) is not bool or type(member["id"]) is not int
                or user_id(member["id"]) in seen or not isinstance(member["name"], str)
                or not 1 <= len(member["name"]) <= 40
                or any(ord(c) < 32 or ord(c) == 127 for c in member["name"])):
            raise ValueError("家庭用户记录无效；不开放额外授权")
        seen.add(member["id"])
    for event in item["events"]:
        if (not isinstance(event, dict) or set(event) != {"id", "action", "at"}
                or type(event["id"]) is not int or user_id(event["id"]) == admin_id
                or event["action"] not in {"add", "enable", "disable", "remove"}
                or type(event["at"]) is not int or event["at"] < 0):
            raise ValueError("家庭授权审计记录无效")
    return item


def read(connection: sqlite3.Connection, admin_id: int) -> dict:
    row = connection.execute("SELECT value FROM service_meta WHERE key=?", (KEY,)).fetchone()
    if row is None:
        return {"schema": 1, "admin_id": admin_id, "revision": "initial", "users": [], "events": []}
    if len(row[0]) > 32768:
        raise ValueError("家庭授权记录过大")
    return validate(json.loads(row[0]), admin_id)


def change(connection: sqlite3.Connection, admin_id: int, request: dict) -> dict:
    action = request.get("action")
    if action not in {"add", "enable", "disable", "remove"}:
        raise ValueError("未知用户管理操作")
    member_id = user_id(request.get("id"))
    if member_id == admin_id:
        raise ValueError("安装时的管理员不能通过家庭成员菜单移除或变更角色")
    connection.execute("BEGIN IMMEDIATE")
    try:
        item = read(connection, admin_id)
        if request.get("revision") != item["revision"]:
            raise ValueError("确认期间授权记录已变化，请刷新后重试")
        member = next((m for m in item["users"] if m["id"] == member_id), None)
        if action == "add":
            if member is not None or len(item["users"]) >= MAX_MEMBERS:
                raise ValueError("用户已存在或达到家庭成员数量限制")
            member = {"id": member_id, "name": request.get("name", "家庭成员"), "enabled": True}
            item["users"].append(member)
        elif member is None:
            raise ValueError("未找到已登记的家庭成员")
        elif action == "remove":
            item["users"].remove(member)
        else:
            member["enabled"] = action == "enable"
        item["revision"] = secrets.token_hex(16)
        item["events"] = [*item["events"][-99:], {"id": member_id, "action": action, "at": int(time.time())}]
        validate(item, admin_id)
        connection.execute("INSERT INTO service_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (KEY, json.dumps(item, ensure_ascii=True)))
        connection.execute("COMMIT")
        return item
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def main() -> int:
    """Fixed local Docker exec endpoint; never create or migrate a missing DB."""
    try:
        admin_id = user_id(os.environ.get("ALLOWED_USER_ID", ""))
        path = Path(os.environ.get("DATA_DIR", "/data")) / "tg115.db"
        if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
            raise ValueError("现有数据库不存在或路径不安全")
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError("请求过大")
        request = json.loads(raw)
        if not isinstance(request, dict) or request.get("admin_id") != admin_id:
            raise ValueError("管理员身份与运行实例不一致")
        with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=15)) as connection:
            if request.get("action") == "list":
                item = read(connection, admin_id)
            else:
                item = change(connection, admin_id, request)
        print(json.dumps({"api": 1, "record": item}, ensure_ascii=True))
        return 0
    except Exception:  # noqa: BLE001 - fixed endpoint must not print private database tracebacks
        print("家庭授权操作未完成；请核对 Bot 版本、数据库及授权记录，不输出配置或凭据。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
