"""Independent, ownership-checked TG2Cloud removal; no package management."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import stat
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path

from tg2cloud.cli import terminal
from tg2cloud.deployment import configuration, preflight
from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
from tg2cloud.deployment.profiles import PRODUCTS, ProductProfile
from tg2cloud.deployment.proxy.maintenance import ARCHIVE_NAME
from tg2cloud.deployment.proxy.maintenance import BACKUP_ROOT as PROXY_BACKUP_ROOT
from tg2cloud.deployment.proxy.manager import (
    PROXY_CERTBOT_CONTAINER,
    PROXY_NGINX_CONTAINER,
    PROXY_ROOT,
    DomainProxyManager,
    defer_interruptions,
    empty_state,
    normalize_state,
    proxy_lock_command,
)

LAN_ROOT = Path("/opt/tg2cloud-lan")
LOCK_ROOT = Path("/opt/tg2cloud-cli-locks")
PROXY_PROJECT = "tg2cloud-proxy"
PROXY_NETWORK = PROXY_PROJECT + "_default"
COMPOSE = "com.docker.compose."
MANAGED = "com.tg2cloud.managed"
ROLE = "com.tg2cloud.role"
HEX_ID = re.compile(r"[0-9a-f]{64}")
PROXY_CHILDREN = frozenset({"state", "nginx", "certbot", "docker-compose.yml", "external-auth"})


class UninstallError(ValueError):
    """Only static, credential-free diagnostics created by this module."""


def checked_path(path: Path) -> None:
    """Reject linked parents, non-directories and broad/noncanonical targets."""
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise UninstallError("目标路径缺失绝对位置或经过链接；停止")
    for parent in (*reversed(path.parents), path):
        if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
            raise UninstallError("目录路径经过链接或不是目录；停止")


def read_state() -> dict:
    root = Path(PROXY_ROOT)
    checked_path(root)
    source = root / "state/domains.json"
    if source.exists() or source.is_symlink():
        checked_path(source.parent)
        return normalize_state(configuration.regular_private(source))
    if root.exists() and {item.name for item in root.iterdir()} - {"transaction.lock"}:
        raise UninstallError("共享代理有文件但缺少状态；停止，不能猜测或覆盖未知路由")
    return empty_state()


def docker_snapshot(session: LocalSession) -> tuple[dict, dict]:
    """Read only identity/mount metadata, never Config.Env or container logs."""
    code, output = session.run("docker ps -a --no-trunc --format '{{.ID}}'", timeout=20)
    ids = output.splitlines()
    if code or any(not HEX_ID.fullmatch(value) for value in ids):
        raise UninstallError("Docker 容器清单不可读；停止，不把错误当作空清单")
    containers = {}
    template = ('{"id":{{json .Id}},"name":{{json .Name}},"running":{{json .State.Running}},'
                '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
                '"network":{{json .HostConfig.NetworkMode}}}')
    if ids:
        code, output = session.run("docker container inspect --format " + shlex.quote(template)
                                   + " " + " ".join(ids), timeout=30)
        if code:
            raise UninstallError("容器检查失败；没有显示原始 Docker 输出")
        for line in output.splitlines():
            item = json.loads(line)
            if item.get("id") not in ids or not isinstance(item.get("name"), str):
                raise UninstallError("容器身份格式异常")
            name = item["name"].removeprefix("/")
            if name in containers:
                raise UninstallError("容器身份重复")
            containers[name] = item
        if len(containers) != len(ids):
            raise UninstallError("容器清单在读取期间变化；请重新预检")
    code, output = session.run("docker network ls --no-trunc --format '{{.ID}}'", timeout=20)
    ids = output.splitlines()
    if code or any(not HEX_ID.fullmatch(value) for value in ids):
        raise UninstallError("Docker 网络清单不可读")
    networks = {}
    template = ('{"id":{{json .Id}},"name":{{json .Name}},"labels":{{json .Labels}},'
                '"containers":{{json .Containers}},"driver":{{json .Driver}}}')
    if ids:
        code, output = session.run("docker network inspect --format " + shlex.quote(template)
                                   + " " + " ".join(ids), timeout=30)
        if code:
            raise UninstallError("网络检查失败；没有显示原始 Docker 输出")
        for line in output.splitlines():
            item = json.loads(line)
            if item.get("id") not in ids or not isinstance(item.get("name"), str):
                raise UninstallError("网络身份格式异常")
            networks[item["name"]] = item
        if len(networks) != len(ids):
            raise UninstallError("网络清单在读取期间变化；请重新预检")
    return containers, networks


def bind_map(item: dict) -> dict:
    result = {}
    for mount in item.get("mounts", []):
        if mount.get("Type") == "tmpfs":
            continue
        destination = mount.get("Destination")
        if mount.get("Type") != "bind" or destination in result:
            raise UninstallError("容器使用了未知挂载；停止，不清理命名卷或外部数据")
        result[destination] = mount.get("Source")
    return result


def mount_overlaps(item: dict, root: Path) -> bool:
    """Parent bind mounts also expose the subtree about to be removed."""
    for mount in item.get("mounts", []):
        if mount.get("Type") == "tmpfs":
            continue
        source = mount.get("Source")
        if not isinstance(source, str) or not source:
            raise UninstallError("挂载源无法核对；停止，不删除数据")
        path = Path(source)
        if path.is_relative_to(root) or root.is_relative_to(path):
            return True
    return False


def require_labels(item: dict, expected: dict) -> None:
    labels = item.get("labels") or {}
    if any(labels.get(key) != value for key, value in expected.items()):
        raise UninstallError("同名资源归属不符；停止，不接管其他项目")


def core_identity(product: ProductProfile, name: str, item: dict) -> str:
    directory = Path(product.install_dir)
    checked_path(directory)
    service = product.bot_service if name == product.bot_container else product.key
    require_labels(item, {COMPOSE + "service": service,
                          COMPOSE + "project.working_dir": str(directory),
                          COMPOSE + "project.config_files": str(directory / "docker-compose.yml")})
    project = (item.get("labels") or {}).get(COMPOSE + "project", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", project):
        raise UninstallError("容器缺少有效 Compose 项目身份")
    expected = {"/" + child: str(directory / child) for child in ("data", "downloads", "logs", "config")}
    if name == product.storage_container:
        expected = ({"/opt/openlist/data": str(directory / "openlist/data")} if product.is_openlist else
                    {"/Config": str(directory / "clouddrive/config"),
                     "/CloudNAS": str(directory / "clouddrive/mounts")})
    if bind_map(item) != expected:
        raise UninstallError("容器挂载不属于标准安装目录；停止，不接管自定义部署")
    return project


def lan_name(product: ProductProfile) -> str:
    return "tg2cloud-lan-" + ("openlist" if product.is_openlist else "cd2")


def lan_identity(product: ProductProfile, item: dict) -> None:
    directory = LAN_ROOT / product.key
    checked_path(directory)
    require_labels(item, {MANAGED: "true", ROLE: "lan-management", "com.tg2cloud.edition": product.key,
                          COMPOSE + "project": lan_name(product), COMPOSE + "service": "lan",
                          COMPOSE + "project.working_dir": str(directory),
                          COMPOSE + "project.config_files": str(directory / "compose.json")})
    if item.get("network") != "host" or bind_map(item) != {
        "/etc/nginx/nginx.conf": str(directory / "nginx.conf"),
    }:
        raise UninstallError("内网入口身份或挂载不符")


def proxy_identity(name: str, item: dict, *, state: dict | None = None) -> None:
    labels = item.get("labels") or {}
    service = labels.get(COMPOSE + "service")
    expected_service = "nginx" if name == PROXY_NGINX_CONTAINER else "certbot"
    if (name not in {PROXY_NGINX_CONTAINER, PROXY_CERTBOT_CONTAINER}
            and (labels.get(COMPOSE + "oneoff") != "True" or item.get("running")
                 or not re.fullmatch(r"tg2cloud-proxy-certbot-run-[a-z0-9]+", name))):
        raise UninstallError("存在未知或运行中的代理辅助容器；先完成维护，不强制删除")
    require_labels(item, {MANAGED: "true", ROLE: "reverse-proxy" if expected_service == "nginx" else "certificate-manager",
                          COMPOSE + "project": PROXY_PROJECT, COMPOSE + "service": expected_service,
                          COMPOSE + "project.working_dir": PROXY_ROOT,
                          COMPOSE + "project.config_files": PROXY_ROOT + "/docker-compose.yml"})
    expected_network = "host" if expected_service == "nginx" else PROXY_NETWORK
    if service != expected_service or item.get("network") != expected_network:
        raise UninstallError("共享代理容器身份不符")
    paths = {"/var/www/certbot": "/certbot/www", "/etc/letsencrypt": "/certbot/letsencrypt"}
    if expected_service == "nginx":
        paths.update({"/etc/nginx/nginx.conf": "/nginx/nginx.conf", "/etc/nginx/conf.d": "/nginx/conf.d"})
        if state and state.get("version") == 2:
            paths["/etc/nginx/external-auth"] = "/external-auth"
    else:
        paths.update({"/var/lib/letsencrypt": "/certbot/lib", "/var/log/letsencrypt": "/certbot/log", "/status": "/certbot/status"})
    if bind_map(item) != {destination: PROXY_ROOT + suffix for destination, suffix in paths.items()}:
        raise UninstallError("共享代理挂载含未知路径；停止")


@dataclass(eq=True)
class Plan:
    editions: tuple[str, ...]
    containers: dict
    networks: dict
    state: dict
    remove_proxy: bool
    purge_data: bool
    purge_backups: bool = False
    backups: dict = field(default_factory=dict)


def other_edition_present(editions: tuple[str, ...], containers: dict) -> bool:
    """Retained data also needs its shared certificates, not just live containers."""
    return any(PRODUCTS[key].bot_container in containers or PRODUCTS[key].storage_container in containers
               or Path(PRODUCTS[key].install_dir).exists() or (LAN_ROOT / key).exists()
               for key in PRODUCTS if key not in editions)


def backup_targets(editions: tuple[str, ...], containers: dict, remove_proxy: bool) -> dict:
    targets = {}
    for key in editions:
        kinds = r"config-[A-Za-z0-9]{8}\.tar\.gz|database-[A-Za-z0-9]{8}\.db|env-[A-Za-z0-9]{8}\.env"
        if PRODUCTS[key].is_openlist:
            kinds += r"|openlist-state-[A-Za-z0-9]{8}\.tar\.gz"
        targets[Path(PRODUCTS[key].backup_dir)] = re.compile(kinds)
    if remove_proxy and not other_edition_present(editions, containers):
        targets[PROXY_BACKUP_ROOT] = ARCHIVE_NAME
    return targets


def backup_identity(root: Path, pattern: re.Pattern) -> tuple | None:
    """Inspect only generated file names and metadata, never backup secrets."""
    checked_path(root)
    if not root.exists():
        return None
    info = root.stat()
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise UninstallError("备份目录所有者/权限不符合受管私密目录；停止")
    entries = []
    for child in sorted(root.iterdir()):
        metadata = child.lstat()
        if (not pattern.fullmatch(child.name) or not stat.S_ISREG(metadata.st_mode)
                or child.is_symlink() or child.resolve() != child
                or (os.name == "posix" and (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077))):
            raise UninstallError("备份目录含未知文件、链接或不安全归属；停止，不按目录名猜测删除")
        entries.append((child.name, metadata.st_dev, metadata.st_ino, metadata.st_size,
                        metadata.st_mtime_ns, metadata.st_ctime_ns))
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, tuple(entries))


def build_plan(editions: tuple[str, ...], session: LocalSession, *, purge_data: bool = False,
               purge_backups: bool = False) -> Plan:
    purge_data = purge_data or purge_backups
    containers, networks = docker_snapshot(session)
    state = read_state()
    if any(key in state.get("external_webdav", {}) or (Path("/opt/tg2cloud-webdav") / key / "config.json").exists() for key in editions):
        raise UninstallError("所选网关仍被外部 WebDAV 依赖；请先运行 tg2cloud-webdav uninstall，不静默中断外部入口。")
    selected = {}
    selected_networks = {}
    for key in editions:
        product = PRODUCTS[key]
        checked_path(Path(product.install_dir))
        projects = set()
        core = {product.bot_container, product.storage_container}
        for name in core:
            if name in containers:
                projects.add(core_identity(product, name, containers[name]))
                selected[name] = containers[name]
        if len(projects) > 1:
            raise UninstallError("Bot 与网关不属于同一个 Compose 项目")
        for name, item in containers.items():
            labels = item.get("labels") or {}
            if name not in core and (labels.get(COMPOSE + "project") in projects or
                                    labels.get(COMPOSE + "project.working_dir") == product.install_dir):
                raise UninstallError("安装目录关联了其他容器；停止，不使用 remove-orphans")
        name = lan_name(product)
        if name in containers:
            lan_identity(product, containers[name])
            selected[name] = containers[name]
        lan_dir = LAN_ROOT / key
        checked_path(lan_dir)
        if lan_dir.exists():
            entries = {path.name for path in lan_dir.iterdir()}
            if entries != {"state.json", "compose.json", "nginx.conf"}:
                raise UninstallError("内网入口目录有未知文件或不完整；停止，不递归清理")
            record = json.loads(configuration.regular_private(lan_dir / "state.json"))
            if (not isinstance(record, dict) or record.get("mode") != "lan" or record.get("schema") != 1
                    or record.get("edition") != key or record.get("install_dir") != product.install_dir):
                raise UninstallError("内网入口模式记录不符")
        if product.docker_network in networks:
            network = networks[product.docker_network]
            labels = network.get("labels") or {}
            project = labels.get(COMPOSE + "project")
            if (network.get("driver") != "bridge" or labels.get(COMPOSE + "network") != product.docker_network
                    or not project or (projects and project not in projects)):
                raise UninstallError("同名网络缺少预期 Compose 归属；停止")
            if not projects and project != Path(product.install_dir).name:
                raise UninstallError("残留网络缺少可验证的标准项目身份")
            if set(network.get("containers") or {}) - {item["id"] for item in selected.values()}:
                raise UninstallError("项目网络有外部容器连接；停止，不强制断开")
            selected_networks[product.docker_network] = network
    remaining = set(state["domains"]) - set(editions)
    remove_proxy = not remaining and not state.get("external_webdav")
    for name, item in containers.items():
        labels = item.get("labels") or {}
        if name in {PROXY_NGINX_CONTAINER, PROXY_CERTBOT_CONTAINER} or labels.get(COMPOSE + "project") == PROXY_PROJECT:
            proxy_identity(name, item, state=state)
            if remove_proxy:
                selected[name] = item
        if labels.get(ROLE) == "maintenance-dry-run":
            raise UninstallError("检测到代理证书维护辅助容器；先完成/核对维护，不在卸载时接管")
    if remove_proxy and PROXY_NETWORK in networks:
        network = networks[PROXY_NETWORK]
        require_labels(network, {COMPOSE + "project": PROXY_PROJECT, COMPOSE + "network": "default"})
        if network.get("driver") != "bridge" or set(network.get("containers") or {}) - {item["id"] for item in selected.values()}:
            raise UninstallError("共享代理网络有外部连接或类型不符；不强制删除")
        selected_networks[PROXY_NETWORK] = network
    if (not Path(PROXY_ROOT, "state/domains.json").exists()
            and any(name in containers for name in (PROXY_NGINX_CONTAINER, PROXY_CERTBOT_CONTAINER))):
        raise UninstallError("共享代理容器存在但状态缺失；停止")
    for key in editions:
        directory = LAN_ROOT / key
        if directory.exists():
            if any(point == directory or point.is_relative_to(directory) for point in mountpoints()):
                raise UninstallError("内网入口目录下存在挂载点；不递归清理")
            if any(name not in selected and mount_overlaps(item, directory)
                   for name, item in containers.items()):
                raise UninstallError("其他容器正在使用内网入口文件；停止")
    # Purge is allowed only for verified live roots, or recognizable retained
    # standard payloads. Never infer ownership from the name of a directory.
    if purge_data:
        for key in editions:
            root = Path(PRODUCTS[key].install_dir)
            if root.exists() and not any(name in selected for name in (PRODUCTS[key].bot_container, PRODUCTS[key].storage_container)):
                source = root / "docker-compose.yml"
                if source.is_symlink() or source.resolve() != source or not source.is_file() or source.stat().st_size > 128 * 1024:
                    raise UninstallError("残留目录缺少可核对的标准 Compose；不删除")
                text = source.read_text(encoding="utf-8")
                if not all(re.search(r"(?m)^    container_name: " + re.escape(name) + r"\s*$", text)
                           for name in (PRODUCTS[key].bot_container, PRODUCTS[key].storage_container)):
                    raise UninstallError("残留目录不是所选 Edition 的标准 payload；不删除")
        targets = backup_targets(editions, containers, remove_proxy) if purge_backups else {}
        backups = {root: backup_identity(root, pattern) for root, pattern in targets.items()}
        purge_preflight(editions, containers, selected, remove_proxy, tuple(targets))
    else:
        backups = {}
    return Plan(editions, selected, selected_networks, state, remove_proxy, purge_data, purge_backups, backups)


def mountpoints() -> tuple[Path, ...]:
    def unescape(text: str) -> str:
        return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), text)

    result = []
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 7 or "-" not in parts:
            raise UninstallError("无法完整核对挂载点；不删除数据")
        result.append(Path(unescape(parts[4])))
    if not result:
        raise UninstallError("挂载点清单为空；不删除数据")
    return tuple(result)


def purge_preflight(editions: tuple[str, ...], containers: dict, selected: dict, remove_proxy: bool,
                    backups: tuple[Path, ...] = ()) -> None:
    roots = [Path(PRODUCTS[key].install_dir) for key in editions]
    # Never delete shared certificates while another Edition is still present,
    # even if that Edition has no committed HTTPS route yet.
    if remove_proxy and not other_edition_present(editions, containers):
        roots.append(Path(PROXY_ROOT))
    roots.extend(backups)
    points = mountpoints()
    for root in roots:
        checked_path(root)
        if any(point == root or point.is_relative_to(root) for point in points):
            raise UninstallError("数据目录下仍有挂载点（可能是云盘/FUSE）；不递归删除、不强制卸载，请处理后重新预检")
        for name, item in containers.items():
            if name not in selected and mount_overlaps(item, root):
                raise UninstallError("其他容器正在使用待删除的数据；停止")
    if (Path(PROXY_ROOT) in roots and Path(PROXY_ROOT).exists()
            and {path.name for path in Path(PROXY_ROOT).iterdir()} - (PROXY_CHILDREN | {"transaction.lock"})):
        raise UninstallError("共享代理目录有未知文件；不递归删除")


def delete_tree(root: Path, allowed: set[Path]) -> None:
    if root not in allowed:
        raise UninstallError("删除目标不在本次已确认的精确目录白名单中")
    checked_path(root.parent)
    if root.is_symlink() or root.resolve() != root:
        raise UninstallError("删除目标经过链接；停止")
    if not root.exists():
        return
    if any(point == root or point.is_relative_to(root) for point in mountpoints()):
        raise UninstallError("删除前发现挂载点；停止，不触碰云盘文件")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise UninstallError("本机缺少防符号链接竞争的目录删除能力；停止")
    if root.is_dir():
        # Do not follow child symlinks. Mount traversal was separately rejected.
        shutil.rmtree(root)
    elif stat.S_ISREG(root.lstat().st_mode):
        root.unlink()
    else:
        raise UninstallError("删除目标文件类型异常；停止")


def remove_container(session: LocalSession, name: str, item: dict, log: SafeLog) -> None:
    identifier = item["id"]
    if not HEX_ID.fullmatch(identifier):
        raise UninstallError("容器 ID 无效")
    # Stop by immutable ID, never rm -f. Docker can use its configured signal
    # after this grace period; explicitly ask users to finish active transfers.
    code, _ = session.run("docker container stop --time 60 " + identifier, timeout=85)
    if code:
        raise UninstallError("容器停止失败；没有显示原始输出，停止后续删除")
    code, _ = session.run("docker container rm " + identifier, timeout=25)
    if code:
        raise UninstallError("容器移除失败；停止，请重新预检核对部分完成状态")
    log("已移除容器：" + name)


def execute(plan: Plan, session: LocalSession, log: SafeLog) -> None:
    with ExitStack() as locks:
        # Same lock order for all invocations; preserve lock files to avoid
        # replacing a locked inode. Windows EXEs must not run concurrently.
        for key in sorted(plan.editions):
            locks.enter_context(edition_lock(LOCK_ROOT / (key + ".lock")))
        locks.enter_context(session.hold_lock(proxy_lock_command()))
        if build_plan(plan.editions, session, purge_data=plan.purge_data, purge_backups=plan.purge_backups) != plan:
            raise UninstallError("确认期间实例/网络/HTTPS 状态发生变化；停止，请重新预检")
        # Reuse the existing transactional route removal. Abort before touching
        # Bot/gateway containers if a remaining route cannot pass its checks.
        if len(plan.state["domains"]) > 1 and not set(plan.state["domains"]) - set(plan.editions):
            # No surviving route needs a transient activation between removals.
            manager = DomainProxyManager(session, PRODUCTS[plan.editions[0]], {"ssh_user": "root"}, log)
            manager.prepare()
            with defer_interruptions():
                try:
                    manager._install_config(empty_state())
                    code, _ = manager._compose("stop nginx certbot", timeout=90)
                    if code:
                        raise UninstallError("共享代理停止失败；未移除业务容器，开始恢复原路由")
                    manager._commit_state(empty_state())
                except Exception:
                    try:
                        manager._activate(plan.state)
                        restore_code, _ = manager._compose("up -d certbot", timeout=120)
                        if restore_code:
                            log("警告：共享代理恢复未完全通过，请核对原路由；业务容器尚未移除。")
                    except Exception:  # noqa: BLE001 - do not hide original failure or expose raw output
                        log("警告：共享代理恢复失败，请核对原路由；业务容器尚未移除。")
                    raise
            log("已移除全部所选 HTTPS 路由。")
        else:
            for key in plan.editions:
                if key in plan.state["domains"]:
                    manager = DomainProxyManager(session, PRODUCTS[key], {"ssh_user": "root"}, log)
                    manager.prepare()
                    try:
                        with defer_interruptions():
                            report = manager._remove_locked()
                    except Exception as exc:
                        raise UninstallError("HTTPS 路由移除/剩余入口自检未通过；业务容器尚未移除，请核对共享代理及原路由恢复结果") from exc
                    log(report.message)
        order = []
        for key in plan.editions:
            product = PRODUCTS[key]
            order.extend((lan_name(product), product.bot_container, product.storage_container))
        order.extend(sorted(set(plan.containers) - set(order)))
        for name in order:
            if name in plan.containers:
                remove_container(session, name, plan.containers[name], log)
        for name, item in plan.networks.items():
            # Recheck immutable identity/endpoints after removing containers.
            template = '{"id":{{json .Id}},"containers":{{json .Containers}},"labels":{{json .Labels}}}'
            code, output = session.run("docker network inspect --format " + shlex.quote(template) + " " + item["id"], timeout=15)
            if code:
                raise UninstallError("网络删除前复检失败；停止")
            current = json.loads(output)
            if current.get("id") != item["id"] or current.get("labels") != item.get("labels") or current.get("containers"):
                raise UninstallError("网络归属或连接已变化；不强制断开任何容器")
            code, _ = session.run("docker network rm " + item["id"], timeout=20)
            if code:
                raise UninstallError("网络移除失败；停止，请核对部分完成状态")
            log("已移除网络：" + name)
        containers, networks = docker_snapshot(session)
        if set(containers) & set(plan.containers) or set(networks) & set(plan.networks):
            raise UninstallError("卸载后资源复检未通过；不输出成功标记")
        for key in plan.editions:
            directory = LAN_ROOT / key
            if directory.exists():
                delete_tree(directory, {LAN_ROOT / value for value in plan.editions})
                log("已移除内网入口配置：" + str(directory))
        if plan.purge_data:
            targets = backup_targets(plan.editions, containers, plan.remove_proxy) if plan.purge_backups else {}
            if {root: backup_identity(root, pattern) for root, pattern in targets.items()} != plan.backups:
                raise UninstallError("备份范围或内容在卸载期间变化；停止数据删除，请重新预检")
            purge_preflight(plan.editions, containers, {}, plan.remove_proxy, tuple(targets))
            roots = {Path(PRODUCTS[key].install_dir) for key in plan.editions}
            for root in sorted(roots):
                delete_tree(root, roots)
                if root.exists():
                    raise UninstallError("本地实例目录删除后复检失败；停止，不输出成功")
                log("已删除本地实例目录：" + str(root))
            other_present = other_edition_present(plan.editions, containers)
            if plan.remove_proxy and not other_present:
                roots = {Path(PROXY_ROOT) / name for name in PROXY_CHILDREN}
                for root in sorted(roots):
                    delete_tree(root, roots)
                    if root.exists():
                        raise UninstallError("共享代理配置/证书删除后复检失败")
                log("已删除不再使用的共享代理配置/证书；事务锁文件保留。")
            for root, pattern in sorted(targets.items()):
                if backup_identity(root, pattern) != plan.backups[root]:
                    raise UninstallError("备份在删除前变化；停止，不删除未经确认的新备份")
                if plan.backups[root] is not None:
                    delete_tree(root, set(targets))
                    if root.exists():
                        raise UninstallError("备份目录删除后复检失败；停止，不输出成功")
                    log("已删除历史备份目录：" + str(root))
        state = read_state()
        if set(state["domains"]) & set(plan.editions):
            raise UninstallError("所选 HTTPS 路由仍存在；卸载复检未通过")


def validate_environment(session: LocalSession) -> None:
    preflight.validate_host()
    forbidden = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",
                 "COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES", "COMPOSE_ENV_FILES")
    if any(os.environ.get(key) for key in forbidden):
        raise UninstallError("只允许本机默认 Docker 环境；拒绝远端 daemon 和 Compose 覆盖")
    code, output = session.run("docker context inspect --format '{{json .Endpoints.docker.Host}}'", timeout=15)
    if code or json.loads(output) != "unix:///var/run/docker.sock":
        raise UninstallError("Docker 不可用或不是本机默认 daemon；不安装、不重启 Docker")


def preview(plan: Plan, log: SafeLog) -> None:
    log("TG2Cloud 卸载计划（确认前不停止容器、不修改路由）")
    log("Edition：" + ", ".join(PRODUCTS[key].display_name for key in plan.editions))
    log("容器：" + (", ".join(sorted(plan.containers)) or "无"))
    log("网络：" + (", ".join(sorted(plan.networks)) or "无"))
    log("移除所选 Edition 的 HTTPS 路由和独立 LAN 管理入口；其他 Edition 路由继续保留。")
    log("共享 Nginx/Certbot：" + ("没有剩余 HTTPS 路由，移除受管容器" if plan.remove_proxy else "保留，另一 Edition 仍在使用"))
    for key in plan.editions:
        log(("删除本地数据：" if plan.purge_data else "保留本地配置/数据：") + PRODUCTS[key].install_dir)
        log(("删除历史备份：" if plan.purge_backups else "历史备份保留：") + PRODUCTS[key].backup_dir)
    if PROXY_BACKUP_ROOT in plan.backups:
        log("删除不再使用的共享代理备份：" + str(PROXY_BACKUP_ROOT))
    else:
        log("共享代理历史备份保留；所选范围之外的数据不会清理。")
    log("镜像缓存、并发锁元数据、旧 TG115 和系统软件不清理；不能保证系统逐字节恢复到安装前。")
    log("请先结束进行中的传输并自行备份；停止容器会中断任务。不要同时运行 EXE/其他安装器。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="仅卸载受管 TG2Cloud；不卸载系统 Docker/Nginx")
    parser.add_argument("--edition", choices=(*PRODUCTS, "all"), help="CloudDrive2、OpenList 或全部；不指定时询问")
    parser.add_argument("--check", action="store_true", help="只读预览，无需确认，不执行卸载")
    cleanup = parser.add_mutually_exclusive_group()
    cleanup.add_argument("--purge-all", dest="cleanup", action="store_const", const="all",
                         help="默认模式：双重确认后删除所选实例数据和可识别历史备份")
    cleanup.add_argument("--purge-data", dest="cleanup", action="store_const", const="data",
                         help="双重确认后删除实例数据，保留历史备份（兼容原选项）")
    cleanup.add_argument("--keep-data", dest="cleanup", action="store_const", const="runtime",
                         help="只移除运行资源，保留实例数据、证书和历史备份")
    parser.set_defaults(cleanup="all")
    args = parser.parse_args(argv)
    log = SafeLog()
    ui = None
    try:
        session = LocalSession(log)
        validate_environment(session)
        key = args.edition
        if key is None:
            if args.check:
                raise UninstallError("只读预检请明确指定 --edition clouddrive2/openlist/all")
            ui = terminal.Terminal()
            key = ui.ask("选择卸载 clouddrive2 / openlist / all", validate=lambda value: value if value in {*PRODUCTS, "all"} else "")
            if not key:
                raise UninstallError("没有选择有效 Edition；未执行卸载")
        editions = tuple(PRODUCTS) if key == "all" else (key,)
        plan = build_plan(editions, session, purge_data=args.cleanup != "runtime", purge_backups=args.cleanup == "all")
        preview(plan, log)
        if args.check:
            log("TG2CLOUD_UNINSTALL_CHECK=OK；只是预检，不是已经卸载")
            return 0
        ui = ui or terminal.Terminal()
        if not ui.confirm("是否执行以上 TG2Cloud 资源卸载？"):
            log("TG2CLOUD_UNINSTALL_RESULT=CANCELLED；未执行卸载")
            return 0
        if plan.purge_data:
            log("危险：删除 .env、Session、SQLite、下载、日志、云网关授权配置后不能自动恢复；"
                + ("历史备份也删除，不能使用原备份恢复。" if plan.purge_backups else "历史备份保留。"))
            token = ("DELETE ALL " if plan.purge_backups else "DELETE ") + key
            if ui.ask("请输入 " + token + " 确认删除上述本地数据", validate=lambda value: value) != token:
                log("TG2CLOUD_UNINSTALL_RESULT=CANCELLED；删除确认不匹配，未执行卸载")
                return 0
        execute(plan, session, log)
        log("TG2CLOUD_UNINSTALL_RESULT=OK；所选受管运行资源及路由已移除，系统应用未卸载。")
        if not plan.purge_data:
            log("--keep-data 保留本地实例数据/证书/备份；再次安装前请按卸载文档处理残留目录，不会静默覆盖。")
        elif plan.purge_backups:
            log("所选实例数据和已核对的备份已清理；共享资源按剩余 Edition 保留，镜像缓存/锁元数据与系统应用未清理。")
        return 0
    except (KeyboardInterrupt, EOFError):
        log("TG2CLOUD_UNINSTALL_RESULT=INTERRUPTED；可能部分完成，请用 --check 核对；不自动重装/删除数据。")
        return 130
    except Exception as exc:  # noqa: BLE001 - never expose raw Docker/config output
        log("TG2CLOUD_UNINSTALL_RESULT=FAILED；停止后续操作，可能部分完成；请重新 --check 核对。")
        # Only our static messages are safe; parser/OS errors can contain data.
        log(str(exc) if isinstance(exc, UninstallError) else "错误类型：" + type(exc).__name__)
        return 1
    finally:
        if ui:
            ui.close()


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    for signal_name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), interrupted)
    raise SystemExit(main())
