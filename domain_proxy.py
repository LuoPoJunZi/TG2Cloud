"""Shared, transactional HTTPS management for both TG2Cloud editions.

The module intentionally has no Qt dependency.  Rendering and parsing helpers are
deterministic so the Windows deployers can test every safety decision without
contacting Docker, DNS, nginx, Certbot, or Let's Encrypt.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import json
import re
import shlex
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from deployer_products import ProductProfile

PROXY_ROOT = "/opt/tg2cloud-proxy"
PROXY_NGINX_CONTAINER = "tg2cloud-proxy-nginx"
PROXY_CERTBOT_CONTAINER = "tg2cloud-proxy-certbot"
NGINX_IMAGE = "nginx:1.30.5-alpine"
CERTBOT_IMAGE = "certbot/certbot:v5.8.0"
STATE_VERSION = 1
SUPPORTED_EDITIONS = ("clouddrive2", "openlist")
EDITION_BACKEND_PORTS = {"clouddrive2": 19798, "openlist": 5244}

_FQDN_RE = re.compile(
    r"(?=^.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+")
_MARKER_RE = re.compile(r"^TG2CLOUD_([A-Z0-9_]+)=(.*)$")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

_CERTIFICATE_CHECK_SCRIPT = """import datetime
import pathlib
import sys

from cryptography import x509

certificate = x509.load_pem_x509_certificate(pathlib.Path(sys.argv[1]).read_bytes())
names = certificate.extensions.get_extension_for_class(
    x509.SubjectAlternativeName
).value.get_values_for_type(x509.DNSName)
expires = getattr(certificate, "not_valid_after_utc", None)
if expires is None:
    expires = certificate.not_valid_after.replace(tzinfo=datetime.timezone.utc)
valid = sys.argv[2] in names and expires > datetime.datetime.now(
    datetime.timezone.utc
) + datetime.timedelta(days=7)
if valid:
    print(expires.strftime("%Y-%m-%dT%H:%M:%SZ"))
raise SystemExit(0 if valid else 1)
"""


class RemoteLike(Protocol):
    def run(
        self,
        command: str,
        *,
        sudo: bool = False,
        stream: Callable[[str], None] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str]: ...

    def sftp(self) -> Any: ...


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


def command_failure_summary(
    output: str,
    *,
    secrets: tuple[str, ...] = (),
    max_lines: int = 16,
    max_chars: int = 1600,
) -> str:
    """Return bounded, single-purpose diagnostics safe for the visible log."""
    clean = _ANSI_ESCAPE_RE.sub("", output).replace("\r", "")
    for secret in secrets:
        if secret:
            clean = clean.replace(secret, "[已脱敏]")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    summary = "\n".join(lines[-max_lines:])
    if len(summary) > max_chars:
        summary = "…" + summary[-max_chars:]
    return summary


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
    if not isinstance(value, dict) or value.get("version") != STATE_VERSION:
        raise ValueError("共享代理状态版本无法识别；不会自动覆盖。")
    domains = value.get("domains")
    if not isinstance(domains, dict) or set(domains) - set(SUPPORTED_EDITIONS):
        raise ValueError("共享代理状态包含未知 Edition；不会自动覆盖。")
    normalized = empty_state()
    seen: set[str] = set()
    for edition, item in domains.items():
        if not isinstance(item, dict):
            raise TypeError("共享代理域名状态格式不正确。")
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
    return normalized


def state_with_route(
    state: dict[str, Any], product: ProductProfile, domain: str
) -> dict[str, Any]:
    result = normalize_state(json.dumps(state))
    domain = validate_domain(domain)
    for edition, item in result["domains"].items():
        if edition != product.key and item["domain"] == domain:
            raise ValueError("该域名已分配给另一个 TG2Cloud Edition。")
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


def render_certbot_loop() -> str:
    return (
        "trap 'exit 0' TERM INT; while :; do "
        'for cert in $TG2CLOUD_CERT_NAMES; do certbot renew --cert-name "$cert" '
        "--webroot -w /var/www/certbot --quiet || true; done; "
        "sleep 43200 & wait $!; done"
    )


def render_compose(active_domains: tuple[str, ...] = ()) -> str:
    certificate_names = " ".join(validate_domain(domain) for domain in active_domains)
    certbot_command = render_certbot_loop().replace("$", "$$")
    return f"""services:
  nginx:
    image: {NGINX_IMAGE}
    container_name: {PROXY_NGINX_CONTAINER}
    network_mode: host
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - DAC_OVERRIDE
      - NET_BIND_SERVICE
      - SETGID
      - SETUID
    security_opt:
      - no-new-privileges:true
    labels:
      com.tg2cloud.managed: "true"
      com.tg2cloud.role: reverse-proxy
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./certbot/www:/var/www/certbot:ro
      - ./certbot/letsencrypt:/etc/letsencrypt:ro
    command:
      - /bin/sh
      - -c
      - while sleep 21600; do nginx -s reload; done & exec nginx -g 'daemon off;'
  certbot:
    image: {CERTBOT_IMAGE}
    container_name: {PROXY_CERTBOT_CONTAINER}
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    labels:
      com.tg2cloud.managed: "true"
      com.tg2cloud.role: certificate-manager
    environment:
      TG2CLOUD_CERT_NAMES: {json.dumps(certificate_names)}
    volumes:
      - ./certbot/www:/var/www/certbot
      - ./certbot/letsencrypt:/etc/letsencrypt
      - ./certbot/lib:/var/lib/letsencrypt
      - ./certbot/log:/var/log/letsencrypt
    entrypoint: /bin/sh
    command:
      - -c
      - {certbot_command}
