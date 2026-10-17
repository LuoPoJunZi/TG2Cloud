"""Reuse core identities; never install/restart/repair a gateway."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
from pathlib import Path

from tg2cloud.addons.external_webdav.config import decode
from tg2cloud.deployment import instances


def host(session) -> None:
    if platform.system() != "Linux" or os.geteuid() != 0 or platform.machine().lower() not in {"x86_64", "amd64", "aarch64", "arm64"}:
        raise ValueError("需本机 Linux root，x86_64 或 ARM64；实际网关架构仍需独立验收。")
    if not re.search(r'(?m)^ID="?(?:debian|ubuntu)"?$', Path("/etc/os-release").read_text()):
        raise ValueError("当前支持 Debian/Ubuntu；不修改其他系统。")
    if any(os.environ.get(key) for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "COMPOSE_FILE", "COMPOSE_PROJECT_NAME")):
        raise ValueError("拒绝继承远程 Docker 或 Compose 覆盖环境。")
    for tool in ("docker", "bash", "openssl", "curl", "ss", "ip", "getent", "flock", "timeout"):
        if not shutil.which(tool):
            raise ValueError("缺少工具 " + tool + "；请人工准备，不自动安装系统软件。")
    code, output = session.run("docker context inspect --format '{{.Endpoints.docker.Host}}' && docker info --format '{{json .SecurityOptions}}'", timeout=20)
    if code or not output.startswith("unix:///var/run/docker.sock\n") or "rootless" in output.lower():
        raise ValueError("只支持本机默认 rootful Docker daemon。")


def selected(product, directory, session, log, *, require_running: bool = True):
    item = instances.discover(product, instances.docker_inventory(session), session, log, install_dir=directory)
    if not item.present:
        raise ValueError("尚无完整 TG2Cloud 实例；附加功能不调用主安装器。")
    gateway = instances.inspect_container(session, product.storage_container)
    if require_running and not gateway.get("running"):
        raise ValueError("所选存储网关未运行；请先自行处理，不自动重启。")
    if decode(item.config, "URL").rstrip("/") != product.webdav_url.rstrip("/"):
        raise ValueError("此实例不是当前支持的同机受管 WebDAV 后端。")
    code, output = session.run("docker inspect --format '{{json .HostConfig.PortBindings}}' " + product.storage_container, timeout=15)
    if code:
        raise ValueError("无法核对网关发布端口。")
    port = str(product.management_port)
    bindings = {key: value for key, value in (json.loads(output) or {}).items() if value}
    if bindings != {port + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]}:
        raise ValueError("网关不再仅发布受管回环端口；不自动修改监听或防火墙。")
    return item
