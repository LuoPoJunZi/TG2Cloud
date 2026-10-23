"""Per-member admission accounting; caller owns BEGIN IMMEDIATE and RLock."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import time as day_time
from zoneinfo import ZoneInfo

ACTIVE = ("reserved", "downloading", "streaming", "uploading", "verifying", "finalizing")


class QuotaExceeded(ValueError):
    pass


def day_bounds(now: float, zone_name: str) -> tuple[float, float]:
    zone = timezone.utc if zone_name == "UTC" else ZoneInfo(zone_name)
    day = datetime.fromtimestamp(now, zone).date()
    return (datetime.combine(day, day_time(), zone).timestamp(),
            datetime.combine(day + timedelta(days=1), day_time(), zone).timestamp())


def limits(connection, user_id: int) -> dict:
    row = connection.execute("SELECT daily_bytes,max_queued,max_active FROM member_quotas WHERE user_id=?", (user_id,)).fetchone()
    return dict(zip(("daily_bytes", "max_queued", "max_active"), row)) if row else {"daily_bytes": 0, "max_queued": 0, "max_active": 0}


def usage(connection, user_id: int, now: float, zone_name: str) -> dict:
    result = limits(connection, user_id)
    # Unlimited legacy users must not require tzdata just to submit a task.
    start, end = day_bounds(now, zone_name)
    completed, reserved = connection.execute(
        "SELECT COALESCE(SUM(CASE WHEN charged_at>=? AND charged_at<? THEN bytes ELSE 0 END),0),"
        "COALESCE(SUM(CASE WHEN charged_at IS NULL AND released=0 THEN bytes ELSE 0 END),0) "
        "FROM quota_ledger WHERE user_id=?", (start, end, user_id)).fetchone()
    queued = connection.execute("SELECT COUNT(*) FROM tasks WHERE sender_id=? AND state IN "
                                "('queued','downloaded','waiting_upload')", (user_id,)).fetchone()[0]
    active = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE sender_id=? AND (state IN "
        "('reserved','downloading','streaming','uploading','verifying','finalizing') "
        "OR id IN (SELECT task_id FROM quota_slots))", (user_id,)).fetchone()[0]
    result.update(completed_bytes=completed, reserved_bytes=reserved, queued=queued, active=active,
                  available_bytes=max(0, result["daily_bytes"] - completed - reserved) if result["daily_bytes"] else None)
    return result


def admit(connection, user_id: int, size: int, now: float, zone_name: str, *, task_id: int | None = None) -> None:
    limit = limits(connection, user_id)
    if not any(limit.values()):
        return
    value = usage(connection, user_id, now, zone_name)
    ledger = connection.execute("SELECT charged_at,released FROM quota_ledger WHERE task_id=?", (task_id,)).fetchone() if task_id else None
    reserved = bool(ledger and (ledger[0] is not None or not ledger[1]))
    if limit["daily_bytes"] and not reserved and (size <= 0 or size > value["available_bytes"]):
        raise QuotaExceeded("今日转存额度不足（含未完成任务预留）；请查看 /quota 或联系管理员")
    if limit["max_queued"] and value["queued"] >= limit["max_queued"]:
        raise QuotaExceeded("个人排队数量达到上限；请等待任务处理或取消自己的排队任务")


def slot_available(connection, user_id: int, task_id: int) -> bool:
    limit = limits(connection, user_id)["max_active"]
    if not limit:
        return True
    # Count tasks, not phases: a stream consumes one member slot while still
    # respecting BOTH existing global download and upload windows.
    count = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE sender_id=? AND id!=? AND (state IN "
        "('reserved','downloading','streaming','uploading','verifying','finalizing') "
        "OR id IN (SELECT task_id FROM quota_slots))", (user_id, task_id)).fetchone()[0]
    return count < limit


def configure(connection, user_id: int, values: dict) -> None:
    if not isinstance(values, dict) or set(values) != {"daily_bytes", "max_queued", "max_active"}:
        raise ValueError("配额配置字段无效")
    if any(type(value) is not int or value < 0 for value in values.values()) or values["daily_bytes"] > 2**60 or max(values["max_queued"], values["max_active"]) > 100000:
        raise ValueError("配额值无效；0 表示不限制")
    connection.execute("INSERT INTO member_quotas(user_id,daily_bytes,max_queued,max_active) VALUES(?,?,?,?) "
                       "ON CONFLICT(user_id) DO UPDATE SET daily_bytes=excluded.daily_bytes,"
                       "max_queued=excluded.max_queued,max_active=excluded.max_active",
                       (user_id, values["daily_bytes"], values["max_queued"], values["max_active"]))
