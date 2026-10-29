"""Root-owned offline manager endpoint; credentials are never part of this API."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

from tg2cloud.persistence import features, quotas, users
from tg2cloud.persistence.migrations import SCHEMA_VERSION
from tg2cloud.persistence.paths import database_path


def handle(connection, admin: int, request: dict) -> dict:
    if type(request.get("admin_id")) is not int or request["admin_id"] != admin:
        raise ValueError("管理员身份不匹配")
    action = request.get("action")
    if action == "settings-read":
        return {"api": 1, "settings": features.read(connection)}
    if action == "settings-write":
        return {"api": 1, "settings": features.change(connection, request.get("revision"), request.get("updates"))}
    if action not in {"quota-read", "quota-write"}:
        raise ValueError("未知操作")
    user_id = users.user_id(request.get("user_id"))
    # Use the current existing grant, not a new parallel identity system.
    connection.execute("BEGIN IMMEDIATE")
    try:
        record = users.read(connection, admin)
        if user_id == admin or not any(member["id"] == user_id for member in record["users"]):
            raise ValueError("只能管理已登记的家庭成员配额；管理员不受本菜单限制")
        if action == "quota-write":
            if request.get("revision") != record["revision"]:
                raise ValueError("授权已变化，请刷新")
            before = quotas.limits(connection, user_id)
            if before != request.get("expected"):
                raise ValueError("配额已变化，请刷新")
            quotas.configure(connection, user_id, request.get("values"))
        value = quotas.usage(connection, user_id, time.time(), features.read(connection)["timezone"])
        connection.execute("COMMIT")
        return {"api": 1, "usage": value}
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def main() -> int:
    try:
        admin = users.user_id(os.environ.get("ALLOWED_USER_ID", ""))
        path = database_path(Path(os.environ.get("DATA_DIR", "/data")), require_existing=True)
        if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
            raise ValueError("数据库路径不安全")
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("请求过大")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise TypeError("请求格式无效")
        with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=15)) as connection:
            connection.row_factory = sqlite3.Row
            if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("数据库版本不匹配；此端点不迁移数据库")
            result = handle(connection, admin, request)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception:  # noqa: BLE001 - no private traceback or raw request output
        print("操作未完成；请刷新配置并核对 Bot 版本、权限和数据库。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
