#!/usr/bin/env python3
"""TG2Cloud desktop deployer using a single-file PySide6 interface.

Keep ``vps_resources.py`` and both product payload directories beside this file, install the
versions pinned in ``requirements-build.txt``, then run ``python installer.py``.
Local diagnostics and preview commands do not connect to a VPS::

    python installer.py --preview
    python installer.py --check-deps
    python installer.py --self-test --self-test-result result.txt
    python installer.py --preview --screenshots preview/native

All GUI layout, SVG icons, style, validation, SSH, tunnel, deployment, repair,
WebDAV acceptance, resource-advice integration and redaction code is in here.
The existing project module and server scripts are dependencies, NOT replaced
by implementations invented for this UI. --preview never connects to a VPS.
No credentials are auto-saved locally and no packages are auto-installed.

Public entry points are ``main()``, ``InstallerWindow`` (also exported as
``InstallerApp`` for symbol compatibility), and ``packaged_self_test(Path)``.
InstallerApp is a Qt window, not a ``tk.Tk`` adapter. PyInstaller builds must
retain the bundled payload data.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
import re
import secrets
import select
import shlex
import socket
import socketserver
import sys
import tarfile
import tempfile
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit

from deployer_products import (
    CLOUDDRIVE2_PRODUCT,
    ProductProfile,
)

# ============================================================================
# 1. Constants, original configuration fields and payload manifest
# ============================================================================

APP_TITLE = CLOUDDRIVE2_PRODUCT.app_title
APP_VERSION = CLOUDDRIVE2_PRODUCT.app_version
UI_VERSION = "qt-1.0-single"
MANAGED_CD2_WEBDAV_URL = CLOUDDRIVE2_PRODUCT.webdav_url
EMPTY_FIELD = ""
BRAND_ICON_ASSET = "assets/brand/tg2cloud-icon-256.png"
BRAND_LOGO_ASSET = "assets/brand/tg2cloud-logo.svg"
REQUIRED_BRAND_ASSETS = (
    BRAND_ICON_ASSET,
    BRAND_LOGO_ASSET,
    "assets/brand/tg2cloud.ico",
)

def secure_password(length: int = 28) -> str:
    """Return a copy-friendly password from a cryptographic random source."""
    if not 24 <= length <= 32:
        raise ValueError("安全密码长度必须在 24 到 32 之间")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def defaults_for(product: ProductProfile) -> dict[str, str]:
    defaults = {
        "vps_host": "",
        "vps_port": "22",
        "vps_user": "root",
        "vps_password": EMPTY_FIELD,
        "ssh_key_path": "",
        "ssh_key_passphrase": EMPTY_FIELD,
        "sudo_password": EMPTY_FIELD,
        "bot_token": EMPTY_FIELD,
        "telegram_api_id": "",
        "telegram_api_hash": EMPTY_FIELD,
        "allowed_user_id": "",
        "cd2_url": product.webdav_url,
        "cd2_username": product.webdav_username,
        "cd2_password": EMPTY_FIELD,
        "cd2_target": product.webdav_target,
        "install_dir": product.install_dir,
        "local_budget_gb": "20",
        "min_free_disk_gb": "8",
        "timezone": "Asia/Shanghai",
        "auth_method": "密码",
        "deploy_clouddrive2": "true",
        "redeploy_apply_config": "false",
    }
    if product.is_openlist:
        defaults["cd2_password"] = secure_password()
        defaults["openlist_admin_password"] = secure_password()
        defaults["preserve_webdav"] = "false"
    return defaults


DEFAULTS = defaults_for(CLOUDDRIVE2_PRODUCT)
REQUIRED_PAYLOAD = CLOUDDRIVE2_PRODUCT.required_payload

SECRET_FIELDS = (
    "vps_password",
    "ssh_key_passphrase",
    "sudo_password",
    "bot_token",
    "telegram_api_hash",
    "cd2_password",
    "openlist_admin_password",
)
OPENLIST_ADMIN_SECRET_FIELD = SECRET_FIELDS[-1]


def resource_path(name: str) -> Path:
    # Resolve relative to THIS file (or the frozen bundle), not the working directory.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def dependency_report(
    product: ProductProfile = CLOUDDRIVE2_PRODUCT,
) -> dict[str, object]:
    modules: dict[str, bool] = {}
    for name in ("PySide6", "paramiko", "vps_resources"):
        try:
            modules[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, AttributeError):
            modules[name] = False
    missing = [
        name for name in product.required_payload if not resource_path(name).is_file()
    ]
    brand_missing = [
        name for name in REQUIRED_BRAND_ASSETS if not resource_path(name).is_file()
    ]
    return {
        "modules": modules,
        "payload_missing": missing,
        "brand_missing": brand_missing,
        "ready": all(modules.values()) and not missing and not brand_missing,
    }


# ============================================================================
# 2. Credential redaction and source UI labels
# ============================================================================


class Redactor:
    def __init__(self) -> None:
        self._secrets: set[str] = set()

    def update(self, values: dict[str, str]) -> None:
        # Retain old secrets too: changing a field must not expose old log lines.
        for key in SECRET_FIELDS:
            value = values.get(key, "")
            if not value:
                continue
            for candidate in {value, value.strip()}:
                if candidate:
                    self._secrets.add(candidate)
                    self._secrets.add(base64.b64encode(candidate.encode()).decode())
                    self._secrets.add(quote(candidate, safe=""))

    def clean(self, text: str) -> str:
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        # Remove other terminal control bytes, preserving tabs and line breaks.
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(
            r"(?i)((?:[A-Z_]*(?:PASSWORD|TOKEN|API_HASH|PASSPHRASE)[A-Z_]*)\s*[=:]\s*)([^\s]+)",
            r"\1[REDACTED]",
            text,
        )
        text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
        return text


FIELDS = {
    "vps_host": {"label": "VPS IP 或域名", "masked": False},
    "vps_port": {"label": "SSH 端口", "masked": False},
    "vps_user": {"label": "SSH 用户名", "masked": False},
    "vps_password": {"label": "VPS 登录密码", "masked": True},
    "ssh_key_path": {"label": "SSH 私钥文件", "masked": False},
    "ssh_key_passphrase": {"label": "私钥口令（没有则留空）", "masked": True},
    "sudo_password": {"label": "sudo 密码（root 或免密 sudo 留空）", "masked": True},
    "bot_token": {"label": "Bot Token", "masked": True},
    "telegram_api_id": {"label": "Telegram API ID", "masked": False},
    "telegram_api_hash": {"label": "Telegram API Hash", "masked": True},
    "allowed_user_id": {"label": "你的 Telegram 数字 ID", "masked": False},
    "cd2_url": {"label": "WebDAV 地址（同机安装保持默认）", "masked": False},
    "cd2_username": {"label": "WebDAV 用户名", "masked": False},
    "cd2_password": {"label": "WebDAV 密码", "masked": True},
    "cd2_target": {"label": "WebDAV 根目录后的子目录（可留空）", "masked": False},
    "openlist_admin_password": {
        "label": "OpenList 管理员密码（首次／恢复）",
        "masked": True,
    },
    "install_dir": {"label": "安装目录", "masked": False},
    "local_budget_gb": {"label": "本地任务预算（GB）", "masked": False},
    "min_free_disk_gb": {"label": "磁盘最少保留（GB）", "masked": False},
    "timezone": {"label": "时区", "masked": False},
}

SOURCE_HINTS = {
    "_build_ui": [],
    "_build_vps_tab": ["首次连接会显示 VPS 主机密钥指纹，确认后才会保存并继续。"],
    "_build_telegram_tab": [
        "Bot Token 来自 @BotFather；API ID 和 API Hash 来自 my.telegram.org；数字 ID 用于限制只有你本人可以使用。"
    ],
    "_build_cloud_tab": [
        "部署完成后点击“打开 CloudDrive2 管理页”，登录 CloudDrive2、添加并挂载你的云存储（例如 115），然后开启 WebDAV。如果 WebDAV 根目录已经选中目标 Telegram 文件夹，子目录必须留空；只有根目录在更上层时才填写相对路径。"
    ],
    "_build_options_tab": [
        "源码默认仍为 20GB 本地任务预算和 8GB 磁盘安全线。检测只提供当前 VPS 的实例建议，点击应用后才会改输入框；部署前还会重新检测。单文件超过本地预算时自动使用流式模式。"
    ],
    "_build_config": [],
}


# ============================================================================
# 3. SSH transport, host-key confirmation and localhost tunnel
# ============================================================================

_SSH_IMPORT_ERROR: Exception | None = None
try:
    import paramiko
except (ImportError, OSError) as exc:
    # Leave --preview / --check-deps usable; never provide a fake SSH client.
    _SSH_IMPORT_ERROR = exc

if _SSH_IMPORT_ERROR is None:

    def b64(value: str) -> str:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    def fingerprint_sha256(key: paramiko.PKey) -> str:
        digest = hashlib.sha256(key.asbytes()).digest()
        return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")

    def normalize_ssh_host(host: str) -> str:
        """Return a Paramiko/socket compatible host without IPv6 URL brackets."""
        value = host.strip()
        if value.startswith("[") and value.endswith("]") and ":" in value:
            return value[1:-1]
        return value

    def ssh_host_key_name(host: str, port: int) -> str:
        """Match Paramiko's known_hosts identity for default and custom ports."""
        normalized = normalize_ssh_host(host)
        return normalized if port == 22 else f"[{normalized}]:{port}"

    def ssh_server_label(host: str, port: int) -> str:
        normalized = normalize_ssh_host(host)
        display_host = f"[{normalized}]" if ":" in normalized else normalized
        return f"{display_host}:{port}"

    @dataclass(frozen=True)
    class HostKeyChallenge:
        reason: str
        host: str
        port: int
        host_key_name: str
        new_key_type: str
        new_fingerprint: str
        old_key_type: str = ""
        old_fingerprint: str = ""

        @property
        def server(self) -> str:
            return ssh_server_label(self.host, self.port)

    class UserRejectedHostKey(paramiko.SSHException):
        user_cancelled = True

    class HostKeyStorageError(RuntimeError):
        pass

    class SSHConnectionFailure(RuntimeError):
        pass

    class KnownHostsStore:
        """Atomic, target-scoped persistence for the deployer's host keys."""

        def __init__(self, path: Path):
            self.path = path

        def load(self) -> paramiko.HostKeys:
            host_keys = paramiko.HostKeys()
            if not self.path.exists():
                return host_keys
            try:
                host_keys.load(str(self.path))
            except (OSError, ValueError, paramiko.SSHException) as exc:
                raise HostKeyStorageError(
                    f"SSH 主机记录无法读取：{self.path}。请检查文件格式和访问权限。"
                ) from exc
            return host_keys

        def _save(self, host_keys: paramiko.HostKeys) -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path: Path | None = None
            try:
                descriptor, temp_name = tempfile.mkstemp(
                    prefix=".known_hosts-", dir=self.path.parent
                )
                os.close(descriptor)
                temp_path = Path(temp_name)
                host_keys.save(str(temp_path))
                os.replace(temp_path, self.path)
            except OSError as exc:
                raise HostKeyStorageError(
                    f"SSH 主机记录无法安全写入：{self.path}。请检查目录权限。"
                ) from exc
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)

        def remember_first(self, host_key_name: str, key: paramiko.PKey) -> None:
            host_keys = self.load()
            recorded = host_keys.lookup(host_key_name)
            if recorded is not None:
                current = recorded.get(key.get_name())
                if current == key:
                    return
                raise HostKeyStorageError(
                    "SSH 主机记录在确认期间发生了变化。为避免覆盖其他连接结果，本次连接已停止。"
                )
            host_keys.add(host_key_name, key.get_name(), key)
            self._save(host_keys)

        def replace_changed_key(
            self,
            host_key_name: str,
            expected_key: paramiko.PKey,
            new_key: paramiko.PKey,
        ) -> None:
            """Replace only the confirmed target/key, preserving every other entry."""
            host_keys = self.load()
            recorded = host_keys.lookup(host_key_name)
            if recorded is None or not any(
                candidate == expected_key for candidate in recorded.values()
            ):
                raise HostKeyStorageError(
                    "SSH 主机记录在确认期间已被其他程序修改，本次没有覆盖该文件。请重新测试连接。"
                )

            matched = False
            # Paramiko's mapping deletion removes an entire multi-host entry. Split
            # only the matching alias so a combined known_hosts line cannot make us
            # delete another server while replacing this target.
            for entry in list(host_keys._entries):
                if entry.key is None or entry.key != expected_key:
                    continue
                retained: list[str] = []
                removed = False
                for alias in entry.hostnames:
                    alias_entry = paramiko.hostkeys.HostKeyEntry([alias], entry.key)
                    if host_keys._hostname_matches(host_key_name, alias_entry):
                        removed = True
                    else:
                        retained.append(alias)
                if not removed:
                    continue
                matched = True
                if retained:
                    entry.hostnames = retained
                else:
                    host_keys._entries.remove(entry)

            if not matched:
                raise HostKeyStorageError(
                    "SSH 主机记录无法精确定位，本次没有修改 known_hosts。请重新测试连接。"
                )
            host_keys.add(host_key_name, new_key.get_name(), new_key)
            self._save(host_keys)

    class ConfirmHostKeyPolicy(paramiko.MissingHostKeyPolicy):
        def __init__(
            self,
            confirm: Callable[[HostKeyChallenge], bool],
            store: KnownHostsStore,
            host: str,
            port: int,
            log: Callable[[str], None],
        ):
            self.confirm = confirm
            self.store = store
            self.host = host
            self.port = port
            self.log = log

        def missing_host_key(
            self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey
        ) -> None:
            fingerprint = fingerprint_sha256(key)
            challenge = HostKeyChallenge(
                reason="first_seen",
                host=self.host,
                port=self.port,
                host_key_name=hostname,
                new_key_type=key.get_name(),
                new_fingerprint=fingerprint,
            )
            self.log(
                f"[SSH 主机密钥：首次发现] {challenge.server} / "
                f"{challenge.new_key_type} / {challenge.new_fingerprint}"
            )
            if not self.confirm(challenge):
                raise UserRejectedHostKey(
                    "已取消连接：未信任首次发现的 SSH 主机密钥；主机记录未修改。"
                )
            self.store.remember_first(hostname, key)
            client._host_keys.add(hostname, key.get_name(), key)
            self.log(f"[SSH 主机密钥：已保存] {challenge.server}")

    class RemoteSession:
        def __init__(
            self,
            values: dict[str, str],
            confirm_host_key: Callable[[HostKeyChallenge], bool],
            log: Callable[[str], None] | None = None,
            client_factory: Callable[[], paramiko.SSHClient] = paramiko.SSHClient,
        ):
            self.values = values
            self.confirm_host_key = confirm_host_key
            self.log = log or (lambda _message: None)
            self.host = normalize_ssh_host(values["vps_host"])
            self.port = int(values["vps_port"])
            app_data = Path(os.getenv("APPDATA", Path.home()))
            self.known_hosts = app_data / "TG2Cloud-Deployer" / "known_hosts"
            legacy_known_hosts = app_data / "TG115-Deployer" / "known_hosts"
            if legacy_known_hosts.is_file() and not self.known_hosts.exists():
                self.log(
                    "检测到旧 TG115 SSH 主机记录；TG2Cloud 不会自动导入或覆盖，"
                    "首次连接时请重新核对主机指纹。"
                )
            self.host_keys = KnownHostsStore(self.known_hosts)
            self.client_factory = client_factory
            self.client = self._new_client()

        def _new_client(self) -> paramiko.SSHClient:
            client = self.client_factory()
            if self.known_hosts.exists():
                try:
                    client.load_host_keys(str(self.known_hosts))
                except (OSError, ValueError, paramiko.SSHException) as exc:
                    client.close()
                    raise HostKeyStorageError(
                        f"SSH 主机记录无法读取：{self.known_hosts}。请检查文件格式和访问权限。"
                    ) from exc
            client.set_missing_host_key_policy(self._host_key_policy())
            return client

        def _host_key_policy(self) -> ConfirmHostKeyPolicy:
            return ConfirmHostKeyPolicy(
                self.confirm_host_key,
                self.host_keys,
                self.host,
                self.port,
                self.log,
            )

        def set_log(self, log: Callable[[str], None]) -> None:
            self.log = log
            self.client.set_missing_host_key_policy(self._host_key_policy())

        def _connection_kwargs(self) -> dict[str, object]:
            kwargs: dict[str, object] = {
                "hostname": self.host,
                "port": self.port,
                "username": self.values["vps_user"].strip(),
                "timeout": 15,
                "banner_timeout": 20,
                "auth_timeout": 20,
                "look_for_keys": False,
                "allow_agent": False,
            }
            if self.values["auth_method"] == "密码":
                kwargs["password"] = self.values["vps_password"]
            else:
                kwargs["key_filename"] = self.values["ssh_key_path"]
                passphrase = self.values["ssh_key_passphrase"]
                if passphrase:
                    kwargs["passphrase"] = passphrase
            return kwargs

        def connect(self) -> None:
            kwargs = self._connection_kwargs()
            target = ssh_server_label(self.host, self.port)
            key_updated = False
            while True:
                try:
                    self.client.connect(**kwargs)
                except UserRejectedHostKey:
                    self.client.close()
                    raise
                except paramiko.BadHostKeyException as exc:
                    self.client.close()
                    if key_updated:
                        self.log(
                            f"[SSH 主机密钥：重连仍不一致] {target}；已停止，未继续覆盖记录。"
                        )
                        raise SSHConnectionFailure(
                            "SSH 主机密钥在更新后再次变化。为避免连接到错误服务器，已停止重连。"
                        ) from exc
                    challenge = HostKeyChallenge(
                        reason="changed",
                        host=self.host,
                        port=self.port,
                        host_key_name=ssh_host_key_name(self.host, self.port),
                        old_key_type=exc.expected_key.get_name(),
                        old_fingerprint=fingerprint_sha256(exc.expected_key),
                        new_key_type=exc.key.get_name(),
                        new_fingerprint=fingerprint_sha256(exc.key),
                    )
                    self.log(
                        f"[SSH 主机密钥：发生变化] {challenge.server} / "
                        f"旧 {challenge.old_key_type} {challenge.old_fingerprint} / "
                        f"新 {challenge.new_key_type} {challenge.new_fingerprint}"
                    )
                    if not self.confirm_host_key(challenge):
                        raise UserRejectedHostKey(
                            "已取消连接：SSH 主机密钥变化未获确认；原主机记录保持不变。"
                        ) from exc
                    self.host_keys.replace_changed_key(
                        challenge.host_key_name, exc.expected_key, exc.key
                    )
                    self.log(
                        f"[SSH 主机密钥：已更新] 仅替换 {challenge.server} 的对应记录；"
                        "正在自动重连（1/1）。"
                    )
                    key_updated = True
                    self.client = self._new_client()
                    continue
                except paramiko.AuthenticationException as exc:
                    self.client.close()
                    detail = "（主机密钥已更新并通过校验）" if key_updated else ""
                    self.log(f"[SSH 身份认证失败] {target}{detail}")
                    raise SSHConnectionFailure(
                        "SSH 身份认证失败：服务器身份已核验，但用户名、密码、私钥或私钥口令不正确。"
                    ) from exc
                except paramiko.ssh_exception.NoValidConnectionsError as exc:
                    self.client.close()
                    self.log(f"[SSH 端口不可达] {target}")
                    raise SSHConnectionFailure(
                        f"无法连接 SSH 端口 {target}。请检查 VPS 是否开机、端口和安全组设置。"
                    ) from exc
                except socket.gaierror as exc:
                    self.client.close()
                    self.log(f"[SSH 域名解析失败] {target}")
                    raise SSHConnectionFailure(
                        f"无法解析 VPS 地址：{self.host}。请检查域名或 IP。"
                    ) from exc
                except TimeoutError as exc:
                    self.client.close()
                    self.log(f"[SSH 连接超时] {target}")
                    raise SSHConnectionFailure(
                        f"SSH 连接超时：{target}。请检查网络、端口和安全组。"
                    ) from exc
                except paramiko.SSHException as exc:
                    self.client.close()
                    self.log(f"[SSH 协议错误] {target} / {type(exc).__name__}")
                    raise SSHConnectionFailure(
                        "SSH 握手或协议协商失败。请确认目标端口确实是 SSH 服务并稍后重试。"
                    ) from exc
                except OSError as exc:
                    self.client.close()
                    self.log(f"[SSH 网络错误] {target} / {type(exc).__name__}")
                    raise SSHConnectionFailure(
                        f"SSH 网络连接失败：{target}。请检查本机网络和 VPS 防火墙。"
                    ) from exc
                except Exception:
                    self.client.close()
                    raise
                transport = self.client.get_transport()
                if transport:
                    transport.set_keepalive(30)
                self.log(f"[SSH 连接成功] {target}；主机身份校验已通过。")
                return

        def close(self) -> None:
            self.client.close()

        def run(
            self,
            command: str,
            *,
            sudo: bool = False,
            stream: Callable[[str], None] | None = None,
            timeout: float | None = None,
        ) -> tuple[int, str]:
            transport = self.client.get_transport()
            if transport is None or not transport.is_active():
                raise RuntimeError("SSH 连接已经断开")
            channel = transport.open_session(timeout=15)
            actual = (
                f"sudo -S -p '' -- /bin/bash -c {shlex.quote(command)}"
                if sudo
                else command
            )
            try:
                channel.exec_command(actual)  # nosec B601
                if sudo:
                    channel.sendall(
                        (self.values.get("sudo_password", "") + "\n").encode("utf-8")
                    )
                channel.shutdown_write()
                import codecs

                decoders = {
                    False: codecs.getincrementaldecoder("utf-8")("replace"),
                    True: codecs.getincrementaldecoder("utf-8")("replace"),
                }
                pending = {False: "", True: ""}
                output: list[str] = []
                started = time.monotonic()

                def consume(chunk: bytes, stderr: bool, final: bool = False) -> None:
                    text = decoders[stderr].decode(chunk, final=final)
                    output.append(text)
                    pending[stderr] += text
                    while "\n" in pending[stderr]:
                        line, pending[stderr] = pending[stderr].split("\n", 1)
                        if stream:
                            stream(line.rstrip("\r"))

                while True:
                    if timeout is not None and time.monotonic() - started > timeout:
                        raise TimeoutError(f"远程命令超时：{timeout:g}s")
                    if channel.recv_ready():
                        consume(channel.recv(65536), False)
                    if channel.recv_stderr_ready():
                        consume(channel.recv_stderr(65536), True)
                    if (
                        channel.exit_status_ready()
                        and (not channel.recv_ready())
                        and (not channel.recv_stderr_ready())
                    ):
                        break
                    time.sleep(0.03)
                for stderr in (False, True):
                    consume(b"", stderr, final=True)
                    if pending[stderr] and stream:
                        stream(pending[stderr].rstrip("\r"))
                return (channel.recv_exit_status(), "".join(output))
            finally:
                channel.close()

        def sftp(self) -> paramiko.SFTPClient:
            return self.client.open_sftp()

    class ForwardHandler(socketserver.BaseRequestHandler):
        ssh_transport: paramiko.Transport
        remote_host = "127.0.0.1"
        remote_port = 19798
        report_error: Callable[[Exception], None]

        def handle(self) -> None:
            try:
                channel = self.ssh_transport.open_channel(
                    "direct-tcpip",
                    (self.remote_host, self.remote_port),
                    self.request.getpeername(),
                    timeout=10,
                )
            except (OSError, paramiko.SSHException) as exc:
                self.report_error(exc)
                return
            if channel is None:
                self.report_error(RuntimeError("SSH 服务没有创建端口转发通道"))
                return
            try:
                while True:
                    readable, _, _ = select.select([self.request, channel], [], [], 1)
                    if self.request in readable:
                        data = self.request.recv(65536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in readable:
                        data = channel.recv(65536)
                        if not data:
                            break
                        self.request.sendall(data)
            except (OSError, EOFError, ValueError, paramiko.SSHException) as exc:
                self.report_error(exc)
            finally:
                channel.close()
                self.request.close()

    class TunnelServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    class Tunnel:
        def __init__(
            self,
            session: RemoteSession,
            local_port: int = 19798,
            remote_port: int | None = None,
            product_name: str = "CloudDrive2",
        ):
            transport = session.client.get_transport()
            if transport is None:
                raise RuntimeError("SSH 连接不可用")
            self.remote_port = remote_port if remote_port is not None else local_port
            self.product_name = product_name
            self._error_lock = threading.Lock()
            self._last_error: Exception | None = None
            self._closed = False
            handler_type = type(
                "CloudDriveForwardHandler",
                (ForwardHandler,),
                {
                    "ssh_transport": transport,
                    "remote_port": self.remote_port,
                    "report_error": staticmethod(self._report_error),
                },
            )
            self.session = session
            try:
                self.server = TunnelServer(("127.0.0.1", local_port), handler_type)
            except OSError as exc:
                raise RuntimeError(
                    f"本机 SSH 隧道端口 127.0.0.1:{local_port} 无法使用，请关闭占用该端口的程序后重试。"
                ) from exc
            self.port = int(self.server.server_address[1])
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                name=f"{self.product_name.lower()}-tunnel",
                daemon=True,
            )

        @property
        def url(self) -> str:
            return f"http://127.0.0.1:{self.port}"

        def _report_error(self, error: Exception) -> None:
            with self._error_lock:
                self._last_error = error

        def _clear_error(self) -> None:
            with self._error_lock:
                self._last_error = None

        def _get_error(self) -> Exception | None:
            with self._error_lock:
                return self._last_error

        def _probe_error(self, error: Exception | None) -> RuntimeError:
            detail = str(error).strip() if error else "没有收到任何 HTTP 响应"
            forwarding_denied = (
                isinstance(error, paramiko.ChannelException)
                and error.code == paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
                or "administratively prohibited" in detail.lower()
            )
            if forwarding_denied:
                return RuntimeError(
                    "VPS 的 SSH 服务禁止 TCP 端口转发。请检查 sshd 的 "
                    f"AllowTcpForwarding，并允许 PermitOpen 127.0.0.1:{self.remote_port}；"
                    f"部署器不会把 {self.product_name} 管理端口暴露到公网。"
                )
            return RuntimeError(
                f"SSH 隧道已建立，但没有收到 {self.product_name} 管理页响应：{detail}。"
                f"请关闭部署器后重试，并确认 VPS 本机的 {self.remote_port} 端口仍可访问。"
            )

        def start(self) -> None:
            self.thread.start()

        def probe(self, timeout: float = 10) -> None:
            """Verify the exact local URL before handing it to a browser."""
            self._clear_error()
            request = f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nConnection: close\r\n\r\n".encode(
                "ascii"
            )
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.port), timeout=timeout
                ) as connection:
                    connection.settimeout(timeout)
                    connection.sendall(request)
                    response = connection.recv(4096)
            except OSError as exc:
                error = self._get_error() or exc
                raise self._probe_error(error) from error
            if not response.startswith(b"HTTP/"):
                error = self._get_error()
                raise self._probe_error(error) from error

        def close(self) -> None:
            if self._closed:
                return
            self._closed = True
            if self.thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
            self.session.close()

    def re_safe_remote_stage(path: str) -> bool:
        prefix = "/tmp/tg2cloud-deploy-"  # nosec B108
        suffix = path.removeprefix(prefix)
        return (
            path.startswith(prefix)
            and len(suffix) == 32
            and all(char in "0123456789abcdef" for char in suffix)
        )


