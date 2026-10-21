"""Strict metadata and deterministic, single-hop external Nginx rendering.

Only the standard library is used. Downloaded Nginx configuration is data, never
Python or shell code. Ambiguous include contexts are rejected, not guessed.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import ipaddress
import json
import re
import shlex
from pathlib import PurePosixPath

from .state import EDITION_BACKEND_PORTS, validate_domain

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
HEX = re.compile(r"[0-9a-f]{64}")
OWNER = "tg2cloud.external_docker.v1"
PREFIX = "tg2cloud-"


def identifier(value: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("Docker 名称或网络名格式不安全。")
    return value


def absolute_path(value: str) -> str:
    if (not isinstance(value, str) or not value.startswith("/") or value == "/"
            or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value)
            or any(part in {"", ".", ".."} for part in value.split("/")[1:])):
        raise ValueError("外部入口路径必须为不含链接、空格或特殊字符的绝对路径。")
    return value


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_entry(value: dict) -> dict:
    required = {"mode", "owner", "identity", "mount", "network", "files", "certificates", "revision"}
    if not isinstance(value, dict) or set(value) != required or value.get("mode") != "external_docker" or value.get("owner") != OWNER:
        raise ValueError("外部 Docker Nginx 状态归属或字段不受支持。")
    result = copy.deepcopy(value)
    identity = result["identity"]
    fields = {"name", "container_id", "image", "image_id", "project", "service", "working_dir", "config_files", "config_digest"}
    if not isinstance(identity, dict) or set(identity) != fields:
        raise ValueError("外部容器身份记录不完整。")
    identifier(identity["name"])
    if identity["name"] in {"tg2cloud-proxy-nginx", "tg2cloud-proxy-certbot"}:
        raise ValueError("TG2Cloud 自带代理不能冒充外部代理。")
    if not HEX.fullmatch(identity["container_id"]) or not HEX.fullmatch(identity["config_digest"]):
        raise ValueError("外部容器身份／配置摘要无效。")
    if not isinstance(identity["image_id"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity["image_id"]):
        raise ValueError("外部镜像不可变身份无效。")
    if not isinstance(identity["image"], str) or not re.fullmatch(r"[A-Za-z0-9_./:@-]{1,512}", identity["image"]):
        raise ValueError("外部镜像引用无效。")
    if identity["project"]:
        identifier(identity["project"])
        identifier(identity["service"])
        absolute_path(identity["working_dir"])
    if not isinstance(identity["config_files"], list) or len(identity["config_files"]) > 8:
        raise ValueError("外部 Compose 清单不受支持。")
    for path in identity["config_files"]:
        absolute_path(path)
    mount = result["mount"]
    if not isinstance(mount, dict) or set(mount) != {"source", "destination", "type", "name", "conf_dir", "host_dir", "worker_gid"}:
        raise ValueError("外部持久化挂载记录不完整。")
    for key in ("source", "destination", "conf_dir", "host_dir"):
        absolute_path(mount[key])
    if mount["type"] not in {"bind", "volume"} or type(mount["worker_gid"]) is not int or not 0 <= mount["worker_gid"] < 65536:
        raise ValueError("外部持久化挂载／worker 组不受支持。")
    if mount["type"] == "volume":
        identifier(mount["name"])
    relative = PurePosixPath(mount["conf_dir"]).relative_to(mount["destination"])
    if str(PurePosixPath(mount["source"]) / relative) != mount["host_dir"]:
        raise ValueError("容器目录与宿主目录映射不一致。")
    network = result["network"]
    if not isinstance(network, dict) or set(network) != {"mode", "name", "id", "listen_address"}:
        raise ValueError("外部网络记录不完整。")
    if network["mode"] not in {"host", "bridge"}:
        raise ValueError("只支持 host 或自定义 bridge 网络。")
    if network["mode"] == "bridge":
        identifier(network["name"])
        if network["name"] == "bridge" or not HEX.fullmatch(network["id"]):
            raise ValueError("默认 bridge 或未知网络不支持持久化接入。")
    address = ipaddress.ip_address(network["listen_address"])
    if address.is_unspecified or address.is_multicast:
        raise ValueError("本机验收地址无效。")
    if not isinstance(result["files"], dict) or len(result["files"]) > 20:
        raise ValueError("受管文件清单无效。")
    for name, digest in result["files"].items():
        if not re.fullmatch(r"tg2cloud-(?:clouddrive2|openlist|webdav-clouddrive2|webdav-openlist)\.conf", name) or not HEX.fullmatch(digest):
            raise ValueError("受管配置名称或摘要无效。")
    if not isinstance(result["certificates"], dict) or len(result["certificates"]) > 4:
        raise ValueError("证书记录无效。")
    for domain, cert in result["certificates"].items():
        validate_domain(domain)
        fields = {"owner", "chain", "key", "name", "loaded", "pending_load", "last_attempt", "last_success", "last_change"}
        if not isinstance(cert, dict) or set(cert) != fields or cert["owner"] not in {"tg2cloud", "external"}:
            raise ValueError("证书归属记录无效。")
        absolute_path(cert["chain"])
        absolute_path(cert["key"])
        if cert["name"] != domain or type(cert["pending_load"]) is not bool:
            raise ValueError("证书名称或加载记录无效。")
        if cert["loaded"] and not HEX.fullmatch(cert["loaded"]):
            raise ValueError("服务证书摘要无效。")
        for key in ("last_attempt", "last_success", "last_change"):
            if type(cert[key]) is not int or cert[key] < 0:
                raise ValueError("证书检查时间无效。")
    if not re.fullmatch(r"[0-9a-f]{32}", result["revision"]):
        raise ValueError("外部入口修订无效。")
    return result


def configuration_files(dump: str) -> dict[str, str]:
    if len(dump.encode()) > 4 * 1024 * 1024:
        raise ValueError("Nginx 配置输出超过安全上限。")
    result = {}
    current = None
    for line in dump.splitlines():
        match = re.fullmatch(r"# configuration file (/[A-Za-z0-9_./-]+):", line)
        if match:
            current = absolute_path(match[1])
            if current in result:
                raise ValueError("重复的 Nginx 配置来源。")
            result[current] = ""
        elif current:
            result[current] += line + "\n"
    if not result:
        raise ValueError("无法识别 nginx -T 配置入口；仅支持标准配置输出。")
    return result


def directives(text: str):
    """Yield (context, statement); fail closed on unsupported/ambiguous syntax."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars="{};")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    stack, statement = [], []
    tokens = (part for token in lexer for part in (list(token) if re.fullmatch(r"[{};]+", token) else [token]))
    for lexeme in tokens:
        if lexeme in {"{", "}", ";"}:
            if lexeme == "{":
                if not statement:
                    raise ValueError("Nginx 配置块无法解析。")
                yield tuple(stack), tuple(statement + ["{"])
                stack.append(statement[0])
            elif lexeme == "}":
                if statement or not stack:
                    raise ValueError("Nginx 配置上下文无法解析。")
                stack.pop()
            elif statement:
                yield tuple(stack), tuple(statement)
            statement = []
        else:
            statement.append(lexeme)
    if stack or statement:
        raise ValueError("Nginx 配置不完整。")


