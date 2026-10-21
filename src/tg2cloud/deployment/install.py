from __future__ import annotations

import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tg2cloud.cli import terminal
from tg2cloud.deployment import (
    architecture,
    configuration,
    instances,
    payload,
    preflight,
    releases,
    upgrade,
)
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.proxy.manager import (
    DomainProxyManager,
    validate_domain,
    validate_email,
)
from tg2cloud.deployment.proxy.state import (
    dns_diagnostic,
    nat_public_ipv4_candidate,
    public_endpoint_error,
)


@dataclass
class Plan:
    instance: instances.Instance
    action: str
    manager: DomainProxyManager
    config: dict[str, str] = field(default_factory=dict, repr=False)
    domain: str = ""
    email: str = ""
    configure_https: bool = False


def make_plan(
    instance: instances.Instance, release: releases.Release, source: Path, old_source: Path | None,
    session: LocalSession, log: SafeLog, ui: terminal.Terminal | None, *, configure_https: bool = False,
) -> Plan:
    action = upgrade.action_for(instance, release)
    if action in {"install", "upgrade"}:
        architecture.require_payload(source)
        payload.payload_sources(source, instance.product)
    if instance.present:
        if old_source is None:
            raise ValueError("缺少当前版本的官方源码基线，无法安全升级")
        upgrade.assert_unmodified(instance, old_source)
        if action == "upgrade" and payload.gateway_image(source, instance.product) != instance.gateway_image:
            raise ValueError("此升级涉及云网关镜像变化；停止自动升级。请先备份，按发布说明在隔离环境验证迁移；不要用旧 EXE 覆盖新实例")
    elif any(name in instances.docker_inventory(session) for name in instance.product.legacy_containers):
        raise ValueError("发现旧 TG115 容器，停止首次安装")
    if action in {"upgrade", "install"}:
        # The stable repair helper can adopt foreign CD2 containers; refuse them.
        instances.check_foreign_gateway(instance.product, session)
    manager = DomainProxyManager(
        session, instance.product, {"vps_host": "127.0.0.1"}, log,
        confirm_public_ipv4=(lambda domain, environment: terminal.confirm_nat_public_ipv4(ui, domain, environment, log))
        if ui is not None else None,
    )
    manager.prepare()
    state = manager.read_state()
    report = manager.status(state)
    log(instance.product.display_name + " HTTPS：" + report.message)
    plan = Plan(instance, action, manager, dict(instance.config), report.domain)
    needs_https = action == "install" or configure_https
    if action == "upgrade" and report.state != "healthy" and not configure_https:
        raise ValueError("已有 HTTPS 未通过；先用 --configure-https 显式修复，不在升级中隐式变更域名")
    if configure_https and action == "newer":
        raise ValueError("当前实例新于 latest；请使用匹配版本的源码维护 HTTPS，不使用旧 EXE 降级")
    if needs_https and report.state != "healthy":
        plan.configure_https = True
        if ui is not None:
            # Reuse an existing route, never offer an implicit domain switch.
            plan.domain = report.domain or ui.ask("管理页域名（A/AAAA 直指本机；Cloudflare 仅 DNS）", validate=validate_domain)
            old_route = state["domains"].get(instance.product.key, {})
            plan.email = old_route.get("email", "") or ui.ask("Let's Encrypt 邮箱（可留空）", validate=validate_email)
            if any(item["domain"] == plan.domain for key, item in state["domains"].items() if key != instance.product.key):
                raise ValueError("该域名已由另一个 Edition 使用")
            if instance.present:
                detection = manager.detect(plan.domain)
                if detection.state != "detected":
                    raise ValueError(detection.message)
            else:
                environment = manager.probe(plan.domain)
                if nat_public_ipv4_candidate(environment):
                    environment = manager.confirm_nat(plan.domain, environment)
                error = public_endpoint_error(environment, "127.0.0.1")
                if error:
                    raise ValueError("首次安装 HTTPS 前置检查未通过：" + error + "\n"
                                     + dns_diagnostic(environment, "127.0.0.1"))
    if action == "install" and ui is not None:
        log("\n── 磁盘与资源 ──")
        storage = preflight.choose_storage(instance, session, log, ui)
        log("\n── Telegram 与 WebDAV ──")
        plan.config = terminal.collect_config(ui, instance.product, storage=storage)
        log.register(plan.config)
    if action in {"install", "upgrade"} and (ui is not None or instance.present):
        preflight.resource_check(instance, plan.config, session, log)
    if action == "upgrade":
        code, _ = session.run("docker compose version >/dev/null 2>&1", timeout=15)
        if code:
            raise ValueError("升级要求现有 Docker Compose 可用；不在升级中自动安装依赖")
    return plan


