"""Single-shot offline-manager view of the Bot's recent read-only observations."""
from __future__ import annotations

import json
import shlex

LABELS = {"heartbeat": "运行心跳", "telegram": "Telegram 连接", "destination": "WebDAV 最近目录探测",
          "queue": "调度开关", "capacity": "新下载空间"}
STATES = {"ok": "通过", "failed": "未通过", "unknown": "未核实／记录过期",
          "partial": "仅账号根目录可读，目标目录未确认", "paused": "手动暂停", "cooldown": "冷却中，不追加请求"}


def inspect(instance, session) -> dict[str, str] | None:
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
    return {key: checks[key] for key in LABELS}


def check(instance, session, log) -> bool:
    checks = inspect(instance, session)
    if checks is None:
        log("业务就绪未核实：运行中的 Bot 可能未支持本协议，或返回不完整；请核对版本与运行日志，不重启／重装。")
        return False
    for key, label in LABELS.items():
        log(label + "：" + STATES[checks[key]])
    ready = all(value == "ok" for value in checks.values())
    log("业务就绪：" + ("基础条件通过" if ready else "尚未全部确认")
        + "；使用最近观察，不额外请求 Telegram/WebDAV，不代表可写或实际转存完成。")
    return ready
