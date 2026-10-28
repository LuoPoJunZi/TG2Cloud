"""Short-lived Compose tools. No Docker socket, network or Bot startup."""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import os
import re
import secrets
import shutil
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from tg2cloud.config import Settings
from tg2cloud.deployment import configuration
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence.bundle import pack
from tg2cloud.version import VERSION

MARKER = "tg2cloud-compose.json"


class ComposeError(ValueError):
    """Fixed operator-facing messages, never configuration values."""


def regular(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or path.resolve() != path.absolute() or not path.is_file():
        raise ComposeError("必要文件缺失或经过链接；停止")
    return path


def metadata(root: Path) -> dict:
    regular(root, "docker-compose.yml")
    path = regular(root, "compose-bundle.json")
    if path.stat().st_size > 8192:
        raise ComposeError("部署包元数据过大")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("format") != 1 or value.get("mode") != "compose"
            or value.get("edition") not in PRODUCTS or value.get("version") != VERSION):
        raise ComposeError("部署包与运行工具版本不匹配，请使用同一正式版本")
    return value


def lan_address(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    if address.is_loopback or any(address in ipaddress.ip_network(net) for net in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    )):
        return str(address)
    raise ComposeError("请输入回环或内网 IPv4，不开放公网监听")


def checked(pattern, value):
    if not re.fullmatch(pattern, value):
        raise ComposeError("输入格式无效")
    return value


def collect(ui, product):
    from tg2cloud.domain.classification import safe_directory
    def reserve(value):
        configuration.size_gb(value)
        if float(value) < 8:
            raise ComposeError("至少保留 8GB 空闲空间")
        return value
    values = {
        "api_id": ui.ask("Telegram API ID", validate=configuration.positive),
        "api_hash": ui.ask("Telegram API Hash（隐藏输入）", secret=True,
                           validate=lambda v: checked(r"[0-9a-fA-F]{32}", v)),
        "bot_token": ui.ask("Bot Token（隐藏输入）", secret=True,
                            validate=lambda v: checked(r"[0-9]+:[A-Za-z0-9_-]{20,}", v)),
        "user_id": ui.ask("管理员 Telegram 用户 ID（仅一个）", validate=configuration.positive),
        "webdav_user": ui.ask("WebDAV 用户名", default="tg2cloud",
                              validate=lambda v: checked(r"[A-Za-z][A-Za-z0-9_-]{2,31}", v)),
        "webdav_password": ui.ask("WebDAV 密码（回车自动生成；隐藏输入）", secret=True,
                                  default=secrets.token_urlsafe(12)),
        "target": ui.ask("Bot 保存子目录（可留空）", validate=safe_directory),
        "budget": ui.ask("任务暂存预算 GB", default="20", validate=configuration.size_gb),
        "reserve": ui.ask("最少保留空间 GB", default="8", validate=reserve),
        "timezone": "Asia/Shanghai", "admin_password": secrets.token_urlsafe(24),
    }
    result = configuration.new_config(product, values)
    result["TG2CLOUD_BIND_IP"] = ui.ask("管理端口绑定 IPv4（内网访问请填本机内网地址）",
                                      default="127.0.0.1", validate=lan_address)
    result["TG2CLOUD_INSTALL_MODE"] = "compose"
    return result


@contextmanager
def environment(config):
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(config)
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def validate_config(root, config, edition):
    if (config.get("TG2CLOUD_INSTALL_MODE") != "compose"
            or config.get("TG2CLOUD_STORAGE_BACKEND") != edition):
        raise ComposeError("配置不属于此 Compose Edition，停止")
    lan_address(config.get("TG2CLOUD_BIND_IP", "127.0.0.1"))
    with environment(config):
        settings = Settings.from_env(create_directories=False)
    if settings.cd2_url != PRODUCTS[edition].webdav_url:
        raise ComposeError("此部署包仅支持自身受管网关，不接管外部部署")
    return settings


def private_config_file(path):
    info = path.stat()
    if os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o077):
        raise ComposeError("私有配置必须归 root 所有且权限为 600")


def saved_config(root, edition):
    marker = regular(root, MARKER)
    if marker.stat().st_size > 8192:
        raise ComposeError("实例标记无效")
    value = json.loads(marker.read_text(encoding="utf-8"))
    if value.get("format") != 1 or value.get("edition") != edition or value.get("state") != "ready":
        raise ComposeError("初始化未完成或实例身份不匹配；保留文件，请核对")
    path = regular(root, ".env")
    private_config_file(path)
    if path.stat().st_size > 128 * 1024:
        raise ComposeError("配置文件过大")
    config = configuration.parse_config(path.read_bytes())
    validate_config(root, config, edition)
    return config


def write_exclusive(path, content):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)  # Only the file exclusively created above.
        raise


def own_directory(path, uid):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ComposeError("数据目录经过链接；停止")
    if path.exists() and any(child.is_symlink() or not child.is_dir() for child in path.iterdir()):
        raise ComposeError("发现已有数据；不会重新初始化或改写归属")
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    if os.name == "posix":
        os.chown(path, uid, uid)