# ============================================================================
# 4. Original-project resource integration and all remote operations
# ============================================================================

_BACKEND_IMPORT_ERROR: Exception | None = _SSH_IMPORT_ERROR
if _BACKEND_IMPORT_ERROR is None:
    try:
        from vps_resources import (
            GIB,
            StorageAdvice,
            StoragePlan,
            VpsResources,
            assess_storage_choice,
            build_probe_command,
            parse_probe_output,
            recommend_storage,
            validate_install_dir,
        )
    except (ImportError, AttributeError) as exc:
        _BACKEND_IMPORT_ERROR = exc

if _BACKEND_IMPORT_ERROR is None:

    @dataclass(frozen=True)
    class OperationResult:
        title: str
        message: str
        statuses: tuple[tuple[str, str], ...] = ()
        secret_field: str = ""
        secret_value: str = field(default="", repr=False, compare=False)
        openlist_state: str = ""

    class OperationError(RuntimeError):
        """An operation failure that can still expose safe structured status."""

        def __init__(
            self, message: str, statuses: tuple[tuple[str, str], ...] = ()
        ) -> None:
            super().__init__(message)
            self.statuses = statuses

    _MACHINE_MARKER = re.compile(r"^(TG2CLOUD|TG115)_([A-Z0-9_]+)=(.*)$")

    def machine_markers(output: str) -> dict[str, str]:
        """Read current protocol first; TG115 markers are legacy compatibility."""
        current: dict[str, str] = {}
        legacy: dict[str, str] = {}
        for line in output.splitlines():
            matched = _MACHINE_MARKER.fullmatch(line.strip())
            if matched is None:
                continue
            namespace, key, value = matched.groups()
            (current if namespace == "TG2CLOUD" else legacy)[key] = value
        return legacy | current

    def runtime_status_command(product: ProductProfile, install_dir: str) -> str:
        """Read-only VPS probe; legacy names are detection-only, never targets."""
        legacy_checks = [
            f"test -e {shlex.quote(path)}" for path in product.legacy_install_dirs
        ] + [
            f"docker container inspect {shlex.quote(name)} >/dev/null 2>&1"
            for name in product.legacy_containers
        ]
        script = f"""
install_dir={shlex.quote(install_dir)}
if {' || '.join(legacy_checks)}; then
  printf 'TG2CLOUD_LEGACY=DETECTED\\n'
else
  printf 'TG2CLOUD_LEGACY=NONE\\n'
fi
if [[ -L "$install_dir" ]]; then
  printf 'TG2CLOUD_STATUS=UNKNOWN\\n'
  exit 2
fi
if [[ ! -f "$install_dir/docker-compose.yml" ]]; then
  printf 'TG2CLOUD_STATUS=NOT_INSTALLED\\n'
  exit 0
fi
if ! grep -Fq {shlex.quote('container_name: ' + product.bot_container)} "$install_dir/docker-compose.yml" \
  || ! grep -Fq {shlex.quote('container_name: ' + product.storage_container)} "$install_dir/docker-compose.yml"; then
  printf 'TG2CLOUD_STATUS=UNKNOWN\\n'
  exit 2
fi
bot_health="$(docker inspect --format '{{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{else}}}}{{{{.State.Status}}}}{{{{end}}}}' {shlex.quote(product.bot_container)} 2>/dev/null || true)"
gateway_running="$(docker inspect --format '{{{{.State.Running}}}}' {shlex.quote(product.storage_container)} 2>/dev/null || true)"
if docker network inspect {shlex.quote(product.docker_network)} >/dev/null 2>&1; then network=PRESENT; else network=MISSING; fi
if [[ {shlex.quote(product.key)} == clouddrive2 ]] \
  && grep -Fxq 'DEPLOY_CLOUDDRIVE2=false' "$install_dir/.env"; then
  gateway=EXTERNAL
elif [[ "$gateway_running" == true ]]; then gateway=RUNNING
else gateway=STOPPED
fi
if [[ {shlex.quote(product.key)} == openlist && "$gateway" == RUNNING ]] \
  && ! curl -fsS --max-time 3 http://127.0.0.1:5244/ >/dev/null 2>&1; then
  gateway=UNHEALTHY
fi
printf 'TG2CLOUD_BOT_HEALTH=%s\\nTG2CLOUD_GATEWAY=%s\\nTG2CLOUD_NETWORK=%s\\n' "${{bot_health:-missing}}" "$gateway" "$network"
if [[ "$bot_health" == healthy && "$network" == PRESENT ]] \
  && [[ "$gateway" == RUNNING || "$gateway" == EXTERNAL ]]; then
  printf 'TG2CLOUD_STATUS=RUNNING\\n'
else
  printf 'TG2CLOUD_STATUS=STOPPED\\n'
fi
"""
        return "bash -c " + shlex.quote(script)

    _VERIFICATION_STEPS = (
        ("OpenList 服务", "OPENLIST"),
        ("WebDAV 认证", "WEBDAV_AUTH"),
        ("目标目录", "WEBDAV_LIST"),
        ("测试写入", "WEBDAV_WRITE"),
        ("大小校验", "WEBDAV_SIZE"),
        ("临时改名", "WEBDAV_MOVE"),
        ("测试清理", "WEBDAV_DELETE"),
    )

    def verification_statuses(output: str) -> tuple[tuple[str, str], ...]:
        markers = machine_markers(output)
        bot_health = markers.get("BOT_HEALTH")
        if bot_health is None:
            # Legacy TG115 compatibility: early verify scripts emitted an unprefixed key.
            bot_health = next(
                (line.partition("=")[2] for line in output.splitlines()
                 if line.startswith("BOT_HEALTH=")),
                None,
            )
        statuses: list[tuple[str, str]] = [
            ("Bot 容器", "通过" if bot_health == "healthy" else "失败" if bot_health else "未执行")
        ]
        for title, key in _VERIFICATION_STEPS:
            value = markers.get(key)
            state = "通过" if value == "OK" else "失败" if value == "FAILED" else "未执行"
            statuses.append((title, state))
        return tuple(statuses)

    @dataclass(frozen=True)
    class ResourceUpdate:
        resources: VpsResources
        advice: StorageAdvice
        basis: tuple[str, str, str, str, bool]
        summary: str

    class InstallerBackend:
        def __init__(
            self,
            log: Callable[[str], None],
            confirm_host_key: Callable[[HostKeyChallenge], bool],
            publish_resources: Callable[[ResourceUpdate], None],
            session_factory=RemoteSession,
            tunnel_factory=Tunnel,
            browser_open=webbrowser.open,
            product: ProductProfile = CLOUDDRIVE2_PRODUCT,
        ):
            self.product = product
            self._log = log
            self._ask_host_key = confirm_host_key
            self._publish_resources = publish_resources
            self._session_factory = session_factory
            self._tunnel_factory = tunnel_factory
            self._browser_open = browser_open
            self.tunnel = None
            self._tunnel_identity = None
            self.vps_resources = None
            self.storage_advice = None
            self.storage_probe_basis = None

        @staticmethod
        def connection_identity(values: dict[str, str]) -> tuple[str, str, str]:
            return (
                normalize_ssh_host(values["vps_host"]).lower(),
                str(int(values["vps_port"])),
                values["vps_user"].strip(),
            )

        def close(self) -> None:
            if self.tunnel is not None:
                try:
                    self.tunnel.close()
                finally:
                    self.tunnel = None
                    self._tunnel_identity = None

        def _publish_resource_advice(self, resources, advice, basis) -> None:
            self.vps_resources, self.storage_advice = resources, advice
            self.storage_probe_basis = basis
            summary = self._resource_summary_text(resources, advice)
            self._log(summary)
            self._publish_resources(ResourceUpdate(resources, advice, basis, summary))

        def _storage_probe_basis(
            self, values: dict[str, str]
        ) -> tuple[str, str, str, str, bool]:
            # ``managed_clouddrive`` is retained in vps_resources for backwards
            # compatibility. OpenList has no FUSE/cache requirement.
            managed_clouddrive = (
                self.product.key == "clouddrive2"
                and values.get("deploy_clouddrive2", "true") == "true"
            )
            return (
                *self.connection_identity(values),
                validate_install_dir(values["install_dir"]),
                managed_clouddrive,
            )

        def storage_plan(self, key: str, values: dict[str, str]) -> tuple[str, str]:
            if key not in {"balanced", "stream_first"}:
                raise ValueError("Unknown storage plan")
            if self.storage_advice is None or self.storage_probe_basis is None:
                raise ValueError("请先检测 VPS 并生成建议。")
            if self._storage_probe_basis(values) != self.storage_probe_basis:
                raise ValueError("VPS、安装目录或部署方式已变化，请重新检测。")
            plan = getattr(self.storage_advice, key)
            if not plan.safe:
                raise ValueError(plan.reason)
            self._log(f"已应用{plan.label}：{plan.budget_gb}/{plan.reserve_gb}GB")
            return str(plan.budget_gb), str(plan.reserve_gb)

        def _validate(self, values: dict[str, str]) -> None:
            self._validate_connection(values)
            required = {
                "bot_token": FIELDS["bot_token"]["label"],
                "telegram_api_id": "Telegram API ID",
                "telegram_api_hash": FIELDS["telegram_api_hash"]["label"],
                "allowed_user_id": "Telegram 数字 ID",
                "cd2_url": f"{self.product.display_name} WebDAV 地址",
                "cd2_username": "WebDAV 用户名",
                "cd2_password": FIELDS["cd2_password"]["label"],
            }
            if self.product.is_openlist:
                required["openlist_admin_password"] = FIELDS[
                    "openlist_admin_password"
                ]["label"]
            for name, label in required.items():
                if not values.get(name, "").strip():
                    raise ValueError(f"请填写：{label}")
            try:
                api_id = int(values["telegram_api_id"])
                user_id = int(values["allowed_user_id"])
                budget = float(values["local_budget_gb"])
                reserve = float(values["min_free_disk_gb"])
            except ValueError as exc:
                raise ValueError("端口、API ID、数字 ID 和磁盘数值必须是数字") from exc
            if api_id <= 0 or user_id <= 0:
                raise ValueError("API ID 和 Telegram 数字 ID 必须大于 0")
            if not math.isfinite(budget) or not math.isfinite(reserve):
                raise ValueError("磁盘预算与安全线必须是有限数字")
            if budget <= 0 or reserve <= 0:
                raise ValueError("磁盘预算与安全线必须大于 0")
            token = values["bot_token"].strip()
            if ":" not in token or len(token) < 25:
                raise ValueError("Bot Token 格式看起来不正确")
            api_hash = values["telegram_api_hash"].strip()
            if len(api_hash) != 32 or any(
                c not in "0123456789abcdefABCDEF" for c in api_hash
            ):
                raise ValueError("Telegram API Hash 应为 32 位十六进制字符")
            if self.product.is_openlist:
                for name, label in (
                    ("cd2_password", "WebDAV 密码"),
                    ("openlist_admin_password", "OpenList 首次管理员密码"),
                ):
                    secret = values[name]
                    if not 24 <= len(secret) <= 32:
                        raise ValueError(f"{label}长度必须为 24 到 32 个字符")
                    if any(char.isspace() or ord(char) < 33 for char in secret):
                        raise ValueError(f"{label}不能包含空格或控制字符")
                    if not re.fullmatch(r"[A-Za-z0-9_-]+", secret):
                        raise ValueError(
                            f"{label}只能包含英文字母、数字、连字符和下划线"
                        )
            url = self._effective_webdav_url(values)
            if not url.startswith(("http://", "https://")):
                raise ValueError("WebDAV 地址必须以 http:// 或 https:// 开头")
            parsed_url = urlsplit(url)
            if not parsed_url.hostname:
                raise ValueError("WebDAV 地址缺少有效主机名")
            if parsed_url.username or parsed_url.password:
                raise ValueError(
                    "WebDAV 用户名和密码应填写在专用输入框，不能放在地址中"
                )
            try:
                _ = parsed_url.port
            except ValueError as exc:
                raise ValueError("WebDAV 地址端口格式不正确") from exc
            if parsed_url.query or parsed_url.fragment:
                raise ValueError("WebDAV 地址不能包含查询参数或片段")
            if any(ord(char) < 32 or char.isspace() for char in url):
                raise ValueError("WebDAV 地址不能包含空格或控制字符")
            if parsed_url.scheme == "http":
                host = parsed_url.hostname.lower()
                try:
                    address = ipaddress.ip_address(host)
                    private_http = (
                        address.is_private
                        or address.is_loopback
                        or address.is_link_local
                    )
                except ValueError:
                    private_http = (
                        "." not in host
                        or host == "localhost"
                        or host.endswith((".local", ".internal"))
                    )
                if not private_http:
                    raise ValueError("公网 WebDAV 地址必须使用 HTTPS，避免密码明文传输")
            target = values["cd2_target"].strip()
            if any(ord(char) < 32 for char in target) or "\\" in target:
                raise ValueError("WebDAV 目标路径不能包含控制字符或反斜杠")
            if ".." in target.split("/"):
                raise ValueError("WebDAV 目标路径不能包含 ..")
            install_dir = validate_install_dir(values["install_dir"])
            if install_dir in self.product.legacy_install_dirs:
                raise ValueError(
                    f"检测到旧 TG115 安装目录 {install_dir}；TG2Cloud 不会静默覆盖，"
                    "请改用当前版本的默认目录，或先按迁移文档处理旧部署"
                )
            if not re.fullmatch("[A-Za-z0-9_+./-]+", values["timezone"]):
                raise ValueError("时区格式不正确")
            if values["timezone"].startswith("/") or any(
                part in {".", ".."} for part in values["timezone"].split("/")
            ):
                raise ValueError("时区格式不正确")

        def _effective_webdav_url(self, values: dict[str, str]) -> str:
            if self.product.is_openlist:
                return self.product.webdav_url
            if values.get("deploy_clouddrive2", "true") == "true":
                return self.product.webdav_url
            return values["cd2_url"].strip()

        def _validate_connection(self, values: dict[str, str]) -> None:
            for name, label in (
                ("vps_host", "VPS IP 或域名"),
                ("vps_port", "SSH 端口"),
                ("vps_user", "SSH 用户名"),
            ):
                if not values.get(name, "").strip():
                    raise ValueError(f"请填写：{label}")
            if any(
                ord(char) < 32 or char.isspace() for char in values["vps_host"].strip()
            ):
                raise ValueError("VPS IP 或域名不能包含空格或控制字符")
            try:
                port = int(values["vps_port"])
            except ValueError as exc:
                raise ValueError("SSH 端口必须是数字") from exc
            if not 1 <= port <= 65535:
                raise ValueError("SSH 端口必须在 1–65535 之间")
            if any(char in values["vps_user"] for char in "\r\n"):
                raise ValueError("SSH 用户名格式不正确")
            if any(char in values.get("sudo_password", "") for char in "\r\n"):
                raise ValueError("sudo 密码不能包含换行符")
            if values["auth_method"] == "密码":
                if not values["vps_password"]:
                    raise ValueError("密码登录方式必须填写 VPS 登录密码")
            else:
                key_path = Path(values["ssh_key_path"])
                if not key_path.is_file():
                    raise ValueError("SSH 私钥文件不存在")

        def _new_session(self, values: dict[str, str]) -> RemoteSession:
            session = self._session_factory(values, self._ask_host_key)
            if isinstance(session, RemoteSession):
                session.set_log(self._log)
            session.connect()
            return session

        @staticmethod
        def _plan_summary(plan: StoragePlan, preferred_key: str | None) -> str:
            marker = "（推荐）" if plan.key == preferred_key else ""
            if not plan.safe:
                return f"{plan.label}{marker}：不可安全应用，{plan.reason}"
            return f"{plan.label}{marker}：本地预算 {plan.budget_gb}GB，最少保留 {plan.reserve_gb}GB"

        def _resource_summary_text(
            self, resources: VpsResources, advice: StorageAdvice
        ) -> str:
            memory_total = resources.memory_total_bytes / GIB
            memory_available = resources.memory_available_bytes / GIB
            swap_total = resources.swap_total_bytes / GIB
            storage_total = resources.storage_total_bytes / GIB
            storage_available = resources.storage_available_bytes / GIB
            install_used = resources.install_used_bytes / GIB
            backups_used = resources.backups_used_bytes / GIB
            if resources.docker_same_filesystem:
                docker_storage = "与安装目录位于同一文件系统"
            else:
                detected = (
                    "Docker 已报告实际目录"
                    if resources.docker_root_detected
                    else "按默认目录估算"
                )
                docker_available = resources.docker_storage_available_bytes / GIB
                docker_storage = (
                    f"位于另一文件系统，可用 {docker_available:.1f}GB（{detected}）"
                )
            fuse = "可用" if resources.fuse_available else "不可用"
            return f"检测结果：{resources.cpu_cores} 核 / 内存 {memory_total:.1f}GB（可用 {memory_available:.1f}GB）/ Swap {swap_total:.1f}GB；存储 {storage_total:.1f}GB（可用 {storage_available:.1f}GB，{resources.filesystem_type}）；当前安装目录占用 {install_used:.1f}GB；历史备份占用 {backups_used:.1f}GB；Docker：{docker_storage}；FUSE：{fuse}；性能档位（仅提示）：{advice.performance_profile}。\n{self._plan_summary(advice.balanced, advice.preferred_key)}；{self._plan_summary(advice.stream_first, advice.preferred_key)}。"

        def _probe_and_recommend(
            self, session: RemoteSession, values: dict[str, str]
        ) -> tuple[VpsResources, StorageAdvice]:
            basis = self._storage_probe_basis(values)
            uid_code, uid_output = session.run("id -u", timeout=10)
            uid_lines = [
                line.strip() for line in uid_output.splitlines() if line.strip()
            ]
            if uid_code != 0 or not uid_lines or (not uid_lines[-1].isdigit()):
                raise RuntimeError("SSH 已连接，但无法确认 VPS 用户权限")
            code, output = session.run(
                build_probe_command(basis[3], self.product.backup_dir),
                sudo=uid_lines[-1] != "0",
                timeout=30,
            )
            if code != 0:
                raise RuntimeError("SSH 已连接，但无法读取 VPS CPU、内存和目标文件系统")
            try:
                resources = parse_probe_output(output)
            except ValueError as exc:
                raise RuntimeError(f"VPS 资源探测结果无效：{exc}") from exc
            advice = recommend_storage(
                resources,
                managed_clouddrive=basis[4],
                managed_storage=(
                    self.product.is_openlist
                    or values.get("deploy_clouddrive2", "true") == "true"
                ),
                requires_fuse=(self.product.requires_fuse and basis[4]),
                minimum_memory_mb=900 if self.product.is_openlist else 1800,
            )
            self._publish_resource_advice(resources, advice, basis)
            return (resources, advice)

        def _build_config(self, values: dict[str, str]) -> str:
            pairs = {
                "TELEGRAM_API_ID": values["telegram_api_id"].strip(),
                "TELEGRAM_API_HASH_B64": b64(values["telegram_api_hash"].strip()),
                "BOT_TOKEN_B64": b64(values["bot_token"].strip()),
                "ALLOWED_USER_ID": values["allowed_user_id"].strip(),
                "CD2_WEBDAV_URL_B64": b64(self._effective_webdav_url(values)),
                "CD2_WEBDAV_USERNAME_B64": b64(values["cd2_username"].strip()),
                "CD2_WEBDAV_PASSWORD_B64": b64(values["cd2_password"]),
                "CD2_TARGET_PATH_B64": b64(values["cd2_target"].strip().strip("/")),
                "WEBDAV_URL_B64": b64(self._effective_webdav_url(values)),
                "WEBDAV_USERNAME_B64": b64(values["cd2_username"].strip()),
                "WEBDAV_PASSWORD_B64": b64(values["cd2_password"]),
                "WEBDAV_TARGET_PATH_B64": b64(
                    values["cd2_target"].strip().strip("/")
                ),
                "TG2CLOUD_STORAGE_BACKEND": self.product.key,
                "TG2CLOUD_DESTINATION_LABEL": self.product.display_name,
                "TG2CLOUD_RCLONE_REMOTE_NAME": (
                    "openlist" if self.product.is_openlist else "cd2"
                ),
                # Compatibility aliases keep rollback to the proven TG115 core possible.
                "TG115_STORAGE_BACKEND": self.product.key,
                "TG115_DESTINATION_LABEL": self.product.display_name,
                "TG115_RCLONE_REMOTE_NAME": (
                    "openlist" if self.product.is_openlist else "cd2"
                ),
                "LOCAL_TEMP_BUDGET_GB": values["local_budget_gb"].strip(),
                "MIN_FREE_DISK_GB": values["min_free_disk_gb"].strip(),
                "CONTROL_INTERVAL_SECONDS": "3",
                "CPU_TARGET_LOW_PERCENT": "60",
                "CPU_TARGET_HIGH_PERCENT": "80",
                "CPU_PRESSURE_PERCENT": "90",
                "MEMORY_SOFT_MIN_MB": "1024",
                "MEMORY_HARD_MIN_MB": "512",
                "RAMP_UP_STEP": "1",
                "RAMP_DOWN_FACTOR": "0.5",
                "MAX_RETRIES": "3",
                "REMOTE_HEALTH_INTERVAL_SECONDS": "30",
                "TZ": values["timezone"].strip() or "Asia/Shanghai",
                "DEPLOY_CLOUDDRIVE2": (
                    values["deploy_clouddrive2"]
                    if self.product.key == "clouddrive2"
                    else "false"
                ),
                "TG2CLOUD_REDEPLOY_APPLY_CONFIG": values.get(
                    "redeploy_apply_config", "false"
                ),
            }
            if self.product.is_openlist:
                pairs["OPENLIST_ADMIN_PASSWORD"] = values[
                    "openlist_admin_password"
                ]
                preserve = values.get("preserve_webdav", "false")
                pairs["TG2CLOUD_PRESERVE_WEBDAV"] = preserve
                pairs["TG115_PRESERVE_WEBDAV"] = preserve
            return "\n".join((f"{key}={value}" for key, value in pairs.items())) + "\n"

        def _add_payload_to_archive(self, archive: tarfile.TarFile) -> None:
            if self.product.key == "clouddrive2":
                archive.add(
                    resource_path(self.product.payload_variant), arcname="payload"
                )
                return
            for relative in self.product.required_payload:
                source = resource_path(relative)
                if relative.startswith("payload_openlist/"):
                    target = "payload/" + relative.removeprefix("payload_openlist/")
                elif relative.startswith("payload_clouddrive2/"):
                    target = "payload/" + relative.removeprefix(
                        "payload_clouddrive2/"
                    )
                else:
                    raise RuntimeError(f"未知的 payload 来源：{relative}")
                archive.add(source, arcname=target)

        def detect_resources(self, values: dict[str, str]) -> OperationResult:
            self._validate_connection(values)
            validate_install_dir(values["install_dir"])
            self._log("正在读取 VPS CPU、内存和目标文件系统……")
            session = self._new_session(values)
            try:
                self._probe_and_recommend(session, values)
            finally:
                session.close()
            return OperationResult("检测完成", "VPS 资源与存储建议已更新。")

        def test_connection(self, values: dict[str, str]) -> OperationResult:
            self._validate_connection(values)
            self._log("正在连接 VPS……")
            session = self._new_session(values)
            try:
                code, output = session.run(
                    "printf 'SSH_OK\\n'; uname -a; id; awk -F= '/^(ID|VERSION_ID)=/ {print}' /etc/os-release; free -h; df -h /"
                )
                if code != 0 or "SSH_OK" not in output:
                    raise RuntimeError("SSH 已连接，但预检命令失败")
                for line in output.splitlines():
                    self._log(line)
                self._probe_and_recommend(session, values)
                self._log("SSH 测试成功。")
                return OperationResult("测试成功", "SSH 连接和基础预检正常。")
            finally:
                session.close()

        def deploy(self, values: dict[str, str]) -> OperationResult:
            self._validate(values)
            missing = [
                p
                for p in self.product.required_payload
                if not resource_path(p).is_file()
            ]
            if missing:
                raise RuntimeError("payload 不完整：\n" + "\n".join(missing))
            remote_installer = resource_path(
                f"{self.product.payload_variant}/remote_install.sh"
            )
            if not remote_installer.is_file():
                raise RuntimeError("部署器内部 payload 缺失，请重新下载完整安装包")
            if (
                self.product.key == "clouddrive2"
                and
                values.get("deploy_clouddrive2", "true") == "true"
                and values["cd2_url"].strip() != self.product.webdav_url
            ):
                self._log(
                    f"CloudDrive2 与 Bot 位于同一台 VPS：已自动使用安全的容器内网 WebDAV 地址 {self.product.webdav_url}。"
                )
            self._log("开始一键部署基础环境。请关注下方运行日志。")
            with tempfile.TemporaryDirectory(prefix="tg2cloud-deployer-") as temp_name:
                temp = Path(temp_name)
                archive = temp / "payload.tar.gz"
                config_file = temp / "config.env"
                config_file.touch(mode=384, exist_ok=False)
                config_file.write_bytes(self._build_config(values).encode("utf-8"))
                with tarfile.open(archive, "w:gz") as tar:
                    self._add_payload_to_archive(tar)
                session = self._new_session(values)
                remote_stage = f"/tmp/tg2cloud-deploy-{uuid.uuid4().hex}"  # nosec B108
                try:
                    self._log("SSH 连接成功，重新核对 VPS 资源和当前存储配置……")
                    resources, advice = self._probe_and_recommend(session, values)
                    if resources.architecture not in {
                        "x86_64",
                        "amd64",
                        "aarch64",
                        "arm64",
                    }:
                        raise RuntimeError(
                            f"当前 CPU 架构暂不支持：{resources.architecture}"
                        )
                    assessment = assess_storage_choice(
                        resources,
                        budget_gb=float(values["local_budget_gb"]),
                        reserve_gb=float(values["min_free_disk_gb"]),
                        managed_clouddrive=(
                            self.product.key == "clouddrive2"
                            and values.get("deploy_clouddrive2", "true") == "true"
                        ),
                        managed_storage=(
                            self.product.is_openlist
                            or values.get("deploy_clouddrive2", "true") == "true"
                        ),
                        requires_fuse=(
                            self.product.requires_fuse
                            and values.get("deploy_clouddrive2", "true") == "true"
                        ),
                        minimum_memory_mb=(900 if self.product.is_openlist else 1800),
                    )
                    if not assessment.safe:
                        preferred = advice.preferred
                        hint = (
                            f"建议先应用{preferred.label}的 {preferred.budget_gb}/{preferred.reserve_gb}GB。"
                            if preferred
                            else "当前 VPS 需要释放空间或扩容后再部署。"
                        )
                        raise RuntimeError(
                            f"部署前资源校验未通过：{assessment.reason}。{hint}"
                        )
                    if (
                        advice.preferred
                        and float(values["min_free_disk_gb"])
                        < advice.preferred.reserve_gb
                    ):
                        self._log(
                            "警告：当前磁盘保留线低于实例建议；部署会继续，但应关注存储服务缓存和 Docker 空间。"
                        )
                    self._log(
                        f"部署前容量校验通过：预计至少需要 {assessment.required_available_gb:.1f}GB 可用空间。"
                    )
                    self._log("SSH 连接成功，上传部署包……")
                    code, _ = session.run(f"mkdir -m 700 {remote_stage}")
                    if code != 0:
                        raise RuntimeError("无法在 VPS 创建临时部署目录")
                    sftp = session.sftp()
                    try:
                        sftp.put(str(archive), f"{remote_stage}/payload.tar.gz")
                        sftp.put(str(config_file), f"{remote_stage}/config.env")
                        sftp.chmod(f"{remote_stage}/config.env", 384)
                    finally:
                        sftp.close()
                    self._log("上传完成，开始安装 VPS 运行环境和服务……")
                    extract = (
                        f"tar -xzf {remote_stage}/payload.tar.gz -C {remote_stage}"
                    )
                    code, output = session.run(extract, stream=self._log, timeout=120)
                    if code != 0:
                        raise RuntimeError("VPS 解压部署包失败")
                    uid_code, uid_output = session.run("id -u")
                    if uid_code != 0:
                        raise RuntimeError("无法确认 VPS 用户权限")
                    use_sudo = uid_output.strip().splitlines()[-1] != "0"
                    if use_sudo and (not values.get("sudo_password")):
                        sudo_code, _ = session.run("sudo -n true")
                        if sudo_code != 0:
                            raise RuntimeError(
                                "当前用户不是 root，也没有免密 sudo；请填写 sudo 密码"
                            )
                    install_dir = values["install_dir"].strip()
                    command = f"INSTALL_DIR={shlex.quote(install_dir)} bash {shlex.quote(remote_stage + '/payload/remote_install.sh')} {shlex.quote(remote_stage + '/payload')} {shlex.quote(remote_stage + '/config.env')}"
                    code, output = session.run(
                        command, sudo=use_sudo, stream=self._log, timeout=1800
                    )
                    result_markers = machine_markers(output)
                    if code != 0 or result_markers.get("RESULT") != "SUCCESS":
                        raise RuntimeError("远程基础安装没有通过容器健康检查")
                    self._log("基础部署和容器自检通过。")
                    openlist_initialized = (
                        result_markers.get("OPENLIST_INITIALIZED") == "NEW"
                    )
                    return OperationResult(
                        "部署成功",
                        (
                            "Bot 已经在 VPS 上运行。\n\n下一步：点击“打开 OpenList 管理页”，"
                            + (
                                "使用本页生成的管理员信息登录，"
                                if openlist_initialized
                                else "当前是已有 OpenList，原管理员凭据保持不变；登录后"
                            )
                            + "添加你的云存储（例如 115 Open）并配置 WebDAV 用户；"
                            "然后执行最终 WebDAV 验收。"
                            if self.product.is_openlist
                            else "Bot 已经在 VPS 上运行。\n\n下一步：点击“打开 CloudDrive2 管理页”，登录 CloudDrive2、挂载你的云存储并开启 WebDAV；然后点击“WebDAV 验收（写入测试文件）”。"
                        ),
                        openlist_state=(
                            "new" if openlist_initialized else "existing"
                        )
                        if self.product.is_openlist
                        else "",
                    )
                finally:
                    try:
                        if re_safe_remote_stage(remote_stage):
                            session.run(f"rm -rf -- {remote_stage}", timeout=60)
                    except Exception:  # noqa: BLE001 - best-effort remote cleanup
                        self._log("警告：VPS 临时部署目录未能自动清理。")
                    session.close()

        def open_clouddrive(self, values: dict[str, str]) -> OperationResult:
            self._validate_connection(values)
            identity = self.connection_identity(values)
            if self.tunnel and self._tunnel_identity != identity:
                self.close()
            if self.tunnel:
                try:
                    self.tunnel.probe()
                except RuntimeError as exc:
                    self._log(f"现有 SSH 隧道已失效，正在自动重建：{exc}")
                    self.tunnel.close()
                    self.tunnel = None
                else:
                    self._browser_open(self.tunnel.url)
                    self._log(f"{self.product.display_name} 管理页：{self.tunnel.url}")
                    return OperationResult(
                        self.product.display_name,
                        "已验证并重新打开现有 SSH 安全隧道。",
                    )
            session = self._new_session(values)
            tunnel: Tunnel | None = None
            try:
                code, _ = session.run(
                    "curl -fsS --max-time 10 "
                    f"http://127.0.0.1:{self.product.management_port}/ >/dev/null"
                )
                if code != 0:
                    raise RuntimeError(
                        f"VPS 本机的 {self.product.display_name} "
                        f"{self.product.management_port} 端口没有响应，请先完成部署"
                    )
                tunnel = self._tunnel_factory(
                    session,
                    local_port=self.product.management_port,
                    remote_port=self.product.management_port,
                    product_name=self.product.display_name,
                )
                tunnel.start()
                tunnel.probe()
                self.tunnel = tunnel
                self._tunnel_identity = identity
                url = tunnel.url
                self._log(f"SSH 安全隧道已验收：{url}")
                self._browser_open(url)
                return OperationResult(
                    f"{self.product.display_name} 管理页",
                    "管理页已通过真实 HTTP 请求验收并打开。部署器关闭时 SSH 隧道会自动关闭。",
                )
            except Exception:
                if tunnel:
                    tunnel.close()
                else:
                    session.close()
                raise

        def repair_clouddrive(self, values: dict[str, str]) -> OperationResult:
            if self.product.is_openlist:
                return self.check_openlist(values)
            self._validate_connection(values)
            validate_install_dir(values["install_dir"])
            repair_script = resource_path(
                "payload_clouddrive2/repair_clouddrive_network.sh"
            )
            if not repair_script.is_file():
                raise RuntimeError("部署器内部修复脚本缺失，请重新下载完整安装包")
            session = self._new_session(values)
            remote_stage = f"/tmp/tg2cloud-deploy-{uuid.uuid4().hex}"  # nosec B108
            try:
                code, _ = session.run(f"mkdir -m 700 {remote_stage}")
                if code != 0:
                    raise RuntimeError("无法在 VPS 创建临时修复目录")
                sftp = session.sftp()
                try:
                    remote_script = f"{remote_stage}/repair_clouddrive_network.sh"
                    sftp.put(str(repair_script), remote_script)
                    sftp.chmod(remote_script, 448)
                finally:
                    sftp.close()
                uid_code, uid_output = session.run("id -u")
                if uid_code != 0 or not uid_output.strip():
                    raise RuntimeError("无法确认 VPS 用户权限")
                use_sudo = uid_output.strip().splitlines()[-1] != "0"
                if use_sudo and (not values.get("sudo_password")):
                    sudo_code, _ = session.run("sudo -n true")
                    if sudo_code != 0:
                        raise RuntimeError("需要 sudo 密码才能修复 CloudDrive2 网络")
                install_dir = values["install_dir"].strip()
                command = f"INSTALL_DIR={shlex.quote(install_dir)} bash {shlex.quote(remote_script)}"
                self._log("开始修复 CloudDrive2 Docker 网络并执行真实 WebDAV 验收……")
                code, output = session.run(
                    command, sudo=use_sudo, stream=self._log, timeout=240
                )
                if code != 0 or machine_markers(output).get("REPAIR") != "SUCCESS":
                    raise RuntimeError("CloudDrive2 网络修复或 WebDAV 验收没有通过")
                self._log("CloudDrive2 网络修复和 WebDAV 真实验收均已通过。")
                return OperationResult(
                    "修复成功",
                    "已保留 CloudDrive2 登录和挂载数据，修复 Docker 网络，并通过 WebDAV 写入、校验、改名和清理测试。",
                )
            finally:
                try:
                    if re_safe_remote_stage(remote_stage):
                        session.run(f"rm -rf -- {remote_stage}", timeout=60)
                except Exception:  # noqa: BLE001 - best-effort remote cleanup
                    self._log("警告：VPS 临时修复目录未能自动清理。")
                session.close()

        def check_openlist(self, values: dict[str, str]) -> OperationResult:
            self._run_openlist_manage(
                values, "status", "STATUS", timeout=120
            )

        def runtime_status(self, values: dict[str, str]) -> OperationResult:
            self._validate_connection(values)
            install_dir = validate_install_dir(values["install_dir"])
            session = self._new_session(values)
            try:
                uid_code, uid_output = session.run("id -u", timeout=10)
                if uid_code != 0 or not uid_output.strip().splitlines()[-1].isdigit():
                    raise RuntimeError("无法确认 VPS 用户权限，未完成状态检查")
                use_sudo = uid_output.strip().splitlines()[-1] != "0"
                if use_sudo and not values.get("sudo_password"):
                    sudo_code, _ = session.run("sudo -n true", timeout=10)
                    if sudo_code != 0:
                        raise RuntimeError("需要 sudo 权限才能读取 Docker 状态")
                code, output = session.run(
                    runtime_status_command(self.product, install_dir),
                    sudo=use_sudo,
                    timeout=30,
                )
                markers = machine_markers(output)
                state = markers.get("STATUS", "UNKNOWN")
                if code != 0 or state not in {"RUNNING", "STOPPED", "NOT_INSTALLED"}:
                    raise RuntimeError("目标目录不是可识别的 TG2Cloud 安装，无法判定运行状态")
                labels = {
                    "RUNNING": "运行中",
                    "STOPPED": "已安装但未正常运行",
                    "NOT_INSTALLED": "未安装",
                }
                legacy = (
                    "；另检测到旧 TG115，仅作提示，不参与本次状态判断"
                    if markers.get("LEGACY") == "DETECTED"
                    else ""
                )
                details = (
                    f"；Bot={markers.get('BOT_HEALTH', 'unknown')}，"
                    f"网关={markers.get('GATEWAY', 'unknown')}，"
                    f"Network={markers.get('NETWORK', 'unknown')}"
                    if state != "NOT_INSTALLED"
                    else ""
                )
                return OperationResult(
                    "运行状态", f"TG2Cloud {self.product.display_name}：{labels[state]}{details}{legacy}。"
                )
            finally:
                session.close()
            return OperationResult(
                "检查通过",
                "OpenList 容器和 Bot 正在运行，VPS 本机 5244 管理端口可以访问。"
                "这项检查不会读取云存储登录信息，也不代表 WebDAV 已配置完成。",
            )

        def _run_openlist_manage(
            self,
            values: dict[str, str],
            action: str,
            expected_marker: str,
            *,
            timeout: float,
        ) -> str:
            if not self.product.is_openlist:
                raise RuntimeError("该操作只适用于 OpenList 版部署器")
            allowed_actions = {
                "status",
                "recent-logs",
                "restart-bot",
                "restart-openlist",
                "backup",
            }
            if action not in allowed_actions:
                raise ValueError("未知的 OpenList 管理操作")
            self._validate_connection(values)
            install_dir = validate_install_dir(values["install_dir"])
            session = self._new_session(values)
            try:
                uid_code, uid_output = session.run("id -u")
                if uid_code != 0 or not uid_output.strip():
                    raise RuntimeError("无法确认 VPS 用户权限")
                use_sudo = uid_output.strip().splitlines()[-1] != "0"
                if use_sudo and not values.get("sudo_password"):
                    sudo_code, _ = session.run("sudo -n true")
                    if sudo_code != 0:
                        raise RuntimeError("需要 sudo 密码才能管理 OpenList 服务")
                command = (
                    f"cd {shlex.quote(install_dir)} && "
                    f"INSTALL_DIR={shlex.quote(install_dir)} "
                    f"bash ./manage.sh {shlex.quote(action)}"
                )
                code, output = session.run(
                    command, sudo=use_sudo, stream=self._log, timeout=timeout
                )
                if code != 0 or machine_markers(output).get(expected_marker) != "OK":
                    raise RuntimeError(
                        f"OpenList 管理操作没有通过（{action}）"
                    )
                return output
            finally:
                session.close()

        def openlist_status(self, values: dict[str, str]) -> OperationResult:
            return self.runtime_status(values)

        def openlist_logs(self, values: dict[str, str]) -> OperationResult:
            self._run_openlist_manage(
                values, "recent-logs", "LOGS", timeout=120
            )
            return OperationResult(
                "日志已读取",
                "最近 30 分钟、最多 200 行的脱敏日志已显示在运行日志区域。",
            )

        def restart_bot(self, values: dict[str, str]) -> OperationResult:
            self._run_openlist_manage(
                values, "restart-bot", "BOT_RESTART", timeout=240
            )
            return OperationResult(
                "Bot 已重启", "TG2Cloud Bot 已重新启动并通过健康检查。"
            )

        def restart_openlist(self, values: dict[str, str]) -> OperationResult:
            self._run_openlist_manage(
                values,
                "restart-openlist",
                "OPENLIST_RESTART",
                timeout=240,
            )
            return OperationResult(
                "OpenList 已重启",
                "OpenList 已重新启动，VPS 本机 5244 管理端口已恢复响应。",
            )

        def backup_openlist(self, values: dict[str, str]) -> OperationResult:
            self._run_openlist_manage(
                values, "backup", "BACKUP", timeout=600
            )
            return OperationResult(
                "备份完成",
                "程序配置、TG2Cloud 数据库和 OpenList 状态已保存到 VPS 的受限备份目录。",
            )

        def reset_openlist_admin(self, values: dict[str, str]) -> OperationResult:
            if not self.product.is_openlist:
                raise RuntimeError("该操作只适用于 OpenList 版部署器")
            self._validate_connection(values)
            install_dir = validate_install_dir(values["install_dir"])
            session = self._new_session(values)
            try:
                uid_code, uid_output = session.run("id -u")
                if uid_code != 0 or not uid_output.strip():
                    raise RuntimeError("无法确认 VPS 用户权限")
                use_sudo = uid_output.strip().splitlines()[-1] != "0"
                if use_sudo and not values.get("sudo_password"):
                    sudo_code, _ = session.run("sudo -n true")
                    if sudo_code != 0:
                        raise RuntimeError("需要 sudo 密码才能恢复管理员密码")
                command = (
                    f"cd {shlex.quote(install_dir)} && "
                    f"INSTALL_DIR={shlex.quote(install_dir)} "
                    "bash ./openlist_admin.sh reset-random "
                    "I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD"
                )
                # The command intentionally returns a new password. Never stream its
                # raw output into the normal log path.
                code, output = session.run(
                    command, sudo=use_sudo, stream=None, timeout=120
                )
                # Legacy TG115 compatibility is handled by machine_markers().
                values_by_key = machine_markers(output)
                password = values_by_key.get("OPENLIST_ADMIN_PASSWORD", "")
                if (
                    code != 0
                    or values_by_key.get("OPENLIST_ADMIN_RESET") != "OK"
                    or values_by_key.get("OPENLIST_ADMIN_USERNAME") != "admin"
                    or not 8 <= len(password) <= 256
                    or any(ord(char) < 33 or ord(char) > 126 for char in password)
                ):
                    raise RuntimeError("OpenList 管理员密码恢复没有成功")
                return OperationResult(
                    "管理员密码已恢复",
                    "新密码已安全写入当前窗口的管理员密码输入框；请立即复制保存。"
                    "该密码不会写入普通运行日志。",
                    secret_field=OPENLIST_ADMIN_SECRET_FIELD,
                    secret_value=password,
                )
            finally:
                session.close()

        def verify(self, values: dict[str, str]) -> OperationResult:
            self._validate_connection(values)
            validate_install_dir(values["install_dir"])
            session = self._new_session(values)
            try:
                install_dir = values["install_dir"].strip()
                uid_code, uid_output = session.run("id -u")
                if uid_code != 0 or not uid_output.strip():
                    raise RuntimeError("无法确认 VPS 用户权限")
                use_sudo = uid_output.strip().splitlines()[-1] != "0"
                if use_sudo and (not values.get("sudo_password")):
                    sudo_code, _ = session.run("sudo -n true")
                    if sudo_code != 0:
                        raise RuntimeError("需要 sudo 密码才能检查服务")
                bot_container = shlex.quote(self.product.bot_container)
                bot_service = shlex.quote(self.product.bot_service)
                if self.product.is_openlist:
                    command = (
                        f"cd {shlex.quote(install_dir)} && "
                        "INSTALL_DIR="
                        f"{shlex.quote(install_dir)} bash ./manage.sh verify && "
                        f"docker compose logs --tail=40 {bot_service}"
                    )
                else:
                    command = f"cd {shlex.quote(install_dir)} && docker compose ps && docker inspect --format 'TG2CLOUD_BOT_HEALTH={{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{else}}}}{{{{.State.Status}}}}{{{{end}}}}' {bot_container} && docker compose exec -T {bot_service} python -m app.verify_destination && docker compose logs --tail=40 {bot_service}"
                code, output = session.run(
                    command, sudo=use_sudo, stream=self._log, timeout=120
                )
                markers = machine_markers(output)
                statuses = verification_statuses(output)
                if code != 0:
                    if markers.get("OPENLIST") == "FAILED":
                        raise OperationError(
                            "OpenList 当前没有正常运行，或 VPS 本机 5244 管理端口没有响应。"
                            "请先点击“重启 OpenList”，成功后再次验收。",
                            statuses,
                        )
                    if markers.get("WEBDAV_AUTH") == "FAILED":
                        raise OperationError(
                            "无法登录 OpenList WebDAV。请确认已经创建与本页用户名一致的专用用户，"
                            "OpenList 中的密码与“配置 WebDAV”页一致，并已授予所需权限。",
                            statuses,
                        )
                    if markers.get("WEBDAV_LIST") == "FAILED":
                        raise OperationError(
                            "WebDAV 目标目录无法访问。请检查用户基本路径、本页配置的目标目录、"
                            "云存储挂载状态和目录权限。",
                            statuses,
                        )
                    if markers.get("WEBDAV_WRITE") == "FAILED":
                        raise OperationError(
                            "WebDAV 登录和目录访问成功，但无法写入测试文件。"
                            "请检查创建／上传权限以及 VPS、目标云存储端可用空间。",
                            statuses,
                        )
                    if markers.get("WEBDAV_SIZE") == "FAILED":
                        raise OperationError(
                            "测试文件已写入，但远端大小校验失败。"
                            "请查看脱敏日志并检查 OpenList 与目标云存储的上传状态。",
                            statuses,
                        )
                    if markers.get("WEBDAV_MOVE") == "FAILED":
                        raise OperationError(
                            "测试文件已写入，但远端改名或改名后的复验失败。"
                            "请检查移动／改名权限。",
                            statuses,
                        )
                    if markers.get("WEBDAV_DELETE") == "FAILED":
                        raise OperationError(
                            "测试文件无法安全清理。请检查删除权限，并在 OpenList 中核对"
                            "是否残留 WebDAV 验收测试文件。",
                            statuses,
                        )
                    if "server gave HTTP response to HTTPS client" in output:
                        raise OperationError(
                            "WebDAV 协议不匹配：19798 端口提供 HTTP，当前已部署配置却使用 HTTPS。请用新版部署器重新执行“一键部署基础环境”，再做验收。",
                            statuses,
                        )
                    if (
                        self.product.key == "clouddrive2"
                        and (
                            "lookup tg2cloud-clouddrive2" in output
                            or "lookup clouddrive2" in output
                        )
                    ):
                        raise OperationError(
                            "Bot 无法解析 CloudDrive2 Docker 地址。请先点击“修复 CloudDrive2 网络”，成功后再验收。",
                            statuses,
                        )
                    raise OperationError("远程状态检查失败", statuses)
                if dict(statuses)["Bot 容器"] != "通过":
                    raise OperationError("Bot 当前没有通过健康检查", statuses)
                if markers.get("DESTINATION") != "OK":
                    raise OperationError(
                        f"{self.product.display_name} WebDAV 写入、校验、改名和清理没有通过",
                        statuses,
                    )
                self._log("WebDAV 验收通过：测试文件已写入、校验、改名并清理。")
                return OperationResult(
                    "验收通过",
                    f"Bot 容器健康；{self.product.display_name} WebDAV 已通过真实测试文件的写入、大小校验、改名和清理。\n\n注意：这只证明 {self.product.display_name} WebDAV 已接收文件；上游云存储是否完成同步，请以对应官方客户端中的文件大小和可打开状态为准。",
                    statuses=statuses,
                )
            finally:
                session.close()


