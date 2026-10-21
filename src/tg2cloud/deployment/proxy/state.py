from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any

from tg2cloud.deployment.profiles import ProductProfile

STATE_VERSION = 1
EXTERNAL_STATE_VERSION = 2

SUPPORTED_EDITIONS = ("clouddrive2", "openlist")

EDITION_BACKEND_PORTS = {"clouddrive2": 19798, "openlist": 5244}

_FQDN_RE = re.compile(
    r"(?=^.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+")

_MARKER_RE = re.compile(r"^TG2CLOUD_([A-Z0-9_]+)=(.*)$")

@dataclass(frozen=True)
class DomainRoute:
    edition: str
    domain: str
    backend_port: int

@dataclass(frozen=True)
class ProxyEnvironment:
    core: str
    docker: str
    port_80: str
    port_443: str
    dns_a: tuple[str, ...] = ()
    dns_aaaa: tuple[str, ...] = ()
    local_addresses: tuple[str, ...] = ()
    # Ephemeral operator confirmation; never read from remote markers or state.
    confirmed_public_ipv4: str = ""

    @property
    def ports_safe(self) -> bool:
        return self.port_80 in {"FREE", "OWN"} and self.port_443 in {"FREE", "OWN"}

@dataclass(frozen=True)
class ProxyReport:
    domain: str
    state: str
    message: str
    statuses: tuple[tuple[str, str], ...]
    markers: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()

def validate_domain(value: str) -> str:
    """Return a strict lowercase ASCII FQDN or raise a user-facing error."""
    domain = value.strip().lower().rstrip(".")
    if not domain:
        raise ValueError("请填写要用于管理页的域名。")
    if any(char.isspace() for char in value):
        raise ValueError("域名不能包含空格或换行。")
    if "://" in domain or any(char in domain for char in "/?#@:*\\'\";$`()[]{}|<>"):
        raise ValueError("只填写域名，不要包含协议、端口、路径、通配符或命令字符。")
    try:
        ipaddress.ip_address(domain.strip("[]"))
    except ValueError:
        pass
    else:
        raise ValueError("必须使用域名，不能填写 IPv4 或 IPv6 地址。")
    if not domain.isascii():
        raise ValueError("请输入域名的 ASCII/Punycode 形式（例如 xn-- 开头的域名）。")
    if not _FQDN_RE.fullmatch(domain):
        raise ValueError("域名格式不正确；请填写完整的 ASCII/Punycode FQDN。")
    return domain

def validate_email(value: str) -> str:
    email = value.strip()
    if not email:
        return ""
    if any(char.isspace() for char in email) or not email.isascii():
        raise ValueError("Let's Encrypt 邮箱格式不正确。")
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("Let's Encrypt 邮箱格式不正确。")
    return email

def empty_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "domains": {}}

def normalize_state(raw: str | bytes | None) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "strict")
    if raw is None or not raw.strip():
        return empty_state()
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("共享代理状态文件不是有效 JSON；请先检查 VPS 上的状态。") from exc
    if (not isinstance(value, dict) or type(value.get("version")) is not int
            or value.get("version") not in {STATE_VERSION, EXTERNAL_STATE_VERSION}):
        raise ValueError("共享代理状态版本无法识别；不会自动覆盖。")
    domains = value.get("domains")
    if not isinstance(domains, dict) or set(domains) - set(SUPPORTED_EDITIONS):
        raise ValueError("共享代理状态包含未知 Edition；不会自动覆盖。")
    normalized = empty_state()
    if value["version"] == EXTERNAL_STATE_VERSION:
        if set(value) != {"version", "domains", "external_webdav"}:
            raise ValueError("共享代理状态含未知资源；拒绝覆盖。")
        normalized.update(version=EXTERNAL_STATE_VERSION, external_webdav={})
    elif set(value) - {"version", "domains"}:
        raise ValueError("旧状态含未声明资源；拒绝丢弃或降级。")
    seen: set[str] = set()
    for edition, item in domains.items():
        if not isinstance(item, dict):
            raise TypeError("共享代理域名状态格式不正确。")
        if set(item) != {"domain", "backend_port"}:
            raise ValueError("管理路由含未知字段；拒绝丢弃资源。")
        domain = validate_domain(str(item.get("domain", "")))
        if domain in seen:
            raise ValueError("同一个域名不能同时分配给两个 Edition。")
        port = int(item.get("backend_port", 0))
        expected_port = EDITION_BACKEND_PORTS[edition]
        if port != expected_port:
            raise ValueError(
                f"共享代理状态中的 {edition} 后端端口应为 {expected_port}；不会自动覆盖。"
            )
        seen.add(domain)
        normalized["domains"][edition] = {
            "domain": domain,
            "backend_port": port,
        }
    if value["version"] == EXTERNAL_STATE_VERSION:
        entries = value.get("external_webdav")
        if not isinstance(entries, dict) or set(entries) - set(SUPPORTED_EDITIONS):
            raise ValueError("外部 WebDAV 路由清单无法识别。")
        for edition, item in entries.items():
            required = {"kind", "owner", "edition", "instance_dir", "domain", "enabled", "backend_port", "auth_file"}
            if not isinstance(item, dict) or set(item) != required:
                raise ValueError("外部 WebDAV 路由字段不完整或未知。")
            if (item["kind"] != "external_webdav" or item["owner"] != "tg2cloud.external_webdav"
                    or item["edition"] != edition or type(item["enabled"]) is not bool
                    or item["backend_port"] != EDITION_BACKEND_PORTS[edition]
                    or item["auth_file"] != f"external-auth/{edition}.htpasswd"
                    or not isinstance(item["instance_dir"], str)
                    or not re.fullmatch(r"/opt/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", item["instance_dir"])
                    or any(part in {".", ".."} for part in item["instance_dir"].split("/"))):
                raise ValueError("外部 WebDAV 路由归属不符。")
            domain = validate_domain(item["domain"])
            if domain in seen:
                raise ValueError("外部域名与已有路由冲突。")
            seen.add(domain)
            normalized["external_webdav"][edition] = dict(item, domain=domain)
    return normalized

