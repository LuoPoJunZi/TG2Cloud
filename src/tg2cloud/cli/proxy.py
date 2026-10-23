"""Explicit offline proxy selection, diagnostics, recovery and renewal entry."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from tg2cloud.deployment import preflight
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.docker_nginx import DockerNginx
from tg2cloud.deployment.proxy.external_config import validate_domain
from tg2cloud.deployment.proxy.external_entry import ExternalEntry
from tg2cloud.deployment.proxy.external_transaction import SiteTransaction, atomic
from tg2cloud.deployment.proxy.manager import (
    PROXY_ROOT,
    DomainProxyManager,
    proxy_lock_command,
)
from tg2cloud.deployment.proxy.state import has_routes


def select_entry(manager, ui, domain: str, options: dict | None = None):
    """Read-only plan; final installation confirmation is still mandatory."""
    from tg2cloud.cli.presentation import numbered_menu
    options = options or {}
    state = manager.read_state()
    if state.get("version") == 3:
        if options.get("proxy_mode") == "managed":
            raise ValueError("已有外部入口不会在升级时切回独立模式；需独立迁移操作。")
        if options.get("nginx_container") and options["nginx_container"] != state["entry"]["identity"]["name"]:
            raise ValueError("已有外部入口不会静默切换容器；请先导出并核对迁移方案。")
        return
    if has_routes(state):
        if options.get("proxy_mode") == "external_docker":
            raise ValueError("已有独立代理不会自动切换；先使用 proxy migration-plan 核对全部域名及维护窗口。")
        return
    environment = manager.probe(domain)
    if options.get("proxy_mode") == "managed":
        if not environment.ports_safe:
            raise ValueError("公网端口已占用，不能强行启用独立 Nginx。")
        return
    if environment.ports_safe and options.get("proxy_mode") != "external_docker":
        return
    candidates = DockerNginx(manager.session).candidates()
    manager.log("\n── HTTPS 入口检测 ──")
    for item in candidates:
        manager.log(item["name"] + "：" + item["kind"] + ("；" + item["reason"] if item["reason"] else ""))
    target = options.get("nginx_container", "")
    if options.get("proxy_mode") == "external_docker":
        if not target or not options.get("authorize_proxy"):
            raise ValueError("显式复用必须同时指定 --nginx-container 和 --authorize-proxy。")
    else:
        if ui is None:
            raise ValueError("非交互环境不能静默接管已有 Nginx；请显式指定入口模式、容器和授权。")
        valid = [item for item in candidates if item["kind"] == "external_docker"]
        if not valid:
            raise ValueError("没有可安全复用的 Docker Nginx；请用 tg2cloud proxy export 查看人工接入说明。")
        manager.log(numbered_menu(((1, "复用已有 Docker Nginx（推荐）"), (2, "使用独立 Nginx（端口占用时不可用）"),
                                   (3, "查看详细检测结果"), (0, "返回"))))
        while True:
            choice = ui.ask("请选择", default="1")
            if choice == "3":
                for item in candidates:
                    manager.log(json.dumps(item, ensure_ascii=False))
                continue
            if choice == "0":
                raise ValueError("用户取消代理接入，未修改外部配置。")
            if choice == "2":
                raise ValueError("80/443 已被占用；独立模式不可用，不会停止原服务。")
            if choice != "1":
                continue
            break
        manager.log(numbered_menu((number, item["name"]) for number, item in enumerate(valid, 1)))
        chosen = ui.ask("选择目标容器", default="1" if len(valid) == 1 else "")
        if not chosen.isdigit() or not 1 <= int(chosen) <= len(valid):
            raise ValueError("未选择有效容器；不随机选择。")
        target = valid[int(chosen) - 1]["name"]
    entry = DockerNginx(manager.session).plan(target)
    if manager.values.get("install_dir", manager.product.install_dir) != manager.product.install_dir:
        raise ValueError("外部复用目前仅自动管理标准实例目录；自定义目录请导出计划人工接入，不在基础安装后才猜测网络归属。")
    adapter = ExternalEntry(manager, entry)
    adapter.preflight(domain)
    entry["certificates"][domain] = adapter.certificate_record(domain)
    manager.log("入口模式：复用外部 Docker Nginx；不停止、不重建原容器，不增加第二层 Nginx。")
    manager.log("目标容器：" + target + "；网络：" + entry["network"]["mode"] + " " + entry["network"]["name"])
    manager.log("专属域名：" + domain + "；站点目录：" + entry["mount"]["conf_dir"])
    manager.log("将新增专属站点、私有证书／ACME／认证资源及单一宿主续期任务；只平滑重载原 Nginx。")
    manager.log("证书方式：" + ("复用外部证书，续期仍由原工具负责" if entry["certificates"][domain]["owner"] == "external" else "TG2Cloud Certbot Webroot 签发与续期"))
    if ui is not None and not ui.confirm("授权按上述范围修改外部 Nginx 专属站点并平滑重载？原网站配置不修改"):
        raise ValueError("未授权接入，未写入任何外部资源。")
    manager.external_plan = entry


def parser():
    result = argparse.ArgumentParser(description="TG2Cloud HTTPS 入口：只读检测、外部接入、维护与恢复")
    result.add_argument("action", choices=("detect", "check", "export", "configure", "maintain", "recover", "revalidate", "migration-plan", "migrate"))
    result.add_argument("--edition", choices=tuple(PRODUCTS))
    result.add_argument("--nginx-container")
    result.add_argument("--domain")
    result.add_argument("--email", default="")
    result.add_argument("--output", help="导出到不存在的新目录；不修改原 Nginx")
    result.add_argument("--authorize-proxy", action="store_true")
    result.add_argument("--yes", action="store_true", help="确认已审阅计划；不代替容器/资源归属校验")
    result.add_argument("--dry-run", action="store_true")
    return result


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.dry_run and args.action != "maintain":
        arguments.error("--dry-run 仅用于证书 maintain 演练，不能用于 configure 或 migrate；未执行任何操作")
    log = SafeLog()
    try:
        preflight.validate_host()
        session = LocalSession(log)
        from tg2cloud.deployment import architecture
        architecture.check_docker(session)
        if args.action == "detect":
            for item in DockerNginx(session).candidates():
                log(json.dumps(item, ensure_ascii=False))
            return 0
        if args.action != "maintain" and not args.edition:
            raise ValueError("请显式选择 --edition，不能替用户选择实例。")
        manager = DomainProxyManager(session, PRODUCTS[args.edition or "clouddrive2"], {"vps_host": "127.0.0.1"}, log)
        manager.prepare()
        state = manager.read_state()
        adapter = manager.external_entry(state)
        if args.action == "check":
            report = manager.status(state)
            log(report.message)
            for warning in report.warnings:
                log("提醒：" + warning)
            return 0 if report.state == "healthy" else 1
        if args.action in {"export", "migration-plan"}:
            return export_plan(args, manager, state, log)
        if not args.yes or not args.authorize_proxy:
            raise ValueError("写入操作需要 --yes 和 --authorize-proxy；检测／导出不需要授权。")
        if args.action == "configure":
            domain = validate_domain(args.domain or "")
            select_entry(manager, None, domain, {"proxy_mode": "external_docker", "nginx_container": args.nginx_container,
                                               "authorize_proxy": args.authorize_proxy})
            if not manager.external_entry():
                raise ValueError("已有独立模式不能通过 configure 隐式迁移。")
            log(manager.configure(domain, args.email).message)
        elif args.action == "maintain":
            if adapter is None:
                raise ValueError("当前没有外部 Docker 入口，未运行任何签发任务。")
            log(adapter.maintain(dry_run=args.dry_run))
        elif args.action == "recover":
            recover(manager, args.nginx_container, log)
        elif args.action == "revalidate":
            revalidate(manager, args.nginx_container, log)
        else:
            migrate(manager, args.nginx_container, args.email, log)
        return 0
    except KeyboardInterrupt:
        log("代理操作已中断；请先检查状态或恢复事务，不自动重复签发。")
        return 130
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        log(str(exc))
        return 1


def export_plan(args, manager, state, log):
    """Unsupported environments receive instructions, never a success marker."""
    result = {"schema": 1, "owner": "tg2cloud.proxy.export", "installed": False,
              "edition": args.edition, "domain": validate_domain(args.domain) if args.domain else "",
              "current_mode": state.get("entry", {}).get("mode", "managed"),
              "routes": state["domains"], "external_webdav": state.get("external_webdav", {}),
              "instructions": ["确认现有 Docker Nginx 的真实 Compose、挂载和 http include 目录。",
                               "为专属域名配置单层反向代理，后端不开放公网；管理域名继续阻断 /dav 与 /dav/。",
                               "Certbot 使用持久化 Webroot；保留原续期工具归属，不能抢占公网端口。",
                               "bridge 模式需原 Compose 已声明自定义网络，再持久化连接 TG2Cloud 网关。",
                               "迁移须覆盖所有管理及附加域名；先备份，维护窗口内由用户完成公网端口切换。",
                               "外部入口接通失败时不停止它；保留原代理和证书材料，人工安排回切。"]}
    if args.nginx_container:
        try:
            entry = DockerNginx(manager.session).plan(args.nginx_container)
            result["candidate"] = entry
            if result["domain"]:
                adapter = ExternalEntry(manager, entry)
                adapter.preflight(result["domain"])
                entry["certificates"][result["domain"]] = adapter.certificate_record(result["domain"])
                from tg2cloud.deployment.proxy.external_config import render_route
                from tg2cloud.deployment.proxy.state import DomainRoute
                result["site_candidate"] = render_route(DomainRoute(args.edition, result["domain"], manager.product.management_port), entry)
        except ValueError as exc:
            result["blocked_reason"] = str(exc)
    content = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output:
        target = Path(args.output).absolute()
        if target.exists() or target.resolve() != target:
            raise ValueError("导出目录必须是不存在且不经过链接的新目录。")
        target.mkdir(mode=0o700)
        atomic(target / "proxy-plan.json", content)
        if result.get("site_candidate") and "blocked_reason" not in result:
            atomic(target / ("tg2cloud-" + args.edition + ".conf"), result["site_candidate"].encode())
        log("已导出接入／迁移计划；这不是安装成功：" + str(target))
    else:
        log(content.decode())
    return 0


def recover(manager, name, log):
    from tg2cloud.deployment.proxy.external_config import checksum
    from tg2cloud.deployment.proxy.external_transaction import read
    root = Path(PROXY_ROOT)
    context = json.loads(read(root / "state/external-context.json"))
    adapter = ExternalEntry(manager, context)
    if not name or name != context["identity"]["name"]:
        raise ValueError("恢复必须显式指定与事务相同的 --nginx-container。")
    with manager.session.hold_lock(proxy_lock_command()):
        transaction = SiteTransaction.recover(adapter.directory, adapter.journal)
        state = manager.read_state()
        expected = {key: checksum(base64.b64decode(value["after"], validate=True)) for key, value in transaction.items.items()
                    if value["after"] is not None}
        adapter.active_files = set(transaction.items)
        item = adapter.context()
        if (state.get("version") == 3 and state["entry"]["files"] == expected
                and state["entry"]["revision"] == context["revision"]):
            # Covers power loss between atomic state commit and journal finish.
            for filename, digest in expected.items():
                if checksum(read(adapter.directory / filename) or b"") != digest:
                    raise ValueError("已提交站点发生漂移，不清除恢复日志。")
            adapter.entry = state["entry"]
            adapter.verify(state)
        else:
            transaction.rollback()
            adapter.docker.reload(item)
        transaction.finish()
        log("受管文件事务已恢复；没有恢复整目录或覆盖其他站点。")


def revalidate(manager, name, log):
    """Explicitly accept unrelated site changes, never unknown owned changes."""
    import copy

    from tg2cloud.deployment.proxy.external_config import checksum
    from tg2cloud.deployment.proxy.external_transaction import read
    with manager.session.hold_lock(proxy_lock_command()):
        state = manager.read_state()
        if state.get("version") != 3 or name != state["entry"]["identity"]["name"]:
            raise ValueError("仅能复核已登记且显式指定的外部容器。")
        saved = state["entry"]
        owned = {saved["mount"]["conf_dir"] + "/" + key for key in saved["files"]}
        fresh = DockerNginx(manager.session).plan(name, owned=owned)
        if saved["mount"] != fresh["mount"] or saved["network"] != fresh["network"]:
            raise ValueError("挂载或网络变化需独立迁移，不通过复核接管。")
        for key in ("image", "image_id", "project", "service", "working_dir", "config_files"):
            if saved["identity"][key] != fresh["identity"][key]:
                raise ValueError("逻辑身份变化，不通过复核接管。")
        if not saved["identity"]["project"] and saved["identity"]["container_id"] != fresh["identity"]["container_id"]:
            raise ValueError("非 Compose 容器重建需人工迁移，不能仅凭名字接受。")
        candidate = copy.deepcopy(saved)
        candidate["identity"] = fresh["identity"]
        for key, digest in saved["files"].items():
            if checksum(read(Path(saved["mount"]["host_dir"]) / key) or b"") != digest:
                raise ValueError("TG2Cloud 专属站点被修改，停止，不接受未知代码。")
        adapter = ExternalEntry(manager, candidate)
        for domain in [route["domain"] for route in state["domains"].values()] + [route["domain"] for route in state.get("external_webdav", {}).values()]:
            adapter.preflight(domain)
        adapter.verify(state)
        state["entry"] = candidate
        manager._commit_state(state)
        log("已显式复核原逻辑身份、网络、专属站点及真实服务；更新其他站点的基线，不改动其内容。")


def migrate(manager, name, email, log):
    """Explicit cutover after operator frees the old managed listener.

    Port switching is intentionally not hidden in a normal install/upgrade.
    The original managed proxy is retained for an operator-controlled rollback.
    """
    from tg2cloud.deployment.proxy.external_transaction import read
    state = manager.read_state()
    if state.get("version") == 3 or not has_routes(state) or not name:
        raise ValueError("迁移仅适用于已有独立代理，且必须显式选择目标容器。")
    old = DockerNginx(manager.session).inspect("tg2cloud-proxy-nginx")
    if old["running"]:
        raise ValueError("请先导出 migration-plan，在维护窗口由用户切换公网入口；当前不会自动停止任何 Nginx。")
    old_certbot = DockerNginx(manager.session).inspect("tg2cloud-proxy-certbot")
    if old_certbot["running"]:
        raise ValueError("原受管 Certbot 仍在运行；请在迁移窗口先由用户停止旧续期任务并确认新责任，避免双重续期。")
    entry = DockerNginx(manager.session).plan(name)
    adapter = ExternalEntry(manager, entry)
    domains = [route["domain"] for route in state["domains"].values()] + [route["domain"] for route in state.get("external_webdav", {}).values()]
    for domain in domains:
        adapter.preflight(domain)
    # A bridge cutover must already have a durable, operator-reviewed backend
    # connection; migration never silently recreates a live storage gateway.
    for edition in set(state["domains"]) | set(state.get("external_webdav", {})):
        adapter.check_backend(edition)
    with manager.session.hold_lock(proxy_lock_command()):
        if manager.read_state() != state:
            raise ValueError("迁移确认期间共享状态已改变。")
        manager.external_plan = entry
        # Reuse every certificate only if it is already accessible and valid in
        # the new persistent mount. Otherwise explicit preparation is required;
        # do not issue all domains again and consume production rate limits.
        for domain in domains:
            cert = adapter.certificate_record(domain)
            if cert["owner"] != "external":
                raise ValueError("迁移前请按导出计划将有效证书安全配置到目标持久化挂载，确认原续期责任。")
            entry["certificates"][domain] = cert
        # Keep a private metadata snapshot for manual port-switch rollback.
        backup = adapter.root / "state" / ("managed-before-migration-" + entry["identity"]["container_id"][:12] + ".json")
        if backup.exists() and read(backup) != (json.dumps(state, sort_keys=True) + "\n").encode():
            raise ValueError("已有同名迁移恢复材料，停止覆盖。")
        atomic(backup, (json.dumps(state, sort_keys=True) + "\n").encode())
        adapter.transaction(state)
        log("入口模式已显式迁移；旧代理与证书材料保留，不自动删除，公网切换不承诺零中断。证书续期／加载仍须由你确认的原工具负责，未自动验收其调度。")