def _require_backend():
    """Resolve local definitions, never import any of the old split modules."""
    if _BACKEND_IMPORT_ERROR is not None:
        raise RuntimeError(
            "远程功能依赖加载失败："
            + str(_BACKEND_IMPORT_ERROR)
            + "\n请安装 paramiko，并保留原项目的 vps_resources.py。"
        ) from _BACKEND_IMPORT_ERROR
    return InstallerBackend


# ============================================================================
# 5. PySide6 GUI, embedded icons/styles and worker signals
# ============================================================================

_QT_IMPORT_ERROR: Exception | None = None
try:
    from PySide6.QtCore import (
        QByteArray,
        QObject,
        QSize,
        Qt,
        QThread,
        QTimer,
        Signal,
        Slot,
    )
    from PySide6.QtGui import (
        QColor,
        QFont,
        QFontDatabase,
        QIcon,
        QPainter,
        QPixmap,
        QTextCharFormat,
        QTextCursor,
    )
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSplitter,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
except (ImportError, OSError) as exc:
    # Keep CLI diagnostics and backend tests available without a GUI runtime.
    _QT_IMPORT_ERROR = exc


def _require_qt() -> None:
    if _QT_IMPORT_ERROR is not None:
        raise RuntimeError(
            "PySide6 加载失败。请在项目使用的 Python 环境执行：\n"
            'python -m pip install "PySide6>=6.8,<7"\n' + str(_QT_IMPORT_ERROR)
        ) from _QT_IMPORT_ERROR