def apply_base(plan: Plan, release: releases.Release, source: Path, session: LocalSession, log: SafeLog) -> None:
    instance = plan.instance
    if plan.action not in {"install", "upgrade"}:
        return
    architecture.check_docker(session, allow_missing=True)
    with tempfile.TemporaryDirectory(prefix="tg2cloud-cli-payload-") as private:
        root = Path(private)
        payload_dir = root / "payload"
        payload.build_payload(source, instance.product, payload_dir)
        candidate = root / "config.env"
        content = ("TG2CLOUD_REDEPLOY_APPLY_CONFIG=false\n" if instance.present else
                   "".join(key + "=" + value + "\n" for key, value in plan.config.items()))
        with candidate.open("x", encoding="utf-8") as writer:
            candidate.chmod(0o600)
            writer.write(content)
        command = ("INSTALL_DIR=" + shlex.quote(str(instance.directory)) + " bash "
                   + shlex.quote(str(payload_dir / "remote_install.sh")) + " "
                   + shlex.quote(str(payload_dir)) + " " + shlex.quote(str(candidate)))
        code, output = session.run(command, stream=log, timeout=2400)
        if code or "TG2CLOUD_RESULT=SUCCESS" not in output.splitlines() or "TG2CLOUD_BOT_HEALTH=healthy" not in output.splitlines():
            raise RuntimeError("基础安装/升级失败；请核对现有安装器的回退结果和备份，不假定已恢复")
    architecture.check_container(session, instance.product.bot_container, require_running=True)
    architecture.check_container(session, instance.product.storage_container, require_running=True)
    if instance.present and configuration.regular_private(instance.directory / ".env") != instance.raw_config:
        raise RuntimeError("升级后 .env 字节发生变化，停止后续操作；请核对备份")
    upgrade.record_release(instance.directory, release)


def verify_destination(plan: Plan, session: LocalSession, log: SafeLog, ui: terminal.Terminal) -> bool:
    if not ui.confirm("运行 WebDAV 写入验收？会创建并清理随机测试文件；请先完成云挂载/专用 WebDAV 用户配置"):
        log("TG2CLOUD_CLI_WEBDAV=NOT_RUN；未把基础健康状态当作转存验收通过")
        return False
    directory = shlex.quote(str(plan.instance.directory))
    code, output = session.run("cd " + directory + " && INSTALL_DIR=" + directory + " bash ./manage.sh verify", stream=log, timeout=600)
    if code or "TG2CLOUD_DESTINATION=OK" not in output.splitlines():
        raise RuntimeError("WebDAV 验收未通过；不自动重复验收或修改凭据，请查看脱敏日志")
    log("TG2CLOUD_CLI_WEBDAV=OK；仍请在云存储官方客户端确认最终文件")
    return True


def execute_plan(
    plan: Plan, release: releases.Release, source: Path, old_source: Path | None,
    session: LocalSession, log: SafeLog, ui: terminal.Terminal, *, verify: bool = False,
) -> None:
    instance = plan.instance
    with edition_lock(Path("/opt/tg2cloud-cli-locks") / (instance.product.key + ".lock")):
        if instance.present:
            current = instances.discover(instance.product, instances.docker_inventory(session), session, log, install_dir=str(instance.directory))
            if (current.raw_config != instance.raw_config or current.version != instance.version
                    or current.gateway_image != instance.gateway_image):
                raise ValueError("预览之后实例配置/版本已变更；停止，重新预检")
            upgrade.assert_unmodified(current, old_source)
        else:
            current = instances.discover(instance.product, instances.docker_inventory(session), session, log, install_dir=str(instance.directory))
            if current.present:
                raise ValueError("预览之后出现实例；停止，不覆盖")
        if plan.action in {"install", "upgrade"}:
            instances.check_foreign_gateway(instance.product, session)
            preflight.resource_check(instance, plan.config, session, log)
        apply_base(plan, release, source, session, log)
        if plan.configure_https:
            plan.manager.configure(plan.domain, plan.email)
        report = plan.manager.status()
        log(report.message)
        if report.state != "healthy":
            raise RuntimeError("基础服务可能已安装，但 HTTPS 尚未通过；用 --configure-https 显式续做，不要重装/删除数据")
        log("TG2CLOUD_CLI_BASE_HTTPS=OK；公网访问仍需外部网络检查")
        if plan.action == "install" or plan.configure_https:
            log("请在 https://" + report.domain + " 配置自己的云存储，再建立专用 WebDAV 用户。")
            if plan.action == "install":
                terminal.show_setup_credentials(ui, instance.product, plan.config, log)
            else:
                terminal.show_credentials(ui, instance.product, plan.config, log)
        if verify or plan.action == "install":
            verify_destination(plan, session, log, ui)
