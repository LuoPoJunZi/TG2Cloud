from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from tg2cloud.deployment import configuration, releases
from tg2cloud.deployment.fingerprints import deployed_fingerprint
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import ProductProfile


def inspect_container(session: LocalSession, name: str) -> dict:
    template = ('{"image":{{json .Config.Image}},"running":{{json .State.Running}},'
                '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}}}')
    code, output = session.run(
        "docker container inspect --format " + shlex.quote(template) + " " + shlex.quote(name), timeout=15,
    )
    if code:
        raise RuntimeError("容器检查失败；不会把不可读容器当作未安装")
    return json.loads(output)


def docker_inventory(session: LocalSession) -> set[str]:
    code, _ = session.run("command -v docker >/dev/null 2>&1", timeout=10)
    if code:
        return set()
    code, output = session.run("docker ps -a --format '{{.Names}}'", timeout=15)
    if code:
        raise RuntimeError("Docker 已安装但不可用；不会自动重启或升级 Docker")
    return set(output.splitlines())


@dataclass
class Instance:
    product: ProductProfile
    directory: Path
    present: bool
    version: str = ""
    running: bool = False
    gateway_image: str = ""
    config: dict[str, str] = field(default_factory=dict, repr=False)
    raw_config: bytes = field(default=b"", repr=False)


def discover(
    product: ProductProfile, inventory: set[str], session: LocalSession, log: SafeLog,
    *, install_dir: str | None = None,
) -> Instance:
    default = configuration.checked_directory(install_dir or product.install_dir)
    configuration.check_product_directory(product, default)
    has_bot = product.bot_container in inventory
    has_gateway = product.storage_container in inventory
    if not has_bot and not has_gateway:
        if any(name in inventory for name in product.legacy_containers) or any(
            Path(name).exists() for name in product.legacy_install_dirs
        ):
            raise ValueError("发现旧 TG115；请按迁移文档人工迁移，不自动覆盖")
        if default.exists() and any(default.iterdir()):
            raise ValueError("安装目录有残留但缺少容器；停止，不能当作首次安装覆盖")
        return Instance(product, default, False)
    if not has_bot or not has_gateway:
        raise ValueError("仅检测到部分容器；请先核对实例，不自动重装")
    bot = inspect_container(session, product.bot_container)
    gateway = inspect_container(session, product.storage_container)
    labels = bot.get("labels") or {}
    if not labels.get("com.docker.compose.project"):
        raise ValueError("容器缺少 Compose 项目身份")
    directory = configuration.checked_directory(labels.get("com.docker.compose.project.working_dir", ""))
    configuration.check_product_directory(product, directory)
    if install_dir and directory != default:
        raise ValueError("指定目录与容器实际目录不一致")
    if labels.get("com.docker.compose.service") != product.bot_service:
        raise ValueError("同名 Bot 容器不属于预期 Compose 服务")
    gateway_labels = gateway.get("labels") or {}
    if (gateway_labels.get("com.docker.compose.project.working_dir") != str(directory)
            or gateway_labels.get("com.docker.compose.project") != labels.get("com.docker.compose.project")
            or gateway_labels.get("com.docker.compose.service") != ("openlist" if product.is_openlist else "clouddrive2")):
        raise ValueError("同名网关容器不属于此实例")
    mounts = {item["Destination"]: item for item in bot.get("mounts", [])}
    for destination, relative in (("/data", "data"), ("/config", "config"), ("/downloads", "downloads"), ("/logs", "logs")):
        mount = mounts.get(destination, {})
        if mount.get("Type") != "bind" or mount.get("Source") != str(directory / relative):
            raise ValueError("Bot 持久化挂载与安装目录不一致")
    gateway_mounts = {item["Destination"]: item for item in gateway.get("mounts", [])}
    expected_mounts = (("/opt/openlist/data", "openlist/data"),) if product.is_openlist else (
        ("/Config", "clouddrive/config"), ("/CloudNAS", "clouddrive/mounts"),
    )
    for destination, relative in expected_mounts:
        mount = gateway_mounts.get(destination, {})
        child = directory / relative
        if (mount.get("Type") != "bind" or mount.get("Source") != str(child)
                or not child.is_dir() or child.resolve() != child):
            raise ValueError("云网关持久化挂载与安装目录不一致")
    raw = configuration.regular_private(directory / ".env")
    if not product.is_openlist and b"\r" in raw:
        raise ValueError("CloudDrive2 .env 含 CRLF/回车；现有安装器会规范化它，为保留原始字节已停止，请人工核对")
    config = configuration.parse_config(raw)
    log.register(config)
    backend = config.get("TG2CLOUD_STORAGE_BACKEND", config.get("TG115_STORAGE_BACKEND"))
    if backend != product.key or (not product.is_openlist and config.get("DEPLOY_CLOUDDRIVE2", "true") != "true"):
        raise ValueError("实例不是此 Edition 的受管网关部署；不会覆盖外部 WebDAV 配置")
    for name in ("app", "data", "config", "downloads", "logs"):
        child = directory / name
        if not child.is_dir() or child.resolve() != child:
            raise ValueError("持久化/程序目录缺失或经过链接")
    for path in (directory / "app").rglob("*.py"):
        if path.resolve() != path or not path.is_file():
            raise ValueError("程序文件经过链接")
    version = releases.source_version(directory)
    code, output = session.run(
        "docker compose -f " + shlex.quote(str(directory / "docker-compose.yml")) + " config --format json", timeout=20,
    )
    if code:
        raise ValueError("现有 Compose 配置无法解析；未显示配置内容")
    services = json.loads(output)["services"]
    if (services[product.bot_service].get("container_name") != product.bot_container
            or services["openlist" if product.is_openlist else "clouddrive2"].get("container_name") != product.storage_container):
        raise ValueError("Compose 与容器身份不一致")
    if bot.get("running"):
        script = (
            "from app import __version__; from app.deployment_check import code_fingerprint; "
            "import json; print(json.dumps({'version':__version__,'fingerprint':code_fingerprint()}))"
        )
        code, output = session.run("docker exec " + product.bot_container + " python -c " + shlex.quote(script), timeout=20)
        if code:
            raise ValueError("无法核对实际运行版本/代码；停止升级")
        actual = json.loads(output)
        expected_fingerprint = deployed_fingerprint(directory / "app")
        if actual.get("version") != version or actual.get("fingerprint") != expected_fingerprint:
            raise ValueError("运行代码与磁盘程序不一致；不会猜测或自动覆盖")
    return Instance(product, directory, True, version, bool(bot.get("running")), gateway["image"], config, raw)


def check_foreign_gateway(product: ProductProfile, session: LocalSession) -> None:
    if product.is_openlist:
        return
    code, output = session.run("docker ps -a --format '{{.Names}} {{.Image}}'", timeout=15)
    if code:
        available, _ = session.run("command -v docker >/dev/null 2>&1", timeout=10)
        if not available:
            raise ValueError("Docker 容器列表无法检查；不会跳过外部实例冲突检查")
        return  # A fresh host may not have Docker yet.
    for line in output.splitlines():
        name, _, image = line.partition(" ")
        matches = "clouddrive2" in name.lower() or re.search(r"(^|/)clouddrive2([:@]|$)", image.lower())
        if matches and name not in {product.storage_container, product.bot_container}:
            raise ValueError("存在其他 CloudDrive2 容器；请人工处理冲突，不自动接管")
