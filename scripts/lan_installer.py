"""Optional LAN-only entry. Never imported by the EXEs or the VPS wizard."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shlex
import shutil
import signal
import socket
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from deployer_products import PRODUCTS, ProductProfile
from domain_proxy import NGINX_IMAGE
from scripts import vps_installer as vps
from scripts.vps_runtime import LocalSession, SafeLog, edition_lock

LAN_ROOT = Path("/opt/tg2cloud-lan")
HTTPS_STATE = Path("/opt/tg2cloud-proxy/state/domains.json")
RFC1918 = tuple(ipaddress.IPv4Network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
FILES = {"state.json", "compose.json", "nginx.conf"}
# This is an isolated container tmpfs, not a predictable host temporary file.
CONTAINER_TMP = "/tmp"  # nosec B108
TMPFS_FLAGS = "rw,noexec,nosuid,mode=1777,size=64m"


def validate_ip(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("内网地址必须是标准 IPv4 文本")  # noqa: TRY004 - invalid external config, not an API type contract
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError("请输入标准内网 IPv4 地址，不接受域名、URL 或端口") from exc
    if str(address) != value or not any(address in network for network in RFC1918):
        raise ValueError("只接受 RFC1918 内网 IPv4，不接受公网、回环或通配地址")
    return value


def validate_local_ip(value: str, session: LocalSession) -> str:
    value = validate_ip(value)
    code, output = session.run("ip -j -4 address show", timeout=15)
    if code:
        raise ValueError("无法读取本机网卡；需要 iproute2，不会猜测内网地址")
    for interface in json.loads(output):
        name = interface.get("ifname", "")
        if name == "lo" or name.startswith(("docker", "br-", "veth")) or "UP" not in interface.get("flags", []):
            continue
        for item in interface.get("addr_info", []):
            if item.get("family") != "inet" or item.get("local") != value:
                continue
            network = ipaddress.IPv4Network(f"{value}/{item['prefixlen']}", strict=False)
            address = ipaddress.IPv4Address(value)
            if network.prefixlen < 31 and address in {network.network_address, network.broadcast_address}:
                continue
            return value
    raise ValueError("该地址不属于本机已启用的内网网卡；虚拟机请填虚拟机地址，不填 NAS 宿主机地址")


def validate_environment(session: LocalSession) -> None:
    vps.validate_host()
    # Do not install onto a remote daemon, or inherit arbitrary Compose inputs.
    forbidden = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",
                 "COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES", "COMPOSE_ENV_FILES")
    if any(os.environ.get(name) for name in forbidden):
        raise ValueError("请使用本机默认 Docker/Compose 环境；不接受远端 daemon 或外部 Compose 覆盖")
    code, _ = session.run("command -v ip >/dev/null 2>&1", timeout=10)
    if code:
        raise ValueError("缺少 iproute2；请先人工安装，不在信息收集前安装软件")
    available, _ = session.run("command -v docker >/dev/null 2>&1", timeout=10)
    if available:
        return
    code, output = session.run("docker context inspect --format '{{json .Endpoints.docker.Host}}'", timeout=15)
    if code or json.loads(output) != "unix:///var/run/docker.sock":
        raise ValueError("首版仅支持本机默认 rootful Docker，不接管自定义/远端 Docker context")
    template = '{"version":{{json .ServerVersion}},"security":{{json .SecurityOptions}}}'
    code, output = session.run("docker info --format " + shlex.quote(template), timeout=15)
    if code:
        raise ValueError("Docker 不可用或为 rootless；内网入口需要 Linux rootful host 网络")
    info = json.loads(output)
    if any("rootless" in item for item in info.get("security", [])):
        raise ValueError("Docker 不可用或为 rootless；内网入口需要 Linux rootful host 网络")
    version = info.get("version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+].*)?", version) or int(version.split(".")[0]) < 28:
        raise ValueError("内网模式要求 Docker Engine 28+，避免旧版回环端口被同网段直接访问；请人工升级，不重启其他容器")


def private_directory(path: Path) -> None:
    if path.is_symlink() or path.resolve() != path or not path.is_dir():
        raise ValueError("内网状态目录缺失或经过链接")
    info = path.stat()
    if os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o077):
        raise ValueError("内网状态目录必须归 root 所有且权限为 700")


def container_name(product: ProductProfile) -> str:
    # The stable CD2 discovery helper matches any name containing clouddrive2.
    # Do not let this Nginx be mistaken for a second CloudDrive2 gateway.
    return "tg2cloud-lan-" + ("openlist" if product.is_openlist else "cd2")


def state_for(product: ProductProfile, address: str) -> dict:
    return {"schema": 1, "mode": "lan", "edition": product.key, "bind_ip": validate_ip(address),
            "install_dir": product.install_dir, "proxy_image": NGINX_IMAGE}


def render_files(product: ProductProfile, address: str) -> dict[str, str]:
    state = state_for(product, address)
    port = product.management_port
    directory = LAN_ROOT / product.key
    compose = {"services": {"lan": {
        "image": NGINX_IMAGE, "container_name": container_name(product), "network_mode": "host",
        "user": "101:101", "entrypoint": ["nginx"], "command": ["-g", "daemon off;"],
        "restart": "unless-stopped", "read_only": True, "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"], "tmpfs": [CONTAINER_TMP + ":" + TMPFS_FLAGS],
        "labels": {"com.tg2cloud.managed": "true", "com.tg2cloud.role": "lan-management",
                   "com.tg2cloud.edition": product.key},
        "volumes": [{"type": "bind", "source": str(directory / "nginx.conf"),
                     "target": "/etc/nginx/nginx.conf", "read_only": True}],
    }}}
    nginx = f"""worker_processes auto;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events {{ worker_connections 1024; }}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log off;
    server_tokens off;
    client_max_body_size 16m;
    client_body_temp_path /tmp/client_body;
    proxy_temp_path /tmp/proxy;
    fastcgi_temp_path /tmp/fastcgi;
    uwsgi_temp_path /tmp/uwsgi;
    scgi_temp_path /tmp/scgi;
    map $http_upgrade $connection_upgrade {{ default upgrade; '' close; }}
    server {{
        listen {address}:{port};
        server_name {address};
        add_header X-TG2Cloud-LAN {product.key} always;
        if ($host != '{address}') {{ return 403; }}
        location ~* ^/dav(?:/|$) {{ return 403; }}
        location / {{
            proxy_pass http://127.0.0.1:{port};
            proxy_http_version 1.1;
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto http;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 300s;
        }}
    }}
}}
"""
    return {"state.json": json.dumps(state, sort_keys=True) + "\n",
            "compose.json": json.dumps(compose, indent=2) + "\n", "nginx.conf": nginx}


def load_state(product: ProductProfile) -> dict | None:
    directory = LAN_ROOT / product.key
    if not LAN_ROOT.exists() and not LAN_ROOT.is_symlink():
        return None
    private_directory(LAN_ROOT)
    if not directory.exists() and not directory.is_symlink():
        return None
    private_directory(directory)
    if {path.name for path in directory.iterdir()} != FILES:
        raise ValueError("内网入口文件不完整或含额外文件；停止，不自动清理")
    state = json.loads(vps.regular_private(directory / "state.json"))
    if not isinstance(state, dict) or state != state_for(product, state.get("bind_ip", "")) or type(state.get("schema")) is not int:
        raise ValueError("内网模式记录无效；不接管其他实例或改变安装模式")
    for name, expected in render_files(product, state["bind_ip"]).items():
        path = directory / name
        if path.is_symlink() or path.resolve() != path or not path.is_file():
            raise ValueError("内网入口文件经过链接或缺失")
        info = path.stat()
        if info.st_size > 128 * 1024 or (os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o022)):
            raise ValueError("内网入口文件权限/大小不安全")
        if path.read_text(encoding="utf-8") != expected:
            raise ValueError("内网入口配置被修改；停止，不覆盖手改配置")
    return state


def save_state(product: ProductProfile, address: str) -> None:
    if LAN_ROOT.exists() or LAN_ROOT.is_symlink():
        private_directory(LAN_ROOT)
    else:
        LAN_ROOT.mkdir(mode=0o700)
        private_directory(LAN_ROOT)
    directory = LAN_ROOT / product.key
    if directory.exists() or directory.is_symlink():
        existing = load_state(product)
        if existing != state_for(product, address):
            raise ValueError("不隐式切换内网地址")
        return
    staged = Path(tempfile.mkdtemp(prefix=".stage-" + product.key + "-", dir=LAN_ROOT))
    try:
        for name, text in render_files(product, address).items():
            path = staged / name
            with path.open("x", encoding="utf-8", newline="\n") as writer:
                path.chmod(0o644 if name == "nginx.conf" else 0o600)
                writer.write(text)
                writer.flush()
                os.fsync(writer.fileno())
        os.rename(staged, directory)
    finally:
        if staged.exists():
            # Only our mkdtemp staging tree, never a user installation.
            shutil.rmtree(staged)


def reject_https_route(product: ProductProfile) -> None:
    path = HTTPS_STATE
    if not path.exists() and not path.is_symlink():
        return
    state = json.loads(vps.regular_private(path))
    if not isinstance(state, dict) or not isinstance(state.get("domains"), dict):
        raise ValueError("既有 HTTPS 状态无法核对，不改变访问模式")  # noqa: TRY004 - invalid persisted state
    if product.key in state["domains"]:
        raise ValueError("该 Edition 已配置 HTTPS；内网脚本不转换、不移除已有域名路由")


def inspect_lan(product: ProductProfile, session: LocalSession, inventory: set[str]) -> dict | None:
    name = container_name(product)
    if name not in inventory:
        return None
    template = ('{"image":{{json .Config.Image}},"running":{{json .State.Running}},'
                '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
                '"network":{{json .HostConfig.NetworkMode}},"readonly":{{json .HostConfig.ReadonlyRootfs}},'
                '"privileged":{{json .HostConfig.Privileged}},"user":{{json .Config.User}},'
                '"cap_add":{{json .HostConfig.CapAdd}},"cap_drop":{{json .HostConfig.CapDrop}},'
                '"security":{{json .HostConfig.SecurityOpt}},"tmpfs":{{json .HostConfig.Tmpfs}},'
                '"entrypoint":{{json .Config.Entrypoint}},"command":{{json .Config.Cmd}}}')
    code, output = session.run("docker container inspect --format " + shlex.quote(template) + " " + name, timeout=15)
    if code:
        raise ValueError("无法核对内网入口容器，不接管同名容器")
    item = json.loads(output)
    labels = item.get("labels") or {}
    required = {"com.tg2cloud.managed": "true", "com.tg2cloud.role": "lan-management",
                "com.tg2cloud.edition": product.key, "com.docker.compose.project": name,
                "com.docker.compose.service": "lan", "com.docker.compose.project.working_dir": str(LAN_ROOT / product.key),
                "com.docker.compose.project.config_files": str(LAN_ROOT / product.key / "compose.json")}
    mount = [{"Type": value.get("Type"), "Source": value.get("Source"),
              "Destination": value.get("Destination"), "RW": value.get("RW")}
             for value in item.get("mounts", []) if value.get("Destination") != CONTAINER_TMP]
    expected_mount = [{"Type": "bind", "Source": str(LAN_ROOT / product.key / "nginx.conf"),
                       "Destination": "/etc/nginx/nginx.conf", "RW": False}]
    if (any(labels.get(key) != value for key, value in required.items())
            or item.get("image") != NGINX_IMAGE or item.get("network") != "host"
            or item.get("readonly") is not True or item.get("privileged") is not False
            or item.get("cap_add") or item.get("cap_drop") != ["ALL"]
            or item.get("security") not in (["no-new-privileges:true"], ["no-new-privileges"])
            or item.get("tmpfs") != {CONTAINER_TMP: TMPFS_FLAGS}
            or item.get("user") != "101:101" or item.get("entrypoint") != ["nginx"]
            or item.get("command") != ["-g", "daemon off;"] or mount != expected_mount):
        raise ValueError("同名内网入口归属或运行配置不符，停止，不接管")
    return item


def check_port(product: ProductProfile, address: str, running: bool) -> None:
    if running:
        return  # Owned, canonical container is validated separately.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((address, product.management_port))
        except OSError as exc:
            raise ValueError("指定内网地址/固定管理端口不可绑定；请核对占用，不会停止外部服务或更换端口") from exc


def check_published_ports(product: ProductProfile, session: LocalSession, inventory: set[str]) -> None:
    if not inventory:
        return
    # NAT-only publications may not appear as listening sockets. Match the
    # original installer's container port ownership gate before secret input.
    code, output = session.run("docker ps --format '{{.Names}}|{{.Ports}}'", timeout=15)
    if code:
        raise ValueError("无法核对 Docker 固定端口占用，不跳过冲突检查")
    pattern = re.compile(r":" + str(product.management_port) + r"->")
    for line in output.splitlines():
        name, _, ports = line.partition("|")
        if pattern.search(ports) and name != product.storage_container:
            raise ValueError("固定管理端口已由其他容器发布；请人工核对，不自动停用或换端口")


def check_backend(instance: vps.Instance, session: LocalSession, log: SafeLog) -> None:
    code, output = session.run("docker inspect --format '{{json .HostConfig.PortBindings}}' " + instance.product.storage_container, timeout=15)
    if code:
        raise ValueError("无法核对网关回环监听")
    bindings = {key: value for key, value in (json.loads(output) or {}).items() if value}
    port = str(instance.product.management_port)
    if bindings != {port + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]}:
        raise ValueError("网关不再仅发布预期回环端口；停止，不把异常实例降级为内网安装")
    directory = shlex.quote(str(instance.directory))
    code, output = session.run("cd " + directory + " && INSTALL_DIR=" + directory + " bash ./manage.sh ready", stream=log, timeout=90)
    if code:
        raise ValueError("Bot/网关基础检查未通过；不冒充部署成功，不自动重装")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def request_status(product: ProductProfile, address: str, path: str, method: str = "GET") -> tuple[int, str]:
    url = f"http://{validate_ip(address)}:{product.management_port}{path}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, method=method)
    try:
        # URL scheme and literal RFC1918 address are validated above.
        response = opener.open(request, timeout=5)  # nosec B310
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.code, response.headers.get("X-TG2Cloud-LAN", "")


def check_entry(product: ProductProfile, address: str) -> None:
    for path, method in (("/", "GET"), ("/dav", "GET"), ("/dav/", "PROPFIND"), ("/DAV/", "PROPFIND")):
        code, marker = request_status(product, address, path, method)
        expected = 200 <= code < 400 if path == "/" else code == 403
        if marker != product.key or not expected:
            raise ValueError("内网管理页或 /dav 阻断未通过；不冒充部署成功")


def wait_for_entry(product: ProductProfile, address: str) -> None:
    # Nginx can still be starting just after compose up; bounded local probes
    # only, never retrying WebDAV writes or rebuilding the Bot.
    deadline = time.monotonic() + 20
    while True:
        try:
            check_entry(product, address)
            return
        except (ValueError, OSError):
            if time.monotonic() >= deadline:
                raise RuntimeError("内网入口启动后的管理页或 /dav 阻断检查未通过；数据保留，请核对日志") from None
            time.sleep(0.5)


def compose_command(product: ProductProfile, arguments: str) -> str:
    directory = shlex.quote(str(LAN_ROOT / product.key))
    return "cd " + directory + " && docker compose -p " + container_name(product) + " -f compose.json " + arguments


@dataclass
class Plan:
    instance: vps.Instance
    action: str
    address: str
    saved: dict | None
    config: dict[str, str] = field(default_factory=dict, repr=False)
    entry_running: bool = False
    entry_healthy: bool = False


def make_plan(instance, release, source, baseline, session, log, ui=None, *, address="") -> Plan:
    product = instance.product
    reject_https_route(product)
    saved = load_state(product)
    if instance.present:
        if saved is None:
            raise ValueError("已有实例不是本内网脚本创建；不转换 VPS/HTTPS 或接管已有网关")
        if baseline is None:
            raise ValueError("缺少原版本正式源码基线")
        vps.assert_unmodified(instance, baseline)
    action = vps.action_for(instance, release)
    if action in {"install", "upgrade"}:
        vps.payload_sources(source, product)
        vps.check_foreign_gateway(product, session)
        if action == "upgrade" and vps.gateway_image(source, product) != instance.gateway_image:
            raise ValueError("云网关镜像变化需要人工迁移验收；不自动升级数据库")
    if saved:
        if address and address != saved["bind_ip"]:
            raise ValueError("不隐式切换已保存的内网地址")
        address = saved["bind_ip"]
    elif not address:
        if ui is None:
            raise ValueError("首次只读预检请显式提供 --lan-ip；不会自动猜测地址")
        address = ui.ask("运行脚本的 Linux 内网 IPv4（虚拟机填虚拟机地址）", validate=validate_ip)
    address = validate_local_ip(address, session)
    inventory = vps.docker_inventory(session)
    check_published_ports(product, session, inventory)
    entry = inspect_lan(product, session, inventory)
    if entry and saved is None:
        raise ValueError("同名内网容器存在但缺少受管记录；不接管")
    if entry and not instance.present:
        raise ValueError("只有内网入口、缺少完整 Bot/网关；停止，不重装")
    running = bool(entry and entry.get("running"))
    check_port(product, address, running)
    if not instance.present:
        # The original installer checks the fixed port across all listeners.
        # Detect a loopback conflict before collecting any credentials.
        check_port(product, "127.0.0.1", False)
    plan = Plan(instance, action, address, saved, dict(instance.config), running)
    if instance.present:
        check_backend(instance, session, log)
    if running:
        try:
            check_entry(product, address)
            plan.entry_healthy = True
        except (ValueError, OSError):
            log("已有内网入口检查未通过；预览后需确认才尝试恢复入口，不重装 Bot。")
    if action == "install" and ui is not None:
        plan.config = vps.collect_config(ui, product)
        log.register(plan.config)
    if action in {"install", "upgrade"}:
        vps.resource_check(instance, plan.config, session, log)
    return plan


def preview(plan: Plan, release: vps.Release, log: SafeLog) -> None:
    labels = {"install": "首次安装", "upgrade": "保留配置升级", "current": "已是最新，不重建 Bot", "newer": "高于 latest，不降级"}
    log(f"{plan.instance.product.display_name}：{labels[plan.action]}；{plan.instance.version or '未安装'} → {release.version}")
    log("内网 HTTP 管理地址：" + f"http://{plan.address}:{plan.instance.product.management_port}")
    log("安装目录：" + str(plan.instance.directory))
    log("不申请证书、不操作共享 HTTPS、不占用 80/443；HTTP 不加密，请勿端口转发到公网。")
    if plan.instance.present:
        log("内网入口：" + ("本机检查通过" if plan.entry_healthy else "未就绪，需要确认后恢复；不会仅凭预检标记为可用"))
    if plan.action in {"install", "upgrade"}:
        log("复用正式安装器的 APT/Docker 依赖与备份/有限回退；可能更新系统软件包，所选 Bot 可能短暂停止。")
    log("已有 .env、Session、SQLite、下载和网关数据保留；不改另一 Edition，不接管第三方服务。")


def execute(plan: Plan, release, source, baseline, session, log, ui, *, verify=False) -> None:
    instance = plan.instance
    product = instance.product
    with edition_lock(Path("/opt/tg2cloud-cli-locks") / (product.key + ".lock")):
        current = vps.discover(product, vps.docker_inventory(session), session, log, install_dir=product.install_dir)
        if (current.present != instance.present or current.raw_config != instance.raw_config
                or current.version != instance.version or current.gateway_image != instance.gateway_image):
            raise ValueError("确认前后实例发生变化；停止，重新预检")
        if load_state(product) != plan.saved:
            raise ValueError("确认前后内网配置发生变化；停止")
        reject_https_route(product)
        validate_local_ip(plan.address, session)
        inventory = vps.docker_inventory(session)
        check_published_ports(product, session, inventory)
        entry = inspect_lan(product, session, inventory)
        check_port(product, plan.address, bool(entry and entry.get("running")))
        if current.present:
            vps.assert_unmodified(current, baseline)
            check_backend(current, session, log)
        else:
            check_port(product, "127.0.0.1", False)
        vps.check_foreign_gateway(product, session)
        # Persist the explicit intent before base installation. If base succeeds
        # but Nginx fails, rerunning resumes the LAN entry, not a fresh reinstall.
        save_state(product, plan.address)
        vps.apply_base(plan, release, source, session, log)
        validate_environment(session)  # also validate a newly installed daemon
        current = vps.discover(product, vps.docker_inventory(session), session, log, install_dir=product.install_dir)
        check_backend(current, session, log)
        entry_healthy = False
        if entry and entry.get("running"):
            try:
                check_entry(product, plan.address)
                entry_healthy = True
            except (ValueError, OSError):
                pass  # Repair only the already validated, managed LAN entry.
        if not entry_healthy:
            for arguments in ("config --quiet", "pull lan", "run --rm --no-deps lan -t", "up -d lan"):
                code, _ = session.run(compose_command(product, arguments), stream=log, timeout=180)
                if code:
                    raise RuntimeError("内网入口未就绪；基础数据和模式记录保留，请重新检查后续做，不要删除实例")
        entry = inspect_lan(product, session, vps.docker_inventory(session))
        if not entry or not entry.get("running"):
            raise RuntimeError("内网入口容器未运行；不冒充成功")
        wait_for_entry(product, plan.address)
        log("TG2CLOUD_LAN_BASE=OK；TG2CLOUD_LAN_ENTRY=OK；HTTPS=NOT_APPLICABLE")
        log("本机内网入口检查通过；请另用局域网电脑访问管理页，再配置云存储与专用 WebDAV 用户。")
        if plan.action == "install" or not plan.entry_healthy:
            vps.show_credentials(ui, product, current.config, log)
        if verify or plan.action == "install":
            vps.verify_destination(plan, session, log, ui)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="TG2Cloud 独立局域网/NAS 向导；不改变 EXE/VPS HTTPS 模式")
    result.add_argument("--edition", choices=["clouddrive2", "openlist"])
    result.add_argument("--lan-ip", help="人工指定本机 RFC1918 IPv4；已有实例不隐式换地址")
    result.add_argument("--check", action="store_true", help="只读预检；首次需 --edition 和 --lan-ip")
    result.add_argument("--verify", action="store_true", help="另行确认 WebDAV 真写验收")
    result.add_argument("--show-credentials", action="store_true", help="仅在私有终端逐项确认显示已保存凭据")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    log, ui = SafeLog(), None
    try:
        if args.check and (args.verify or args.show_credentials):
            raise ValueError("--check 不能与写入验收或凭据显示组合")
        if args.show_credentials and args.verify:
            raise ValueError("凭据显示必须单独使用")
        if (args.check or args.show_credentials) and not args.edition:
            raise ValueError("只读检查/凭据显示请明确 --edition")
        session = LocalSession(log)
        validate_environment(session)
        if not args.edition:
            ui = vps.Terminal()
            choice = ui.ask("选择 Edition：1 CloudDrive2，2 OpenList", default="1")
            args.edition = {"1": "clouddrive2", "2": "openlist"}.get(choice)
            if not args.edition:
                raise ValueError("Edition 选择无效")
        product = PRODUCTS[args.edition]
        instance = vps.discover(product, vps.docker_inventory(session), session, log, install_dir=product.install_dir)
        saved = load_state(product)
        if args.show_credentials:
            reject_https_route(product)
            if not saved or not instance.present:
                raise ValueError("没有本脚本创建的完整内网实例；不生成凭据")
            if ui is None:
                ui = vps.Terminal()
            vps.show_credentials(ui, product, instance.config, log)
            log("TG2CLOUD_LAN_RESULT=NO_CHANGE；未修改配置或密码")
            return 0
        client = vps.ReleaseClient()
        release = client.resolve()
        log("正式 Release：" + release.tag + "；固定 payload commit：" + release.commit)
        with tempfile.TemporaryDirectory(prefix="tg2cloud-lan-source-") as private:
            root = Path(private)
            source = client.download(release, root)
            baseline = None
            if instance.present:
                if instance.version == release.version:
                    baseline = source
                else:
                    old_root = root / "baseline"
                    old_root.mkdir(mode=0o700)
                    baseline = client.download(client.resolve("v" + instance.version), old_root)
            if not args.check and ui is None:
                ui = vps.Terminal()
            plan = make_plan(instance, release, source, baseline, session, log, ui, address=args.lan_ip or "")
            preview(plan, release, log)
            if args.check:
                if instance.present and not plan.entry_healthy:
                    raise ValueError("基础预检完成，但内网管理入口尚未通过；未执行恢复或重建")
                log("TG2CLOUD_LAN_CHECK=OK；只读预检，不等于安装/外部访问/WebDAV/转存通过")
                return 0
            if plan.action == "newer" or (plan.action == "current" and plan.entry_healthy and not args.verify):
                log("TG2CLOUD_LAN_RESULT=NO_CHANGE；不重建、不降级")
                return 0
            if not ui.confirm("确认上述内网 HTTP 计划？仅用于可信局域网，禁止公网转发；所选 Bot 可能短暂停止"):
                log("TG2CLOUD_LAN_RESULT=CANCELLED；未修改实例或内网状态")
                return 0
            execute(plan, release, source, baseline, session, log, ui, verify=args.verify)
            log("TG2CLOUD_LAN_RESULT=BASE_LAN_OK；WebDAV 与真实转存以独立验收为准")
        return 0
    except KeyboardInterrupt:
        log("TG2CLOUD_LAN_RESULT=INTERRUPTED；核对原安装器回退与入口状态，不假定已恢复")
        return 130
    except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
        log("TG2CLOUD_LAN_RESULT=FAILED：" + str(exc))
        return 1
    except Exception:  # noqa: BLE001 - do not dump configuration/credentials
        log("TG2CLOUD_LAN_RESULT=FAILED：检查/操作异常；未输出配置，请核对实例后重试")
        return 1
    finally:
        if ui is not None:
            ui.close()


if __name__ == "__main__":
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt

    for _name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, _name):
            signal.signal(getattr(signal, _name), interrupted)
    raise SystemExit(main())