def http_includes(files: dict[str, str]) -> tuple[str, ...]:
    main = next(iter(files))
    result = []

    def visit(path: str, inherited: tuple[str, ...], chain: tuple[str, ...]):
        if path in chain or len(chain) > 16:
            raise ValueError("Nginx include 循环或层级过深。")
        for context, words in directives(files[path]):
            context = inherited + context
            if words[0] != "include" or len(words) != 2:
                continue
            pattern = words[1]
            if not pattern.startswith("/"):
                raise ValueError("相对 include 不支持自动写入；请使用配置导出。")
            if pattern.endswith("/*.conf") and context == ("http",):
                result.append(pattern[:-7])
            for name in files:
                if fnmatch.fnmatchcase(name, pattern):
                    visit(name, context, (*chain, path))
    visit(main, (), ())
    return tuple(sorted(set(result)))


def conflicting_names(files: dict[str, str], domain: str, owned: set[str]) -> tuple[str, ...]:
    result = []
    for path, content in files.items():
        if path in owned:
            continue
        for _, words in directives(content):
            if words[0] != "server_name":
                continue
            for name in words[1:]:
                name = name.lower()
                if (name == domain or (name.startswith(".") and (domain == name[1:] or domain.endswith(name)))
                        or ("*" in name and fnmatch.fnmatchcase(domain, name)) or name.startswith("~")):
                    result.append(path)
    return tuple(sorted(set(result)))