def state_with_route(
    state: dict[str, Any], product: ProductProfile, domain: str
) -> dict[str, Any]:
    result = normalize_state(json.dumps(state))
    domain = validate_domain(domain)
    for edition, item in result["domains"].items():
        if edition != product.key and item["domain"] == domain:
            raise ValueError("该域名已分配给另一个 TG2Cloud Edition。")
    if any(item["domain"] == domain for item in result.get("external_webdav", {}).values()):
        raise ValueError("该域名已由外部 WebDAV 使用。")
    result["domains"][product.key] = {
        "domain": domain,
        "backend_port": product.management_port,
    }
    return result

def state_without_route(state: dict[str, Any], edition: str) -> dict[str, Any]:
    result = normalize_state(json.dumps(state))
    result["domains"].pop(edition, None)
    return result

def routes_from_state(state: dict[str, Any]) -> tuple[DomainRoute, ...]:
    normalized = normalize_state(json.dumps(state))
    return tuple(
        DomainRoute(edition, item["domain"], item["backend_port"])
        for edition, item in sorted(normalized["domains"].items())
    )


def has_routes(state: dict[str, Any]) -> bool:
    return bool(state["domains"] or state.get("external_webdav"))


def certificate_domains(state: dict[str, Any]) -> tuple[str, ...]:
    current = normalize_state(json.dumps(state))
    return tuple(sorted(item["domain"] for group in (current["domains"], current.get("external_webdav", {}))
                        for item in group.values()))

