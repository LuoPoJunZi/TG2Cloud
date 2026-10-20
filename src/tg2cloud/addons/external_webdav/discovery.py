"""Reuse core identities; never install/restart/repair a gateway."""
from __future__ import annotations

import json
import shutil

from tg2cloud.addons.external_webdav.config import decode
from tg2cloud.deployment import architecture, instances, preflight


def host(session, *, log=None) -> None:
    preflight.validate_host(log=log)
    architecture.check_environment()
    for tool in ("docker", "bash", "openssl", "curl", "ss", "ip", "getent", "flock", "timeout"):
        if not shutil.which(tool):
            raise ValueError("缺少工具 " + tool + "；请人工准备，不自动安装系统软件。")
    architecture.check_docker(session)


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
