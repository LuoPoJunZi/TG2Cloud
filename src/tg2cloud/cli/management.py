"""Offline, single-Edition maintenance UI built on the existing safety boundaries."""
from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime, timezone
from pathlib import Path

from tg2cloud.cli import terminal
from tg2cloud.cli.presentation import (
    InstallerLog,
    edition_menu,
    numbered_menu,
    page_heading,
    terminal_report,
)
from tg2cloud.deployment import architecture, instances, preflight, runtime, uninstall
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import lan
from tg2cloud.deployment.proxy.certificates import parse_certificate_enddate
from tg2cloud.deployment.proxy.manager import (
    DomainProxyManager,
    validate_domain,
    validate_email,
)

MENU_ITEMS = (
    (1, "安装与升级"), (2, "查看运行状态"), (3, "查看运行日志"),
    (4, "服务启停管理"), (5, "Bot 用户管理"), (6, "WebDAV 凭据"),
    (7, "HTTPS 与管理"), (8, "文件分类设置"), (9, "异常通知设置"),
    (10, "业务就绪检查"), (11, "WebDAV 验收"), (12, "故障诊断报告"),
    (13, "数据备份管理"), (14, "卸载当前实例"), (15, "外部 WebDAV"), (16, "监听管理"), (0, "退出"),
)
MENU = numbered_menu(MENU_ITEMS) + "\n"
MENU_ACTIONS = tuple(str(number) for number, _ in MENU_ITEMS)


def choose(ui, prompt: str, values: tuple[str, ...], default: str = "") -> str:
    def validate(value):
        if value not in values:
            raise ValueError("请选择菜单中的序号")
        return value
    return ui.ask(prompt, default=default, validate=validate)


