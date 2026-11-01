"""Single-shot offline-manager view of the Bot's recent read-only observations."""
from __future__ import annotations

import json
import math
import shlex

# Shared optional-observation protocol: host helpers need only this existing
# stdlib module; sampling and bounded event collection remain in monitoring.
PER_KIND = 64
LISTENER_STATES = {
    "unknown",
    "disabled",
    "connecting",
    "healthy",
    "cooldown",
    "stale",
    "partial",
}

EVENT_LABELS = {
    "listener_wait": "Telegram 下载限速等待",
    "listener_network": "监听请求连接异常",
    "listener_server": "Telegram 服务端异常",
    "destination_network": "WebDAV 探测连接异常",
    "destination_authentication": "WebDAV 探测认证异常",
    "destination_permission": "WebDAV 探测权限异常",
    "destination_rate_limited": "WebDAV 探测限流",
    "destination_server": "WebDAV 探测服务端异常",
}

def unknown_listener():
    return {
        "state": "unknown",
        "enabled": False,
        "sources": 0,
        "stale_sources": 0,
        "gap_sources": 0,
        "retrying_sources": 0,
        "poll_age_seconds": -1,
        "loop_age_seconds": -1,
        "cooldown_seconds": 0,
    }

def validate_listener(value):
    if not isinstance(value, dict) or set(value) != set(unknown_listener()):
        return None
    if (
        type(value["enabled"]) is not bool
        or not isinstance(value["state"], str)
        or value["state"] not in LISTENER_STATES
    ):
        return None
    for key in ("sources", "stale_sources", "gap_sources", "retrying_sources"):
        if type(value[key]) is not int or not 0 <= value[key] <= 32:
            return None
    if any(
        value[k] > value["sources"]
        for k in ("stale_sources", "gap_sources", "retrying_sources")
    ):
        return None
    for key in ("poll_age_seconds", "loop_age_seconds", "cooldown_seconds"):
        if (
            type(value[key]) is not int
            or not (-1 if key.endswith("age_seconds") else 0) <= value[key] <= 10**12
        ):
            return None
    if (
        value["state"] == "disabled"
        and value["enabled"]
        or not value["enabled"]
        and value["state"] not in {"disabled", "unknown"}
    ):
        return None
    if value["state"] == "healthy" and (
        value["stale_sources"]
        or value["gap_sources"]
        or value["retrying_sources"]
        or not 0 <= value["loop_age_seconds"] <= 90
    ):
        return None
    return dict(value)

def validate_events(value):
    if not isinstance(value, dict) or set(value) - set(EVENT_LABELS):
        return None
    for entry in value.values():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"count", "last_at", "bounded"}
            or type(entry["count"]) is not int
            or not 1 <= entry["count"] <= PER_KIND
            or type(entry["bounded"]) is not bool
            or type(entry["last_at"]) not in {int, float}
            or not math.isfinite(entry["last_at"])
            or not 0 <= entry["last_at"] <= 10**12
        ):
            return None
    return value

def listener_line(value):
    value = validate_listener(value)
    if value is None:
        return "个人监听：未核实（旧快照或尚未观察）"
    labels = {
        "unknown": "未核实",
        "disabled": "未启用",
        "connecting": "等待连接",
        "healthy": "正常",
        "cooldown": "冷却中",
        "stale": "循环或来源轮询未及时更新",
        "partial": "部分来源待重试或存在补拉缺口",
    }
    line = "个人监听：" + labels[value["state"]]
    if value["enabled"]:
        line += f"；启用来源 {value['sources']}，轮询过期 {value['stale_sources']}，缺口 {value['gap_sources']}"
        if value["cooldown_seconds"]:
            line += f"；冷却剩余 {value['cooldown_seconds']} 秒"
    return line

LABELS = {"heartbeat": "运行心跳", "telegram": "Telegram 连接", "destination": "WebDAV 最近目录探测",
          "queue": "调度开关", "capacity": "新下载空间"}
STATES = {"ok": "通过", "failed": "未通过", "unknown": "未核实／记录过期",
          "partial": "仅账号根目录可读，目标目录未确认", "paused": "手动暂停", "cooldown": "冷却中，不追加请求"}


def inspect(instance, session, *, details=False) -> dict | None:
    """Read one bounded local observation; never trigger a network probe or retry."""
    command = "docker exec " + shlex.quote(instance.product.bot_container) + " python -B -m tg2cloud.monitoring.readiness"
    try:
        code, output = session.run(command, timeout=20)
        if code or len(output) > 16384:
            raise ValueError
        report = json.loads(output)
        checks = report["checks"]
        if (type(report.get("schema")) is not int or report["schema"] != 1
                or report.get("version") != instance.version or set(checks) != set(LABELS)
                or any(value not in STATES for value in checks.values())
                or type(report.get("ready")) is not bool):
            raise ValueError
        if report.get("edition") not in {None, instance.product.key}:
            raise ValueError
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, TimeoutError):
        return None
    return report if details else {key: checks[key] for key in LABELS}


def check(instance, session, log) -> bool:
    report = inspect(instance, session, details=True)
    if report is None:
        log("业务就绪未核实：运行中的 Bot 可能未支持本协议，或返回不完整；请核对版本与运行日志，不重启／重装。")
        return False
    checks = report["checks"]
    for key, label in LABELS.items():
        log(label + "：" + STATES[checks[key]])
    log(listener_line(report.get("listener")))
    ready = all(value == "ok" for value in checks.values())
    log("业务就绪：" + ("基础条件通过" if ready else "尚未全部确认")
        + "；以上为 Bot 基础条件，个人监听单独观察；不额外请求 Telegram/WebDAV，不代表实际转存完成。")
    return ready
