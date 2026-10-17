"""Independent lifecycle with native manual accounts and fail-closed rotation."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from tg2cloud.addons.external_webdav import config, discovery, verification
from tg2cloud.deployment import uninstall
from tg2cloud.deployment.host import edition_lock
from tg2cloud.deployment.proxy import maintenance
from tg2cloud.deployment.proxy.manager import (
    NGINX_IMAGE,
    PROXY_ROOT,
    DomainProxyManager,
    proxy_lock_command,
    render_compose,
    render_config_set,
)
from tg2cloud.deployment.proxy.state import certificate_domains


class Service:
    def __init__(self, product, session, log, ui, *, root: Path = config.ROOT):
        self.product, self.session, self.log, self.ui, self.root = product, session, log, ui, root
        self.directory = root / product.key
        self.record_path = self.directory / "config.json"
        self.auth = Path(PROXY_ROOT) / "external-auth" / (product.key + ".htpasswd")
        self.launcher = Path("/usr/local/bin/tg2cloud-webdav")
        self.manager = DomainProxyManager(session, product, {"vps_host": "127.0.0.1"}, log)

    def preflight(self, directory: str | None, domain: str = "", *, require_running: bool = True):
        instance = discovery.selected(self.product, directory, self.session, self.log, require_running=require_running)
        self.manager.prepare()
        state = uninstall.read_state()
        retained = state.get("external_webdav", {}).get(self.product.key)
        if retained and (self.record() is None or retained["instance_dir"] != str(instance.directory)):
            raise ValueError("活动外部路由缺少对应记录或实例不符；不自动接管。")
        # Reject unknown mounts/containers before invoking the shared manager.
        containers, _ = uninstall.docker_snapshot(self.session)
        for name in ("tg2cloud-proxy-nginx", "tg2cloud-proxy-certbot"):
            if name in containers:
                uninstall.proxy_identity(name, containers[name], state=state)
        root = Path(PROXY_ROOT)
        managed = {"tg2cloud-proxy-nginx", "tg2cloud-proxy-certbot"} & containers.keys()
        if (managed and not (root / "docker-compose.yml").is_file()) or (
                (state["domains"] or state.get("external_webdav")) and len(managed) != 2):
            raise ValueError("共享代理只部分存在；不自动修复或接管。")
        config.canonical(root)
        for path in (root / "docker-compose.yml", root / "external-auth"):
            config.canonical(path)
        auth_dir = root / "external-auth"
        if state.get("version") == 2 and not auth_dir.is_dir():
            raise ValueError("schema 2 代理缺少受管认证目录。")
        for owner in state.get("external_webdav", {}):
            if not (auth_dir / (owner + ".htpasswd")).is_file():
                raise ValueError("活动外部路由缺少认证文件，停止，不猜测密码。")
        if auth_dir.exists():
            if not auth_dir.is_dir() or {p.name for p in auth_dir.iterdir()} - {"clouddrive2.htpasswd", "openlist.htpasswd"}:
                raise ValueError("共享认证目录含未知资源。")
            for path in auth_dir.iterdir():
                config.canonical(path)
                if (not path.is_file() or path.stat().st_size > 512
                        or (os.name == "posix" and path.stat().st_mode & 0o007)):
                    raise ValueError("认证文件类型／大小不受支持。")
                content = path.read_text(encoding="ascii")
                lines = content.splitlines()
                if len(lines) != 1 or not (content == "disabled:!\n" or (
                        lines[0].count(":") == 1 and config.HASH.fullmatch(lines[0].split(":", 1)[1]))):
                    raise ValueError("认证文件不是单账号强哈希格式，拒绝发布。")
        if (root / "docker-compose.yml").exists():
            expected = render_compose(certificate_domains(state), external_auth=state.get("version") == 2)
            if (root / "docker-compose.yml").read_text().replace("\r\n", "\n") != expected:
                raise ValueError("共享 Compose 与受管清单不一致；不自动接管或覆盖。")
            files = render_config_set(state)
            directory_path = root / "nginx/conf.d"
            if {path.name for path in directory_path.iterdir()} != {Path(name).name for name in files if name.startswith("conf.d/")}:
                raise ValueError("共享代理含未知或缺失路由文件。")
            for name, content in files.items():
                path = root / "nginx" / name
                config.canonical(path)
                if not path.is_file() or path.read_text() != content:
                    raise ValueError("共享 Nginx 文件与状态不一致；先人工恢复受管基线。")
        elif state["domains"] or state.get("external_webdav"):
            raise ValueError("共享代理有状态但运行配置缺失。")
        existing_domain = next(iter(certificate_domains(state)), "")
        if domain or existing_domain:
            environment = self.manager.probe(domain or existing_domain)
            if not environment.ports_safe:
                raise ValueError("80/443 存在其他占用或归属不明；不接管任何服务。")
        if domain:
            self.manager._validate_environment(environment)
            for key, item in state["domains"].items():
                if item["domain"] == domain:
                    raise ValueError("外部域名不得复用管理域名。")
            for key, item in state.get("external_webdav", {}).items():
                if key != self.product.key and item["domain"] == domain:
                    raise ValueError("外部域名已由其他实例占用。")
        return instance, state

    @contextmanager
    def locked(self):
        # Same order as the core uninstaller: Edition first, shared proxy second.
        with (edition_lock(Path("/opt/tg2cloud-cli-locks") / (self.product.key + ".lock")),
              self.session.hold_lock(proxy_lock_command())):
            yield

    def record(self):
        item = config.read_record(self.record_path)
        if item and item["edition"] != self.product.key:
            raise ValueError("附加功能记录 Edition 与目录不符。")
        return item

    def save(self, item: dict) -> None:
        config.canonical(self.directory)
        if self.directory.exists() and {p.name for p in self.directory.iterdir()} - {"config.json", "backups"}:
            raise ValueError("附加功能目录包含未知文件。")
        config.write_record(self.record_path, item)

    def backup(self, state: dict) -> None:
        if self.record_path.exists():
            config.atomic(self.directory / "backups" / (str(time.time_ns()) + ".json"), self.record_path.read_bytes())
        if (Path(PROXY_ROOT) / "docker-compose.yml").exists():
            maintenance.create_backup(Path(PROXY_ROOT), maintenance.BACKUP_ROOT)

    def route(self, item: dict, enabled: bool) -> dict:
        return {"kind": "external_webdav", "owner": config.OWNER, "edition": self.product.key,
                "instance_dir": item["instance_dir"], "domain": item["domain"], "enabled": enabled,
                "backend_port": self.product.management_port, "auth_file": f"external-auth/{self.product.key}.htpasswd"}

    def auth_write(self, content: bytes) -> None:
        # Only after confirmation. Query the actual pinned image's worker group,
        # rather than assume host nginx owns the same numeric group.
        code, output = self.session.run("docker run --rm --read-only --entrypoint id " + shlex.quote(NGINX_IMAGE) + " -g nginx", timeout=120)
        if code or not output.strip().isdigit() or not 0 < int(output.strip()) < 65536:
            raise ValueError("不能确认受管 Nginx worker 组，拒绝扩大认证文件权限。")
        gid = int(output.strip())
        config.canonical(self.auth.parent)
        self.auth.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        os.chown(self.auth.parent, 0, gid)
        self.auth.parent.chmod(0o750)
        config.atomic(self.auth, content, mode=0o640, gid=gid)

    def revoke(self) -> None:
        if self.auth.exists():
            # Directory bind mounts observe atomic replacement; no stale file
            # inode mount can retain the previous password after revocation.
            config.atomic(self.auth, b"disabled:!\n", mode=0o640, gid=self.auth.stat().st_gid)

    def display(self, item: dict) -> None:
        for line in ("名称：TG2Cloud 文件", "协议：HTTPS", "服务器：" + item["domain"], "端口：443",
                     "根路径：/dav/", "用户名：" + item["username"], "密码（不回显）：使用新设置的外部专用密码",
                     "目标目录：" + item["target_dir"], "目录／原生只读权限：用户在网关后台确认；不是自动权限审计",
                     "状态：" + item["phase"]):
            self.log(line)

    def assert_binding(self, item: dict, instance) -> None:
        if (item["instance_dir"] != str(instance.directory) or item["binding"] != config.binding(instance.config)
                or item["backend_image"] != instance.gateway_image):
            raise ValueError("Bot 目录配置／网关版本已变化；外部范围不自动扩大，请用 configure 显式核对。")

    def assert_record(self, item: dict | None) -> None:
        if self.record() != item:
            raise ValueError("附加功能记录已被另一操作修改；停止，请刷新状态。")

    def configure(self, *, install_dir: str | None, install: bool = False, sample_file: str = "") -> bool:
        previous = self.record()
        if previous and install:
            self.log("外部 WebDAV 已登记；不重复安装或自动启用。使用 check／configure／enable 维护。")
            self.display(previous)
            return False
        launcher = self.launcher
        config.canonical(launcher)
        if launcher.exists() and not launcher.read_text().startswith("#!/bin/sh\n# TG2Cloud external_webdav managed\n"):
            raise ValueError("同名维护命令不是本功能拥有，停止，不覆盖。")
        instance, _ = self.preflight(install_dir or (previous or {}).get("instance_dir"))
        from tg2cloud.deployment.proxy.state import validate_domain, validate_email
        domain = self.ui.ask("外部 HTTPS 域名（不能复用管理域名）", default=(previous or {}).get("domain", ""), validate=validate_domain)
        email = self.ui.ask("Let's Encrypt 邮箱（可留空）", validate=validate_email)
        self.log("Bot 用户根目录不是 TARGET_PATH；程序不能从相对子目录推断网盘绝对目录。")
        bot_root = self.ui.ask("请先在后台核对 Bot WebDAV 用户根目录，填写网关逻辑绝对路径", validate=lambda v: config.logical_path(v, allow_root=True))
        relative = config.decode(instance.config, "TARGET_PATH").strip("/")
        target = config.logical_path(bot_root.rstrip("/") + "/" + relative if relative else bot_root)
        user = self.ui.ask("新的外部专用用户名", default=(previous or {}).get("username", ""),
                           validate=lambda v: config.username(v, config.decode(instance.config, "USERNAME")))
        generated = config.new_password()
        secret = self.ui.ask("新的外部密码（留空安全生成；不回显）", default=generated, secret=True, validate=config.password)
        self.log.register({"EXTERNAL_PASSWORD": secret})
        item = {"schema": 1, "owner": config.OWNER, "edition": self.product.key, "instance_dir": str(instance.directory),
                "domain": domain, "username": user, "bot_root": bot_root, "target_dir": target,
                "binding": config.binding(instance.config), "phase": "pending", "scope_verification": "manual-native-readonly",
                "backend_image": instance.gateway_image, "revision": secrets.token_hex(16)}
        self.preflight(str(instance.directory), domain)
        self.log("计划：独立外部 WebDAV；实例 " + str(instance.directory) + "；域名 " + domain)
        self.log("新账号 " + user + "；原生账号根目录必须直接限定为 " + target)
        self.log("新增私密配置／备份：" + str(self.directory) + "；认证哈希：" + str(self.auth))
        self.log("新增／更新离线代码 " + str(self.root / "runtime") + "/<代码摘要>；维护命令 " + str(self.launcher) + "。")
        self.log("共享代理将迁移至 schema 2；旧写入端会拒绝操作。可能重建 Nginx 挂载并短暂中断管理入口；不重启 Bot／网关。")
        if not self.ui.confirm("确认计划并继续人工建号？已有外部入口会先撤销认证"):
            return False
        with self.locked():
            self.assert_record(previous)
            current, state = self.preflight(str(instance.directory), domain)
            if config.binding(current.config) != item["binding"]:
                raise ValueError("确认期间 Bot 配置已变，停止。")
            self.backup(state)
            self.save(item)
            self.revoke()
            if self.product.key in state.get("external_webdav", {}):
                state["external_webdav"][self.product.key]["enabled"] = False
                self.manager.apply_shared_state_locked(state, verify_remaining=False)
        self.log("人工步骤：登录自己的 " + self.product.display_name + " 后台，核对当前版本支持独立只读用户。")
        self.log("创建／调整普通外部账号 " + user + "，根目录直接设为 " + target + "，仅 WebDAV 读取／列表；关闭所有写入／管理权限。")
        self.log("CloudDrive2 须确认当前版本／会员支持独立 WebDAV 用户；OpenList 不使用管理员或 Bot 用户。能力不足请取消，入口不开放。")
        try:
            self.ui.reveal("新外部 WebDAV 密码（仅当前终端）", secret)
            confirmed = self.ui.ask("完成后输入外部账号根目录的完整路径以确认；不能为 /", validate=config.logical_path)
            if confirmed != target or not self.ui.confirm("已在后台确认这是独立账号、根目录隔离且原生只读，无上传／删除／改名／管理权限？"):
                raise ValueError("未完成人工目录／权限确认；入口保持关闭。")
            route = dict(self.route(item, True), username=user)
            verification.check_backend(route, secret)
            with self.locked():
                current, state = self.preflight(str(instance.directory), domain)
                self.assert_binding(item, current)
                if self.record() != item:
                    raise ValueError("人工确认期间附加功能记录已变化。")
                self.auth_write((user + ":" + config.password_hash(secret) + "\n").encode())
                state.update(version=2)
                state.setdefault("external_webdav", {})[self.product.key] = self.route(item, True)
                try:
                    self.manager.apply_shared_state_locked(state, domain=domain, email=email,
                        verify=lambda: verification.check_public(route, secret, sample_file=sample_file))
                    self.verify_mounted_hash()
                except BaseException:
                    self.revoke()
                    raise
                item["phase"] = "enabled"
                self.save(item)
            self.display(item)
            self.log("EXTERNAL_WEBDAV=OK；本机 TLS、认证与目录检查通过；公网手机和真实视频拖动仍需独立验收。")
            return True
        except BaseException:
            with self.locked():
                current = self.record()
                if current and current["revision"] == item["revision"] and current["phase"] == "pending":
                    self.revoke()
                    item["phase"] = "needs_repair"
                    self.save(item)
            self.log("外部入口保持拒绝访问；后端由用户手动修改，不能声称密码原子回滚。Bot 未改动。")
            raise

    def verify_mounted_hash(self) -> None:
        code, output = self.session.run("docker exec tg2cloud-proxy-nginx sha256sum /etc/nginx/external-auth/" + self.product.key + ".htpasswd", timeout=15)
        if code or not output.split() or output.split()[0] != hashlib.sha256(self.auth.read_bytes()).hexdigest():
            raise ValueError("容器没有读取到当前认证文件，拒绝宣称密码轮换成功。")

    def maintain(self, action: str, *, sample_file: str = "") -> None:
        item = self.record()
        if item is None:
            raise ValueError("尚未登记此 Edition 的外部 WebDAV。")
        if action in {"status", "print-config"}:
            self.display(item)
            if action == "status":
                self.log("这是本地登记状态；check 才检查实际网关、代理和认证。")
            return
        instance, state = self.preflight(item["instance_dir"], require_running=action not in {"disable", "uninstall"})
        if action in {"disable", "uninstall"}:
            self.log("只操作本功能的认证／路由；不删除云端文件、Bot 数据或人工创建的后端账号。")
            if not self.ui.confirm("确认" + action + "外部入口？现有读取连接重载后最多约 10 秒退出"):
                return
            with self.locked():
                self.assert_record(item)
                _, state = self.preflight(item["instance_dir"], require_running=False)
                self.backup(state)
                item.update(phase="pending", revision=secrets.token_hex(16))
                self.save(item)
                self.revoke()
                routes = state.get("external_webdav", {})
                if self.product.key in routes:
                    if action == "uninstall":
                        routes.pop(self.product.key)
                    else:
                        routes[self.product.key]["enabled"] = False
                    self.manager.apply_shared_state_locked(state, verify_remaining=False)
                item["phase"] = "disabled"
                self.save(item)
                if action == "uninstall":
                    self.auth.unlink(missing_ok=True)
                    self.record_path.unlink()
                    # Keep private backup receipts and offline runtime, not data.
                    if (self.directory / "backups").exists():
                        self.log("私密备份保留于 " + str(self.directory / "backups") + "；含旧元数据／密码哈希，请自行保管。")
                    else:
                        self.directory.rmdir()
                    self.log("外部路由及活动状态已移除；后端人工账号未删除，证书未盲目清理。")
            return
        self.assert_binding(item, instance)
        secret = self.ui.ask("外部专用密码（仅用于本次认证检查，不保存）", secret=True, validate=config.password)
        self.log.register({"EXTERNAL_PASSWORD": secret})
        route = dict(self.route(item, True), username=item["username"])
        verification.check_backend(route, secret)
        if action == "check":
            current = state.get("external_webdav", {}).get(self.product.key)
            if current != self.route(item, item["phase"] == "enabled"):
                raise ValueError("活动路由与登记状态不一致，需 configure 修复。")
            if item["phase"] == "enabled":
                verification.check_public(route, secret, sample_file=sample_file)
                self.verify_mounted_hash()
            else:
                if sample_file:
                    raise ValueError("入口已关闭，不能执行外部样本读取验收。")
                verification.check_public_denials(self.route(item, False))
            self.log("只读检查通过；原生目录／权限仍须在后台人工复核，不能自动感知后台根目录变更。")
            return
        if action != "enable":
            raise ValueError("未知外部入口操作。")
        if not self.ui.confirm("已重新核对原生独立只读账号和目标目录，确认启用？"):
            return
        with self.locked():
            self.assert_record(item)
            instance, state = self.preflight(item["instance_dir"], item["domain"])
            self.assert_binding(item, instance)
            self.backup(state)
            item.update(phase="pending", revision=secrets.token_hex(16))
            self.save(item)
            try:
                self.revoke()
                self.auth_write((item["username"] + ":" + config.password_hash(secret) + "\n").encode())
                state.update(version=2)
                state.setdefault("external_webdav", {})[self.product.key] = self.route(item, True)
                self.manager.apply_shared_state_locked(state, domain=item["domain"],
                    verify=lambda: verification.check_public(route, secret, sample_file=sample_file))
                self.verify_mounted_hash()
                item["phase"] = "enabled"
                self.save(item)
            except BaseException:
                self.revoke()
                item["phase"] = "needs_repair"
                self.save(item)
                raise
        self.display(item)

    def install_runtime(self, source: Path, identity: dict, *, launcher: Path = Path("/usr/local/bin/tg2cloud-webdav")) -> None:
        """Install only reviewed host Python, never Bot deps or user configs."""
        from tg2cloud.addons.external_webdav.releases import host_files
        paths = host_files(source)
        checksum = hashlib.sha256()
        for relative in paths:
            checksum.update(relative.encode() + b"\0" + (source / relative).read_bytes())
        revision = checksum.hexdigest()
        destination = self.root / "runtime" / revision
        config.canonical(destination)
        if not destination.exists():
            staged = destination.with_name("stage-" + revision)
            if staged.exists():
                raise ValueError("存在未完成的运行代码候选；先人工核对，不覆盖。")
            staged.mkdir(parents=True, mode=0o700)
            for relative in paths:
                target = staged / relative
                target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                shutil.copyfile(source / relative, target)
                target.chmod(0o600)
            config.atomic(staged / "installation.json", (json.dumps(dict(identity, code_sha256=revision)) + "\n").encode())
            os.replace(staged, destination)
        actual = hashlib.sha256()
        for relative in paths:
            path = destination / relative
            config.canonical(path)
            if not path.is_file():
                raise ValueError("已有离线维护代码不完整，拒绝切换。")
            actual.update(relative.encode() + b"\0" + path.read_bytes())
        if actual.hexdigest() != revision:
            raise ValueError("已有离线维护代码摘要不匹配，拒绝覆盖或切换。")
        config.canonical(launcher)
        if launcher.exists() and not launcher.read_text().startswith("#!/bin/sh\n# TG2Cloud external_webdav managed\n"):
            raise ValueError("已有同名命令不属于 TG2Cloud，拒绝覆盖。")
        script = '#!/bin/sh\n# TG2Cloud external_webdav managed\nexec python3 -B ' + shlex.quote(str(destination / "scripts/run_source.py")) + ' webdav "$@"\n'
        config.atomic(launcher, script.encode(), mode=0o700)
        self.log("离线维护命令：tg2cloud-webdav；旧运行代码保留以便人工回退，不自动删除。")