if _QT_IMPORT_ERROR is None:
    # Product branding comes only from assets/brand; utility icons remain embedded.
    ICON_PATHS = {
        "server": '<rect x="4" y="3" width="16" height="7" rx="2"/><rect x="4" y="14" width="16" height="7" rx="2"/><path d="M8 6.5h.01M8 17.5h.01M12 6.5h5M12 17.5h5"/>',
        "plane": '<path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13"/>',
        "cloud": '<path d="M6 18h12a4 4 0 0 0 .5-8A6.5 6.5 0 0 0 6 9a4.5 4.5 0 0 0 0 9Z"/>',
        "settings": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2" fill="white"/><circle cx="16" cy="12" r="2" fill="white"/><circle cx="10" cy="18" r="2" fill="white"/>',
        "rocket": '<path d="M14 4c3-2 6-2 6-2s0 3-2 6l-7 7-4-4 7-7ZM7 11l-4 1 3-6 6-1M11 15l-1 6 6-3 1-4M4 16l-2 6 6-2"/><circle cx="15.5" cy="6.5" r="1.5"/>',
        "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
        "wrench": '<path d="m14 6 4 4 3-3a7 7 0 0 1-8 9l-6 6-4-4 6-6a7 7 0 0 1 9-8l-4 2Z"/>',
        "external": '<path d="M14 3h7v7M21 3l-10 10M10 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-5"/>',
        "terminal": '<path d="m5 7 5 5-5 5M13 17h6"/>',
        "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
        "folder": '<path d="M3 7V5h6l2 2h10v13H3V7Z"/>',
        "shield": '<path d="m12 2 8 3v7c0 5-8 10-8 10S4 17 4 12V5l8-3Z"/><path d="m8 11 3 3 5-6"/>',
        "download": '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
        "copy": '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
        "disk": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    }

    STYLE = """
    QWidget { color:#25344c; font-size:13px; }
    QMainWindow, QWidget#Root { background:#f3f6fb; }
    QLabel { background:transparent; }
    QLabel#Brand { font-size:26px; font-weight:700; color:#172b4d; }
    QLabel#Subtitle, QLabel#Hint, QLabel#Small { color:#78869b; }
    QLabel#Small { font-size:11px; }
    QLabel#SectionTitle { font-size:18px; font-weight:700; color:#213450; }
    QLabel#FieldLabel { color:#46556d; font-size:12px; }
    QLabel#Status { border:1px solid #dbe5f1; border-radius:15px;
     background:#eaf0f7; color:#52637c; padding:6px 14px; font-size:12px; }
    QLabel#Status[state="running"] { background:#e8f0ff; color:#2563eb; border-color:#cfe0ff; }
    QLabel#Status[state="success"] { background:#e7f5ef; color:#168063; border-color:#cbe9dc; }
    QLabel#Status[state="error"] { background:#fff0ef; color:#be4f45; border-color:#f6d4ce; }
    QLabel#Status[state="cancelled"] { background:#f3f4f6; color:#596273; border-color:#dfe2e7; }
    QLabel#Banner { border:1px solid #f1dfb8; background:#fff9ed; color:#8a6223;
     border-radius:9px; padding:9px 12px; font-size:12px; }
    QFrame#Card, QFrame#Navigation { background:#ffffff; border:1px solid #e2e9f2;
     border-radius:15px; }
    QFrame#InfoBox { background:#f3f7fe; border:1px solid #e1eafb; border-radius:10px; }
    QFrame#SoftBox { background:#f7f9fc; border:1px solid #e9eef5; border-radius:10px; }
    QFrame#Divider { background:#edf1f6; border:0; max-height:1px; min-height:1px; }
    QPushButton { background:#ffffff; border:1px solid #dbe3ed; border-radius:9px;
     padding:9px 13px; color:#40516d; font-weight:500; }
    QPushButton:hover { background:#f3f7ff; border-color:#b7cceb; }
    QPushButton:pressed { background:#e6efff; }
    QPushButton:focus { border:1px solid #4e83e8; }
    QPushButton:disabled { color:#a2adbd; background:#f4f6f9; border-color:#e6eaf0; }
    QPushButton#Primary { background:#3474ed; border-color:#3474ed; color:white; font-weight:600; }
    QPushButton#Primary:hover { background:#2363d9; }
    QPushButton#Primary:disabled { background:#cad6ec; border-color:#cad6ec; color:#f7f9ff; }
    QPushButton#Repair { color:#99672c; border-color:#eadfcf; background:#fffcf6; }
    QPushButton#Repair:hover { background:#fff4de; }
    QPushButton#Verify { color:#188168; border-color:#d2e7df; background:#f7fcf9; }
    QPushButton#Verify:hover { background:#eaf8f1; }
    QPushButton#Ghost { border:0; background:transparent; color:#6f8097; padding:6px 9px; }
    QPushButton#Ghost:hover { background:#e8eff9; color:#3474ed; }
    QPushButton#Tab { border:0; border-radius:9px; color:#8390a4; background:transparent;
     text-align:left; padding:13px 14px; }
    QPushButton#Tab:checked { background:#eaf2ff; color:#2766d6; font-weight:600; }
    QPushButton#Tab:hover { background:#f2f6fc; }
    QPushButton#Auth { border:0; border-radius:7px; padding:8px 13px; background:#eef2f8; color:#7e8da3; }
    QPushButton#Auth:checked { background:#e6efff; color:#2e6cdf; font-weight:600; }
    QLineEdit { background:#fbfcfe; border:1px solid #dce4ef; border-radius:8px;
     padding:8px 11px; selection-background-color:#c6dbff; min-height:20px; }
    QLineEdit:focus { border-color:#4f86ec; background:#ffffff; }
    QLineEdit:disabled, QLineEdit:read-only { color:#8b98aa; background:#f1f4f8; }
    QLineEdit[invalid="true"] { border-color:#d97165; }
    QScrollArea { border:0; background:transparent; }
    QScrollArea > QWidget > QWidget { background:transparent; }
    QScrollBar:vertical { background:transparent; width:8px; margin:3px; }
    QScrollBar::handle:vertical { background:#c9d4e2; border-radius:3px; min-height:25px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
    QCheckBox { spacing:9px; }
    QCheckBox::indicator { width:17px; height:17px; border:1px solid #b9c9de; border-radius:4px; background:white; }
    QCheckBox::indicator:checked { background:#3474ed; border-color:#3474ed; }
    QProgressBar { border:0; background:#e5edf8; border-radius:2px; max-height:4px; }
    QProgressBar::chunk { background:#4783ed; border-radius:2px; }
    QPlainTextEdit#Console { background:#132137; color:#ced8e8; border:0;
     border-radius:11px; padding:10px; selection-background-color:#3a5375; font-size:12px; }
    QSplitter::handle { background:transparent; height:9px; }
    QToolTip { background:#243654; color:white; border:0; padding:8px; }
    QDialog { background:#f7f9fd; }
    """

    def icon(name: str, color: str = "#6d83a2", size: int = 22) -> QIcon:
        path = ICON_PATHS.get(name, ICON_PATHS["info"])
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" '
            f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        return QIcon(pixmap)

    def brand_icon() -> QIcon:
        """Load the official TG2Cloud icon from the bundled brand directory."""
        return QIcon(str(resource_path(BRAND_ICON_ASSET)))

    def brand_pixmap(asset: str, width: int, height: int) -> QPixmap:
        """Load and scale an official TG2Cloud brand asset without modifying it."""
        pixmap = QPixmap(str(resource_path(asset)))
        if pixmap.isNull():
            return pixmap
        return pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
        widget = QLabel(text)
        if role:
            widget.setObjectName(role)
        widget.setWordWrap(wrap)
        widget.setTextFormat(Qt.TextFormat.PlainText)
        return widget

    def frame(role: str = "Card") -> QFrame:
        widget = QFrame()
        widget.setObjectName(role)
        return widget

    @dataclass
    class Confirmation:
        challenge: HostKeyChallenge
        done: threading.Event = field(default_factory=threading.Event)
        approved: bool = False

    class Bridge(QObject):
        """Queued signals are the only path from Python/SSH threads to widgets."""

        log = Signal(str)
        resources = Signal(object)
        confirm = Signal(object)

    class OperationThread(QThread):
        succeeded = Signal(str, object)
        failed = Signal(str, object)

        def __init__(
            self, backend: Any, operation: str, values: dict[str, str], parent=None
        ):
            super().__init__(parent)
            self.backend, self.operation, self.values = backend, operation, dict(values)

        def run(self) -> None:
            try:
                result = getattr(self.backend, self.operation)(self.values)
                self.succeeded.emit(self.operation, result)
            except Exception as exc:  # noqa: BLE001 - GUI worker boundary
                self.failed.emit(self.operation, exc)

    class InstallerWindow(QMainWindow):
        PAGE_TITLES = (
            "01   连接 VPS",
            "02   Telegram",
            "03   CloudDrive2",
            "04   部署选项",
        )
        ACTION_TITLES: ClassVar[dict[str, str]] = {
            "test_connection": "测试 SSH",
            "deploy": "一键部署基础环境",
            "open_clouddrive": "打开 CloudDrive2 管理页",
            "repair_clouddrive": "修复 CloudDrive2 网络",
            "verify": "WebDAV 验收",
            "detect_resources": "检测 VPS 并推荐",
            "runtime_status": "查看运行状态",
            "openlist_status": "查看运行状态",
            "openlist_logs": "查看脱敏日志",
            "restart_bot": "重启 TG2Cloud Bot",
            "restart_openlist": "重启 OpenList",
            "backup_openlist": "创建安全备份",
            "reset_openlist_admin": "恢复管理员密码",
        }

        def __init__(
            self,
            *,
            preview: bool = False,
            product: ProductProfile = CLOUDDRIVE2_PRODUCT,
        ):
            super().__init__()
            self.product = product
            self.defaults = defaults_for(product)
            if product.is_openlist:
                self.PAGE_TITLES = (
                    "01   连接 VPS",
                    "02   Telegram",
                    "03   部署 OpenList",
                    "04   配置 WebDAV",
                    "05   部署选项",
                )
            else:
                self.PAGE_TITLES = type(self).PAGE_TITLES
            self.ACTION_TITLES = dict(type(self).ACTION_TITLES)
            self.ACTION_TITLES["open_clouddrive"] = (
                f"打开 {product.display_name} 管理页"
            )
            self.ACTION_TITLES["repair_clouddrive"] = (
                "检查 OpenList 服务"
                if product.is_openlist
                else "修复 CloudDrive2 网络"
            )
            self.preview = preview
            self.backend: Any = None
            self.backend_error = ""
            self.worker: OperationThread | None = None
            self.exit_after_worker = False
            self.resource_update: Any = None
            self.edits: dict[str, QLineEdit] = {}
            self.field_boxes: dict[str, QWidget] = {}
            self.action_buttons: dict[str, QPushButton] = {}
            self.redactor = Redactor()
            self.bridge = Bridge(self)
            self.bridge.log.connect(self.append_log, Qt.ConnectionType.QueuedConnection)
            self.bridge.resources.connect(
                self.publish_resources, Qt.ConnectionType.QueuedConnection
            )
            self.bridge.confirm.connect(
                self.confirm_host_key, Qt.ConnectionType.QueuedConnection
            )
            self.setWindowTitle(
                f"{self.product.app_title}  v{self.product.app_version}  |  Qt"
            )
            self.setWindowIcon(brand_icon())
            self.setMinimumSize(900, 600)
            screen = QApplication.primaryScreen()
            area = screen.availableGeometry() if screen else None
            self.resize(
                min(1280, max(900, area.width() - 50)) if area else 1280,
                min(920, max(600, area.height() - 60)) if area else 920,
            )
            self._build_ui()
            self._load_backend()
            self._update_auth()
            self._update_managed()
            self._update_actions()
            self.append_log("准备就绪。先配置 VPS，再测试 SSH 连接。")
            self.append_log("凭据不在本地自动保存；日志导出前仍需人工核对敏感信息。")

        def _build_ui(self) -> None:
            root = QWidget()
            root.setObjectName("Root")
            self.setCentralWidget(root)
            outer = QVBoxLayout(root)
            outer.setContentsMargins(28, 22, 28, 15)
            outer.setSpacing(15)
            header = QHBoxLayout()
            self.brand_icon_label = label("")
            self.brand_icon_label.setObjectName("BrandIcon")
            self.brand_icon_label.setPixmap(
                brand_pixmap(BRAND_ICON_ASSET, 56, 56)
            )
            self.brand_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.brand_icon_label.setFixedSize(60, 60)
            header.addWidget(self.brand_icon_label)
            brand = QVBoxLayout()
            brand.setSpacing(3)
            self.brand_name_label = label("TG2Cloud", "Brand")
            self.brand_subtitle_label = label(
                f"From Telegram to Your Cloud  ·  {self.product.display_name} Edition",
                "Subtitle",
            )
            brand.addWidget(self.brand_name_label)
            brand.addWidget(self.brand_subtitle_label)
            header.addSpacing(4)
            header.addLayout(brand)
            header.addStretch()
            header.addWidget(
                label(f"v{self.product.app_version}  /  Qt", "Small")
            )
            header.addSpacing(10)
            self.status = label("准备就绪", "Status")
            header.addWidget(self.status)
            about = QPushButton()
            about.setObjectName("Ghost")
            about.setIcon(icon("info"))
            about.setToolTip("依赖检查与关于")
            about.setAccessibleName("依赖检查与关于")
            about.clicked.connect(self.show_diagnostics)
            header.addWidget(about)
            outer.addLayout(header)

            navigation = frame("Navigation")
            nav_layout = QHBoxLayout(navigation)
            nav_layout.setContentsMargins(7, 7, 7, 7)
            nav_layout.setSpacing(7)
            self.nav_group = QButtonGroup(self)
            self.nav_group.setExclusive(True)
            symbols = (
                ("server", "plane", "cloud", "check", "settings")
                if self.product.is_openlist
                else ("server", "plane", "cloud", "settings")
            )
            for index, (text, symbol) in enumerate(zip(self.PAGE_TITLES, symbols)):
                button = QPushButton(text)
                button.setObjectName("Tab")
                button.setIcon(icon(symbol))
                button.setIconSize(QSize(19, 19))
                button.setCheckable(True)
                self.nav_group.addButton(button, index)
                nav_layout.addWidget(button, 1)
            self.nav_group.idClicked.connect(self._change_page)
            self.nav_group.button(0).setChecked(True)
            outer.addWidget(navigation)

            self.banner = label("", "Banner", True)
            self.banner.hide()
            outer.addWidget(self.banner)
            self.splitter = QSplitter(Qt.Orientation.Vertical)
            self.splitter.setChildrenCollapsible(False)
            self.splitter.setHandleWidth(10)
            workspace = QWidget()
            columns = QHBoxLayout(workspace)
            columns.setContentsMargins(0, 0, 0, 0)
            columns.setSpacing(18)
            self.pages = QStackedWidget()
            self.pages.addWidget(self._vps_page())
            self.pages.addWidget(self._telegram_page())
            if self.product.is_openlist:
                self.pages.addWidget(self._openlist_page())
            self.pages.addWidget(self._cloud_page())
            self.pages.addWidget(self._options_page())
            columns.addWidget(self.pages, 1)
            action_scroll = QScrollArea()
            action_scroll.setWidgetResizable(True)
            action_scroll.setFixedWidth(316)
            action_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            action_scroll.setWidget(self._actions_card())
            columns.addWidget(action_scroll)
            self.splitter.addWidget(workspace)
            self.splitter.addWidget(self._log_panel())
            self.splitter.setSizes([550, 165])
            self.splitter.setStretchFactor(0, 4)
            self.splitter.setStretchFactor(1, 1)
            outer.addWidget(self.splitter, 1)

            footer = QHBoxLayout()
            shield = label("")
            shield.setPixmap(icon("shield", "#8a9bb3", 15).pixmap(15, 15))
            footer.addWidget(shield)
            footer.addWidget(label("SSH 安全隧道 · 管理端口不暴露到公网", "Small"))
            footer.addStretch()
            self.footer_state = label("本地配置 · 未执行远程操作", "Small")
            footer.addWidget(self.footer_state)
            outer.addLayout(footer)

        def _change_page(self, index: int) -> None:
            self.pages.setCurrentIndex(index)

        def _page(self, title: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
            card = frame()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(24, 21, 24, 21)
            layout.setSpacing(15)
            layout.addWidget(label(title, "SectionTitle"))
            layout.addWidget(label(subtitle, "Hint", True))
            scroll.setWidget(content)
            card_layout.addWidget(scroll)
            return card, layout

        def _field(
            self, name: str, *, title: str = "", placeholder: str = ""
        ) -> QWidget:
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(7)
            field_title = title or FIELDS[name]["label"]
            caption = label(field_title, "FieldLabel", True)
            layout.addWidget(caption)
            edit = QLineEdit(self.defaults.get(name, ""))
            edit.setObjectName(name)
            edit.setAccessibleName(field_title)
            edit.setPlaceholderText(placeholder)
            edit.setMinimumWidth(70)
            caption.setBuddy(edit)
            if FIELDS[name]["masked"]:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
                eye = edit.addAction(
                    icon("eye"), QLineEdit.ActionPosition.TrailingPosition
                )
                eye.setToolTip("显示 / 隐藏")
                eye.setCheckable(True)
                eye.toggled.connect(
                    lambda checked, e=edit: e.setEchoMode(
                        QLineEdit.EchoMode.Normal
                        if checked
                        else QLineEdit.EchoMode.Password
                    )
                )
            edit.textChanged.connect(self._configuration_changed)
            self.edits[name] = edit
            self.field_boxes[name] = box
            layout.addWidget(edit)
            return box

        def _add_copy_action(self, field_name: str) -> None:
            edit = self.edits[field_name]
            action = edit.addAction(
                icon("copy"), QLineEdit.ActionPosition.TrailingPosition
            )
            action.setToolTip("复制")
            action.triggered.connect(
                lambda checked=False, source=edit: QApplication.clipboard().setText(
                    source.text()
                )
            )

        def _regenerate_secret(self, field_name: str) -> None:
            self.edits[field_name].setText(secure_password())

        def _row(
            self, left: QWidget, right: QWidget, ratio: tuple[int, int] = (1, 1)
        ) -> QWidget:
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)
            layout.addWidget(left, ratio[0])
            layout.addWidget(right, ratio[1])
            return widget

        def _hint(self, text: str, role: str = "InfoBox") -> QFrame:
            box = frame(role)
            layout = QHBoxLayout(box)
            layout.setContentsMargins(13, 11, 13, 11)
            layout.addWidget(label(text, "Hint", True))
            return box

        def _vps_page(self) -> QFrame:
            card, layout = self._page(
                "VPS 连接配置", "建立安全连接，为部署准备好服务器。"
            )
            layout.addWidget(
                self._row(
                    self._field(
                        "vps_host",
                        title="主机地址",
                        placeholder="例如：203.0.113.10 或 vps.example.com",
                    ),
                    self._field("vps_port", title="SSH 端口"),
                    (3, 1),
                )
            )
            self.auth_group = QButtonGroup(self)
            self.auth_group.setExclusive(True)
            auth = QWidget()
            auth_layout = QVBoxLayout(auth)
            auth_layout.setContentsMargins(0, 0, 0, 0)
            auth_layout.setSpacing(7)
            auth_layout.addWidget(label("认证方式", "FieldLabel"))
            tabs = QHBoxLayout()
            for index, title in enumerate(("密码", "SSH 密钥")):
                button = QPushButton(title)
                button.setObjectName("Auth")
                button.setCheckable(True)
                button.setMinimumHeight(20)
                self.auth_group.addButton(button, index)
                tabs.addWidget(button)
            self.auth_group.button(0).setChecked(True)
            self.auth_group.idClicked.connect(self._update_auth)
            auth_layout.addLayout(tabs)
            layout.addWidget(
                self._row(self._field("vps_user", title="SSH 用户名"), auth)
            )
            layout.addWidget(
                self._field(
                    "vps_password", title="VPS 登录密码", placeholder="请输入登录密码"
                )
            )
            key = self._field("ssh_key_path")
            select_key = self.edits["ssh_key_path"].addAction(
                icon("folder"), QLineEdit.ActionPosition.TrailingPosition
            )
            select_key.setToolTip("选择 SSH 私钥")
            select_key.triggered.connect(self.choose_key)
            layout.addWidget(key)
            layout.addWidget(self._field("ssh_key_passphrase"))
            layout.addWidget(
                self._field(
                    "sudo_password",
                    title="sudo 密码（可选）",
                    placeholder="root 或免密 sudo 可留空",
                )
            )
            layout.addWidget(self._hint(SOURCE_HINTS["_build_vps_tab"][0]))
            layout.addStretch(1)
            return card

        def _telegram_page(self) -> QFrame:
            card, layout = self._page(
                "Telegram 机器人", "配置机器人凭据和使用者白名单。"
            )
            layout.addWidget(self._field("bot_token", placeholder="123456789:AA..."))
            layout.addWidget(
                self._row(
                    self._field("telegram_api_id", placeholder="填写数字 API ID"),
                    self._field("allowed_user_id", title="你的 Telegram 数字 ID"),
                )
            )
            layout.addWidget(
                self._field("telegram_api_hash", placeholder="32 位十六进制字符")
            )
            layout.addWidget(self._hint(SOURCE_HINTS["_build_telegram_tab"][0]))
            layout.addWidget(
                self._hint(
                    "凭据仅在当前程序内存中使用，部署时会写入 VPS 的受限配置文件。",
                    "SoftBox",
                )
            )
            layout.addStretch(1)
            return card

        def _cloud_page(self) -> QFrame:
            card, layout = self._page(
                (
                    "配置 WebDAV"
                    if self.product.is_openlist
                    else "CloudDrive2"
                ),
                "配置 WebDAV 入口与文件存储位置。",
            )
            layout.addWidget(
                self._field(
                    "cd2_url",
                    title="WebDAV 地址",
                    placeholder="https://dav.example.com/dav",
                )
            )
            self.cloud_mode_hint = label("", "Small", True)
            layout.addWidget(self.cloud_mode_hint)
            layout.addWidget(
                self._row(self._field("cd2_username"), self._field("cd2_password"))
            )
            layout.addWidget(
                self._field(
                    "cd2_target",
                    title="WebDAV 根目录后的子目录（可留空）",
                    placeholder="例如：Telegram / 根目录已是目标文件夹则留空",
                )
            )
            if self.product.is_openlist:
                self.edits["cd2_url"].setReadOnly(True)
                for name in ("cd2_url", "cd2_username", "cd2_password", "cd2_target"):
                    self._add_copy_action(name)
                regenerate = QPushButton("重新生成 WebDAV 密码")
                regenerate.clicked.connect(
                    lambda: self._regenerate_secret("cd2_password")
                )
                layout.addWidget(regenerate)
                self.preserve_webdav = QCheckBox(
                    "明确覆盖全部配置时，仍保留 VPS 当前 WebDAV 与管理员配置"
                )
                self.preserve_webdav.setToolTip(
                    "仅与“使用本页配置覆盖 VPS 当前 .env”配合；凭据只在 VPS 内合并"
                )
                self.preserve_webdav.setEnabled(False)
                self.preserve_webdav.toggled.connect(
                    self._update_preserve_webdav
                )
                layout.addWidget(self.preserve_webdav)
                layout.addWidget(
                    self._hint(
                        "先在 OpenList 添加你的云存储（例如 115 Open），再创建专用 WebDAV 用户。"
                        "用户名、密码和基本路径按本页建议填写；密码只在当前程序会话中保留。"
                    )
                )
            else:
                layout.addWidget(self._hint(SOURCE_HINTS["_build_cloud_tab"][0]))
            layout.addWidget(
                self._hint(
                    "WebDAV 验收只确认网关已接收文件。请在所用云存储的官方客户端确认最终文件大小和可打开状态。",
                    "SoftBox",
                )
            )
            if self.product.is_openlist:
                verification_box = frame("SoftBox")
                verification_layout = QVBoxLayout(verification_box)
                verification_layout.setContentsMargins(13, 11, 13, 11)
                verification_layout.setSpacing(6)
                verification_layout.addWidget(label("最终验收状态", "FieldLabel"))
                self.verification_summary = label(
                    "尚未执行。完成 OpenList 存储和 WebDAV 配置后，点击右侧“WebDAV 验收”。",
                    "Hint",
                    True,
                )
                self.verification_summary.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                verification_layout.addWidget(self.verification_summary)
                layout.addWidget(verification_box)
            layout.addStretch(1)
            return card

        def _openlist_page(self) -> QFrame:
            card, layout = self._page(
                "部署 OpenList",
                "OpenList 管理后台只通过固定 SSH 隧道访问，不开放公网端口。",
            )
            username = QLineEdit("admin")
            username.setReadOnly(True)
            username.setAccessibleName("OpenList 管理员用户名")
            username_box = QWidget()
            username_layout = QVBoxLayout(username_box)
            username_layout.setContentsMargins(0, 0, 0, 0)
            username_layout.setSpacing(7)
            username_layout.addWidget(label("OpenList 管理员用户名", "FieldLabel"))
            username_layout.addWidget(username)
            password_box = self._field("openlist_admin_password")
            self._add_copy_action("openlist_admin_password")
            self.openlist_credentials_row = self._row(username_box, password_box)
            layout.addWidget(self.openlist_credentials_row)
            self.openlist_regenerate_admin = QPushButton("重新生成首次管理员密码")
            self.openlist_regenerate_admin.clicked.connect(
                lambda: self._regenerate_secret("openlist_admin_password")
            )
            layout.addWidget(self.openlist_regenerate_admin)
            self.openlist_instance_notice = label(
                "尚未检测实例状态。全新部署将使用上方密码；已有实例不会自动重置。",
                "Hint",
                True,
            )
            layout.addWidget(self.openlist_instance_notice)
            layout.addWidget(
                self._hint(
                    "该密码只在全新 OpenList 数据目录首次初始化时生效。已有实例不会自动重置密码；"
                    "如需恢复密码，应使用带二次确认的高级操作。"
                )
            )
            layout.addWidget(
                self._hint(
                    "部署后点击“打开 OpenList 管理页”，登录并由你本人添加云存储（例如 115 Open）。"
                    "部署器不会读取任何云盘 Cookie、Token、OAuth 凭据或登录信息。",
                    "SoftBox",
                )
            )
            layout.addStretch(1)
            return card

        def _options_page(self) -> QFrame:
            card, layout = self._page(
                "部署选项与存储建议", "根据当前 VPS 资源设置安全的存储预算。"
            )
            self.managed = QCheckBox(
                f"在 VPS 上安装并管理 {self.product.display_name} 容器"
            )
            self.managed.setChecked(True)
            self.managed.toggled.connect(self._update_managed)
            layout.addWidget(self.managed)
            if not self.product.managed_toggle:
                self.managed.setEnabled(False)
                self.managed.setToolTip("OpenList 版始终部署独立的受管 OpenList 容器")
            layout.addWidget(
                self._row(self._field("install_dir"), self._field("timezone"))
            )
            layout.addWidget(
                self._row(
                    self._field("local_budget_gb"), self._field("min_free_disk_gb")
                )
            )
            self.redeploy_apply_config = QCheckBox(
                "已有 TG2Cloud：重新部署时使用本页配置覆盖 VPS 当前 .env"
            )
            self.redeploy_apply_config.setToolTip(
                "默认保留 VPS 上的全部现有配置；仅在确需修改配置且已备份时勾选"
            )
            self.redeploy_apply_config.toggled.connect(
                self._update_redeploy_apply_config
            )
            layout.addWidget(self.redeploy_apply_config)
            resources_box = frame("SoftBox")
            resources_layout = QVBoxLayout(resources_box)
            resources_layout.setContentsMargins(14, 13, 14, 13)
            resources_layout.setSpacing(11)
            resources_layout.addWidget(label("VPS 资源检测", "FieldLabel"))
            self.resource_summary = label(
                "尚未检测。测试 SSH 时也会自动生成实例级建议。", "Hint", True
            )
            self.resource_summary.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            resources_layout.addWidget(self.resource_summary)
            actions = QGridLayout()
            detect = QPushButton(self.ACTION_TITLES["detect_resources"])
            detect.setIcon(icon("disk"))
            detect.clicked.connect(lambda: self.run_operation("detect_resources"))
            self.action_buttons["detect_resources"] = detect
            actions.addWidget(detect, 0, 0, 1, 2)
            self.apply_buttons: dict[str, QPushButton] = {}
            for key, title in (
                ("balanced", "应用均衡值"),
                ("stream_first", "应用流式优先值"),
            ):
                button = QPushButton(title)
                button.setEnabled(False)
                button.clicked.connect(lambda checked=False, k=key: self.apply_plan(k))
                self.apply_buttons[key] = button
                actions.addWidget(button, 1, 0 if key == "balanced" else 1)
            resources_layout.addLayout(actions)
            layout.addWidget(resources_box)
            layout.addWidget(self._hint(SOURCE_HINTS["_build_options_tab"][0]))
            layout.addStretch(1)
            return card

        def _actions_card(self) -> QFrame:
            card = frame()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 19, 18, 17)
            layout.setSpacing(7)
            layout.addWidget(label("部署工作台", "SectionTitle"))
            layout.addWidget(label("配置完成后，按顺序执行。", "Hint"))
            layout.addSpacing(3)
            definitions = (
                ("test_connection", "server", "", "#6985aa"),
                ("deploy", "rocket", "Primary", "#ffffff"),
                *(
                    (("runtime_status", "check", "", "#6985aa"),)
                    if not self.product.is_openlist
                    else ()
                ),
                ("open_clouddrive", "external", "", "#6985aa"),
                ("repair_clouddrive", "wrench", "Repair", "#ac7b3e"),
                ("verify", "check", "Verify", "#26896f"),
            )
            hints = {
                "test_connection": "连接测试与 VPS 资源预检",
                "deploy": "部署 Bot、运行环境与选定服务",
                "runtime_status": "区分当前 TG2Cloud 与旧 TG115 实例",
                "open_clouddrive": "通过固定 SSH 隧道打开管理页",
                "repair_clouddrive": (
                    "检查容器与 VPS 回环管理端口"
                    if self.product.is_openlist
                    else "修复网络并调用原项目验收"
                ),
                "verify": "写入 → 大小校验 → 改名 → 清理",
            }
            for operation, symbol, role, color in definitions:
                button = QPushButton(self.ACTION_TITLES[operation])
                if role:
                    button.setObjectName(role)
                button.setIcon(icon(symbol, color, 19))
                button.setIconSize(QSize(19, 19))
                button.setMinimumHeight(22)
                button.clicked.connect(
                    lambda checked=False, op=operation: self.run_operation(op)
                )
                self.action_buttons[operation] = button
                layout.addWidget(button)
                hint = label(hints[operation], "Small", True)
                hint.setContentsMargins(3, 0, 0, 3)
                layout.addWidget(hint)
            if self.product.is_openlist:
                layout.addSpacing(4)
                layout.addWidget(frame("Divider"))
                layout.addWidget(label("OpenList 日常管理", "FieldLabel"))
                management = QGridLayout()
                management.setHorizontalSpacing(7)
                management.setVerticalSpacing(7)
                management_definitions = (
                    ("openlist_status", "check", "#6985aa"),
                    ("openlist_logs", "terminal", "#6985aa"),
                    ("restart_bot", "rocket", "#6985aa"),
                    ("restart_openlist", "cloud", "#6985aa"),
                    ("backup_openlist", "folder", "#26896f"),
                    ("reset_openlist_admin", "shield", "#ac7b3e"),
                )
                for index, (operation, symbol, color) in enumerate(
                    management_definitions
                ):
                    button = QPushButton(self.ACTION_TITLES[operation])
                    if operation == "reset_openlist_admin":
                        button.setObjectName("Repair")
                    button.setIcon(icon(symbol, color, 17))
                    button.setIconSize(QSize(17, 17))
                    button.setMinimumHeight(24)
                    button.clicked.connect(
                        lambda checked=False, op=operation: self.run_operation(op)
                    )
                    self.action_buttons[operation] = button
                    management.addWidget(button, index // 2, index % 2)
                layout.addLayout(management)
            layout.addStretch(1)
            divider = frame("Divider")
            layout.addWidget(divider)
            self.step_summary = label("下一步：填写配置，测试 SSH", "Hint", True)
            layout.addWidget(self.step_summary)
            return card

        def _log_panel(self) -> QWidget:
            panel = QWidget()
            panel.setMinimumHeight(38)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            head = QHBoxLayout()
            head.addWidget(label("运行日志", "FieldLabel"))
            self.progress = QProgressBar()
            self.progress.setTextVisible(False)
            self.progress.setFixedWidth(95)
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            head.addSpacing(6)
            head.addWidget(self.progress)
            head.addStretch()
            self.follow = QCheckBox("自动滚动")
            self.follow.setChecked(True)
            head.addWidget(self.follow)
            export = QPushButton("导出日志")
            export.setObjectName("Ghost")
            export.setIcon(icon("download", size=16))
            export.clicked.connect(self.export_log)
            head.addWidget(export)
            clear = QPushButton("清空")
            clear.setObjectName("Ghost")
            clear.clicked.connect(self.clear_log)
            head.addWidget(clear)
            self.log_toggle = QPushButton("收起日志")
            self.log_toggle.setObjectName("Ghost")
            self.log_toggle.clicked.connect(self.toggle_log)
            head.addWidget(self.log_toggle)
            layout.addLayout(head)
            self.console = QPlainTextEdit()
            self.console.setObjectName("Console")
            self.console.setReadOnly(True)
            self.console.setMinimumHeight(78)
            self.console.setMaximumBlockCount(20000)
            mono = (
                "Consolas"
                if "Consolas" in QFontDatabase.families()
                else "DejaVu Sans Mono"
            )
            self.console.setFont(QFont(mono, 10))
            layout.addWidget(self.console, 1)
            return panel

        def _load_backend(self) -> None:
            if self.preview:
                self.banner.setText(
                    "界面预览模式 · 可查看所有配置页，不连接 VPS、不执行远程操作。"
                )
                self.banner.show()
                return
            try:
                backend_type = _require_backend()
                self.backend = backend_type(
                    self.bridge.log.emit,
                    self._ask_from_worker,
                    self.bridge.resources.emit,
                    product=self.product,
                )
            except Exception as exc:  # noqa: BLE001 - dependency diagnostic boundary
                self.backend_error = str(exc)
                self.banner.setText(
                    "远程功能未就绪：请补齐 paramiko 和原项目 vps_resources.py。右上角可查看依赖详情。"
                )
                self.banner.show()
                return
            report = dependency_report(self.product)
            if report["payload_missing"]:
                self.banner.setText(
                    "产品 payload 不完整：请使用原项目的完整部署资源。测试 SSH、管理页和远程验收仍可使用。"
                )
                self.banner.show()

        @property
        def busy(self) -> bool:
            return self.worker is not None

        def snapshot(self) -> dict[str, str]:
            values = {key: edit.text() for key, edit in self.edits.items()}
            values["auth_method"] = (
                "密码" if self.auth_group.checkedId() == 0 else "SSH 密钥"
            )
            values["deploy_clouddrive2"] = (
                "true"
                if (self.product.is_openlist or self.managed.isChecked())
                else "false"
            )
            values["redeploy_apply_config"] = (
                "true" if self.redeploy_apply_config.isChecked() else "false"
            )
            if self.product.is_openlist:
                values["preserve_webdav"] = (
                    "true" if self.preserve_webdav.isChecked() else "false"
                )
            return values

        def _configuration_changed(self, *_: Any) -> None:
            # During construction not all widgets exist yet.
            if not hasattr(self, "apply_buttons"):
                return
            self._update_actions()
            if self.resource_update is not None and self.backend is not None:
                try:
                    fresh = (
                        self.backend._storage_probe_basis(self.snapshot())
                        == self.resource_update.basis
                    )
                except (ValueError, KeyError, TypeError):
                    fresh = False
                prefix = "" if fresh else "上次检测（配置已变更，请重新检测）\n"
                self.resource_summary.setText(prefix + self.resource_update.summary)
            if not self.busy and hasattr(self, "status"):
                self._status("准备就绪", "")

        def _update_auth(self, *_: Any) -> None:
            if "vps_password" not in self.field_boxes:
                return
            password = self.auth_group.checkedId() == 0
            self.field_boxes["vps_password"].setVisible(password)
            self.field_boxes["ssh_key_path"].setVisible(not password)
            self.field_boxes["ssh_key_passphrase"].setVisible(not password)
            self._configuration_changed()

        def _update_managed(self, *_: Any) -> None:
            if not hasattr(self, "managed"):
                return
            managed = self.managed.isChecked()
            edit = self.edits["cd2_url"]
            if self.product.is_openlist:
                edit.setText(self.product.webdav_url)
                edit.setReadOnly(True)
                self.cloud_mode_hint.setText(
                    "固定容器内网地址；不在公网传输 WebDAV 凭据。"
                )
                self._configuration_changed()
                return
            # Keep the user's external URL when toggling managed mode on and off.
            if managed:
                self._external_url = edit.text()
                edit.setText(self.product.webdav_url)
            elif hasattr(self, "_external_url"):
                edit.setText(self._external_url)
            edit.setReadOnly(managed)
            self.cloud_mode_hint.setText(
                "同机托管模式：使用 Docker 内网地址。可在“部署选项”中关闭托管。"
                if managed
                else "外部 WebDAV：公网地址必须使用 HTTPS。"
            )
            self._configuration_changed()

        def _update_preserve_webdav(self, checked: bool) -> None:
            for name in ("cd2_username", "cd2_password", "cd2_target"):
                self.field_boxes[name].setEnabled(not checked)
            self._configuration_changed()

        def _update_redeploy_apply_config(self, checked: bool) -> None:
            if self.product.is_openlist:
                self.preserve_webdav.setEnabled(checked)
                if not checked:
                    self.preserve_webdav.setChecked(False)
            self._configuration_changed()

        def _set_openlist_instance_state(self, state: str) -> None:
            if not self.product.is_openlist or not hasattr(
                self, "openlist_instance_notice"
            ):
                return
            if state == "existing":
                self.openlist_credentials_row.hide()
                self.openlist_regenerate_admin.hide()
                self.openlist_instance_notice.setText(
                    "检测到 OpenList 已初始化。原管理员凭据保持不变，请使用之前设置的账号登录；"
                    "部署器不会自动重置密码。忘记密码时再使用右侧高级恢复操作。"
                )
            elif state in {"new", "recovered"}:
                self.openlist_credentials_row.show()
                self.openlist_regenerate_admin.setVisible(state == "new")
                self.openlist_instance_notice.setText(
                    "全新 OpenList 已使用当前窗口中的管理员密码完成初始化。"
                    "请立即复制保存；关闭部署器后不会在 Windows 本地保留。"
                    if state == "new"
                    else "管理员密码已恢复。新密码显示在当前窗口的遮罩字段中；"
                    "请立即复制保存，关闭部署器后不会在 Windows 本地保留。"
                )
            else:
                raise ValueError("未知的 OpenList 实例状态")

        def _update_actions(self) -> None:
            ready = self.backend is not None and not self.busy and not self.preview
            for button in self.action_buttons.values():
                button.setEnabled(ready)
            if hasattr(self, "pages"):
                self.pages.setEnabled(not self.busy)
            for key, button in self.apply_buttons.items():
                safe = False
                if ready and self.resource_update is not None:
                    try:
                        fresh = (
                            self.backend._storage_probe_basis(self.snapshot())
                            == self.resource_update.basis
                        )
                        safe = fresh and getattr(self.resource_update.advice, key).safe
                    except (ValueError, KeyError, TypeError):
                        pass
                button.setEnabled(bool(safe))

        def choose_key(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择 SSH 私钥", "", "All files (*)"
            )
            if path:
                self.edits["ssh_key_path"].setText(path)
                self.edits["ssh_key_path"].setCursorPosition(len(path))

        @Slot(str)
        def append_log(self, text: str) -> None:
            if hasattr(self, "auth_group") and hasattr(self, "managed"):
                self.redactor.update(self.snapshot())
            clean = self.redactor.clean(text).rstrip()
            bar = self.console.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum() - 3
            cursor = QTextCursor(self.console.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            fmt = QTextCharFormat()
            if "[失败]" in clean:
                fmt.setForeground(QColor("#ffa89e"))
            elif "=OK" in clean or "=SUCCESS" in clean:
                fmt.setForeground(QColor("#82d5b5"))
            else:
                fmt.setForeground(QColor("#ced8e8"))
            stamp = dt.datetime.now(dt.UTC).astimezone().strftime("%H:%M:%S")
            cursor.insertText(f"{stamp}  {clean}\n", fmt)
            if self.follow.isChecked() and at_bottom:
                bar.setValue(bar.maximum())

        def clear_log(self) -> None:
            self.console.clear()

        def toggle_log(self) -> None:
            visible = self.console.isVisible()
            self.console.setVisible(not visible)
            self.log_toggle.setText("展开日志" if visible else "收起日志")
            if visible:
                self._saved_split = self.splitter.sizes()
                self.splitter.setSizes([sum(self._saved_split), 38])
            else:
                self.splitter.setSizes(getattr(self, "_saved_split", [550, 165]))

        def export_log(self) -> None:
            now = dt.datetime.now(dt.UTC).astimezone()
            name = f"tg2cloud-{now:%Y%m%d-%H%M%S}.log"
            path, _ = QFileDialog.getSaveFileName(
                self, "导出脱敏日志", name, "Log files (*.log);;Text (*.txt)"
            )
            if not path:
                return
            try:
                self.redactor.update(self.snapshot())
                Path(path).write_text(
                    self.redactor.clean(self.console.toPlainText()), encoding="utf-8"
                )
            except OSError as exc:
                QMessageBox.critical(self, "导出失败", str(exc))

        def _status(self, text: str, state: str) -> None:
            self.status.setText(text)
            self.status.setProperty("state", state)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)

        def _show_verification_statuses(
            self, statuses: tuple[tuple[str, str], ...]
        ) -> None:
            if not self.product.is_openlist or not hasattr(
                self, "verification_summary"
            ):
                return
            icons = {"通过": "✓", "失败": "✕", "未执行": "—", "执行中": "…"}
            lines = [
                f"{title}：{icons.get(state, '—')} {state}"
                for title, state in statuses
            ]
            self.verification_summary.setText("\n".join(lines))

        def run_operation(self, operation: str) -> None:
            if self.busy or self.preview or self.backend is None:
                return
            if operation not in self.ACTION_TITLES:
                raise ValueError("Unknown operation")
            values = self.snapshot()
            self.redactor.update(values)
            # Validate on the GUI thread for immediate, non-network feedback.
            try:
                if operation == "deploy":
                    self.backend._validate(values)
                else:
                    self.backend._validate_connection(values)
            except (ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, "请检查配置", str(exc))
                return
            if operation == "repair_clouddrive" and not self.product.is_openlist:
                answer = QMessageBox.question(
                    self,
                    "确认修复",
                    "将调用原项目修复脚本，可能重建容器网络并短暂中断服务。\n确认已备份重要数据并继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            if operation == "reset_openlist_admin":
                answer = QMessageBox.question(
                    self,
                    "高级操作：恢复管理员密码",
                    "这会立即替换现有 OpenList 管理员密码，旧密码将失效。\n"
                    "不会修改 WebDAV 用户密码，也不会读取云存储登录信息。\n\n"
                    "确认继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                phrase, accepted = QInputDialog.getText(
                    self,
                    "再次确认",
                    "请输入 RESET 以确认恢复管理员密码：",
                )
                if not accepted:
                    return
                if phrase.strip() != "RESET":
                    QMessageBox.warning(self, "未执行", "确认文字不匹配，操作已取消。")
                    return
            if operation == "backup_openlist":
                answer = QMessageBox.question(
                    self,
                    "创建一致性备份",
                    "为保证 OpenList 状态一致，备份期间会短暂停止 Bot 和 OpenList，"
                    "完成后自动恢复并检查健康状态。\n\n确认现在创建备份？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            if operation == "verify" and self.product.is_openlist:
                self._show_verification_statuses(
                    tuple((title, "执行中") for title, *_ in _VERIFICATION_STEPS)
                )
            self.worker = OperationThread(self.backend, operation, values, self)
            self.worker.succeeded.connect(
                self._operation_success, Qt.ConnectionType.QueuedConnection
            )
            self.worker.failed.connect(
                self._operation_failure, Qt.ConnectionType.QueuedConnection
            )
            self.worker.finished.connect(
                self._worker_finished, Qt.ConnectionType.QueuedConnection
            )
            self._status("正在执行", "running")
            self.step_summary.setText("当前操作：" + self.ACTION_TITLES[operation])
            self.progress.setRange(0, 0)
            self._update_actions()
            self.append_log("开始：" + self.ACTION_TITLES[operation])
            self.worker.start()

        @Slot(str, object)
        def _operation_success(self, operation: str, result: Any) -> None:
            self._status("操作完成", "success")
            self.footer_state.setText("最近成功：" + self.ACTION_TITLES[operation])
            next_steps = {
                "test_connection": "下一步：补全配置并部署基础环境",
                "deploy": (
                    "下一步：打开 OpenList，添加云存储并配置 WebDAV"
                    if self.product.is_openlist
                    else "下一步：打开 CloudDrive2，挂载云存储"
                ),
                "open_clouddrive": "下一步：完成存储和 WebDAV 配置后执行验收",
                "verify": "请在所用云存储的官方客户端确认最终文件",
                "repair_clouddrive": (
                    "OpenList 基础服务检查通过；WebDAV 仍需单独验收"
                    if self.product.is_openlist
                    else "网络修复已完成，请关注官方端文件状态"
                ),
                "detect_resources": "可在部署选项页应用安全建议",
                "runtime_status": "请依据状态检查结果决定是否部署或修复",
                "openlist_status": "请依据状态检查结果决定是否部署或修复",
                "openlist_logs": "最近的脱敏日志已显示在下方",
                "restart_bot": "Bot 已恢复运行，可继续发送任务",
                "restart_openlist": "OpenList 管理端已恢复响应",
                "backup_openlist": "备份已保存在 VPS 的受限目录",
                "reset_openlist_admin": "请复制并妥善保存新的管理员密码",
            }
            self.step_summary.setText(next_steps[operation])
            openlist_state = getattr(result, "openlist_state", "")
            if openlist_state:
                self._set_openlist_instance_state(openlist_state)
            secret_field = getattr(result, "secret_field", "")
            secret_value = getattr(result, "secret_value", "")
            if secret_field and secret_value:
                if secret_field not in self.edits:
                    raise RuntimeError("部署器无法显示恢复后的敏感信息")
                self.edits[secret_field].setText(secret_value)
                self.redactor.update(self.snapshot())
                if secret_field == OPENLIST_ADMIN_SECRET_FIELD:
                    self._set_openlist_instance_state("recovered")
            statuses = getattr(result, "statuses", ())
            if statuses:
                self._show_verification_statuses(statuses)
            self.append_log(result.title + "：" + result.message)
            if not self.exit_after_worker:
                QMessageBox.information(self, result.title, result.message)

        @Slot(str, object)
        def _operation_failure(self, operation: str, error: Any) -> None:
            statuses = getattr(error, "statuses", ())
            if statuses:
                self._show_verification_statuses(statuses)
            clean = self.redactor.clean(str(error))
            if getattr(error, "user_cancelled", False):
                self._status("操作已取消", "cancelled")
                self.footer_state.setText(
                    "最近取消：" + self.ACTION_TITLES[operation]
                )
                self.step_summary.setText("未修改未经确认的 SSH 主机记录")
                self.append_log("[已取消] " + clean)
                return
            self._status("操作失败", "error")
            self.step_summary.setText("请查看日志与错误详情")
            self.append_log("[失败] " + clean)
            if not self.exit_after_worker:
                QMessageBox.critical(
                    self, self.ACTION_TITLES[operation] + "失败", clean
                )

        @Slot()
        def _worker_finished(self) -> None:
            worker, self.worker = self.worker, None
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self._update_actions()
            if worker is not None:
                worker.deleteLater()
            if self.exit_after_worker:
                QTimer.singleShot(0, self.close)

        def _ask_from_worker(self, challenge: HostKeyChallenge) -> bool:
            question = Confirmation(challenge)
            self.bridge.confirm.emit(question)
            # Modal confirmation must never make an abandoned worker wait forever.
            question.done.wait(timeout=300)
            return question.done.is_set() and question.approved

        @Slot(object)
        def confirm_host_key(self, question: Confirmation) -> None:
            try:
                challenge = question.challenge
                dialog = QMessageBox(self)
                dialog.setTextFormat(Qt.TextFormat.PlainText)
                dialog.setIcon(QMessageBox.Icon.Warning)
                if challenge.reason == "changed":
                    dialog.setWindowTitle("SSH 主机密钥发生变化")
                    dialog.setText(
                        "检测到服务器返回的 SSH 主机密钥与本机记录不一致。\n\n"
                        f"服务器：{challenge.server}\n"
                        f"旧密钥类型：{challenge.old_key_type}\n"
                        f"旧 SHA256 指纹：{challenge.old_fingerprint}\n\n"
                        f"新密钥类型：{challenge.new_key_type}\n"
                        f"新 SHA256 指纹：{challenge.new_fingerprint}\n\n"
                        "常见原因包括 VPS 重装、恢复快照、重新生成 SSH 密钥或 IP 被重新分配；"
                        "如果这些情况都没有发生，也可能连接到了错误服务器或遭遇中间人攻击。\n\n"
                        "请先通过 VPS 服务商控制台核对新指纹。只有确认变化符合预期时，"
                        "才更新当前服务器的记录并自动重新连接。"
                    )
                    approve_text = "更新并重新连接"
                else:
                    dialog.setWindowTitle("确认 VPS 主机密钥")
                    dialog.setText(
                        "这是部署器首次连接此 SSH 服务器。\n\n"
                        f"服务器：{challenge.server}\n"
                        f"密钥类型：{challenge.new_key_type}\n"
                        f"SHA256 指纹：{challenge.new_fingerprint}\n\n"
                        "请与 VPS 服务商控制台显示的主机指纹核对。完全一致后，"
                        "再信任并保存此记录。"
                    )
                    approve_text = "信任并连接"
                cancel_button = dialog.addButton(
                    "取消", QMessageBox.ButtonRole.RejectRole
                )
                approve_button = dialog.addButton(
                    approve_text, QMessageBox.ButtonRole.AcceptRole
                )
                dialog.setDefaultButton(cancel_button)
                dialog.setEscapeButton(cancel_button)
                dialog.exec()
                question.approved = dialog.clickedButton() is approve_button
            finally:
                question.done.set()

        @Slot(object)
        def publish_resources(self, update: Any) -> None:
            self.resource_update = update
            self.resource_summary.setText(update.summary)
            self._update_actions()

        def apply_plan(self, key: str) -> None:
            if self.busy or self.backend is None:
                return
            try:
                budget, reserve = self.backend.storage_plan(key, self.snapshot())
                self.edits["local_budget_gb"].setText(budget)
                self.edits["min_free_disk_gb"].setText(reserve)
            except (ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, "无法应用建议", str(exc))

        def _diagnostics_dialog(self) -> QDialog:
            report = dependency_report(self.product)
            dialog = QDialog(self)
            dialog.setWindowTitle("依赖检查与关于")
            dialog.setWindowIcon(brand_icon())
            dialog.resize(700, 500)
            layout = QVBoxLayout(dialog)
            about_logo = label("")
            about_logo.setObjectName("AboutLogo")
            about_logo.setPixmap(brand_pixmap(BRAND_LOGO_ASSET, 300, 100))
            about_logo.setAlignment(Qt.AlignmentFlag.AlignLeft)
            about_logo.setAccessibleName("TG2Cloud Logo")
            dialog.brand_logo_label = about_logo
            layout.addWidget(about_logo)
            layout.addWidget(
                label(
                    f"{self.product.app_title}\n"
                    "From Telegram to Your Cloud\n"
                    f"产品 v{self.product.app_version}  /  界面 {UI_VERSION}",
                    "SectionTitle",
                    True,
                )
            )
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setPlainText(
                json.dumps(
                    {
                        **report,
                        "backend_error": self.backend_error,
                        "preview_mode": self.preview,
                        "note": "TG2Cloud 不收集云存储账号、Token 或 Cookie；网盘配置只在用户自己的 CloudDrive2 或 OpenList 中完成。",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            layout.addWidget(view)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            return dialog

        def show_diagnostics(self) -> None:
            dialog = self._diagnostics_dialog()
            dialog.exec()

        def closeEvent(self, event: Any) -> None:
            if self.busy:
                if not self.exit_after_worker:
                    answer = QMessageBox.question(
                        self,
                        "操作正在进行",
                        "直接终止可能中断远程安装。\n是否等当前操作结束后自动关闭？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    self.exit_after_worker = answer == QMessageBox.StandardButton.Yes
                    if self.exit_after_worker:
                        self.step_summary.setText("当前操作结束后自动退出")
                event.ignore()
                return
            if self.backend is not None:
                try:
                    self.backend.close()
                except Exception as exc:  # noqa: BLE001 - GUI shutdown boundary
                    self.append_log("关闭 SSH 隧道时发生错误：" + str(exc))
            event.accept()

    # Preserve the original class symbol; construction now uses Qt, not Tk.
    InstallerApp = InstallerWindow


def make_app() -> QApplication:
    _require_qt()
    if (
        os.name != "nt"
        and not os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
        and "QT_QPA_PLATFORM" not in os.environ
    ):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("TG2Cloud Deployer")
    app.setOrganizationName("TG2Cloud")
    app.setWindowIcon(brand_icon())
    app.setStyle("Fusion")
    fonts = QFontDatabase.families()
    family = next(
        (
            f
            for f in (
                "Microsoft YaHei UI",
                "PingFang SC",
                "Noto Sans CJK SC",
                "WenQuanYi Micro Hei",
            )
            if f in fonts
        ),
        "Sans Serif",
    )
    app.setFont(QFont(family, 10))
    app.setStyleSheet(STYLE)
    return app


# ============================================================================
# 6. Local self-test and script entry point
# ============================================================================


def packaged_self_test(
    result_path: Path,
    product: ProductProfile = CLOUDDRIVE2_PRODUCT,
) -> int:
    """Check local runtime/resources only; no VPS or cloud storage is contacted."""
    result_path = Path(result_path)
    gui_ok = False
    ui_error = ""
    window = None
    try:
        app = make_app()
        window = (
            InstallerWindow(preview=True)
            if product == CLOUDDRIVE2_PRODUCT
            else InstallerWindow(preview=True, product=product)
        )
        app.processEvents()
        gui_ok = set(window.snapshot()) == set(defaults_for(product))
    except Exception as exc:  # noqa: BLE001 - packaged GUI diagnostic boundary
        ui_error = str(exc)
    finally:
        if window is not None:
            window.close()
    report = dependency_report(product)
    backend_ok = False
    backend_error = ""
    try:
        _require_backend()
        backend_ok = True
    except Exception as exc:  # noqa: BLE001 - packaged backend diagnostic boundary
        backend_error = str(exc)
    succeeded = bool(report["ready"]) and gui_ok and backend_ok
    try:
        import PySide6

        pyside6_version = PySide6.__version__
    except ImportError:
        pyside6_version = "MISSING"
    paramiko_version = (
        getattr(paramiko, "__version__", "UNKNOWN")
        if _SSH_IMPORT_ERROR is None
        else "MISSING"
    )
    # A report is generated even when runtime modules are missing.
    error = (ui_error or backend_error).replace(chr(13), " ").replace(chr(10), " | ")
    lines = [
        f"product={product.key}",
        f"app_version={product.app_version}",
        f"ui_version={UI_VERSION}",
        f"pyside6_version={pyside6_version}",
        f"paramiko_version={paramiko_version}",
        "payload_missing=" + ",".join(report["payload_missing"]),
        "brand_missing=" + ",".join(report["brand_missing"]),
        f"gui_runtime={'OK' if gui_ok else 'FAILED'}",
        f"backend_import={'OK' if backend_ok else 'FAILED'}",
        f"error={error}",
        "remote_test=NOT_RUN",
        f"result={'OK' if succeeded else 'FAILED'}",
    ]
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if succeeded else 1


def main(
    argv: list[str] | None = None,
    *,
    product: ProductProfile = CLOUDDRIVE2_PRODUCT,
) -> int:
    parser = argparse.ArgumentParser(description=product.app_title)
    parser.add_argument(
        "--preview", action="store_true", help="UI only; all remote actions disabled"
    )
    parser.add_argument(
        "--screenshots", type=Path, help="Save native Qt screenshots; implies --preview"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Print local dependency diagnostics; no SSH",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-result", type=Path)
    args = parser.parse_args(argv)
    if args.check_deps:
        report = dependency_report(product)
        report["backend_import_error"] = str(_BACKEND_IMPORT_ERROR or "")
        report["gui_import_error"] = str(_QT_IMPORT_ERROR or "")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return (
            0
            if report["ready"]
            and _BACKEND_IMPORT_ERROR is None
            and _QT_IMPORT_ERROR is None
            else 1
        )
    if args.self_test:
        result_path = args.self_test_result
        if result_path is None:
            result_path = Path(tempfile.gettempdir()) / "tg2cloud-self-test.txt"
        return packaged_self_test(result_path, product)
    _require_qt()
    app = make_app()
    window = InstallerWindow(
        preview=args.preview or args.screenshots is not None,
        product=product,
    )
    window.show()
    capture_error: list[str] = []
    if args.screenshots is not None:
        args.screenshots.mkdir(parents=True, exist_ok=True)

        def capture() -> None:
            try:
                names = (
                    (
                        "01-vps",
                        "02-telegram",
                        "03-openlist",
                        "04-webdav",
                        "05-options",
                    )
                    if product.is_openlist
                    else ("01-vps", "02-telegram", "03-clouddrive", "04-options")
                )
                for index, name in enumerate(names):
                    window.nav_group.button(index).setChecked(True)
                    window._change_page(index)
                    app.processEvents()
                    if not window.grab().save(str(args.screenshots / f"{name}.png")):
                        raise RuntimeError("Screenshot write failed: " + name)
                about = window._diagnostics_dialog()
                about.show()
                app.processEvents()
                if not about.grab().save(str(args.screenshots / "about.png")):
                    raise RuntimeError("Screenshot write failed: about")
                about.close()
            except Exception as exc:  # noqa: BLE001 - preview capture boundary
                capture_error.append(str(exc))
                if sys.stderr is not None:
                    print(str(exc), file=sys.stderr)
            finally:
                window.close()
                app.quit()

        QTimer.singleShot(500, capture)
    code = app.exec()
    return 1 if capture_error else code


def _startup_error(message: str, title: str = APP_TITLE) -> None:
    """Show missing-runtime errors even when launched with pythonw on Windows."""
    if sys.stderr is not None:
        print(message, file=sys.stderr)
    if os.name == "nt" and (sys.stderr is None or not sys.stderr.isatty()):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        except Exception:  # noqa: BLE001,S110  # nosec B110
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _startup_error(str(exc))
        raise SystemExit(1) from exc
