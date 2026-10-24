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


def inspect_entry(instance, session) -> tuple[str, str]:
    """Reuse read-only entry checks; never retain URLs, probe output or secrets."""
    from tg2cloud.deployment import instances
    from tg2cloud.deployment.proxy import lan
    from tg2cloud.deployment.proxy.manager import DomainProxyManager

    try:
        saved = lan.load_state(instance.product)
        if saved:
            if instance.directory != Path(saved["install_dir"]):
                return "内网管理入口", "未核实"
            lan.reject_https_route(instance.product)
            entry = lan.inspect_lan(instance.product, session, instances.docker_inventory(session))
            if not entry or not entry.get("running"):
                return "内网管理入口", "未通过"
            lan.check_entry(instance.product, saved["bind_ip"])
            return "内网管理入口", "本机检查通过"
        manager = DomainProxyManager(session, instance.product, {"vps_host": "127.0.0.1"}, lambda _: None)
        manager.prepare()
        report = manager.status()
        if report.state == "healthy":
            return "HTTPS 管理入口", "本机检查通过；有维护提醒" if report.warnings else "本机检查通过"
        if report.state == "not_configured":
            return "HTTPS 管理入口", "未配置"
        if report.state in {"running_error", "certificate_error"}:
            return "HTTPS 管理入口", "未通过"
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError, TimeoutError):
        pass
    return "HTTPS / LAN 入口", "未核实"


def recommendations(checks: dict, failures: dict, configuration: str, containers: dict,
                    entry_state: str) -> list[str]:
    """Actionable fixed text only; inputs must already pass the report whitelist."""
    tips = []
    if any(value not in {"running / healthy", "running / none"} for value in containers.values()):
        tips.append("先在“查看运行状态”核对 Bot 与网关；需启停时手动确认，不先卸载或重建数据库。")
    if configuration == "incomplete":
        tips.append("配置必填项不完整：在本机私密配置中核对，不把 .env、Token 或密码粘贴到聊天或报告。")
    if checks.get("telegram") == "failed":
        tips.append("Telegram 连接异常：核对 VPS 网络与 Bot 授权；不要删除 Session 或重复启动同一个 Bot。")
    if failures.get("authentication", 0):
        tips.append("认证失败：在“WebDAV 凭据”核对 Bot 专用账号，并在网关后台确认；不要使用外部只读账号替代，也不要连续重试。")
    if failures.get("permission", 0):
        tips.append("权限不足：在网关后台核对 Bot 用户根目录、保存子目录及写入权限；不要修改外部只读用户来解决上传失败。")
    if checks.get("destination") == "partial":
        tips.append("账号根目录可读但保存目录未确认：核对根目录与相对子目录，不自动创建或扩大账号访问范围。")
    elif checks.get("destination") == "failed" and not any(failures.get(key, 0) for key in ("authentication", "permission")):
        tips.append("WebDAV 目录探测异常：先核对存储网关、挂载和网络；目录可读不代表可写。")
    if "cooldown" in checks.values() or failures.get("rate_limited", 0):
        tips.append("检测到限流或冷却记录：等待现有冷却结束；历史失败分类不代表当前仍被限流，不反复探测或重启绕过。")
    if checks.get("capacity") == "failed":
        tips.append("容量不足：分别核对暂存额度与相关文件系统可用空间；只人工清理已确认归属的资料，不删除失败保留文件。")
    if checks.get("queue") == "paused":
        tips.append("调度已手动暂停：确认暂停原因解决后再恢复；诊断不会自动恢复调度。")
    if failures.get("remote_conflict", 0):
        tips.append("远端冲突：在 Bot 任务详情核对本地保留文件与远端状态，再确认“换名重传”；不要删除或覆盖未知远端文件。")
    if failures.get("local_missing", 0):
        tips.append("本地文件不可读：核对任务详情及暂存文件；先排除远端已接收，再对自己的任务选择安全重试。")
    if failures.get("network", 0) or failures.get("server", 0):
        tips.append("网络或服务端异常：先核对网关健康与连接；上传结果不确定时保留本地副本，不盲目重复上传。")
    if entry_state != "本机检查通过":
        tips.append("在“HTTPS 与管理”核对入口、证书及续期提醒；不要停掉其他项目的代理，公网或局域网访问还需另一设备验证。")
    if not checks or "unknown" in checks.values() or "unchecked" in failures:
        tips.append("部分诊断未核实：确认实际 Bot 与离线工具版本及观察时间；未核实不是通过，不因诊断缺失自动重装。")
    if not tips:
        tips.append("本次未发现明确处理项；仍需按需完成 WebDAV 写入验收及自有小文件转存，不把只读诊断当作完整验收。")
    return tips


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
    containers = {}
    checks, failures, configuration = {}, {}, "unknown"
    for label, name in (("Bot", instance.product.bot_container), ("网关", instance.product.storage_container)):
        code, output = session.run("docker inspect --format " + shlex.quote('{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}') + " " + shlex.quote(name), timeout=10)
        fields = output.strip().split()
        valid = not code and len(fields) == 2 and fields[0] in {"running", "exited", "restarting", "created", "paused", "dead"} and fields[1] in {"healthy", "unhealthy", "starting", "none"}
        containers[label] = " / ".join(fields) if valid else "未检查"
        lines.append(label + " 容器：" + containers[label])
    code, output = session.run("docker exec " + shlex.quote(instance.product.bot_container)
                               + " python -B -m tg2cloud.monitoring.diagnostics", timeout=20)
    try:
        if code or len(output) > 16384:
            raise ValueError
        value = json.loads(output)
        if (not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1
                or value["edition"] != instance.product.key
                or not isinstance(value["version"], str) or not isinstance(value["python"], str)
                or not isinstance(value["checks"], dict) or not isinstance(value["failures"], dict)
                or not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", value["version"])
                or value["version"] != getattr(instance, "version", value["version"])
                or not re.fullmatch(r"\d+\.\d+\.\d+", value["python"])
                or set(value["checks"]) != set(readiness.LABELS)
                or any(state not in readiness.STATES for state in value["checks"].values())
                or set(value["failures"]) - set(FAILURES)
                or any(type(count) is not int or not 0 <= count <= 10**12 for count in value["failures"].values())
                or value["configuration"] not in {"present", "incomplete"}):
            raise ValueError
        checks, failures, configuration = value["checks"], value["failures"], value["configuration"]
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
    entry_label, entry_state = inspect_entry(instance, session)
    lines += ["", entry_label + "：" + entry_state,
              "入口检查不含公网／其他客户端验收，不执行签发、续期或配置修复。",
              "", "## 建议处理顺序"]
    lines.extend(f"{number}. {tip}" for number, tip in enumerate(
        recommendations(checks, failures, configuration, containers, entry_state), 1))
    lines += ["",
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