def setup(root, ui):
    info = metadata(root)
    product = PRODUCTS[info["edition"]]
    if (root / ".env").exists() or (root / MARKER).exists():
        saved_config(root, product.key)
        return False  # Idempotent; never regenerate passwords or reset an instance.
    for name in ("app", "remote_install.sh", "manage.sh", "tg2cloud-release.json"):
        if (root / name).exists() or (root / name).is_symlink():
            raise ComposeError("发现脚本安装或未知部署文件；不自动接管")
    allowed = {"data", "downloads", "logs", "config", "config/rclone", "clouddrive",
               "clouddrive/config", "clouddrive/mounts", "openlist", "openlist/data"}
    for name in ("data", "downloads", "logs", "config", "clouddrive", "openlist"):
        path = root / name
        if path.is_symlink() or path.exists() and not path.is_dir():
            raise ComposeError("已有目录或数据未登记，停止；不覆盖旧安装")
        if path.exists():
            # Only known, empty initialization directories can survive an interrupted setup.
            for child in path.rglob("*"):
                if child.is_symlink() or not child.is_dir() or child.relative_to(root).as_posix() not in allowed:
                    raise ComposeError("已有目录或数据未登记，停止；不覆盖旧安装")
    config = collect(ui, product)
    settings = validate_config(root, config, product.key)
    free = shutil.disk_usage(root).free
    if free < settings.local_budget_bytes + settings.min_free_disk_bytes:
        raise ComposeError("安装文件系统空间不足，请调整暂存预算；未写入配置")
    print(f"计划：{product.display_name}；Compose 独立安装；暂存预算 {config['LOCAL_TEMP_BUDGET_GB']}GB；保留 {config['MIN_FREE_DISK_GB']}GB")
    print("仅生成本目录配置和权限；请先确认没有另一实例使用同一 Bot Token。")
    if not ui.confirm("确认初始化"):
        return False
    for name in ("data", "downloads", "logs", "config"):
        own_directory(root / name, 10001)
    own_directory(root / "config/rclone", 10001)
    parent = "openlist" if product.is_openlist else "clouddrive"
    own_directory(root / parent, 0)
    if product.is_openlist:
        own_directory(root / "openlist/data", 1001)
    else:
        own_directory(root / "clouddrive/config", 0)
        own_directory(root / "clouddrive/mounts", 0)
    # Commit private files last. An interruption never overwrites an old .env.
    content = "".join(f"{key}={value}\n" for key, value in config.items()).encode()
    state = (json.dumps({"format": 1, "edition": product.key, "state": "ready",
                         "initialized_version": VERSION}) + "\n").encode()
    created = []
    try:
        for name, data in ((".env", content), (MARKER, state)):
            write_exclusive(root / name, data)
            created.append(name)
    except BaseException:
        for name in created:
            (root / name).unlink()
        raise
    print("配置初始化完成；请先启动网关，在后台挂载云存储并创建专用 WebDAV 用户，再启动 Bot。")
    credentials(ui, product, config)
    return True


def credentials(ui, product, config):
    if not ui.confirm("是否仅在当前私有终端显示后台需填写的账号信息"):
        return
    for key, label in (("USERNAME", "WebDAV 用户名"), ("PASSWORD", "WebDAV 密码")):
        ui.private(label, base64.b64decode(config["WEBDAV_" + key + "_B64"]).decode())
    if product.is_openlist:
        ui.private("OpenList 初始化管理员密码（后台更改后可能不再有效）", config["OPENLIST_ADMIN_PASSWORD"])


@contextmanager
def operation_lock(root):
    import fcntl
    path = root / ".tg2cloud-compose.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ComposeError("操作锁归属或权限不安全")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TG2Cloud Compose 交互初始化与离线维护")
    parser.add_argument("action", choices=("setup", "check", "credentials", "backup"))
    parser.add_argument("--offline-confirmed", action="store_true",
                        help="已人工停止此 Edition 的 Bot 和网关；仅供离线备份")
    args = parser.parse_args(argv)
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise ComposeError("请使用部署包中的 setup 服务在 Linux 执行")
        root = Path.cwd()
        if root.resolve() != root.absolute():
            raise ComposeError("工作目录经过链接")
        with operation_lock(root):
            info = metadata(root)
            if args.action in {"setup", "credentials"}:
                from tg2cloud.cli.terminal import Terminal
                ui = Terminal()
                ui.friendly = True
                try:
                    if args.action == "setup":
                        if not setup(root, ui):
                            print("配置保留，未重新生成。")
                    else:
                        credentials(ui, PRODUCTS[info["edition"]], saved_config(root, info["edition"]))
                finally:
                    ui.close()
            else:
                saved_config(root, info["edition"])
                if args.action == "backup":
                    if not args.offline_confirmed:
                        raise ComposeError("先停止此 Edition 的 Bot 和网关，再使用 --offline-confirmed")
                    backup = root / "backups"
                    if (backup.is_symlink() or backup.resolve() != backup.absolute()
                            or not os.path.samefile(backup, "/backups")):
                        raise ComposeError("备份挂载不属于当前部署目录，停止")
                    backup.chmod(0o700)
                    archive = Path("/backups") / ("TG2Cloud-" + info["edition"] + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4) + ".tar.gz")
                    pack(root, archive, info["edition"], VERSION)
                    print("离线配置／数据库备份完成：backups/" + archive.name)
                    print("不含 downloads、logs 或共享 HTTPS；备份包含秘密，请妥善保管。")
                else:
                    print(f"Compose 配置检查通过：{info['edition']} / v{VERSION}；不代表 Telegram、WebDAV 或实际转存通过。")
        return 0
    except ComposeError as exc:
        print("操作未完成：" + str(exc))
        return 1
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - never print private exception details
        print("操作未完成；请核对部署包版本、目录归属、剩余空间和初始化状态。未输出凭据。")
        return 1