def parse_markers(output: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in output.splitlines():
        match = _MARKER_RE.fullmatch(line.strip())
        if match:
            markers[match.group(1)] = match.group(2)
    return markers

def _marker_addresses(markers: dict[str, str], key: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in markers.get(key, "").split(","):
        value = raw.strip()
        if not value:
            continue
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if key == "PROXY_DNS_A" and address.version != 4:
            continue
        if key == "PROXY_DNS_AAAA" and (
            address.version != 6 or getattr(address, "ipv4_mapped", None) is not None
        ):
            continue
        result.append(str(address))
    return tuple(sorted(set(result)))

def parse_environment(output: str) -> ProxyEnvironment:
    markers = parse_markers(output)
    return ProxyEnvironment(
        core=markers.get("PROXY_CORE", "UNKNOWN"),
        docker=markers.get("PROXY_DOCKER", "UNKNOWN"),
        port_80=markers.get("PROXY_PORT_80", "UNKNOWN"),
        port_443=markers.get("PROXY_PORT_443", "UNKNOWN"),
        dns_a=_marker_addresses(markers, "PROXY_DNS_A"),
        dns_aaaa=_marker_addresses(markers, "PROXY_DNS_AAAA"),
        local_addresses=_marker_addresses(markers, "PROXY_LOCAL_IPS"),
    )

def _expected_addresses(environment: ProxyEnvironment, ssh_host: str) -> set[str]:
    expected = set(environment.local_addresses)
    try:
        address = ipaddress.ip_address(ssh_host.strip().strip("[]"))
    except ValueError:
        # A hostname used for SSH can be round-robin or proxied.  Only addresses
        # actually assigned to this VPS are authoritative for the DNS gate.
        pass
    else:
        # The Linux CLI executes locally. Its 127.0.0.1 transport is not a
        # public DNS identity and must never make a loopback A record pass.
        if not (address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast):
            expected.add(str(address))
    return expected


def dns_matches_environment(environment: ProxyEnvironment, ssh_host: str) -> bool:
    expected = _expected_addresses(environment, ssh_host)
    if (environment.confirmed_public_ipv4
            and environment.confirmed_public_ipv4 == nat_public_ipv4_candidate(environment)):
        expected.add(environment.confirmed_public_ipv4)
    targets = set(environment.dns_a) | set(environment.dns_aaaa)
    if any((address := ipaddress.ip_address(value)).is_loopback or address.is_unspecified
           or address.is_link_local or address.is_multicast for value in targets):
        return False
    return bool(targets) and targets <= expected

def validate_public_ipv4(value: str) -> str:
    """Accept a single public IPv4 literal, not a URL, private IP or hostname."""
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("请填写云控制台分配给本机的公网 IPv4。") from exc
    if not address.is_global or address.is_multicast or address.is_reserved:
        raise ValueError("必须填写公网 IPv4，不能使用内网、回环或保留地址。")
    return str(address)


def nat_public_ipv4_candidate(environment: ProxyEnvironment) -> str:
    """A narrow manual-confirmation opportunity, never automatic NAT proof."""
    if len(environment.dns_a) != 1 or not set(environment.dns_aaaa) <= set(environment.local_addresses):
        return ""
    local = [ipaddress.ip_address(value) for value in environment.local_addresses]
    private_v4 = tuple(ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if (any(address.version == 4 and address.is_global for address in local)
            or not any(address.version == 4 and any(address in subnet for subnet in private_v4) for address in local)):
        return ""
    try:
        return validate_public_ipv4(environment.dns_a[0])
    except ValueError:
        return ""


def public_endpoint_error(environment: ProxyEnvironment, ssh_host: str) -> str:
    """Shared first-install and existing-proxy gate, without requiring a gateway."""
    unknown = [port for port, value in (("80", environment.port_80), ("443", environment.port_443))
               if value not in {"FREE", "OWN", "FOREIGN"}]
    if unknown:
        return "无法确认端口 " + "/".join(unknown) + " 的监听归属。为避免接管未知服务，已停止配置。"
    foreign = [port for port, value in (("80", environment.port_80), ("443", environment.port_443)) if value == "FOREIGN"]
    if foreign:
        return "端口 " + "/".join(foreign) + " 已被非 TG2Cloud 服务占用。不会停止、修改或覆盖该服务。"
    if not dns_matches_environment(environment, ssh_host):
        if not environment.dns_a and not environment.dns_aaaa:
            return "VPS 当前没有解析到该域名的 A/AAAA 记录。请等待 DNS 生效；Cloudflare 首次签发时使用“仅 DNS”。"
        if nat_public_ipv4_candidate(environment):
            return "DNS A 未匹配本机网卡；可能使用公网 NAT。请在交互向导中核对并确认云控制台的公网 IPv4。"
        return "域名 A/AAAA 未全部匹配本机地址。请核对 A、删除错误的 AAAA，首次签发时将 Cloudflare 设为“仅 DNS”。"
    return ""


def dns_diagnostic(environment: ProxyEnvironment, ssh_host: str) -> str:
    """Return non-sensitive DNS details suitable for the dialog and errors."""
    expected = _expected_addresses(environment, ssh_host)

    def display(values: tuple[str, ...] | set[str]) -> str:
        return ", ".join(sorted(values)) if values else "无"

    ports = {"FREE": "空闲", "OWN": "TG2Cloud 代理持有", "FOREIGN": "其他服务占用"}
    confirmation = ("；NAT 公网 IPv4：" + environment.confirmed_public_ipv4 + "（本次人工确认，入站仍待验证）"
                    if environment.confirmed_public_ipv4 else "")
    return (
        f"DNS A：{display(environment.dns_a)}；"
        f"AAAA：{display(environment.dns_aaaa)}；"
        f"当前 VPS：{display(expected)}{confirmation}\n"
        f"80 端口：{ports.get(environment.port_80, '无法确认')}；"
        f"443 端口：{ports.get(environment.port_443, '无法确认')}"
    )
