"""Compose ownership adapter for the shared read-only WebDAV lifecycle."""
from __future__ import annotations

import os
from types import SimpleNamespace

from tg2cloud.addons.external_webdav import cli, config, discovery
from tg2cloud.addons.external_webdav.service import Service
from tg2cloud.compose.releases import verify_tools


class ComposeWebDAV(Service):
    def __init__(self, manager):
        self.compose_manager = manager
        super().__init__(manager.product, manager.session, manager.log, manager.ui,
                         instance_provider=self.selected, proxy_manager=manager.proxy())

    def selected(self, product, directory, session, log, *, require_running=True):
        manager = self.compose_manager
        if product.key != manager.product.key or directory is not None and directory != str(manager.root):
            raise ValueError("外部 WebDAV 不属于此 Compose 实例")
        self.manager.guard(require_running=require_running)
        return manager.discover()

    def management_hint(self, *, check=False):
        self.log("外部 WebDAV 后续管理：在当前 Compose 部署目录运行 bash manage.sh，选择“外部 WebDAV”。")

    def operation(self, service, args):
        if args.action in {"install", "configure"}:
            self.configure(install_dir=str(self.compose_manager.root), install=args.action == "install",
                           sample_file=args.sample_file, prepare_runtime=lambda: verify_tools(self.compose_manager.root))
        elif args.action == "upgrade":
            # The verified bundle owns both the host adapter and its helper
            # manifest; never install the script-only WebDAV launcher over it.
            self.compose_manager.upgrade(self.compose_manager.discover())
        elif args.action == "users":
            from tg2cloud.addons.external_webdav.users import menu
            menu(self, sample_file=args.sample_file)
        else:
            self.maintain(args.action, sample_file=args.sample_file)


def open_menu(manager, instance):
    discovery.host(manager.session, log=manager.log)
    service = ComposeWebDAV(manager)
    record = service.record()
    if record and record["instance_dir"] != str(instance.directory):
        raise ValueError("此 Edition 外部 WebDAV 已绑定其他目录；不接管")
    config.canonical(manager.root)
    previous = os.environ.get("TG2CLOUD_MANAGER_MENU")
    try:
        os.environ["TG2CLOUD_MANAGER_MENU"] = "1"
        args = SimpleNamespace(action=None, edition=manager.product.key, install_dir=str(manager.root), sample_file="")
        cli.interactive(service, args, operation=service.operation)
    finally:
        if previous is None:
            os.environ.pop("TG2CLOUD_MANAGER_MENU", None)
        else:
            os.environ["TG2CLOUD_MANAGER_MENU"] = previous
