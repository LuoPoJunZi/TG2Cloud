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
from tg2cloud.deployment.readiness import (
    EVENT_LABELS,
    listener_line,
    validate_events,
)

FAILURES = {"authentication": "认证失败", "permission": "权限不足", "rate_limited": "限流", "server": "服务端异常",
            "remote_conflict": "远端待复核", "local_missing": "本地文件不可读", "network": "网络或校验异常", "source_access": "监听来源或附件不可读", "other": "其他", "unchecked": "未检查"}


LOG_CONTAINERS = ("Bot", "网关", "共享 Nginx", "Certbot")
LOG_STATES = {
    "ok": "已生效（每份不超过10m，最多3份）",
    "pending": "未采用项目轮转限额（旧容器需确认更新）",
    "custom": "已有限额，但与项目设置不同；请核对",
    "other": "使用其他日志驱动；需核对其保留策略",
    "unknown": "未核实（未使用、不可读或归属未确认）",
}


def inspect_container_logs(instance, session) -> dict[str, str]:
    """Inspect actual owned containers, never their env, arguments or log content."""
    result = dict.fromkeys(LOG_CONTAINERS, "unknown")
    template = ('{"driver":{{json .HostConfig.LogConfig.Type}},'
                '"size":{{json (index .HostConfig.LogConfig.Config "max-size")}},'
                '"files":{{json (index .HostConfig.LogConfig.Config "max-file")}},'
                '"directory":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
                '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"managed":{{json (index .Config.Labels "com.tg2cloud.managed")}},'
                '"role":{{json (index .Config.Labels "com.tg2cloud.role")}}}')
    try:
        product = instance.product
        directory = str(instance.directory)
        owned = (("Bot", product.bot_container, directory, product.bot_service, ""),
                 ("网关", product.storage_container, directory, product.key, ""),
                 ("共享 Nginx", "tg2cloud-proxy-nginx", "/opt/tg2cloud-proxy", "nginx", "reverse-proxy"),
                 ("Certbot", "tg2cloud-proxy-certbot", "/opt/tg2cloud-proxy", "certbot", "certificate-manager"))
    except AttributeError:
        return result
    for label, name, root, service, role in owned:
        try:
            code, output = session.run("docker container inspect --format " + shlex.quote(template)
                                       + " " + shlex.quote(name), timeout=10)
            if code or len(output) > 8192:
                continue
            value = json.loads(output)
            if (not isinstance(value, dict) or value.get("directory") != root
                    or value.get("service") != service
                    or role and (value.get("managed") != "true" or value.get("role") != role)):
                continue
            if value.get("driver") != "json-file":
                result[label] = "other" if isinstance(value.get("driver"), str) else "unknown"
                continue
            size = value.get("size")
            files = value.get("files")
            match = re.fullmatch(r"([1-9][0-9]{0,12})([kKmMgG]?)(?:[bB])?", size) if isinstance(size, str) else None
            if not match or not isinstance(files, str) or not re.fullmatch(r"[1-9][0-9]{0,6}", files):
                result[label] = "pending"
                continue
            amount = int(match[1]) * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[match[2].lower()]
            result[label] = "ok" if amount <= 10 * 1024**2 and int(files) <= 3 else "custom"
        except (ValueError, TypeError, KeyError, OSError, RuntimeError, TimeoutError):
            continue
    return result


def log_rotation_lines(value) -> list[str]:
    if not isinstance(value, dict):
        return ["容器日志轮转：未核实"]
    lines = [label + "：" + LOG_STATES.get(value.get(label), LOG_STATES["unknown"])
             if isinstance(value.get(label), str) else label + "：" + LOG_STATES["unknown"]
             for label in LOG_CONTAINERS]
    if any(value.get(label) == "pending" for label in LOG_CONTAINERS):
        lines.append("修改 Compose 或仅重启不会更新旧容器日志参数；先确认中断影响，再按原部署方式更新创建对应容器。")
    return lines


