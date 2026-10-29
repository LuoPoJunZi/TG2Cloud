"""Optional host-only HTTPS for an identified direct-Compose instance.

The shared proxy manager remains the certificate and Nginx implementation.
This adapter supplies the Compose ownership boundary and a fail-closed registry.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import uuid
from pathlib import Path

from tg2cloud.compose import packaging, runtime
from tg2cloud.deployment import architecture, uninstall
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.maintenance import parse_compose_registry
from tg2cloud.deployment.proxy.manager import (
    PROXY_CERTBOT_CONTAINER,
    PROXY_NGINX_CONTAINER,
    PROXY_ROOT,
    DomainProxyManager,
    defer_interruptions,
)
from tg2cloud.deployment.proxy.rendering import (
    CERTBOT_IMAGE,
    NGINX_IMAGE,
    render_compose,
    render_route_conf,
)
from tg2cloud.deployment.proxy.state import (
    DomainRoute,
    certificate_domains,
    empty_state,
    normalize_state,
    validate_domain,
    validate_email,
)

OWNER = "tg2cloud.compose.https"
REGISTRY = "compose-instances.json"
JOURNAL = "compose-transaction.json"
COMPOSE = "com.docker.compose."
OVERRIDES = ("docker-compose.override.yml", "docker-compose.override.yaml", "compose.override.yml", "compose.override.yaml")
INSPECT = ('{"id":{{json .Id}},"name":{{json .Name}},"running":{{json .State.Running}},'
           '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
           '"network":{{json .HostConfig.NetworkMode}},"image":{{json .Config.Image}},'
           '"image_id":{{json .Image}},"ports":{{json .NetworkSettings.Ports}},'
           '"bindings":{{json .HostConfig.PortBindings}}}')


def physical_directory(path: Path) -> None:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink() or not path.is_dir():
        raise runtime.ComposeError("需要实际存在且不经过链接的绝对部署目录")
    info = path.stat()
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise runtime.ComposeError("部署目录必须归 root 所有，且不允许其他用户写入")


def owned_file(path: Path, *, private: bool = False) -> bytes:
    if path.is_symlink() or path.resolve() != path or not path.is_file():
        raise runtime.ComposeError("必要的归属文件缺失或经过链接；停止")
    info = path.stat()
    if (info.st_uid != 0 or info.st_nlink != 1 or info.st_size > 128 * 1024
            or (stat.S_IMODE(info.st_mode) != 0o600 if private else bool(info.st_mode & 0o022))):
        raise runtime.ComposeError("归属文件的所有者、权限或大小不安全；停止")
    return path.read_bytes()


def atomic_private(path: Path, value: dict) -> None:
    """Never follow an existing link or overwrite an unverified owner file."""
    physical_directory(path.parent)
    if path.exists() or path.is_symlink():
        owned_file(path, private=True)
    staged = path.with_name("." + path.name + "-" + uuid.uuid4().hex)
    content = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    runtime.write_exclusive(staged, content)
    try:
        os.replace(staged, path)
        descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if owned_file(path, private=True) != content:
            raise runtime.ComposeError("归属元数据写入结果不确定；停止并人工核对共享代理")
    finally:
        staged.unlink(missing_ok=True)


def container_snapshot(session) -> dict:
    code, output = session.run("docker ps -a --no-trunc --format '{{.ID}}'", timeout=20)
    ids = output.splitlines()
    if code or len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-f0-9]{64}", item) for item in ids):
        raise runtime.ComposeError("Docker 容器清单不可验证；停止")
    if not ids:
        return {}
    code, output = session.run("docker container inspect --format " + shlex.quote(INSPECT) + " " + " ".join(ids), timeout=30)
    try:
        items = [json.loads(line) for line in output.splitlines()]
        result = {}
        for item in items:
            name = item["name"].removeprefix("/")
            if item["id"] not in ids or name in result:
                raise ValueError
            result[name] = item
        if code or len(result) != len(ids) or {item["id"] for item in items} != set(ids):
            raise ValueError
        return result
    except (ValueError, KeyError, TypeError, AttributeError):
        raise runtime.ComposeError("Docker 身份读取失败；没有显示容器环境或原始输出") from None


def image_identity(session, item: dict, expected: str) -> None:
    if item.get("image") != expected:
        raise runtime.ComposeError("容器镜像与受管部署包不符；停止")
    code, output = session.run("docker image inspect --format '{{json .Id}}' " + shlex.quote(expected), timeout=20)
    try:
        image_id = json.loads(output)
        if code or not isinstance(image_id, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) or item.get("image_id") != image_id:
            raise ValueError
    except (ValueError, TypeError):
        raise runtime.ComposeError("容器实际镜像无法与固定镜像核对；停止") from None
    architecture.check_container(session, item["name"].removeprefix("/"))


class ComposeInstance:
    def __init__(self, root: Path, session, log, *, source: Path | None = None):
        self.root, self.session, self.log = root, session, log
        self.source = source or Path(__file__).resolve().parents[3]
        self.info: dict = {}
        self.config: dict = {}
        self.product = None

    def validate(self, *, loopback: bool = True, require_running: bool = True, allow_missing: bool = False) -> dict:
        physical_directory(self.root)
        self.info = runtime.metadata(self.root)
        self.product = PRODUCTS[self.info["edition"]]
        for name in ("docker-compose.yml", "compose-bundle.json", runtime.MARKER):
            owned_file(self.root / name)
        owned_file(self.root / ".env", private=True)
        self.config = runtime.saved_config(self.root, self.product.key)
        self.log.register(self.config)
        if any(self.config.get(key) for key in architecture.FORBIDDEN_ENV):
            raise runtime.ComposeError("实例配置含 Docker/Compose 覆盖；不会接管")
        if any((self.root / name).exists() or (self.root / name).is_symlink() for name in OVERRIDES):
            raise runtime.ComposeError("发现额外 Compose override；请先人工核对，不自动接管")
        image = self.info.get("image", "")
        if not isinstance(image, str) or not packaging.IMAGE.fullmatch(image) or not re.search(r"@sha256:[a-f0-9]{64}$", image):
            raise runtime.ComposeError("HTTPS 只接受部署包中固定 digest 的 Bot 镜像")
        expected = packaging.render(self.source, self.product.key, image)
        if (self.root / "docker-compose.yml").read_text(encoding="utf-8") != expected:
            raise runtime.ComposeError("基础 Compose 已修改或不属于当前部署包；停止")
        if loopback and self.config.get("TG2CLOUD_BIND_IP", "127.0.0.1") != "127.0.0.1":
            raise runtime.ComposeError("HTTPS 要求现有网关绑定 127.0.0.1；请先自行调整并重建网关，此工具不修改 .env 或重启业务")
        architecture.check_docker(self.session)
        containers = container_snapshot(self.session)
        project = None
        for name, service in ((self.product.storage_container, self.product.key), (self.product.bot_container, self.product.bot_service)):
            item = containers.get(name)
            if item is None:
                if allow_missing:
                    continue
                raise runtime.ComposeError("请先创建此部署包的 Bot 与网关容器；停止")
            uninstall.require_labels(item, {"com.tg2cloud.install-mode": "compose", COMPOSE + "service": service,
                COMPOSE + "project.working_dir": str(self.root), COMPOSE + "project.config_files": str(self.root / "docker-compose.yml")})
            candidate = (item.get("labels") or {}).get(COMPOSE + "project", "")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", candidate) or project is not None and project != candidate:
                raise runtime.ComposeError("Bot 与网关的 Compose 项目归属不一致")
            project = candidate
            if item.get("network") in {"host", "none", "container"} or str(item.get("network", "")).startswith("container:"):
                raise runtime.ComposeError("业务容器网络不属于当前基础 Compose")
            mounts = {"/" + child: str(self.root / child) for child in ("data", "downloads", "logs", "config")}
            reference = image
            if service == self.product.key:
                mounts = ({"/opt/openlist/data": str(self.root / "openlist/data")} if self.product.is_openlist else
                          {"/Config": str(self.root / "clouddrive/config"), "/CloudNAS": str(self.root / "clouddrive/mounts")})
                source = self.source / "packaging/compose" / ("docker-compose." + self.product.key + ".yml")
                reference = re.findall(r"(?m)^    image: ([^\s]+)$", source.read_text(encoding="utf-8"))[0]
                if require_running and item.get("running") is not True:
                    raise runtime.ComposeError("网关必须运行，且本机管理端口可用；停止")
                port = str(self.product.management_port)
                # Stopped Docker containers can have empty runtime Ports, but
                # their persistent HostConfig bindings still prove isolation.
                for key in (("ports", "bindings") if item.get("running") is True else ("bindings",)):
                    values = item.get(key)
                    expected_bind = [{"HostIp": "127.0.0.1", "HostPort": port}]
                    if not isinstance(values, dict) or values.get(port + "/tcp") != expected_bind or any(value for name, value in values.items() if name != port + "/tcp"):
                        raise runtime.ComposeError("网关管理端口不是唯一的回环发布；停止")
            if uninstall.bind_map(item) != mounts:
                raise runtime.ComposeError("容器挂载源与此部署目录不一致；停止")
            for source in mounts.values():
                physical = Path(source)
                if physical.resolve() != physical or physical.is_symlink() or not physical.is_dir():
                    raise runtime.ComposeError("业务挂载目录经过链接或不存在；停止")
            image_identity(self.session, item, reference)
        return containers


class ComposeProxyManager(DomainProxyManager):
    def __init__(self, instance: ComposeInstance, ui):
        from tg2cloud.cli.terminal import confirm_nat_public_ipv4
        super().__init__(instance.session, instance.product, {"vps_host": "127.0.0.1"}, instance.log,
                         confirm_public_ipv4=lambda domain, environment: confirm_nat_public_ipv4(ui, domain, environment, instance.log))
        self.instance = instance
        self.registry: dict | None = None
        self.uncertain = False

    @property
    def proxy_root(self):
        return Path(PROXY_ROOT)

    def read_state(self):
        root = self.proxy_root
        if not root.exists():
            state = empty_state()
        else:
            physical_directory(root)
            for name in (".env", *OVERRIDES):
                if (root / name).exists() or (root / name).is_symlink():
                    raise runtime.ComposeError("共享代理含额外环境或 override 文件；停止，不修改未知配置")
            lock = root / "transaction.lock"
            if lock.exists() or lock.is_symlink():
                owned_file(lock, private=True)
            for name in ("state", "nginx", "nginx/conf.d", "nginx/conf.d.next", "nginx/conf.d.previous", "certbot",
                         "certbot/www", "certbot/letsencrypt", "certbot/lib", "certbot/log", "certbot/status", "external-auth"):
                path = root / name
                if path.exists() or path.is_symlink():
                    physical_directory(path)
            source = root / "state/domains.json"
            if source.exists() or source.is_symlink():
                physical_directory(source.parent)
                state = normalize_state(owned_file(source, private=True))
            elif {child.name for child in root.iterdir()} - {"transaction.lock"}:
                raise runtime.ComposeError("共享代理有文件但缺少 domains.json；停止，不覆盖未知路由")
            else:
                state = empty_state()
        if state["version"] not in {1, 2}:
            raise runtime.ComposeError("共享代理使用外部入口或未知模式；Compose HTTPS 仅管理自身 Nginx，外部入口请导出配置")
        self._entry_state = state
        return state

    def validate_shared(self, state, containers):
        root = self.proxy_root
        if (root / "state" / JOURNAL).exists() or (root / "state" / JOURNAL).is_symlink():
            raise runtime.ComposeError("上次共享状态／Compose 归属提交未确认；已停止，须人工核对 compose-transaction.json、domains.json 和 compose-instances.json")
        registry_path = root / "state" / REGISTRY
        registry = {"format": 1, "owner": OWNER, "instances": {}}
        if registry_path.exists() or registry_path.is_symlink():
            registry = parse_compose_registry(owned_file(registry_path, private=True), physical=True)
        for edition, item in registry["instances"].items():
            if item["domain"] != state["domains"].get(edition, {}).get("domain"):
                raise runtime.ComposeError("共享路由与 Compose 归属清单不一致；停止")
        current = registry["instances"].get(self.product.key)
        if current and current["root"] != str(self.instance.root):
            raise runtime.ComposeError("该 Edition 的共享路由属于另一 Compose 部署目录；不会接管")
        if self.product.key in state["domains"] and not current:
            raise runtime.ComposeError("该 Edition 已有未登记给此 Compose 实例的路由；不会替换脚本或未知归属")
        compose = root / "docker-compose.yml"
        if compose.exists() or compose.is_symlink():
            expected = render_compose(certificate_domains(state), external_auth=state["version"] == 2)
            if owned_file(compose).decode("utf-8") != expected:
                raise runtime.ComposeError("共享代理 Compose 不符合已有路由状态；停止，不覆盖外部修改")
        conf_dir = root / "nginx/conf.d"
        if conf_dir.exists():
            expected_names = {"00-default.conf"} | {"20-" + edition + ".conf" for edition in state["domains"]}
            expected_names |= {"30-external-webdav-" + edition + ".conf" for edition in state.get("external_webdav", {})}
            if any(child.name not in expected_names or child.is_symlink() or not child.is_file() for child in conf_dir.iterdir()):
                raise runtime.ComposeError("共享 Nginx 包含未登记站点或链接；停止，不覆盖其他路由")
        for name, item in containers.items():
            labels = item.get("labels") or {}
            if (name in {PROXY_NGINX_CONTAINER, PROXY_CERTBOT_CONTAINER}
                    or labels.get(COMPOSE + "project") == "tg2cloud-proxy"
                    or labels.get("com.tg2cloud.role") in {"reverse-proxy", "certificate-manager"}):
                if not (root / "state/domains.json").is_file():
                    raise runtime.ComposeError("已有共享代理容器但缺少状态；不会接管")
                uninstall.proxy_identity(name, item, state=state)
                image_identity(self.session, item, NGINX_IMAGE if name == PROXY_NGINX_CONTAINER else CERTBOT_IMAGE)
        self.registry = registry
        return registry

    def guard(self, *, require_running=True, allow_missing=False):
        containers = self.instance.validate(require_running=require_running, allow_missing=allow_missing)
        state = self.read_state()
        registry = self.validate_shared(state, containers)
        if (allow_missing and any(name not in containers for name in
                (self.product.storage_container, self.product.bot_container))
                and self.product.key not in registry["instances"]):
            raise runtime.ComposeError("业务容器缺失且没有此部署目录的 HTTPS 登记；不会接管未知实例")
        return state

    def _check_compose_owner(self, state):
        # The generic manager refuses Compose-owned routes. This adapter has
        # already revalidated the instance under its operation/shared locks;
        # re-read the strict registry against the exact state being committed.
        self.validate_shared(state, container_snapshot(self.session))

    def _configure_locked(self, domain, email):
        self.guard()
        return super()._configure_locked(domain, email)

    def _remove_locked(self):
        self.guard(require_running=False, allow_missing=True)
        # Removal changes runtime and ownership together. Honor ordinary
        # INT/TERM only after the bounded shared operation has committed or
        # rolled back, including when the business containers are already down.
        with defer_interruptions():
            return super()._remove_locked()

    def configure(self, domain, email):
        self.guard()  # Validate the path before the shared lock command opens it.
        return super().configure(domain, email)

    def remove(self):
        self.guard(require_running=False, allow_missing=True)
        return super().remove()

    def _commit_state(self, state):
        """Fence two independent atomic files; an interrupted pair needs review."""
        if self.registry is None:
            raise runtime.ComposeError("尚未验证共享归属；拒绝提交")
        root = self.proxy_root
        if not root.exists():
            root.mkdir(mode=0o700)
        state_dir = root / "state"
        if not state_dir.exists():
            state_dir.mkdir(mode=0o700)
        physical_directory(state_dir)
        registry = json.loads(json.dumps(self.registry))
        item = state["domains"].get(self.product.key)
        if item:
            registry["instances"][self.product.key] = {"root": str(self.instance.root), "domain": item["domain"]}
        else:
            registry["instances"].pop(self.product.key, None)
        journal = state_dir / JOURNAL
        if journal.exists() or journal.is_symlink():
            raise runtime.ComposeError("共享归属提交尚未确认；停止")
        self.uncertain = True
        try:
            with defer_interruptions():
                atomic_private(journal, {"format": 1, "owner": OWNER, "root": str(self.instance.root),
                                         "edition": self.product.key, "target": state, "registry": registry})
                super()._commit_state(state)
                if normalize_state(owned_file(state_dir / "domains.json", private=True)) != state:
                    raise runtime.ComposeError("共享路由状态提交无法读回复验；停止")
                atomic_private(state_dir / REGISTRY, registry)
                journal.unlink()
                self.registry = registry
                self.uncertain = False
        except (Exception, KeyboardInterrupt) as exc:
            raise runtime.ComposeError("共享状态／Compose 归属提交结果不确定；已保留事务标记，请人工核对三个状态文件后再操作；未删除业务数据") from exc

    def inspect_status(self):
        # A read does not acquire the creating shared lock or initialize state.
        state = self.guard(require_running=False, allow_missing=True)
        return super().status(state)

    def _maintenance(self, action):
        # The common operation takes the shared lock. Recheck its state read
        # under that same lock without nesting either lock implementation.
        allow_stopped = action == "backup"
        self.guard(require_running=not allow_stopped, allow_missing=allow_stopped)
        original = self.read_state
        def guarded_read():
            containers = self.instance.validate(require_running=not allow_stopped, allow_missing=allow_stopped)
            state = original()
            self.validate_shared(state, containers)
            return state
        self.read_state = guarded_read
        try:
            return super().maintenance(action)
        finally:
            self.read_state = original

    def renewal_dry_run(self):
        return self._maintenance("renew_dry_run")

    def proxy_backup(self):
        return self._maintenance("backup")


def certificate_path(value: str) -> str:
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", value) or any(part in {".", ".."} for part in value.split("/")):
        raise runtime.ComposeError("证书路径须为绝对路径，且不能包含空格、父目录或配置字符")
    return value


def export_existing(instance, ui, *, domain=""):
    # Export has no managed-proxy effects and remains available when that proxy
    # uses schema 3, or when another project owns 80/443. Its upstream must still
    # be the fully identified, running, loopback-only Compose gateway.
    instance.validate()
    domain = validate_domain(domain or ui.ask("现有代理管理域名", validate=validate_domain))
    certificate = ui.ask("现有代理可读取的 fullchain.pem 绝对路径", validate=certificate_path)
    key = ui.ask("现有代理可读取的 privkey.pem 绝对路径", validate=certificate_path)
    content = render_route_conf(DomainRoute(instance.product.key, domain, instance.product.management_port))
    content = content.replace("/etc/letsencrypt/live/" + domain + "/fullchain.pem", certificate)
    content = content.replace("/etc/letsencrypt/live/" + domain + "/privkey.pem", key)
    content = ("# TG2Cloud host Nginx candidate: include inside http {}; define the\n"
               "# $connection_upgrade map from the accompanying instructions.\n" + content)
    instance.log("仅导出候选配置；不会签发证书、修改现有代理或声明 HTTPS 已启用。")
    if not ui.confirm("确认在此部署目录生成候选文件，稍后自行审阅并应用"):
        return None
    target = instance.root / ("nginx-" + instance.product.key + "-" + uuid.uuid4().hex[:12] + ".conf")
    runtime.write_exclusive(target, content.encode())
    instance.log("候选配置：" + str(target))
    instance.log("宿主 Nginx：在 http {} 中定义 map $http_upgrade $connection_upgrade { default upgrade; '' close; }，确认已有证书覆盖域名，审阅候选并执行 nginx -t 后自行 reload。证书续期仍由现有代理负责。")
    instance.log("容器代理：127.0.0.1 指向代理容器自身；仅 host 网络可直接使用此候选。bridge 网络需自行配置并验证可达的宿主地址／网络和证书挂载后调整 proxy_pass；不要开放网关公网端口或挂载 Docker Socket。")
    return target


def configure(instance, manager, ui):
    from tg2cloud.compose.access import ACCESS_FILE, choose_access, read_access
    current = read_access(instance.root, instance.product.key)
    plan = choose_access(ui, instance.product.key, current=current)
    if plan["mode"] == "local":
        instance.log("此次未配置 HTTPS；已有 HTTPS 路由保持原状，需要关闭时请选择“移除本 Edition 路由”。")
        return
    if plan["mode"] == "external":
        if export_existing(instance, ui, domain=plan["domain"]) is not None:
            atomic_private(instance.root / ACCESS_FILE, plan)
        return
    domain, email = validate_domain(plan["domain"]), validate_email(plan["email"])
    manager.guard()
    environment = manager.confirm_nat(domain, manager.probe(domain))
    manager._validate_environment(environment)
    instance.log("将配置共享 Nginx + Certbot：" + domain + "；仅变更此 Edition 路由，保留其他域名和证书。")
    if ui.confirm("确认公开此管理页域名并申请 Let's Encrypt 证书"):
        instance.log(manager.configure(domain, email).message)
        atomic_private(instance.root / ACCESS_FILE, plan)


def run_action(action, instance, manager, ui):
    if action == "configure":
        configure(instance, manager, ui)
    elif action in {"status", "check"}:
        report = manager.inspect_status()
        instance.log(report.message)
        for label, result in report.statuses:
            instance.log(label + "：" + result)
        if report.state not in {"healthy", "not_configured"}:
            raise runtime.ComposeError("HTTPS 运行检查未通过；请核对上述结果")
    elif action == "renewal-dry-run":
        if ui.confirm("确认执行此 Edition 的续期 dry-run（不会替换正式证书）"):
            instance.log(manager.renewal_dry_run())
    elif action == "proxy-backup":
        if ui.confirm("确认创建共享代理私密备份（包含证书私钥，仅保存在宿主机）"):
            instance.log(manager.proxy_backup())
    elif action == "remove":
        if ui.confirm("确认仅移除此 Edition 的管理域名路由；保留证书及全部业务数据"):
            instance.log(manager.remove().message)
    elif action == "export-existing":
        export_existing(instance, ui)


def main(argv=None, *, session=None, ui=None, log=None):
    parser = argparse.ArgumentParser(description="TG2Cloud Compose 可选宿主 HTTPS 向导（待发布；不接管业务容器）")
    parser.add_argument("action", nargs="?", choices=("configure", "status", "check", "renewal-dry-run", "remove", "export-existing", "proxy-backup"))
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="实际 Compose 部署目录的绝对路径")
    args = parser.parse_args(argv)
    log = log or SafeLog()
    owned_ui = False
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise runtime.ComposeError("请在 Linux 宿主机以 root 运行 HTTPS 向导；不要在 setup 容器内运行")
        architecture.check_environment()
        physical_directory(args.root)
        session = session or LocalSession(log)
        if ui is None and args.action not in {"status", "check"}:
            from tg2cloud.cli.terminal import Terminal
            ui = Terminal()
            ui.friendly = True
            owned_ui = True
        with runtime.operation_lock(args.root):
            instance = ComposeInstance(args.root, session, log)
            instance.validate(require_running=False, allow_missing=True)
            manager = ComposeProxyManager(instance, ui)
            manager.prepare()
            # Managed actions guard shared state themselves (and recheck under
            # its lock). Candidate-only export must not be blocked by a shared
            # proxy mode which this tool intentionally will not modify.
            if args.action:
                run_action(args.action, instance, manager, ui)
            else:
                while True:
                    log("\n── Compose HTTPS 管理 ──")
                    log(instance.product.display_name + " · v" + instance.info["version"])
                    for line in ("1. 配置 HTTPS", "2. 查看运行状态", "3. 证书续期演练", "4. 移除当前入口",
                                 "5. 导出反代配置", "6. 备份共享代理", "0. 退出"):
                        log(line)
                    choice = ui.ask("选择操作", default="0", validate=lambda value: runtime.checked(r"[0-6]", value))
                    if choice == "0":
                        break
                    run_action({"1": "configure", "2": "status", "3": "renewal-dry-run", "4": "remove", "5": "export-existing", "6": "proxy-backup"}[choice], instance, manager, ui)
        return 0
    except (runtime.ComposeError, uninstall.UninstallError) as exc:
        log("操作未完成：" + str(exc))
        return 1
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - raw Docker output and config errors stay private
        log("HTTPS 操作未完成；请核对本机依赖、固定版本部署包、容器归属和共享代理状态。未输出凭据；未删除业务数据。")
        return 1
    finally:
        if owned_ui:
            ui.close()


if __name__ == "__main__":
    raise SystemExit(main())
