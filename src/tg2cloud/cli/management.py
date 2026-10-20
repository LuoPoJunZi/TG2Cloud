"""Offline, single-Edition maintenance UI built on the existing safety boundaries."""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from tg2cloud.cli import terminal
from tg2cloud.cli.presentation import InstallerLog, edition_menu
from tg2cloud.deployment import architecture, instances, preflight, runtime, uninstall
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import lan
from tg2cloud.deployment.proxy.manager import (
    DomainProxyManager,
    validate_domain,
    validate_email,
)

MENU = """
── TG2Cloud 本地管理 ──
1. 安装 / 升级
2. 查看运行状态
3. 查看运行日志
4. 启动 / 停止 / 重启
5. WebDAV 验收
6. HTTPS / 管理入口
7. 备份管理
8. 查看 WebDAV 凭据
9. 卸载当前实例
10. Bot 用户管理
0. 退出
"""


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
        manager = DomainProxyManager(self.session, self.product, {"vps_host": "127.0.0.1"}, self.log)
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
        self.log("1. Bot（默认，仅影响任务处理）\n2. 存储网关（会中断存储访问）\n0. 返回")
        target = choose(self.ui, "操作对象", ("0", "1", "2"), "1")
        if target == "0":
            return
        self.log("1. 启动\n2. 停止\n3. 重启\n0. 返回")
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3"))
        if action == "0":
            return
        name = self.product.bot_container if target == "1" else self.product.storage_container
        verb = {"1": "start", "2": "stop", "3": "restart"}[action]
        if not self.ui.confirm(f"确认 {verb} {name}？进行中的任务或外部访问可能中断"):
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
                self.log("1. 公网 VPS（HTTPS 域名）\n2. 可信内网（HTTP 地址）\n0. 返回")
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
        self.log("1. 检查 HTTPS\n2. 显式修复 HTTPS（保留已有域名）\n3. 证书续期演练（dry-run）\n0. 返回")
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3"), "1")
        if action == "1":
            self.log(self.proxy().status().message)
        elif action == "2":
            manager = self.proxy()
            state = manager.read_state()
            route = state["domains"].get(self.product.key, {})
            domain = route.get("domain") or self.ui.ask("管理页域名（A/AAAA 直指本机；Cloudflare 仅 DNS）", validate=validate_domain)
            email = route.get("email", "") or self.ui.ask("Let's Encrypt 邮箱（可留空）", validate=validate_email)
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
        self.log("1. 查看实例历史备份\n2. 创建共享代理备份\n3. 查看共享代理备份\n4. 校验/隔离解包最近代理备份\n5. 清理旧代理备份\n0. 返回\n不提供覆盖运行数据的一键恢复；实例备份由原升级流程生成。")
        action = choose(self.ui, "选择操作", ("0", "1", "2", "3", "4", "5"))
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
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            self.recheck(instance)
            manager = self.proxy()
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
            self.log(f"\n{self.product.display_name} · 版本 {instance.version or '未安装'} · Bot {'运行中' if instance.running else '未运行'}\n安装目录：{instance.directory}")
            if not instance.present:
                if self.ui.confirm(self.product.display_name + " 尚未安装，是否进入安装向导？"):
                    self.upgrade(instance)
                return 0
            self.log(MENU)
            action = choose(self.ui, "选择操作", tuple(str(n) for n in range(11)), "0")
            if action == "0":
                return 0
            try:
                if action == "1":
                    self.upgrade(instance)
                    continue
                if not instance.present:
                    raise ValueError("尚无完整实例，请先安装；不会执行维护操作")
                handlers = {"2": self.status, "3": self.logs, "4": self.control, "5": self.verify,
                            "6": self.entry, "7": self.backups}
                if action == "8":
                    terminal.show_credentials(self.ui, self.product, instance.config, self.log)
                elif action == "9":
                    if self.remove(instance):
                        return 0  # The final uninstall may have removed this offline runtime.
                elif action == "10":
                    from tg2cloud.deployment.users import manage
                    manage(self, instance)
                else:
                    handlers[action](instance)
            except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
                self.log("操作未完成：" + str(exc))
                if action == "9":
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