def global_digest(files: dict[str, str], owned: set[str]) -> str:
    material = {path: value for path, value in files.items() if path not in owned}
    return checksum(json.dumps(material, sort_keys=True).encode())


def compose_network(text: str, edition: str, network: str) -> str:
    """Transform only our official template, never an external Compose file."""
    identifier(network)
    if edition not in EDITION_BACKEND_PORTS:
        raise ValueError("未知 Edition。")
    own = "tg2cloud-" + edition + "-net"
    marker = "    networks:\n      - " + own + "\n"
    if text.count(marker) != 2 or "tg2cloud-external-entry" in text:
        raise ValueError("网关 Compose 不符合受管模板，停止网络修改。")
    return text.replace(marker, marker + "      - tg2cloud-external-entry\n", 1) + (
        "\n  tg2cloud-external-entry:\n    external: true\n    name: " + network + "\n"
    )


def render_route(route, entry: dict, *, bootstrap: bool = False) -> str:
    """Reuse existing DAV policy; replace only owned endpoint/resource values."""
    from .manager import render_bootstrap_conf, render_route_conf
    domain = route.domain if hasattr(route, "domain") else route["domain"]
    port = route.backend_port if hasattr(route, "backend_port") else route["backend_port"]
    domain = validate_domain(domain)
    asset = entry["mount"]["conf_dir"] + "/tg2cloud-assets"
    if bootstrap:
        return "# " + OWNER + "\n" + render_bootstrap_conf(domain).replace("/var/www/certbot", asset + "/webroot")
    if isinstance(route, dict):
        from tg2cloud.addons.external_webdav.nginx import render_route as dav_route
        text = dav_route(route).replace("/etc/nginx/external-auth", asset + "/auth")
        edition = route["edition"]
    else:
        text, edition = render_route_conf(route), route.edition
    cert = entry["certificates"][domain]
    text = text.replace("/var/www/certbot", asset + "/webroot")
    text = text.replace(f"/etc/letsencrypt/live/{domain}/fullchain.pem", cert["chain"])
    text = text.replace(f"/etc/letsencrypt/live/{domain}/privkey.pem", cert["key"])
    # Do not depend on variables defined by someone else's global nginx.conf.
    text = text.replace("$connection_upgrade", '"upgrade"')
    text = text.replace("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;", "proxy_set_header X-Forwarded-For $remote_addr;")
    text = text.replace("ssl_session_cache shared:TG2CloudTLS:10m;", "ssl_session_cache off;")
    if entry["network"]["mode"] == "bridge":
        backend = "tg2cloud-" + edition
        # Variable upstreams use Docker DNS again after backend recreation.
        token = "$tg2cloud_" + edition + "_backend"
        text = text.replace("proxy_pass http://127.0.0.1:" + str(port), "proxy_pass http://" + token)
        # A variable URI must explicitly preserve the request URI.
        text = text.replace("proxy_pass http://" + token + ";", "proxy_pass http://" + token + "$request_uri;")
        text = text.replace("proxy_pass http://" + token + "/dav/;", "proxy_pass http://" + token + "/dav/;")
        text = text.replace("    server_name " + domain + ";", "    server_name " + domain + ";\n    resolver 127.0.0.11 valid=10s ipv6=off;\n    set " + token + " " + backend + ":" + str(port) + ";")
    return "# " + OWNER + "\n" + text
