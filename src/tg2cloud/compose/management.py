"""Host menu for independently owned Compose instances, sharing core operations."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess  # nosec B404
from pathlib import Path

from tg2cloud.cli.management import MENU_ITEMS, Management, choose
from tg2cloud.cli.presentation import InstallerLog, numbered_menu
from tg2cloud.compose import access, runtime
from tg2cloud.compose.https import (
    ComposeInstance,
    ComposeProxyManager,
    owned_file,
    physical_directory,
    run_action,
)
from tg2cloud.deployment import architecture, instances, preflight
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.releases import source_version


class ComposeManagement(Management):
    menu_items = (*MENU_ITEMS[:-1], (17, "资源与安全"), MENU_ITEMS[-1])

    def __init__(self, root, session, log, ui, *, source=None):
        self.root = root
        self.source = source or root / "https-tools"
        info = runtime.metadata(root, expected_version=source_version(self.source))
        from tg2cloud.deployment.profiles import PRODUCTS
        super().__init__(PRODUCTS[info["edition"]], session, log, ui, str(root))
        self.core = ComposeInstance(root, session, log, source=self.source)
        self.additional_handlers = {"17": self.resources}
        self.exit_after_upgrade = True

    def discover(self):
        containers = self.core.validate(loopback=False, require_running=False, allow_missing=True)
        bot = containers.get(self.product.bot_container, {})
        gateway = containers.get(self.product.storage_container, {})
        item = instances.Instance(self.product, self.root, True, self.core.info["version"],
                                  bool(bot.get("running")), gateway.get("image", ""), dict(self.core.config),
                                  owned_file(self.root / ".env", private=True))
        item.deployment_mode = "compose"
        item.container_ids = tuple(containers.get(name, {}).get("id") for name in
                                   (self.product.bot_container, self.product.storage_container))
        self.project = next(((container.get("labels") or {}).get("com.docker.compose.project")
                             for container in (bot, gateway) if container), "tg2cloud-compose-" + self.product.key)
        return item

    def recheck(self, previous):
        current = super().recheck(previous)
        if current.container_ids != previous.container_ids:
            raise ValueError("确认后容器身份发生变化；停止，不操作替代实例")
        return current

    def compose_command(self, *arguments, root=None):
        directory = root or self.root
        return "docker compose --project-directory " + shlex.quote(str(directory)) + " -f " + shlex.quote(
            str(directory / "docker-compose.yml")) + " --project-name " + shlex.quote(self.project) + " " + shlex.join(arguments)

    def proxy(self):
        return ComposeProxyManager(self.core, self.ui)

    def status(self, instance, *, title="查看运行状态"):
        self.heading(title, instance)
        self.log("部署方式：独立 Docker Compose")
        self.show_containers()
        plan = access.read_access(self.root, self.product.key)
        if plan is None or plan["mode"] == "local":
            address = instance.config.get("TG2CLOUD_BIND_IP", "127.0.0.1")
            self.log(f"管理地址：http://{address}:{self.product.management_port}\n仅供本机或可信内网；跨网络请配置 HTTPS。")
        elif plan["mode"] == "external":
            self.log("管理入口由已有反向代理负责；请在 HTTPS 菜单导出配置并独立验收。")
        else:
            self.show_proxy_report(self.proxy().inspect_status())

    def entry(self, instance):
        self.heading("HTTPS 与管理", instance)
        actions = {"1": "configure", "2": "status", "3": "renewal-dry-run", "4": "remove",
                   "5": "export-existing", "6": "proxy-backup"}
        self.log(numbered_menu(((1, "配置 HTTPS"), (2, "检查 HTTPS"), (3, "证书续期演练"),
                                 (4, "移除管理域名"), (5, "导出已有代理配置"), (6, "备份共享代理"), (0, "返回主菜单"))))
        selected = choose(self.ui, "选择操作", ("0", *actions), "0")
        if selected != "0":
            self.recheck(instance)
            run_action(actions[selected], self.core, self.proxy(), self.ui)
        return selected != "0"

    def listen_action(self, instance, action):
        from tg2cloud.deployment.listening import account_command
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            current = self.recheck(instance)
            if not current.running:
                raise ValueError("请先启动当前 Compose Bot")
            return account_command(self.product, action)

    def external_webdav(self, instance):
        from tg2cloud.compose.webdav import open_menu
        open_menu(self, self.recheck(instance))

    def control(self, instance):
        from tg2cloud.deployment.feature_settings import request
        self.heading("服务启停管理", instance)
        self.log(numbered_menu(((1, "启动 Bot"), (2, "停止 Bot"), (3, "重启 Bot"),
            (4, "启动存储网关"), (5, "停止存储网关"), (6, "重启存储网关"),
            (7, "暂停新任务调度"), (8, "恢复任务调度"), (0, "返回主菜单"))))
        action = choose(self.ui, "选择操作", tuple(str(n) for n in range(9)), "0")
        if action == "0":
            return False
        if not self.ui.confirm("确认此操作仅作用于当前实例？服务启停可能中断传输或外部读取"):
            return False
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")):
            current = self.recheck(instance)
            if action in {"7", "8"}:
                if not current.running:
                    raise ValueError("请先启动 Bot；不直接修改离线数据库")
                result = request(self, current, "queue-pause" if action == "7" else "queue-resume")
                value = result.get("queue", {})
                if type(value.get("paused")) is not bool or type(value.get("active")) is not int:
                    raise ValueError("调度控制协议无法核实；旧版可在 Bot 使用 /pause 或 /resume")
                self.log("已暂停新任务，活动任务将继续完成。" if value["paused"] else "已恢复调度；仍须满足资源与目的端检查。")
            else:
                index = int(action) - 1
                service = self.product.bot_service if index < 3 else self.product.key
                verb = ("start", "stop", "restart")[index % 3]
                self.checked_run(self.compose_command(verb, service), timeout=90)
        return True

    def backups(self, instance):
        from tg2cloud.compose.maintenance import backups
        return backups(self, instance)

    def resources(self, instance):
        from tg2cloud.compose.maintenance import resources
        return resources(self, instance)

    def upgrade(self, instance):
        from tg2cloud.compose.lifecycle import upgrade
        return upgrade(self, instance)

    def remove(self, instance):
        from tg2cloud.compose.lifecycle import uninstall
        return uninstall(self, instance)


def initialize(root, session, log, ui):
    """Use the same isolated setup service; never mount the Docker daemon."""
    physical_directory(root)
    if (root / ".env").exists():
        return
    from tg2cloud.compose.releases import verify_tools
    verify_tools(root)
    if not ui.confirm("尚未初始化，进入 Compose 逐项填写向导？仅生成本目录配置"):
        raise ValueError("未初始化；没有启动业务容器")
    architecture.check_docker(session)
    arguments = ["docker", "compose", "--project-directory", str(root), "-f", str(root / "docker-compose.yml"), "run", "--rm", "setup"]
    # The terminal is inherited for credentials; never capture its contents.
    if not os.isatty(0) or not os.isatty(1):
        with open("/dev/tty", "r+b", buffering=0) as tty:
            if not os.isatty(tty.fileno()):
                raise ValueError("初始化需要自己的 SSH 交互终端")
            result = subprocess.run(arguments, stdin=tty, stdout=tty, stderr=tty, check=False)  # nosec B603
    else:
        result = subprocess.run(arguments, check=False)  # nosec B603
    if result.returncode:
        raise ValueError("Compose 初始化未完成；保留现有文件，请核对")
    log("初始化完成；请先在网关后台挂载存储并配置专用 WebDAV 账号。")


def main(argv=None, *, session=None, ui=None, log=None):
    parser = argparse.ArgumentParser(description="TG2Cloud Compose 本地管理；不接管脚本实例或未知容器")
    parser.add_argument("action", nargs="?", default="manage", choices=("manage", "status", "check", "upgrade", "uninstall"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    log = log or InstallerLog(SafeLog())
    own_ui = ui is None
    try:
        preflight.validate_host()
        architecture.check_environment()
        session = session or LocalSession(log)
        if ui is None:
            from tg2cloud.cli.terminal import Terminal
            ui = Terminal()
            ui.friendly = True
        root = args.root.absolute()
        if root.resolve() != root:
            raise ValueError("Compose 目录经过链接；停止")
        from tg2cloud.compose.releases import verify_tools
        # Legacy bundles can be inspected by new tools without executing their
        # old Python sources; images/templates still use their own hashed data.
        info = json.loads(owned_file(root / "compose-bundle.json"))
        if info.get("format") == 1 and not (root / "https-tools").exists():
            raise runtime.ComposeError("早期 Compose 部署包没有离线管理工具；请先完整备份并按 Compose 教程升级部署包，不要只复制管理脚本")
        verify_tools(root, require_manager=info.get("format") == 3)
        initialize(root, session, log, ui)
        manager = ComposeManagement(root, session, log, ui)
        if args.action == "manage":
            return manager.run()
        instance = manager.discover()
        if args.action == "check":
            from tg2cloud.deployment.readiness import check
            return 0 if check(instance, session, log) else 1
        else:
            getattr(manager, {"status": "status", "upgrade": "upgrade", "uninstall": "remove"}[args.action])(instance)
        return 0
    except runtime.ComposeError as exc:
        log("Compose 操作未完成：" + str(exc))
        return 1
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        log("Compose 操作未完成；请核对版本、目录归属、容器身份及上方脱敏结果。未自动接管其他实例。")
        return 1
    except (KeyboardInterrupt, EOFError):
        log("操作中断；保留数据和维护记录，请重新查看状态。")
        return 130
    finally:
        if own_ui and ui is not None:
            ui.close()


if __name__ == "__main__":
    raise SystemExit(main())
