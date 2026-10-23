"""Offline, single-Edition maintenance UI built on the existing safety boundaries."""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from tg2cloud.cli import terminal
from tg2cloud.cli.presentation import InstallerLog, edition_menu, numbered_menu
from tg2cloud.deployment import architecture, instances, preflight, runtime, uninstall
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import lan
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
    (13, "数据备份管理"), (14, "卸载当前实例"), (0, "退出"),
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

    def status(self, instance):
        for name in (self.product.bot_container, self.product.storage_container):
            code, output = self.session.run("docker inspect --format " + shlex.quote('{{.Name}}：{{.State.Status}}{{if .State.Health}} / {{.State.Health.Status}}{{end}}') + " " + shlex.quote(name), timeout=15)
            if code:
                raise RuntimeError("运行状态读取失败，不标记为正常")
            self.log(output.strip())
        saved = self.mode(instance)
        if saved:
            inventory = instances.docker_inventory(self.session)
            entry = lan.inspect_lan(self.product, self.session, inventory)
            if not entry or not entry.get("running"):
                raise RuntimeError("内网管理入口未运行")
            lan.check_entry(self.product, saved["bind_ip"])
            self.log(f"内网管理页：http://{saved['bind_ip']}:{self.product.management_port}（本机检查通过）")
        else:
            self.log(self.proxy().status().message)

    def logs(self, instance):
        self.log("最近 30 分钟、每个容器最多 100 行日志（已脱敏）：")
        for name in (self.product.bot_container, self.product.storage_container):
            self.checked_run("docker logs --since 30m --tail 100 " + shlex.quote(name), timeout=30)

    def control(self, instance):
        self.log("\n── 服务启停管理 ──\n存储网关停止或重启会中断存储访问。\n" + numbered_menu((
            (1, "启动 Bot"), (2, "停止 Bot"), (3, "重启 Bot"),
            (4, "启动存储网关"), (5, "停止存储网关"), (6, "重启存储网关"), (0, "返回"),
        )))
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3", "4", "5", "6"), "0")
        if action == "0":
            return
        number = int(action) - 1
        name = self.product.bot_container if number < 3 else self.product.storage_container
        verb, label = (("start", "启动"), ("stop", "停止"), ("restart", "重启"))[number % 3]
        if not self.ui.confirm(f"确认{label} {name}？进行中的任务或外部访问可能中断"):
            return
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            self.checked_run("docker " + verb + " " + shlex.quote(name), timeout=90)
        self.log("容器操作已完成；健康状态请另选“查看运行状态”。")

    def verify(self, instance):
        if not instance.running:
            raise ValueError("Bot 未运行，请先启动后验收")
        if not self.ui.confirm("运行 WebDAV 写入验收？仅创建并清理随机测试文件，请先配置云挂载与专用账号"):
            return
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            output = self.checked_run("docker exec " + shlex.quote(self.product.bot_container) + " python -m app.verify_destination", timeout=600)
            if "TG2CLOUD_DESTINATION=OK" not in output.splitlines():
                raise RuntimeError("验收缺少完整成功标记；不自动重试或修改凭据")
        self.log("WebDAV 写入与远端大小复验通过；云盘官方端最终完成仍需自行确认。")

    def upgrade(self, instance):
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
            self.status(instance)
            self.log("当前是内网 HTTP 模式，不申请证书或隐式切换为公网模式。")
            return
        self.log(numbered_menu(((1, "检查 HTTPS"), (2, "显式修复 HTTPS（保留已有域名）"), (3, "证书续期演练（dry-run）"), (0, "返回"))))
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3"), "1")
        if action == "1":
            self.log(self.proxy().status().message)
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
                return
            with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                self.recheck(instance)
                if manager.read_state() != state:
                    raise ValueError("预览后代理状态发生变化，请重新检测")
                report = manager.configure(domain, email)
                self.log(report.message)
                if report.state != "healthy":
                    raise RuntimeError("HTTPS 修复尚未通过，请核对状态")
        elif action == "3" and self.ui.confirm("确认执行续期 dry-run？需要外网和 ACME，不替换正式证书"):
            with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                self.recheck(instance)
                self.log(self.proxy().maintenance("renew_dry_run"))

    def backups(self, instance):
        self.log(numbered_menu(((1, "查看实例历史备份"), (2, "创建共享代理备份"), (3, "查看共享代理备份"),
                                (4, "校验/隔离解包最近代理备份"), (5, "清理旧代理备份"),
                                (6, "创建实例快照／导出"), (7, "实例快照隔离预检"), (0, "返回")))
                 + "\n不提供覆盖运行数据的一键恢复；实例快照不包含下载文件和共享 HTTPS。")
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3", "4", "5", "6", "7"))
        if action == "0":
            return
        if action == "1":
            root = Path(self.product.backup_dir)
            pattern = uninstall.backup_targets((self.product.key,), {}, False)[root]
            identity = uninstall.backup_identity(root, pattern)
            for item in identity[-1] if identity else ():
                self.log(item[0] + f"（{item[3]} 字节，尚未校验内容）")
            if not identity or not identity[-1]:
                self.log("没有受管实例历史备份。")
            return
        if action in {"6", "7"}:
            from tg2cloud.deployment import backup
            from tg2cloud.persistence import bundle
            parent = Path(self.ui.ask("私密备份目录", default="/opt/tg2cloud-snapshots/" + self.product.key))
            backup.output_directory(parent, instance)
            if action == "6":
                self.log("备份配置、业务数据库、Session 和网关配置；不备份云端、downloads、日志、共享代理或附加功能状态。请另存这些资料；导出目录在默认卸载清理范围之外。")
                if not self.ui.confirm("确认短暂停止所选 Bot 与网关创建快照？会暂时中断该网关的管理和外部 WebDAV 读取；不停止其他 Edition"):
                    return
                with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
                    current = self.recheck(instance)
                    archive = backup.create(current, self.session, parent)
                self.log("实例快照已核验：" + str(archive) + "；原服务已恢复运行状态，仍需检查业务就绪。含敏感信息，请私密离机保存。")
            else:
                archive = Path(self.ui.ask("实例快照归档绝对路径"))
                runtime.safe_path(archive, private=True)
                runtime.safe_path(parent, private=True)
                if not self.ui.confirm("确认在上述私密目录隔离解包并检查？不覆盖运行数据，不启动第二个 Bot"):
                    return
                result = bundle.preflight(archive, parent, self.product.key, instance.version)
                self.log(f"实例快照结构／数据库预检通过：{result['files']} 文件；不代表运行恢复或全部网关授权已验收。")
            return
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            manager = self.proxy()
            if manager.external_entry() and action in {"3", "5"}:
                self.log("外部模式备份位于 /opt/tg2cloud-proxy/external-backups，仅含元数据与专属站点；不运行独立代理的整目录清理。可选创建或隔离核验，旧备份需人工保管。")
                return
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

    def remove(self, instance):
        if instance.directory != Path(self.product.install_dir):
            raise ValueError("现有卸载器只支持标准目录；自定义目录不自动卸载，避免清理错误实例")
        self.log("仅卸载 " + self.product.display_name + "：默认清理它的配置、数据库和备份；不删除另一 Edition 的容器/数据，云端文件和系统软件不删除。")
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
            self.log(f"\n── TG2Cloud 本地管理 ──\n\n{self.product.display_name} · 版本 {instance.version or '未安装'} · Bot {'运行中' if instance.running else '未运行'}\n安装目录：{instance.directory}\n\n")
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
                    continue
                if not instance.present:
                    raise ValueError("尚无完整实例，请先安装；不会执行维护操作")
                handlers = {"2": self.status, "3": self.logs, "4": self.control,
                            "7": self.entry, "11": self.verify, "13": self.backups}
                if action == "6":
                    terminal.show_credentials(self.ui, self.product, instance.config, self.log)
                elif action == "14":
                    if self.remove(instance):
                        return 0  # The final uninstall may have removed this offline runtime.
                elif action == "5":
                    from tg2cloud.deployment.users import manage
                    manage(self, instance)
                elif action in {"8", "9"}:
                    from tg2cloud.deployment.feature_settings import (
                        manage_classification,
                        manage_notifications,
                    )
                    operation = manage_classification if action == "8" else manage_notifications
                    operation(self, instance)
                elif action == "10":
                    from tg2cloud.deployment.readiness import check
                    check(instance, self.session, self.log)
                elif action == "12":
                    from tg2cloud.deployment.diagnostics import collect, save
                    report = collect(instance, self.session)
                    self.log(report)
                    if self.ui.confirm("保存已脱敏报告到本机私密目录？不会自动上传"):
                        parent = Path(self.ui.ask("报告目录（绝对路径）", default="/opt/tg2cloud-reports"))
                        self.log("报告已保存：" + str(save(report, parent)))
                else:
                    handlers[action](instance)
            except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
                self.log("操作未完成：" + str(exc))
                if action == "14":
                    return 1  # Do not offer a fresh install after a partial uninstall.


def main(argv=None, *, mode_hint=None) -> int:
    parser = argparse.ArgumentParser(description="TG2Cloud 离线本地管理；仅安装/升级查询正式稳定 Release")
    parser.add_argument("--edition", choices=tuple(PRODUCTS))
    parser.add_argument("--install-dir", help="指定已核验的单 Edition 自定义目录")
    args = parser.parse_args(argv)
    log, ui = InstallerLog(SafeLog()), None
    try:
        preflight.validate_host(log=log)
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