def inspect_entry(instance, session) -> tuple[str, str]:
    """Reuse read-only entry checks; never retain URLs, probe output or secrets."""
    from tg2cloud.deployment import instances
    from tg2cloud.deployment.proxy import lan
    from tg2cloud.deployment.proxy.manager import DomainProxyManager

    try:
        if getattr(instance, "deployment_mode", None) == "compose":
            from tg2cloud.compose import access
            from tg2cloud.compose.https import ComposeInstance, ComposeProxyManager
            from tg2cloud.deployment.host import SafeLog
            core = ComposeInstance(instance.directory, session, SafeLog(),
                                   source=instance.directory / "https-tools")
            core.validate(loopback=False, require_running=False)
            plan = access.read_access(instance.directory, instance.product.key)
            if plan is None or plan["mode"] == "local":
                return "Compose 本地管理入口", "未执行网络验收（无需证书）"
            if plan["mode"] == "external":
                return "已有反向代理入口", "待外部代理独立验收"
            report = ComposeProxyManager(core, None).inspect_status()
            return "HTTPS 管理入口", {"healthy": "本机检查通过", "not_configured": "未配置"}.get(report.state, "未通过")
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
                    entry_state: str, listener=None) -> list[str]:
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
        tips.append("下载资源不足：核对可用内存、容器内存上限、暂存额度与文件系统可用空间；不降低保护阈值或删除失败保留文件。")
    if checks.get("queue") == "paused":
        tips.append("调度已手动暂停：确认暂停原因解决后再恢复；诊断不会自动恢复调度。")
    if failures.get("remote_conflict", 0):
        tips.append("远端冲突：在 Bot 任务详情核对本地保留文件与远端状态，再确认“换名重传”；不要删除或覆盖未知远端文件。")
    if failures.get("source_access", 0):
        tips.append("监听来源或附件不可读：在任务详情核对具体原因；原消息可能已删除或没有附件，不因该分类直接要求重新登录，也不无限重试。")
    if failures.get("local_missing", 0):
        tips.append("本地文件不可读：核对任务详情及暂存文件；先排除远端已接收，再对自己的任务选择安全重试。")
    if failures.get("network", 0) or failures.get("server", 0):
        tips.append("网络或服务端异常：先核对网关健康与连接；上传结果不确定时保留本地副本，不盲目重复上传。")
    if entry_state != "本机检查通过":
        tips.append("在“HTTPS 与管理”核对入口、证书及续期提醒；不要停掉其他项目的代理，公网或局域网访问还需另一设备验证。")
    if not checks or "unknown" in checks.values() or "unchecked" in failures:
        tips.append("部分诊断未核实：确认实际 Bot 与离线工具版本及观察时间；未核实不是通过，不因诊断缺失自动重装。")
    listener = readiness.validate_listener(listener)
    if listener and listener["enabled"]:
        if listener["state"] == "cooldown":
            tips.append("个人监听处于冷却：等待记录的冷却结束，不反复登录、测试规则或重启绕过。")
        elif listener["state"] in {"connecting", "stale", "partial"}:
            tips.append("个人监听待核对：在监听管理检查账号连接、来源权限与最近轮询；有缺口时先只读预览历史，不删除 Session 或盲目批量重试。")
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
    checks, failures, configuration, listener = {}, {}, "unknown", None
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
        listener = readiness.validate_listener(value.get("listener"))
        lines.append(listener_line(listener))
        observed = validate_events(value.get("observations"))
        if observed is not None:
            lines += ["", "## 最近24小时本进程临时异常观察",
                      "每类最多保留64次；重启后重新计数，未包含 SDK 内部全部日志。当前状态与历史观察分别判断。"]
            for kind, item in sorted(observed.items()):
                lines.append(EVENT_LABELS[kind] + "：" + ("至少 " if item["bounded"] else "") + str(item["count"]) + " 次")
            if not observed:
                lines.append("当前快照无临时异常观察；不代表历史上从未发生。")
        else:
            lines.append("临时异常观察：未核实（旧快照、记录缺失或过期）")
        for key, label in readiness.LABELS.items():
            lines.append(label + "：" + readiness.STATES[value["checks"][key]])
        lines.extend(readiness.admission_lines(value.get("admission")))
        lines.extend(readiness.waiting_lines(value.get("waiting")))
        for key, label in (("disk_free_bytes", "已检查目录最小可用空间"), ("budget_bytes", "任务暂存额度")):
            amount = value.get(key)
            lines.append(label + "：" + (f"{amount / 1024**3:.2f} GB" if type(amount) is int and 0 <= amount <= 2**60 else "未检查"))
        lines += ["", "## 最近7天当前失败任务分类（非原始日志）"]
        lines.extend(FAILURES[key] + f"：{count}" for key, count in sorted(value["failures"].items()))
        if not value["failures"]:
            lines.append("当前无此范围内的失败任务；不代表从未发生错误。")
    except (ValueError, TypeError, KeyError):
        lines.append("Bot 诊断快照：未检查（未运行、旧版本或响应不受支持）")
    lines += ["", "## 容器日志轮转（实际配置）", *log_rotation_lines(inspect_container_logs(instance, session))]
    entry_label, entry_state = inspect_entry(instance, session)
    lines += ["", entry_label + "：" + entry_state,
              "入口检查不含公网／其他客户端验收，不执行签发、续期或配置修复。",
              "", "## 建议处理顺序"]
    lines.extend(f"{number}. {tip}" for number, tip in enumerate(
        recommendations(checks, failures, configuration, containers, entry_state, listener), 1))
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