class Management:
    def __init__(self, product, session, log, ui, install_dir=None, *, mode_hint=None):
        self.product, self.session, self.log, self.ui = product, session, log, ui
        self.install_dir = install_dir
        self.mode_hint = mode_hint

    def discover(self):
        architecture.check_environment()
        code, _ = self.session.run("command -v docker >/dev/null 2>&1", timeout=10)
        if code == 0:
            uninstall.validate_environment(self.session)
        inventory = instances.docker_inventory(self.session)
        return instances.discover(self.product, inventory, self.session, self.log, install_dir=self.install_dir)

    def recheck(self, previous):
        current = self.discover()
        if (current.present != previous.present or current.raw_config != previous.raw_config
                or current.directory != previous.directory or current.version != previous.version
                or current.gateway_image != previous.gateway_image):
            raise ValueError("确认之后实例发生变化，请重新选择操作")
        return current

    def mode(self, instance):
        saved = lan.load_state(self.product)
        if saved:
            if instance.directory != Path(saved["install_dir"]):
                raise ValueError("内网模式记录与实例目录不一致")
            lan.reject_https_route(self.product)
        return saved

    def proxy(self):
        manager = DomainProxyManager(
            self.session, self.product, {"vps_host": "127.0.0.1"}, self.log,
            confirm_public_ipv4=lambda domain, environment: terminal.confirm_nat_public_ipv4(self.ui, domain, environment, self.log),
        )
        manager.prepare()
        return manager

    def checked_run(self, command: str, *, timeout=60):
        code, output = self.session.run(command, stream=self.log, timeout=timeout)
        if code:
            raise RuntimeError("操作未成功，请检查上方脱敏结果；不会自动重复执行")
        return output

    def heading(self, title, instance):
        self.log(page_heading(title, self.product, instance.version))

    def return_to_main(self):
        self.log("\n" + numbered_menu(((0, "返回主菜单"),)))
        choose(self.ui, "选择操作", ("0",), "0")

    def read_page(self, instance, operation, refresh):
        """Refresh stays on the same page and re-discovers the selected instance."""
        while True:
            try:
                operation(instance)
            except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
                self.log("检查未完成：" + str(exc) + "；不标记为通过。")
            self.log("\n" + numbered_menu(((1, refresh), (0, "返回主菜单"))))
            if choose(self.ui, "选择操作", ("0", "1"), "0") == "0":
                return
            instance = self.discover()
            if not instance.present:
                self.log("当前实例已不可用，返回主菜单；不会自动安装或重建。")
                return

    def container_states(self):
        states = {"running": "运行中", "exited": "已停止", "restarting": "重启中", "created": "尚未启动",
                  "paused": "已暂停", "dead": "异常退出", "removing": "正在移除"}
        health = {"healthy": "通过（容器检查）", "unhealthy": "未通过", "starting": "检查中", "none": "未配置容器检查"}
        result = {}
        for key, name in (("bot", self.product.bot_container), ("gateway", self.product.storage_container)):
            try:
                code, output = self.session.run("docker inspect --format " + shlex.quote(
                    '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')
                    + " " + shlex.quote(name), timeout=15)
                fields = output.strip().split()
                valid = not code and len(fields) == 2 and fields[0] in states and fields[1] in health
                result[key] = (states[fields[0]], health[fields[1]] if fields[0] == "running"
                               else "未检查（容器未运行）") if valid else ("未核实", "未核实")
            except (OSError, RuntimeError, TimeoutError):
                result[key] = ("未核实", "未核实")
        return result

    def show_containers(self):
        states = self.container_states()
        self.log("Bot 状态：" + states["bot"][0] + "\nBot 健康：" + states["bot"][1]
                 + "\n网关状态：" + states["gateway"][0])

    def show_proxy_report(self, report):
        values = {"healthy": "本机通过", "not_configured": "未配置", "running_error": "未通过", "certificate_error": "证书检查未通过"}
        self.log("访问模式：HTTPS\n管理地址：" + ("https://" + report.domain if isinstance(report.domain, str) and report.domain else "未配置")
                 + "\n入口检查：" + values.get(report.state, "未核实"))
        markers = dict(report.markers) if isinstance(report.markers, (tuple, list)) else {}
        if markers.get("PROXY_CERT_END"):
            try:
                expiry, days = parse_certificate_enddate(markers["PROXY_CERT_END"])
                self.log("证书到期：" + expiry + (f"（剩余 {days} 天）" if days >= 0 else "（已到期）"))
            except (ValueError, TypeError):
                self.log("证书到期：未核实")
        attempt = markers.get("PROXY_RENEW_ATTEMPT", "")
        try:
            checked = datetime.fromtimestamp(int(attempt), timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if str(attempt).isdigit() else "尚无记录"
        except (ValueError, OverflowError, OSError):
            checked = "记录无法识别"
        renewal = {"OK": "通过", "FAILED": "未通过"}.get(markers.get("PROXY_RENEW_RESULT"), "未核实")
        self.log("续期检查：" + checked + "（" + renewal + "）")
        if isinstance(report.statuses, (tuple, list)):
            failed = [title for title, value in report.statuses if value != "通过"]
            if failed:
                self.log("\n未通过项目：\n" + "\n".join(failed))
        if isinstance(report.warnings, (tuple, list)):
            for warning in report.warnings:
                self.log("提醒：" + warning)
        self.log("本机检查不代表外网可达；续期检查不代表实际续签。")

    def status(self, instance, *, title="查看运行状态"):
        self.heading(title, instance)
        self.log("正在检查容器与管理入口，请稍候……")
        self.show_containers()
        saved = self.mode(instance)
        if saved:
            inventory = instances.docker_inventory(self.session)
            entry = lan.inspect_lan(self.product, self.session, inventory)
            if not entry or not entry.get("running"):
                raise RuntimeError("内网管理入口未运行")
            lan.check_entry(self.product, saved["bind_ip"])
            self.log(f"访问模式：内网 HTTP\n管理地址：http://{saved['bind_ip']}:{self.product.management_port}\n入口检查：本机通过")
            self.log("证书：不适用；局域网访问仍需另一设备验证。")
        else:
            self.show_proxy_report(self.proxy().status())

    def logs(self, instance):
        self.heading("查看运行日志", instance)
        self.log("最近 30 分钟，每个服务最多 100 行；以下为脱敏日志快照，不持续刷新。")
        for label, name in (("Bot", self.product.bot_container), (self.product.display_name, self.product.storage_container)):
            self.log("\n── " + label + " 日志 ──\n")
            try:
                code, output = self.session.run("docker logs --since 30m --tail 100 " + shlex.quote(name), timeout=30)
                if code:
                    self.log(label + " 日志读取失败；其他服务日志继续显示。")
                else:
                    self.log(output.rstrip() if output.strip() else "最近 30 分钟暂无日志。")
            except (OSError, RuntimeError, TimeoutError):
                self.log(label + " 日志读取失败；其他服务日志继续显示。")

    def readiness(self, instance):
        from tg2cloud.deployment.readiness import check
        self.heading("业务就绪检查", instance)
        self.log("正在读取最近观察，不追加 Telegram／WebDAV 请求……")
        check(instance, self.session, self.log)

    def control(self, instance):
        self.heading("服务启停管理", instance)
        self.show_containers()
        self.log("\n存储网关停止或重启会中断存储访问。\n" + numbered_menu((
            (1, "启动 Bot"), (2, "停止 Bot"), (3, "重启 Bot"),
            (4, "启动存储网关"), (5, "停止存储网关"), (6, "重启存储网关"), (0, "返回主菜单"),
        )))
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3", "4", "5", "6"), "0")
        if action == "0":
            return False
        number = int(action) - 1
        name = self.product.bot_container if number < 3 else self.product.storage_container
        verb, label = (("start", "启动"), ("stop", "停止"), ("restart", "重启"))[number % 3]
        if not self.ui.confirm(f"确认{label} {name}？进行中的任务或外部访问可能中断"):
            return False
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            self.checked_run("docker " + verb + " " + shlex.quote(name), timeout=90)
        self.log("容器操作已完成；健康状态请另选“查看运行状态”。")
        return True

    def verify(self, instance):
        self.heading("WebDAV 验收", instance)
        self.log("验收将创建并清理随机测试文件；不删除已有文件，大小复验不等于云盘官方最终入库。")
        if not instance.running:
            raise ValueError("Bot 未运行，请先启动后验收")
        if not self.ui.confirm("运行 WebDAV 写入验收？仅创建并清理随机测试文件，请先配置云挂载与专用账号"):
            return False
        self.log("\n── 验收进度 ──\n")
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            output = self.checked_run("docker exec " + shlex.quote(self.product.bot_container) + " python -m app.verify_destination", timeout=600)
            if "TG2CLOUD_DESTINATION=OK" not in output.splitlines():
                raise RuntimeError("验收缺少完整成功标记；不自动重试或修改凭据")
        self.log("\n── 验收结果 ──\nWebDAV 写入与远端大小复验通过；云盘官方端最终完成仍需自行确认。")
        return True

    def upgrade(self, instance):
        self.heading("安装与升级", instance)
        saved = self.mode(instance)
        if not instance.present:
            if self.mode_hint:
                use_lan = self.mode_hint == "lan"
            else:
                self.log(numbered_menu(((1, "公网 VPS（HTTPS 域名）"), (2, "可信内网（HTTP 地址）"), (0, "返回"))))
                selected = choose(self.ui, "安装模式", ("0", "1", "2"))
                if selected == "0":
                    return
                use_lan = selected == "2"
        else:
            use_lan = bool(saved)
        arguments = ["--edition", self.product.key]
        if use_lan:
            if instance.directory != Path(self.product.install_dir):
                raise ValueError("内网安装仅支持标准实例目录，不隐式搬迁")
            result = lan.main(arguments, friendly=True)
        else:
            from tg2cloud.cli import vps
            result = vps.main([*arguments, "--install-dir", str(instance.directory)], friendly=True)
        if result:
            raise RuntimeError("安装/升级未完成，请核对结果后重试")

    def entry(self, instance):
        if self.mode(instance):
            self.status(instance, title="HTTPS 与管理")
            self.log("当前是内网 HTTP 模式，不申请证书或隐式切换为公网模式。")
            return True
        self.heading("HTTPS 与管理", instance)
        self.log("只管理入口，不升级或重启 Bot／网关。\n\n" + numbered_menu((
            (1, "检查 HTTPS"), (2, "修复 HTTPS"), (3, "证书续期演练"), (0, "返回主菜单"))))
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3"), "1")
        if action == "0":
            return False
        if action == "1":
            self.log("正在检查 HTTPS，请稍候……")
            self.show_proxy_report(self.proxy().status())
        elif action == "2":
            manager = self.proxy()
            state = manager.read_state()
            route = state["domains"].get(self.product.key, {})
            domain = route.get("domain") or self.ui.ask("管理页域名（A/AAAA 直指本机；Cloudflare 仅 DNS）", validate=validate_domain)
            email = route.get("email", "") or self.ui.ask("Let's Encrypt 邮箱（可留空）", validate=validate_email)
            from .proxy import select_entry
            select_entry(manager, self.ui, domain)
            detection = manager.detect(domain)
            if detection.state != "detected":
                raise ValueError(detection.message)
            self.log(detection.message)
            if not self.ui.confirm("仅配置/修复 " + domain + " 的 HTTPS？可能短暂中断共享管理入口，不升级或重启 Bot/网关"):
                return False
            with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                self.recheck(instance)
                if manager.read_state() != state:
                    raise ValueError("预览后代理状态发生变化，请重新检测")
                report = manager.configure(domain, email)
                self.log(report.message)
                if report.state != "healthy":
                    raise RuntimeError("HTTPS 修复尚未通过，请核对状态")
        elif action == "3":
            self.log("续期演练使用 ACME 测试流程，不代表正式证书已经续签。")
            if not self.ui.confirm("确认执行续期 dry-run？需要外网和 ACME，不替换正式证书"):
                return False
            with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                self.recheck(instance)
                self.log(self.proxy().maintenance("renew_dry_run"))
        return True

    def backups(self, instance):
        self.heading("数据备份管理", instance)
        self.log("实例备份\n" + numbered_menu(((1, "查看历史备份"), (2, "创建实例快照"), (3, "校验实例快照")))
                 + "\n\n共享代理\n" + numbered_menu(((4, "创建代理备份"), (5, "查看代理备份"),
                    (6, "校验代理备份"), (7, "清理代理备份"), (0, "返回主菜单")))
                 + "\n不提供覆盖运行数据的一键恢复；实例快照不包含下载文件和共享 HTTPS。")
        selected = choose(self.ui, "选择操作", ("0", "1", "2", "3", "4", "5", "6", "7"), "0")
        if selected == "0":
            return False
        # Only presentation numbering changes; retain the established execution
        # branches, locks, identity checks and destructive-operation confirmations.
        action = {"1": "1", "2": "6", "3": "7", "4": "2", "5": "3", "6": "4", "7": "5"}[selected]
        if action == "1":
            root = Path(self.product.backup_dir)
            pattern = uninstall.backup_targets((self.product.key,), {}, False)[root]
            identity = uninstall.backup_identity(root, pattern)
            for item in identity[-1] if identity else ():
                self.log(item[0] + f"（{item[3]} 字节，尚未校验内容）")
            if not identity or not identity[-1]:
                self.log("没有受管实例历史备份。")
            return True
        if action in {"6", "7"}:
            from tg2cloud.deployment import backup
            from tg2cloud.persistence import bundle
            parent = Path(self.ui.ask("私密备份目录", default="/opt/tg2cloud-snapshots/" + self.product.key))
            backup.output_directory(parent, instance)
            if action == "6":
                self.log("备份配置、业务数据库、Session 和网关配置；不备份云端、downloads、日志、共享代理或附加功能状态。请另存这些资料；导出目录在默认卸载清理范围之外。")
                if not self.ui.confirm("确认短暂停止所选 Bot 与网关创建快照？会暂时中断该网关的管理和外部 WebDAV 读取；不停止其他 Edition"):
                    return False
                with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                    current = self.recheck(instance)
                    archive = backup.create(current, self.session, parent)
                self.log("实例快照已核验：" + str(archive) + "；原服务已恢复运行状态，仍需检查业务就绪。含敏感信息，请私密离机保存。")
            else:
                archive = Path(self.ui.ask("实例快照归档绝对路径"))
                runtime.safe_path(archive, private=True)
                runtime.safe_path(parent, private=True)
                if not self.ui.confirm("确认在上述私密目录隔离解包并检查？不覆盖运行数据，不启动第二个 Bot"):
                    return False
                result = bundle.preflight(archive, parent, self.product.key, instance.version)
                self.log(f"实例快照结构／数据库预检通过：{result['files']} 文件；不代表运行恢复或全部网关授权已验收。")
            return True
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            manager = self.proxy()
            if manager.external_entry() and action in {"3", "5"}:
                self.log("外部模式备份位于 /opt/tg2cloud-proxy/external-backups，仅含元数据与专属站点；不运行独立代理的整目录清理。可选创建或隔离核验，旧备份需人工保管。")
                return True
            if action == "3":
                for item in manager.manage_backups("list")["items"]:
                    self.log(f"{item['name']}（{item['size_bytes']} 字节，完整性 {item['integrity']}）")
            elif action in {"2", "4"}:
                if self.ui.confirm("确认在 VPS 私密目录备份/校验？含证书私钥，不要公开上传；不会覆盖运行数据"):
                    self.log(manager.maintenance("backup" if action == "2" else "drill"))
            else:
                plan = manager.manage_backups("prune-preview", keep=5)["plan"]
                for item in plan["remove"]:
                    self.log("将删除：" + item["name"])
                if plan["remove"] and self.ui.confirm("确认仅删除上述代理备份？保留最近 5 份有效备份；删除不可撤销"):
                    manager.manage_backups("prune", keep=5, plan=plan["plan_id"])
                    self.log("已按复核后的计划清理旧代理备份。")
                elif not plan["remove"]:
                    self.log("没有需要清理的代理备份。")
        return True

    def remove(self, instance):
        self.heading("卸载当前实例", instance)
        if instance.directory != Path(self.product.install_dir):
            raise ValueError("现有卸载器只支持标准目录；自定义目录不自动卸载，避免清理错误实例")
        self.log("── 卸载计划 ──\n仅卸载 " + self.product.display_name
                 + "\n将清理：当前实例的容器、配置、数据库、下载及受管备份（以最终预检计划为准）。"
                 + "\n保留：另一 Edition 的容器和数据、云端文件及系统 Docker／Nginx 等软件。")
        self.log("另一 Edition 或入口仍在使用时保留 tg2cloud；最后一套完整清理后，核验归属并移除快捷命令及其代码。")
        if not self.ui.confirm("继续查看 " + self.product.display_name + " 的完整卸载计划？"):
            return False
        if uninstall.main(["--edition", self.product.key]):
            raise RuntimeError("卸载未完成，请核对结果")
        inventory = instances.docker_inventory(self.session)
        return not ({self.product.bot_container, self.product.storage_container} & inventory) and not instance.directory.exists()

    def run(self):
        while True:
            instance = self.discover()
            from tg2cloud.version import VERSION
            self.log(f"\n── TG2Cloud 本地管理 ──\n\n{self.product.display_name} · 版本 {instance.version or '未安装'} · Bot {'运行中' if instance.running else '未运行'}\n安装目录：{instance.directory}\n管理工具（当前进程）：v{VERSION}\n\n")
            if not instance.present:
                if self.ui.confirm(self.product.display_name + " 尚未安装，是否进入安装向导？"):
                    self.upgrade(instance)
                return 0
            self.log(MENU + "\n")
            action = choose(self.ui, "选择操作", MENU_ACTIONS, "0")
            if action == "0":
                return 0
            try:
                if action == "1":
                    self.upgrade(instance)
                    self.return_to_main()
                    continue
                if not instance.present:
                    raise ValueError("尚无完整实例，请先安装；不会执行维护操作")
                handlers = {"4": self.control,
                            "7": self.entry, "11": self.verify, "13": self.backups}
                completed = False
                if action in {"2", "3", "10"}:
                    operation, refresh = {"2": (self.status, "重新检查"), "3": (self.logs, "重新读取"),
                                          "10": (self.readiness, "重新检查")}[action]
                    self.read_page(instance, operation, refresh)
                elif action == "6":
                    self.heading("WebDAV 凭据", instance)
                    terminal.show_credentials(self.ui, self.product, instance.config, self.log)
                    completed = True
                elif action == "14":
                    if self.remove(instance):
                        return 0  # The final uninstall may have removed this offline runtime.
                elif action == "5":
                    from tg2cloud.deployment.users import manage
                    manage(self, instance)
                elif action == "15":
                    from tg2cloud.addons.external_webdav.entry import open_menu
                    open_menu(self.recheck(instance), self.ui, self.log)
                elif action == "16":
                    from tg2cloud.deployment.listening import manage
                    manage(self, self.recheck(instance))
                elif action in {"8", "9"}:
                    from tg2cloud.deployment.feature_settings import (
                        manage_classification,
                        manage_notifications,
                    )
                    operation = manage_classification if action == "8" else manage_notifications
                    operation(self, instance)
                elif action == "12":
                    from tg2cloud.deployment.diagnostics import collect, save
                    self.heading("故障诊断报告", instance)
                    self.log("正在生成只读诊断报告，请稍候……")
                    report = collect(instance, self.session)
                    self.log(terminal_report(report))
                    if self.ui.confirm("保存已脱敏报告到本机私密目录？不会自动上传"):
                        parent = Path(self.ui.ask("报告目录（绝对路径）", default="/opt/tg2cloud-reports"))
                        self.log("报告已保存：" + str(save(report, parent)))
                    completed = True
                else:
                    completed = handlers[action](instance) is not False
                if completed:
                    self.return_to_main()
            except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
                self.log("操作未完成：" + str(exc))
                if action == "14":
                    return 1  # Do not offer a fresh install after a partial uninstall.
                self.return_to_main()


def main(argv=None, *, mode_hint=None) -> int:
    parser = argparse.ArgumentParser(description="TG2Cloud 本地管理；已有工具离线运行，首次获取及升级组件仅使用正式稳定 Release")
    parser.add_argument("--edition", choices=tuple(PRODUCTS))
    parser.add_argument("--install-dir", help="指定已核验的单 Edition 自定义目录")
    args = parser.parse_args(argv)
    log, ui = InstallerLog(SafeLog()), None
    try:
        preflight.validate_host()
        if mode_hint not in {None, "public", "lan"}:
            raise ValueError("不支持的安装模式")
        source = Path(__file__).resolve().parents[3]
        if (source / "installation.json").exists():
            runtime.verify(source)
        if args.install_dir and not args.edition:
            raise ValueError("自定义目录必须同时指定 --edition")
        ui = terminal.Terminal()
        ui.friendly = True
        key = args.edition
        if key is None:
            selected = edition_menu(ui, log, title="安装与管理" if mode_hint else "本地管理")
            key = {"1": "clouddrive2", "2": "openlist"}.get(selected)
            if key is None:
                raise ValueError("Edition 选择无效")
        return Management(PRODUCTS[key], LocalSession(log), log, ui, args.install_dir, mode_hint=mode_hint).run()
    except (KeyboardInterrupt, EOFError):
        log("已退出本地管理；中断的变更请重新检查状态，不假定已经回退。")
        return 130
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log("本地管理未启动：" + str(exc))
        return 1
    except Exception:  # noqa: BLE001 - never expose a configuration traceback
        log("本地管理操作异常；未输出配置或凭据，请核对实例状态。")
        return 1
    finally:
        if ui is not None:
            ui.close()
