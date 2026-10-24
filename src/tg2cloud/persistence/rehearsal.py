"""Offline database startup/recovery rehearsal, never a production Restore.

No Session, environment file, archived code, network client or gateway is loaded.
Only the checked database copy is opened with the current TaskDB implementation.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from tg2cloud.deployment.runtime import safe_path
from tg2cloud.persistence import bundle
from tg2cloud.version import VERSION

MAX_TASKS = 20000


def task_count(path: Path) -> int:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + 5
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        # Do not let CREATE TABLE IF NOT EXISTS turn an unrelated SQLite file
        # into a deceptively successful empty business database rehearsal.
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        if not {"id", "chat_id", "message_id", "sender_id", "file_name", "file_size", "state",
                "created_at", "updated_at", "local_path", "remote_path", "downloaded_bytes",
                "uploaded_bytes", "download_retries", "upload_retries", "error", "wait_reason",
                "next_retry_at"} <= columns:
            raise ValueError("unsupported business database")
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count > MAX_TASKS:
            raise ValueError("rehearsal task resource limit")
        return count


def rehearse(archive: Path, scratch: Path, edition: str, target_version: str = VERSION) -> dict:
    if target_version != VERSION:
        raise ValueError("rehearsal target must match executing code")
    safe_path(archive, private=True)
    safe_path(scratch, private=True)
    with bundle.verified_snapshot(archive, scratch, edition, target_version) as (root, coverage):
        # Import from this trusted source tree, never from extracted files.
        from tg2cloud.persistence.sqlite import TaskDB

        downloads = root / "rehearsal-downloads"
        downloads.mkdir(mode=0o700)
        count = task_count(root / "data/tg115.db")
        db = TaskDB(root / "data/tg115.db")
        try:
            # Archives exclude downloads. Never stat/read a production path
            # stored in a row; this intentionally models unavailable local files.
            db._conn.execute("UPDATE tasks SET local_path=NULL WHERE local_path IS NOT NULL")
            recovered = db.recover(downloads)
            if db._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] != count:
                raise ValueError("task history changed unexpectedly")
            if db._conn.execute("PRAGMA quick_check").fetchall()[0][0] != "ok":
                raise ValueError("rehearsal database integrity failed")
            schema = db._conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            db.close()
        return {"scope": "isolated-database-startup-and-recovery-only", "edition": edition,
                "target_version": VERSION, "files": coverage["files"], "tasks": count,
                "schema": schema, "recovery": recovered, "downloads": "excluded-modeled-as-missing",
                "telegram": "not-connected", "gateway": "not-started", "session": "not-loaded"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="隔离数据库启动与重启恢复演练；不连接 Telegram 或网盘，不恢复生产实例")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--edition", choices=("clouddrive2", "openlist"), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = rehearse(args.archive, args.scratch, args.edition)
    except KeyboardInterrupt:
        print("隔离恢复演练已中断；未操作运行实例，请核对私密隔离目录。")
        return 130
    except Exception:  # noqa: BLE001 - backup metadata, credentials and paths are private
        print("隔离恢复演练未通过：请核对来源、版本、权限、备份完整性及私密隔离目录；未修改运行实例。")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"隔离数据库演练通过：{report['tasks']} 个任务，数据库 schema {report['schema']}。")
        print("仅验证当前代码打开／迁移数据库及重启恢复逻辑；缺失本地文件按未备份处理。")
        print("未连接 Telegram、加载 Session 或启动网关；不代表完整服务恢复、网盘授权或真实转存通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
