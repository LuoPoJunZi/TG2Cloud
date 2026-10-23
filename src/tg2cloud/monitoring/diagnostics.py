"""Bounded read-only report endpoint. No raw logs, messages, names or env values."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from tg2cloud.monitoring import readiness
from tg2cloud.version import VERSION

KINDS = {"authentication", "permission", "rate_limited", "server", "remote_conflict", "local_missing", "network", "other"}


def collect(data_dir: Path, *, environment=None, started_at: float = 0) -> dict:
    environment = os.environ if environment is None else environment
    report = {"schema": 1, "version": VERSION, "edition": environment.get("TG2CLOUD_STORAGE_BACKEND", "unknown"),
              "python": platform.python_version(), "architecture": platform.machine(),
              "checks": readiness.read(data_dir, now=time.time(), started_at=started_at)["checks"], "failures": {},
              "disk_free_bytes": None, "budget_bytes": None, "configuration": "incomplete",
              "logs": "未读取原始日志；仅统计任务中白名单错误分类（最近7天）"}
    if report["edition"] not in {"clouddrive2", "openlist"}:
        report["edition"] = "unknown"
    required = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH_B64", "BOT_TOKEN_B64", "ALLOWED_USER_ID")
    report["configuration"] = "present" if all(environment.get(key) for key in required) and all(
        environment.get(primary) or environment.get(legacy) for primary, legacy in (
            ("WEBDAV_URL_B64", "CD2_WEBDAV_URL_B64"), ("WEBDAV_USERNAME_B64", "CD2_WEBDAV_USERNAME_B64"),
            ("WEBDAV_PASSWORD_B64", "CD2_WEBDAV_PASSWORD_B64"))) else "incomplete"
    try:
        report["disk_free_bytes"] = min(shutil.disk_usage(environment.get(key, default)).free for key, default in (
            ("DATA_DIR", str(data_dir)), ("DOWNLOAD_DIR", "/downloads"), ("LOG_DIR", "/logs")))
        amount = float(environment.get("LOCAL_TEMP_BUDGET_GB", "20"))
        if 0 < amount < 2**30:
            report["budget_bytes"] = int(amount * 1024**3)
    except (OSError, ValueError, OverflowError):
        pass
    path = data_dir / "tg115.db"
    if path.is_symlink() or not path.is_file():
        return report
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as connection:
            connection.execute("PRAGMA query_only=ON")
            # Bound SQLite work as well as output size on large installations.
            deadline = time.monotonic() + 2
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            rows = connection.execute(
                "SELECT failure_kind,COUNT(*) FROM tasks WHERE state IN "
                "('download_failed','upload_failed_retained','verification_failed_retained') "
                "AND updated_at>=? GROUP BY failure_kind", (time.time() - 7 * 86400,)).fetchall()
            for kind, count in rows:
                kind = kind if kind in KINDS else "other"
                report["failures"][kind] = report["failures"].get(kind, 0) + count
    except sqlite3.Error:
        report["failures"] = {"unchecked": 0}
    return report


def main():
    try:
        import psutil
        print(json.dumps(collect(Path(os.environ.get("DATA_DIR", "/data")), started_at=psutil.Process(1).create_time())))
    except Exception:  # noqa: BLE001 - do not echo raw paths or tracebacks
        print('{"schema":0}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
