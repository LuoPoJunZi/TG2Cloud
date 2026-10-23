"""Safe report renderer/exporter; subprocess output is validated, never echoed."""
from __future__ import annotations

import json
import os
import platform
import re
import secrets
import shlex
from datetime import datetime, timezone
from pathlib import Path

from tg2cloud.deployment import readiness, runtime

FAILURES = {"authentication": "认证失败", "permission": "权限不足", "rate_limited": "限流", "server": "服务端异常",
            "remote_conflict": "远端待复核", "local_missing": "本地文件不可读", "network": "网络或校验异常", "other": "其他", "unchecked": "未检查"}


def collect(instance, session) -> str:
    lines = ["# TG2Cloud 故障诊断报告", "", "仅只读检查；不包含原始日志、文件名、私人路径或凭据。",
             "", "生成时间（UTC）：" + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
             "Edition：" + instance.product.display_name,
             "宿主系统：" + ("Linux" if platform.system() == "Linux" else "非 Linux（未作宿主实机验收）"),
             "宿主架构：" + {"aarch64": "ARM64", "arm64": "ARM64", "AMD64": "AMD64", "x86_64": "AMD64"}.get(platform.machine(), "未检查")]
    for label, command in (("Docker", "docker version --format '{{.Server.Version}}'"),
                           ("Compose", "docker compose version --short")):
        code, output = session.run(command, timeout=10)
        value = output.strip()
        lines.append(label + "：" + (value if not code and re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?", value) else "未检查"))
    for label, name in (("Bot", instance.product.bot_container), ("网关", instance.product.storage_container)):
        code, output = session.run("docker inspect --format " + shlex.quote('{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}') + " " + shlex.quote(name), timeout=10)
        fields = output.strip().split()
        valid = not code and len(fields) == 2 and fields[0] in {"running", "exited", "restarting", "created", "paused", "dead"} and fields[1] in {"healthy", "unhealthy", "starting", "none"}
        lines.append(label + " 容器：" + (" / ".join(fields) if valid else "未检查"))
    code, output = session.run("docker exec " + shlex.quote(instance.product.bot_container)
                               + " python -B -m tg2cloud.monitoring.diagnostics", timeout=20)
    try:
        if code or len(output) > 16384:
            raise ValueError
        value = json.loads(output)
        if (value["schema"] != 1 or value["edition"] != instance.product.key
                or not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", value["version"])
                or not re.fullmatch(r"\d+\.\d+\.\d+", value["python"])
                or set(value["checks"]) != set(readiness.LABELS)
                or any(state not in readiness.STATES for state in value["checks"].values())
                or set(value["failures"]) - set(FAILURES)
                or any(type(count) is not int or not 0 <= count <= 10**12 for count in value["failures"].values())
                or value["configuration"] not in {"present", "incomplete"}):
            raise ValueError
        lines += ["实际 Bot 版本：" + value["version"], "Bot Python：" + value["python"],
                  "配置必填项：" + ("存在（不代表凭据有效）" if value["configuration"] == "present" else "不完整")]
        for key, label in readiness.LABELS.items():
            lines.append(label + "：" + readiness.STATES[value["checks"][key]])
        for key, label in (("disk_free_bytes", "已检查目录最小可用空间"), ("budget_bytes", "任务暂存额度")):
            amount = value.get(key)
            lines.append(label + "：" + (f"{amount / 1024**3:.2f} GB" if type(amount) is int and 0 <= amount <= 2**60 else "未检查"))
        lines += ["", "## 最近7天当前失败任务分类（非原始日志）"]
        lines.extend(FAILURES[key] + f"：{count}" for key, count in sorted(value["failures"].items()))
        if not value["failures"]:
            lines.append("当前无此范围内的失败任务；不代表从未发生错误。")
    except (ValueError, TypeError, KeyError):
        lines.append("Bot 诊断快照：未检查（未运行、旧版本或响应不受支持）")
    lines += ["", "HTTPS / LAN 入口：未检查（请使用本地管理菜单 6 单独检查）",
              "日志摘要：不读取原始容器日志，仅输出上面的白名单错误分类。",
              "未执行 WebDAV 写入、服务重启或软件安装。目录可读不代表可写或云盘官方最终完成。", ""]
    return "\n".join(lines)


def save(text: str, parent: Path) -> Path:
    if not parent.is_absolute() or parent == Path(parent.anchor) or len(text.encode("utf-8")) > 32768:
        raise ValueError("报告目录或大小无效")
    runtime.safe_path(parent, private=True)
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime.safe_path(parent, private=True)
    if os.name == "posix" and parent.stat().st_mode & 0o077:
        raise ValueError("报告目录必须私有（0700）")
    path = parent / ("diagnostic-" + secrets.token_hex(8) + ".md")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
        writer.write(text)
    return path