"""


def render_nginx_conf() -> str:
    return """user nginx;
worker_processes auto;
pid /var/run/nginx.pid;
error_log /dev/stderr warn;

events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log off;
    sendfile on;
    server_tokens off;
    client_max_body_size 16m;
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }
    include /etc/nginx/conf.d/*.conf;
}
"""


def render_default_conf(*, tls_enabled: bool) -> str:
    tls = """
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    ssl_reject_handshake on;
}
""" if tls_enabled else ""
    return """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}
""" + tls


def render_bootstrap_conf(domain: str) -> str:
    domain = validate_domain(domain)
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    if ($host != {domain}) {{ return 444; }}

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type text/plain;
        try_files $uri =404;
    }}
    location / {{ return 404; }}
}}
"""


def render_route_conf(route: DomainRoute) -> str:
    domain = validate_domain(route.domain)
    if (
        route.edition not in SUPPORTED_EDITIONS
        or route.backend_port != EDITION_BACKEND_PORTS[route.edition]
    ):
        raise ValueError("无法为未知 Edition 或后端端口生成代理配置。")
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    if ($host != {domain}) {{ return 444; }}

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type text/plain;
        try_files $uri =404;
    }}
    location / {{ return 308 https://$host$request_uri; }}
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {domain};
    if ($host != {domain}) {{ return 444; }}

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:TG2CloudTLS:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    location = /dav {{ return 403; }}
    location ^~ /dav/ {{ return 403; }}

    location / {{
        proxy_pass http://127.0.0.1:{route.backend_port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 120s;
    }}
}}
"""


def render_config_set(
    state: dict[str, Any], *, candidate_domain: str = ""
) -> dict[str, str]:
    routes = routes_from_state(state)
    files = {
        "nginx.conf": render_nginx_conf(),
        "conf.d/00-default.conf": render_default_conf(tls_enabled=bool(routes)),
    }
    for route in routes:
        files[f"conf.d/20-{route.edition}.conf"] = render_route_conf(route)
    if candidate_domain:
        candidate = validate_domain(candidate_domain)
        if candidate not in {route.domain for route in routes}:
            files["conf.d/10-acme-bootstrap.conf"] = render_bootstrap_conf(candidate)
    return files


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


def dns_matches_environment(environment: ProxyEnvironment, ssh_host: str) -> bool:
    expected = set(environment.local_addresses)
    try:
        expected.add(str(ipaddress.ip_address(ssh_host.strip().strip("[]"))))
    except ValueError:
        # A hostname used for SSH can be round-robin or proxied.  Only addresses
        # actually assigned to this VPS are authoritative for the DNS gate.
        pass
    targets = set(environment.dns_a) | set(environment.dns_aaaa)
    return bool(targets) and targets <= expected


def dns_diagnostic(environment: ProxyEnvironment, ssh_host: str) -> str:
    """Return non-sensitive DNS details suitable for the dialog and errors."""
    expected = set(environment.local_addresses)
    try:
        expected.add(str(ipaddress.ip_address(ssh_host.strip().strip("[]"))))
    except ValueError:
        pass

    def display(values: tuple[str, ...] | set[str]) -> str:
        return ", ".join(sorted(values)) if values else "无"

    return (
        f"DNS A：{display(environment.dns_a)}；"
        f"AAAA：{display(environment.dns_aaaa)}；"
        f"当前 VPS：{display(expected)}"
    )


def parse_certificate_enddate(value: str, *, now: dt.datetime | None = None) -> tuple[str, int]:
    raw = value.strip().removeprefix("notAfter=").strip()
    try:
        if raw.endswith("Z"):
            expires = dt.datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            expires = dt.datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.UTC)
    except ValueError as exc:
        raise ValueError("无法解析 HTTPS 证书到期时间。") from exc
    current = now or dt.datetime.now(dt.UTC)
    days = max(-1, int((expires - current).total_seconds() // 86400))
    return expires.date().isoformat(), days


def environment_probe_command(product: ProductProfile, domain: str) -> str:
    domain = validate_domain(domain)
    return "bash -c " + shlex.quote(
        f"""
set -u
if docker inspect {shlex.quote(product.storage_container)} >/dev/null 2>&1 \
  && curl -fsS --max-time 5 http://127.0.0.1:{product.management_port}/ >/dev/null 2>&1; then
  printf 'TG2CLOUD_PROXY_CORE=OK\\n'
else
  printf 'TG2CLOUD_PROXY_CORE=MISSING\\n'
fi
if docker compose version >/dev/null 2>&1; then
  printf 'TG2CLOUD_PROXY_DOCKER=OK\\n'
else
  printf 'TG2CLOUD_PROXY_DOCKER=MISSING\\n'
fi
managed=false
managed_pids=""
if [[ "$(docker inspect --format '{{{{index .Config.Labels \"com.tg2cloud.managed\"}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == true \
  && "$(docker inspect --format '{{{{index .Config.Labels \"com.tg2cloud.role\"}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == reverse-proxy \
  && "$(docker inspect --format '{{{{.HostConfig.NetworkMode}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == host \
  && "$(docker inspect --format '{{{{.State.Running}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == true ]]; then
  managed=true
  managed_pids=" $(docker top {PROXY_NGINX_CONTAINER} -eo pid 2>/dev/null | awk 'NR > 1 {{print $1}}' | paste -sd' ' -) "
fi
for port in 80 443; do
  if ! command -v ss >/dev/null 2>&1; then owner=UNKNOWN
  else
    listeners="$(ss -H -ltnp "( sport = :$port )" 2>/dev/null || true)"
    if [[ -z "$listeners" ]]; then owner=FREE
    elif [[ "$managed" == true ]]; then
      listener_pids="$(printf '%s\n' "$listeners" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | paste -sd' ' -)"
      if [[ -z "$listener_pids" || -z "${{managed_pids// /}}" ]]; then owner=UNKNOWN
      else
        owner=OWN
        for pid in $listener_pids; do
          case "$managed_pids" in *" $pid "*) ;; *) owner=FOREIGN; break ;; esac
        done
      fi
    else owner=FOREIGN
    fi
  fi
  printf 'TG2CLOUD_PROXY_PORT_%s=%s\\n' "$port" "$owner"
done
dns_a="$(getent ahostsv4 {shlex.quote(domain)} 2>/dev/null | awk '{{print $1}}' | sort -u | paste -sd, -)"
dns_aaaa="$(getent ahostsv6 {shlex.quote(domain)} 2>/dev/null | awk '{{print $1}}' | grep : | sort -u | paste -sd, -)"
local_ips="$(ip -o addr show scope global 2>/dev/null | awk '{{print $4}}' | cut -d/ -f1 | sort -u | paste -sd, -)"
printf 'TG2CLOUD_PROXY_DNS_A=%s\\nTG2CLOUD_PROXY_DNS_AAAA=%s\\nTG2CLOUD_PROXY_LOCAL_IPS=%s\\n' "$dns_a" "$dns_aaaa" "$local_ips"
"""
    )


def status_command(product: ProductProfile, domain: str) -> str:
    domain = validate_domain(domain)
    certificate_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    certificate_check = (
        f"docker exec {PROXY_CERTBOT_CONTAINER} python -c "
        f"{shlex.quote(_CERTIFICATE_CHECK_SCRIPT)} "
        f"{shlex.quote(certificate_path)} {shlex.quote(domain)}"
    )
    return "bash -c " + shlex.quote(
        f"""
set +u
root={shlex.quote(PROXY_ROOT)}
core=FAILED
ports=FAILED
nginx=FAILED
certbot=FAILED
renewal=FAILED
syntax=FAILED
https_state=FAILED
redirect=FAILED
dav_state=FAILED
backend=FAILED
cert=FAILED
cert_end=""
if docker inspect {shlex.quote(product.storage_container)} >/dev/null 2>&1 \
  && curl -fsS --max-time 5 http://127.0.0.1:{product.management_port}/ >/dev/null 2>&1; then core=OK; else core=FAILED; fi
if [[ "$(docker inspect --format '{{{{.State.Running}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == true ]]; then nginx=OK; else nginx=FAILED; fi
if [[ "$(docker inspect --format '{{{{.State.Running}}}}' {PROXY_CERTBOT_CONTAINER} 2>/dev/null || true)" == true ]]; then certbot=OK; else certbot=FAILED; fi
if [[ -s "$root/certbot/letsencrypt/renewal/{domain}.conf" ]]; then renewal=OK; else renewal=FAILED; fi
managed_pids=" $(docker top {PROXY_NGINX_CONTAINER} -eo pid 2>/dev/null | awk 'NR > 1 {{print $1}}' | paste -sd' ' -) "
owns_port() {{
  local listeners listener_pids pid
  listeners="$(ss -H -ltnp "( sport = :$1 )" 2>/dev/null || true)"
  listener_pids="$(printf '%s\n' "$listeners" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | paste -sd' ' -)"
  [[ -n "$listeners" && -n "$listener_pids" && -n "${{managed_pids// /}}" ]] || return 1
  for pid in $listener_pids; do
    case "$managed_pids" in *" $pid "*) ;; *) return 1 ;; esac
  done
}}
if [[ "$nginx" == OK \
  && "$(docker inspect --format '{{{{index .Config.Labels \"com.tg2cloud.managed\"}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == true \
  && "$(docker inspect --format '{{{{index .Config.Labels \"com.tg2cloud.role\"}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == reverse-proxy \
  && "$(docker inspect --format '{{{{.HostConfig.NetworkMode}}}}' {PROXY_NGINX_CONTAINER} 2>/dev/null || true)" == host ]] \
  && owns_port 80 && owns_port 443; then ports=OK; else ports=FAILED; fi
if docker compose -f "$root/docker-compose.yml" exec -T nginx nginx -t >/dev/null 2>&1; then syntax=OK; else syntax=FAILED; fi
https="$(curl --noproxy '*' --resolve {domain}:443:127.0.0.1 -sS -o /dev/null -w '%{{http_code}}' --max-time 15 https://{domain}/ 2>/dev/null || true)"
http_headers="$(curl --noproxy '*' --resolve {domain}:80:127.0.0.1 -sS -o /dev/null -D - --max-time 15 http://{domain}/ 2>/dev/null || true)"
http_code="$(printf '%s' "$http_headers" | awk 'NR==1 {{print $2}}')"
location="$(printf '%s' "$http_headers" | awk 'BEGIN{{IGNORECASE=1}} /^Location:/ {{gsub(/\\r/,\"\",$2); print $2; exit}}')"
dav="$(curl --noproxy '*' --resolve {domain}:443:127.0.0.1 -sS -o /dev/null -w '%{{http_code}}' --max-time 15 https://{domain}/dav/ 2>/dev/null || true)"
binding="$(ss -H -ltn '( sport = :{product.management_port} )' 2>/dev/null || true)"
if [[ -n "$binding" ]] && printf '%s\n' "$binding" | awk '$4 !~ /^127[.]0[.]0[.]1:/ && $4 !~ /^\\[::1\\]:/ {{bad=1}} END {{exit bad}}'; then backend=OK; else backend=FAILED; fi
if cert_end="$({certificate_check} 2>/dev/null)"; then cert=OK; else cert=FAILED; fi
[[ "$https" =~ ^[123][0-9][0-9]$ ]] && https_state=OK || https_state=FAILED
[[ "$http_code" =~ ^30[18]$ && "$location" == https://{domain}/* ]] && redirect=OK || redirect=FAILED
[[ "$dav" == 403 ]] && dav_state=OK || dav_state=FAILED
printf 'TG2CLOUD_PROXY_CORE=%s\\nTG2CLOUD_PROXY_PORTS=%s\\n' "$core" "$ports"
printf 'TG2CLOUD_PROXY_NGINX=%s\\nTG2CLOUD_PROXY_CERTBOT=%s\\nTG2CLOUD_PROXY_RENEWAL=%s\\nTG2CLOUD_PROXY_NGINX_TEST=%s\\n' "$nginx" "$certbot" "$renewal" "$syntax"
printf 'TG2CLOUD_PROXY_HTTPS=%s\\nTG2CLOUD_PROXY_REDIRECT=%s\\nTG2CLOUD_PROXY_DAV_BLOCK=%s\\n' "$https_state" "$redirect" "$dav_state"
printf 'TG2CLOUD_PROXY_BACKEND_LOCAL=%s\\nTG2CLOUD_PROXY_CERT=%s\\nTG2CLOUD_PROXY_CERT_END=%s\\n' "$backend" "$cert" "$cert_end"
printf 'TG2CLOUD_PROXY_STATUS=OK\\n'
"""
    )


def verification_statuses(markers: dict[str, str]) -> tuple[tuple[str, str], ...]:
    mapping = (
        ("基础服务", "PROXY_CORE"),
        ("80/443 由共享代理持有", "PROXY_PORTS"),
        ("Nginx 容器", "PROXY_NGINX"),
        ("Certbot 容器", "PROXY_CERTBOT"),
        ("当前域名续期配置", "PROXY_RENEWAL"),
        ("Nginx 配置", "PROXY_NGINX_TEST"),
        ("HTTPS 管理页", "PROXY_HTTPS"),
        ("HTTP 跳转", "PROXY_REDIRECT"),
        ("公网 /dav 阻断", "PROXY_DAV_BLOCK"),
        ("后端仅回环监听", "PROXY_BACKEND_LOCAL"),
        ("证书域名与有效期", "PROXY_CERT"),
    )
    return tuple((title, "通过" if markers.get(key) == "OK" else "失败") for title, key in mapping)


def install_config_command(remote: str) -> str:
    """Render the privileged, syntax-checkable config installation transaction."""
    # The remote path is random, privately created with mode 0700, and never user supplied.
    if not re.fullmatch(  # nosec B108
        r"/tmp/tg2cloud-proxy-[0-9a-f]{32}", remote
    ):
        raise ValueError("共享代理临时目录格式不正确。")
    script = f"""
set -e
root={shlex.quote(PROXY_ROOT)}
install -d -m 700 "$root" "$root/state" "$root/nginx" "$root/nginx/conf.d" "$root/certbot" "$root/certbot/letsencrypt" "$root/certbot/lib" "$root/certbot/log"
# Nginx workers run without root. Only the public ACME challenge webroot is
# traversable; account data, private keys and Certbot state remain mode 0700.
install -d -m 755 "$root/certbot/www"
install -d -m 700 "$root/nginx/conf.d.next"
find "$root/nginx/conf.d.next" -maxdepth 1 -type f -delete
install -m 644 {shlex.quote(remote)}/nginx.conf "$root/nginx/nginx.conf.next"
install -m 600 {shlex.quote(remote)}/docker-compose.yml "$root/docker-compose.yml.next"
for source in {shlex.quote(remote)}/conf.d/*.conf; do
  install -m 644 "$source" "$root/nginx/conf.d.next/$(basename "$source")"
done
docker run --rm --network host --read-only \
  --tmpfs /var/cache/nginx --tmpfs /var/run --tmpfs /tmp \
  -v "$root/nginx/nginx.conf.next:/etc/nginx/nginx.conf:ro" \
  -v "$root/nginx/conf.d.next:/etc/nginx/conf.d:ro" \
  -v "$root/certbot/www:/var/www/certbot:ro" \
  -v "$root/certbot/letsencrypt:/etc/letsencrypt:ro" \
  {NGINX_IMAGE} nginx -t
rm -rf "$root/nginx/conf.d.previous"
install -d -m 700 "$root/nginx/conf.d.previous"
cp -a "$root/nginx/conf.d/." "$root/nginx/conf.d.previous/" 2>/dev/null || true
find "$root/nginx/conf.d" -maxdepth 1 -type f -name '*.conf' -delete
cp -a "$root/nginx/conf.d.next/." "$root/nginx/conf.d/"
rm -rf "$root/nginx/conf.d.next"
mv "$root/nginx/nginx.conf.next" "$root/nginx/nginx.conf"
mv "$root/docker-compose.yml.next" "$root/docker-compose.yml"
"""
    return "bash -c " + shlex.quote(script)


class DomainProxyManager:
    """Orchestrate a shared proxy through an already authenticated SSH session."""

    def __init__(
        self,
        session: RemoteLike,
        product: ProductProfile,
        values: dict[str, str],
        log: Callable[[str], None],
    ) -> None:
        self.session = session
        self.product = product
        self.values = values
        self.log = log
        self.use_sudo = False

    def prepare(self) -> None:
        code, output = self.session.run("id -u", timeout=10)
        uid = output.strip().splitlines()[-1] if output.strip() else ""
        if code != 0 or not uid.isdigit():
            raise RuntimeError("无法确认 VPS 用户权限。")
        self.use_sudo = uid != "0"
        if self.use_sudo and not self.values.get("sudo_password"):
            code, _ = self.session.run("sudo -n true", timeout=10)
            if code != 0:
                raise RuntimeError("配置 HTTPS 需要 root 或可用的 sudo 权限。")

    def _run(self, command: str, *, timeout: float = 60) -> tuple[int, str]:
        return self.session.run(command, sudo=self.use_sudo, timeout=timeout)

    def read_state(self) -> dict[str, Any]:
        command = f"""
if [[ -f {PROXY_ROOT}/state/domains.json ]]; then
  cat {PROXY_ROOT}/state/domains.json
elif docker container inspect {PROXY_NGINX_CONTAINER} >/dev/null 2>&1 \
  || [[ -f {PROXY_ROOT}/docker-compose.yml ]] \
  || find {PROXY_ROOT}/nginx/conf.d -maxdepth 1 -type f -name '*.conf' -print -quit 2>/dev/null | grep -q .; then
  printf 'TG2CLOUD_PROXY_STATE_MISSING_WITH_RUNTIME=1\\n'
  exit 3
fi
"""
        code, output = self._run("bash -c " + shlex.quote(command), timeout=10)
        if code == 3 or "TG2CLOUD_PROXY_STATE_MISSING_WITH_RUNTIME=1" in output:
            raise RuntimeError(
                "检测到共享代理运行文件但缺少 domains.json。为避免覆盖未知域名，已停止；请先人工核对 /opt/tg2cloud-proxy。"
            )
        if code != 0:
            raise RuntimeError("无法读取共享代理状态；不会覆盖现有配置。")
        return normalize_state(output)

    def probe(self, domain: str) -> ProxyEnvironment:
        code, output = self._run(environment_probe_command(self.product, domain), timeout=30)
        if code != 0:
            raise RuntimeError("无法完成域名、Docker 与端口环境检测。")
        return parse_environment(output)

    def _validate_environment(self, environment: ProxyEnvironment) -> None:
        if environment.core != "OK":
            raise RuntimeError(f"请先完成 {self.product.display_name} 基础部署并确认管理页在 VPS 回环端口可访问。")
        if environment.docker != "OK":
            raise RuntimeError("VPS 上的 Docker Compose 不可用，请先完成基础环境部署。")
        if not environment.ports_safe:
            unknown = [
                port
                for port, value in (("80", environment.port_80), ("443", environment.port_443))
                if value == "UNKNOWN"
            ]
            if unknown:
                raise RuntimeError(
                    "无法确认端口 "
                    + "/".join(unknown)
                    + " 的监听归属。为避免接管未知服务，已停止配置。"
                )
            ports = []
            if environment.port_80 == "FOREIGN":
                ports.append("80")
            if environment.port_443 == "FOREIGN":
                ports.append("443")
            raise RuntimeError(
                "端口 " + "/".join(ports) + " 已被非 TG2Cloud 服务占用。部署器不会停止、修改或覆盖该服务。"
            )
        if not dns_matches_environment(environment, self.values["vps_host"]):
            detail = dns_diagnostic(environment, self.values["vps_host"])
            if not environment.dns_a and not environment.dns_aaaa:
                raise RuntimeError(
                    "VPS 当前没有解析到该域名的 A/AAAA 记录。请等待 DNS 生效后重新检测；"
                    "Cloudflare 首次签发时应设为“仅 DNS”。\n" + detail
                )
            raise RuntimeError(
                "域名当前解析出的地址没有全部直接指向这台 VPS。请确认 A 记录使用当前 VPS IP，"
                "删除错误的 AAAA，并在首次签发证书时将 Cloudflare 设为“仅 DNS”。\n"
                + detail
            )

    def _upload_files(self, files: dict[str, str]) -> str:
        token = uuid.uuid4().hex
        remote = f"/tmp/tg2cloud-proxy-{token}"  # nosec B108
        code, _ = self.session.run(f"mkdir -m 700 {remote}", timeout=15)
        if code != 0:
            raise RuntimeError("无法创建 HTTPS 配置临时目录。")
        sftp = self.session.sftp()
        try:
            for relative, content in files.items():
                parts = relative.split("/")
                directory = remote
                for part in parts[:-1]:
                    directory += "/" + part
                    try:
                        sftp.mkdir(directory, 448)
                    except OSError:
                        pass
                target = f"{remote}/{relative}"
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", newline="\n", delete=False
                ) as handle:
                    handle.write(content)
                    local = Path(handle.name)
                try:
                    sftp.put(str(local), target)
                    sftp.chmod(target, 384)
                finally:
                    local.unlink(missing_ok=True)
        finally:
            sftp.close()
        return remote

    def _install_config(self, state: dict[str, Any], *, candidate: str = "") -> None:
        files = render_config_set(state, candidate_domain=candidate)
        active_domains = tuple(route.domain for route in routes_from_state(state))
        files["docker-compose.yml"] = render_compose(active_domains)
        remote = self._upload_files(files)
        try:
            code, _ = self._run(install_config_command(remote), timeout=180)
            if code != 0:
                raise RuntimeError("无法安装共享代理配置。")
        finally:
            self.session.run(f"rm -rf -- {remote}", timeout=20)

    def _compose(self, arguments: str, *, timeout: float = 180) -> tuple[int, str]:
        return self._run(
            f"docker compose -f {PROXY_ROOT}/docker-compose.yml {arguments}",
            timeout=timeout,
        )

    def _activate(self, state: dict[str, Any], *, candidate: str = "") -> None:
        self._install_config(state, candidate=candidate)
        code, _ = self._compose("config --quiet", timeout=30)
        if code != 0:
            raise RuntimeError("共享代理 Compose 配置校验失败。")
        code, _ = self._compose("up -d nginx", timeout=180)
        if code != 0:
            raise RuntimeError("Nginx 容器启动失败。")
        code, _ = self._compose("exec -T nginx nginx -t", timeout=30)
        if code != 0:
            raise RuntimeError("Nginx 配置自检失败。")
        code, _ = self._compose("exec -T nginx nginx -s reload", timeout=30)
        if code != 0:
            raise RuntimeError("Nginx 安全重载失败。")

    def _certificate_exists(self, domain: str) -> bool:
        code, _ = self._run(
            f"test -s {PROXY_ROOT}/certbot/letsencrypt/live/{shlex.quote(domain)}/fullchain.pem "
            f"-a -s {PROXY_ROOT}/certbot/letsencrypt/live/{shlex.quote(domain)}/privkey.pem",
            timeout=10,
        )
        return code == 0

    def _renewal_config_exists(self, domain: str) -> bool:
        code, _ = self._run(
            f"test -s {PROXY_ROOT}/certbot/letsencrypt/renewal/{shlex.quote(domain)}.conf",
            timeout=10,
        )
        return code == 0

    def _certificate_valid(self, domain: str) -> bool:
        if not self._certificate_exists(domain) or not self._renewal_config_exists(domain):
            return False
        certificate_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        code, _ = self._run(
            "docker run --rm --read-only --cap-drop ALL "
            "--security-opt no-new-privileges --tmpfs /tmp "
            f"-v {PROXY_ROOT}/certbot/letsencrypt:/etc/letsencrypt:ro "
            f"--entrypoint python {CERTBOT_IMAGE} -c "
            f"{shlex.quote(_CERTIFICATE_CHECK_SCRIPT)} "
            f"{shlex.quote(certificate_path)} {shlex.quote(domain)}",
            timeout=90,
        )
        return code == 0

    def _obtain_certificate(self, domain: str, email: str) -> None:
        certificate_exists = self._certificate_exists(domain)
        if self._certificate_valid(domain):
            self.log("检测到该域名已有且仍有效的证书，将直接复用。")
            return
        registration = (
            "--email " + shlex.quote(email)
            if email
            else "--register-unsafely-without-email"
        )
        command = (
            "run --rm --entrypoint certbot certbot certonly --webroot "
            "-w /var/www/certbot --non-interactive --agree-tos --no-eff-email "
            f"{registration} {'--force-renewal ' if certificate_exists else ''}"
            f"--cert-name {shlex.quote(domain)} -d {shlex.quote(domain)}"
        )
        code, output = self._compose(command, timeout=300)
        if code != 0:
            detail = command_failure_summary(output, secrets=(email,))
            if detail:
                self.log("Certbot 签发详情（已脱敏）：\n" + detail)
            raise RuntimeError(
                "Let's Encrypt 证书签发失败。请检查运行日志中的 Certbot 具体原因；"
                "旧域名配置未提交。"
            )

    def _commit_state(self, state: dict[str, Any]) -> None:
        content = json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        remote = self._upload_files({"domains.json": content})
        try:
            code, _ = self._run(
                f"install -d -m 700 {PROXY_ROOT} {PROXY_ROOT}/state && "
                f"install -m 600 {remote}/domains.json {PROXY_ROOT}/state/domains.json",
                timeout=15,
            )
            if code != 0:
                raise RuntimeError("共享代理状态文件提交失败；已开始回退。")
        finally:
            self.session.run(f"rm -rf -- {remote}", timeout=20)

    def _ensure_state_file(self, state: dict[str, Any]) -> None:
        """Mark a newly created proxy as managed before the first mutation."""
        code, _ = self._run(f"test -f {PROXY_ROOT}/state/domains.json", timeout=10)
        if code == 0:
            return
        if code != 1:
            raise RuntimeError("无法确认共享代理状态文件是否存在。")
        self._commit_state(state)

    def status(self, state: dict[str, Any] | None = None) -> ProxyReport:
        current = state or self.read_state()
        item = current["domains"].get(self.product.key)
        if not item:
            return ProxyReport("", "not_configured", "当前 Edition 尚未配置域名访问。", ())
        domain = item["domain"]
        code, output = self._run(status_command(self.product, domain), timeout=90)
        markers = parse_markers(output)
        if code != 0 or markers.get("PROXY_STATUS") != "OK":
            self.log(
                "TG2CLOUD_PROXY_STATUS_SCRIPT=FAILED: "
                f"exit={code}, completion_marker="
                f"{'present' if markers.get('PROXY_STATUS') == 'OK' else 'missing'}"
            )
            detail = command_failure_summary(output)
            if detail:
                self.log("域名状态检查脚本详情（已脱敏）：\n" + detail)
            return ProxyReport(
                domain,
                "running_error",
                "域名状态检查脚本未完整执行；没有把缺失结果误判为业务失败。",
                (("状态检查脚本", "失败"),),
                tuple(sorted(markers.items())),
            )
        statuses = verification_statuses(markers)
        if any(value != "通过" for _, value in statuses):
            state_name = "certificate_error" if markers.get("PROXY_CERT") == "FAILED" else "running_error"
            return ProxyReport(
                domain,
                state_name,
                "域名路由存在，但至少一项运行检查未通过。",
                statuses,
                tuple(sorted(markers.items())),
            )
        expiry = ""
        days_text = ""
        if markers.get("PROXY_CERT_END"):
            expiry, days = parse_certificate_enddate(markers["PROXY_CERT_END"])
            days_text = f"，剩余约 {days} 天"
        return ProxyReport(
            domain,
            "healthy",
            f"https://{domain} 可用；证书到期日 {expiry}{days_text}。",
            statuses,
            tuple(sorted(markers.items())),
        )

    def detect(self, domain: str) -> ProxyReport:
        environment = self.probe(domain)
        statuses = (
            (f"{self.product.display_name} 基础服务", "通过" if environment.core == "OK" else "失败"),
            ("Docker Compose", "通过" if environment.docker == "OK" else "失败"),
            ("80 端口", "通过" if environment.port_80 in {"FREE", "OWN"} else "失败"),
            ("443 端口", "通过" if environment.port_443 in {"FREE", "OWN"} else "失败"),
            ("DNS 指向当前 VPS", "通过" if dns_matches_environment(environment, self.values["vps_host"]) else "失败"),
        )
        state = "detected" if all(value == "通过" for _, value in statuses) else "detected_error"
        return ProxyReport(
            domain,
            state,
            "环境检测完成。" + dns_diagnostic(environment, self.values["vps_host"]),
            statuses,
        )

    def configure(self, domain: str, email: str) -> ProxyReport:
        domain = validate_domain(domain)
        email = validate_email(email)
        previous = self.read_state()
        target = state_with_route(previous, self.product, domain)
        environment = self.probe(domain)
        self._validate_environment(environment)
        self._ensure_state_file(previous)
        bootstrap_state = previous
        repairing_existing_certificate = False
        current_route = previous["domains"].get(self.product.key)
        if (
            current_route
            and current_route["domain"] == domain
            and not self._certificate_valid(domain)
        ):
            bootstrap_state = state_without_route(previous, self.product.key)
            repairing_existing_certificate = True
            self.log("现有域名的证书或续期配置不可用；将使用安全 ACME 引导模式修复。")
        self.log("环境检查通过；正在启用仅用于 ACME 的安全 HTTP 引导配置。")
        try:
            self._activate(bootstrap_state, candidate=domain)
            self._obtain_certificate(domain, email)
            self._activate(target)
            code, _ = self._compose("up -d certbot", timeout=180)
            if code != 0:
                raise RuntimeError("证书续期容器启动失败。")
            report = self.status(target)
            if report.state != "healthy":
                failed = [title for title, value in report.statuses if value != "通过"]
                for title, value in report.statuses:
                    self.log(f"TG2CLOUD_PROXY_CHECK={title}:{value}")
                raise RuntimeError(
                    "域名访问最终自检未通过："
                    + "、".join(failed or ["状态输出不完整"])
                    + "。详细结果已写入运行日志；域名配置未提交。"
                )
            self._commit_state(target)
            return report
        except Exception:
            try:
                if previous["domains"]:
                    try:
                        self._activate(previous)
                    except Exception:
                        if not repairing_existing_certificate:
                            raise
                        self._activate(bootstrap_state, candidate=domain)
                    self._compose("up -d certbot", timeout=120)
                else:
                    self._install_config(previous)
                    self._compose("stop nginx certbot", timeout=60)
            except Exception as rollback_error:  # noqa: BLE001 - rollback boundary
                self.log(f"警告：共享代理自动回退未完全成功：{type(rollback_error).__name__}")
            raise

    def remove(self) -> ProxyReport:
        previous = self.read_state()
        target = state_without_route(previous, self.product.key)
        if target == previous:
            return ProxyReport("", "not_configured", "当前 Edition 没有可移除的域名路由。", ())
        removed = previous["domains"][self.product.key]["domain"]
        try:
            if target["domains"]:
                self._activate(target)
                self._commit_state(target)
            else:
                self._install_config(target)
                code, _ = self._compose("stop nginx certbot", timeout=60)
                if code != 0:
                    raise RuntimeError("最后一个域名已移除，但共享代理容器停止失败。")
                self._commit_state(target)
        except Exception:
            if previous["domains"]:
                self._activate(previous)
                self._compose("up -d certbot", timeout=120)
            raise
        return ProxyReport(
            "",
            "not_configured",
            f"已移除 {removed} 的 {self.product.display_name} 路由；证书文件默认保留。",
            (),
        )
