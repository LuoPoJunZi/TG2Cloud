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
import sys
import tempfile
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from deployer_products import PRODUCTS, ProductProfile

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

    def hold_lock(
        self, command: str, *, sudo: bool = False, timeout: float = 15
    ) -> AbstractContextManager[None]: ...


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
        "umask 077; trap 'exit 0' TERM INT; while :; do "
        'for cert in $TG2CLOUD_CERT_NAMES; do '
        'attempt=$(date -u +%s); '
        'before=$(sha256sum "/etc/letsencrypt/live/$cert/fullchain.pem" 2>/dev/null | cut -d" " -f1); '
        'if certbot renew --cert-name "$cert" '
        "--webroot -w /var/www/certbot --quiet >/var/log/letsencrypt/renew-console.log 2>&1; "
        'then result=OK; printf "%s\\n" "$attempt" >"/status/$cert.success"; '
        'after=$(sha256sum "/etc/letsencrypt/live/$cert/fullchain.pem" 2>/dev/null | cut -d" " -f1); '
        'if [ -n "$before" ] && [ -n "$after" ] && [ "$before" != "$after" ]; then '
        'printf "%s\\n" "$attempt" >"/status/$cert.renewed"; fi; '
        'else result=FAILED; fi; '
        'printf "ATTEMPT=%s\\nRESULT=%s\\nNEXT=%s\\n" "$attempt" "$result" "$((attempt + 43200))" '
        '>"/status/$cert.check.next"; mv "/status/$cert.check.next" "/status/$cert.check"; '
        "done; "
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
      - ./certbot/status:/status
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
for field in ATTEMPT RESULT NEXT; do
  value="$(awk -F= -v key="$field" '$1 == key {{print $2; exit}}' "$root/certbot/status/{domain}.check" 2>/dev/null || true)"
  if [[ "$value" =~ ^[0-9]{{1,12}}$ || "$value" == OK || "$value" == FAILED ]]; then
    printf 'TG2CLOUD_PROXY_RENEW_%s=%s\\n' "$field" "$value"
  fi
done
for field in success renewed; do
  value="$(cat "$root/certbot/status/{domain}.$field" 2>/dev/null || true)"
  if [[ "$value" =~ ^[0-9]{{1,12}}$ ]]; then
    printf 'TG2CLOUD_PROXY_RENEW_%s=%s\\n' "${{field^^}}" "$value"
  fi
done
printf 'TG2CLOUD_PROXY_STATUS=OK\\n'
"""
    )


def renewal_summary(markers: dict[str, str]) -> str:
    def stamp(key: str) -> str:
        value = markers.get("PROXY_RENEW_" + key, "")
        try:
            if not re.fullmatch(r"[0-9]{1,12}", value):
                return "尚无记录"
            return dt.datetime.fromtimestamp(int(value), dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OverflowError, OSError):
            return "记录无法识别"

    result = {"OK": "通过", "FAILED": "失败，需查看 VPS 的 Certbot 日志"}.get(
        markers.get("PROXY_RENEW_RESULT", ""), "尚无记录"
    )
    return (
        f"\n最近续期检查：{stamp('ATTEMPT')}（{result}）"
        f"\n最近检查成功：{stamp('SUCCESS')}；最近证书变更：{stamp('RENEWED')}"
        f"\n预计下次检查：{stamp('NEXT')}。检查成功不代表本次发生续签。"
    )


def renewal_warnings(markers: dict[str, str], now: dt.datetime | None = None) -> tuple[str, ...]:
    warnings = []
    if markers.get("PROXY_RENEW_RESULT") == "FAILED":
        warnings.append("最近自动续期检查失败，请查看 Certbot 日志并执行续期演练。")
    value = markers.get("PROXY_RENEW_ATTEMPT", "")
    if value:
        try:
            checked = int(value) if re.fullmatch(r"[0-9]{1,12}", value) else 0
            age = (now or dt.datetime.now(dt.UTC)).timestamp() - checked
            if checked <= 0 or age < -300:
                warnings.append("续期记录时间异常，请核对 VPS 时钟和检查记录。")
            elif age > 26 * 3600:  # Two 12h cycles plus scheduling grace.
                warnings.append("超过 26 小时没有新的续期检查记录，请检查续期容器。")
        except (ValueError, OverflowError):
            warnings.append("续期记录无法识别，请检查续期容器。")
    return tuple(warnings)


def dry_run_cleanup_script(task_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise ValueError("invalid maintenance task id")
    name = "tg2cloud-proxy-dry-run-" + task_id
    return f"""
name={shlex.quote(name)}
if timeout 10s docker container inspect "$name" >/dev/null 2>&1; then
  owner="$(timeout 10s docker inspect --format '{{{{index .Config.Labels "com.tg2cloud.task"}}}}' "$name" 2>/dev/null)"
  role="$(timeout 10s docker inspect --format '{{{{index .Config.Labels "com.tg2cloud.role"}}}}' "$name" 2>/dev/null)"
  if [[ "$owner" != {task_id} || "$role" != maintenance-dry-run ]]; then
    printf 'TG2CLOUD_PROXY_TASK_CLEANUP=REFUSED\\n'; return 1
  fi
  timeout 10s docker rm -f "$name" >/dev/null 2>&1 || {{ printf 'TG2CLOUD_PROXY_TASK_CLEANUP=FAILED\\n'; return 1; }}
else
  timeout 10s docker info >/dev/null 2>&1 || {{ printf 'TG2CLOUD_PROXY_TASK_CLEANUP=UNKNOWN\\n'; return 1; }}
fi
printf 'TG2CLOUD_PROXY_TASK_CLEANUP=OK\\n'
"""


def renewal_dry_run_command(domain: str, task_id: str, seconds: int = 540) -> str:
    domain = validate_domain(domain)
    cleanup = dry_run_cleanup_script(task_id)
    if type(seconds) is not int or not 1 <= seconds <= 540:
        raise ValueError("invalid task deadline")
    script = f"""
cleanup() {{ {cleanup} }}
finish() {{ local result="$?"; trap - EXIT HUP INT TERM; cleanup || result=1; exit "$result"; }}
trap finish EXIT
trap 'exit 143' HUP TERM
trap 'exit 130' INT
timeout --signal=TERM --kill-after=15s {seconds}s docker compose \
  -f {PROXY_ROOT}/docker-compose.yml run --rm --no-deps \
  --name tg2cloud-proxy-dry-run-{task_id} \
  --label com.tg2cloud.task={task_id} --label com.tg2cloud.role=maintenance-dry-run \
  --entrypoint certbot certbot renew --dry-run --cert-name {shlex.quote(domain)} \
  --webroot -w /var/www/certbot --non-interactive --no-random-sleep-on-renew --no-directory-hooks
"""
    return "bash -c " + shlex.quote(script)


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
install -d -m 700 "$root" "$root/state" "$root/nginx" "$root/nginx/conf.d" "$root/certbot" "$root/certbot/letsencrypt" "$root/certbot/lib" "$root/certbot/log" "$root/certbot/status"
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


def proxy_lock_command() -> str:
    """Hold one VPS-wide flock until the owning SSH channel is released."""
    return "bash -c " + shlex.quote(f"""
set -eu
umask 077
command -v flock >/dev/null 2>&1 || {{ printf 'TG2CLOUD_REMOTE_LOCK=UNAVAILABLE\\n'; exit 69; }}
install -d -m 700 {PROXY_ROOT}
exec 9>{PROXY_ROOT}/transaction.lock
flock -n 9 || {{ printf 'TG2CLOUD_REMOTE_LOCK=BUSY\\n'; exit 75; }}
trap 'exit 0' HUP INT TERM
printf 'TG2CLOUD_REMOTE_LOCK=ACQUIRED\\n'
# sudo can leave an unused password line on stdin when credentials are cached.
# Ignore every line except the explicit release marker; never echo input.
while IFS= read -r line; do
  [[ "$line" != TG2CLOUD_REMOTE_LOCK_RELEASE ]] || break
done
""")


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
        staged = f"{PROXY_ROOT}/state/.domains-{uuid.uuid4().hex}.json"
        try:
            code, _ = self._run(
                f"install -d -m 700 {PROXY_ROOT} {PROXY_ROOT}/state && "
                f"install -m 600 {remote}/domains.json {staged} && "
                f"mv -f -- {staged} {PROXY_ROOT}/state/domains.json",
                timeout=15,
            )
            if code != 0:
                raise RuntimeError("共享代理状态文件提交失败；已开始回退。")
        finally:
            # Cleanup must not turn an already committed state into a rollback.
            # Otherwise domains.json and the restored runtime would disagree.
            for cleanup, command in (
                (self._run, f"rm -f -- {staged}"),
                (self.session.run, f"rm -rf -- {remote}"),
            ):
                try:
                    code, _ = cleanup(command, timeout=20)
                    if code != 0:
                        self.log("警告：HTTPS 临时文件清理未完成；请人工核对，状态提交结果保持不变。")
                except Exception:  # noqa: BLE001 - best-effort cleanup boundary
                    self.log("警告：HTTPS 临时文件清理未完成；请人工核对，状态提交结果保持不变。")

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
        warnings = list(renewal_warnings(markers))
        if markers.get("PROXY_CERT_END"):
            expiry, days = parse_certificate_enddate(markers["PROXY_CERT_END"])
            days_text = f"，剩余约 {days} 天"
            if days <= 21:
                warnings.append("证书剩余不足 22 天，请检查自动续期是否成功。")
        return ProxyReport(
            domain,
            "healthy",
            f"VPS 本机 https://{domain} 自检通过；证书到期日 {expiry}{days_text}。"
            "公网连通性仍需从你的电脑或外部网络单独验收。"
            + "".join("\n提醒：" + text for text in warnings) + renewal_summary(markers),
            statuses,
            tuple(sorted(markers.items())),
            tuple(warnings),
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
        with self.session.hold_lock(proxy_lock_command(), sudo=self.use_sudo):
            return self._configure_locked(domain, email)

    def _configure_locked(self, domain: str, email: str) -> ProxyReport:
        self.log("TG2CLOUD_STAGE=HTTPS_ENV")
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
            self.log("TG2CLOUD_STAGE=ACME")
            self._activate(bootstrap_state, candidate=domain)
            self.log("TG2CLOUD_STAGE=CERTIFICATE")
            self._obtain_certificate(domain, email)
            self._activate(target)
            code, _ = self._compose("up -d certbot", timeout=180)
            if code != 0:
                raise RuntimeError("证书续期容器启动失败。")
            self.log("TG2CLOUD_STAGE=HTTPS_VERIFY")
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

    def _verify_remaining_routes(self, state: dict[str, Any]) -> None:
        for edition in state["domains"]:
            retained = DomainProxyManager(
                self.session, PRODUCTS[edition], self.values, self.log
            )
            retained.use_sudo = self.use_sudo
            report = retained.status(state)
            if report.state != "healthy":
                raise RuntimeError(
                    f"剩余 {PRODUCTS[edition].display_name} 的 HTTPS 自检未通过；已开始回退。"
                )

    def _backup_helper(self, action: str, *, archive: str = "", keep: int = 5, plan: str = "") -> dict[str, str]:
        if action not in {"backup", "check", "drill", "list", "prune-preview", "prune"}:
            raise ValueError("未知备份操作。")
        if archive and not re.fullmatch(r"proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz", archive):
            raise ValueError("备份文件名无效。")
        if type(keep) is not int or not 1 <= keep <= 50:
            raise ValueError("保留份数必须为 1～50。")
        if action == "prune" and not re.fullmatch(r"[0-9a-f]{64}", plan):
            raise ValueError("请先预览并确认清理计划。")
        self.log("TG2CLOUD_STAGE=PROXY_BACKUP")
        directory = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        source = (directory / "proxy_maintenance.py").read_text(encoding="utf-8")
        remote = self._upload_files({"proxy_maintenance.py": source})
        arguments = [action, "--keep", str(keep)]
        if archive:
            arguments += ["--archive", archive]
        if plan:
            arguments += ["--plan", plan]
        try:
            code, output = self._run(
                "timeout --signal=TERM --kill-after=15s 150s python3 "
                + shlex.quote(remote + "/proxy_maintenance.py") + " " + shlex.join(arguments), timeout=190
            )
            markers = parse_markers(output)
            if code != 0 or markers.get("PROXY_BACKUP") != action.upper().replace("-", "_") + "_OK":
                raise RuntimeError("共享代理备份操作未通过：请核对完整性、磁盘空间及清理计划。源文件或备份清单变化时需重新预览；清理可能部分完成，请刷新清单核对。")
            return markers
        finally:
            try:
                code, _ = self.session.run(f"rm -rf -- {shlex.quote(remote)}", timeout=30)
                if code != 0:
                    self.log("警告：维护临时脚本清理未完成，请恢复连接后检查。")
            except Exception:  # noqa: BLE001 - cleanup must not mask original failure
                self.log("警告：维护连接中断；远端备份操作设有执行时限，请恢复连接后检查。")

    @staticmethod
    def _backup_items(value: object) -> list[dict]:
        if not isinstance(value, list) or len(value) > 500:
            raise RuntimeError("备份清单无法识别。")
        for item in value:
            if (not isinstance(item, dict) or set(item) != {"name", "created_utc", "size_bytes", "integrity"}
                    or not isinstance(item["name"], str)
                    or not re.fullmatch(r"proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz", item["name"])
                    or not isinstance(item["created_utc"], str)
                    or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC", item["created_utc"])
                    or type(item["size_bytes"]) is not int or not 0 <= item["size_bytes"] <= 1024 ** 3
                    or item["integrity"] not in {"OK", "FAILED"}):
                raise RuntimeError("备份清单包含无法识别的数据。")
        return value

    def manage_backups(self, action: str, *, keep: int = 5, plan: str = "") -> dict:
        if action not in {"list", "prune-preview", "prune"}:
            raise ValueError("未知备份管理操作。")
        with self.session.hold_lock(proxy_lock_command(), sudo=self.use_sudo):
            markers = self._backup_helper(action, keep=keep, plan=plan)
            try:
                if action == "list":
                    return {"items": self._backup_items(json.loads(markers["PROXY_BACKUP_ITEMS"]))}
                result = json.loads(markers["PROXY_BACKUP_PLAN"])
                if (not isinstance(result, dict) or set(result) != {"keep", "retain", "remove", "plan_id"}
                        or type(result["keep"]) is not int or result["keep"] != keep or not isinstance(result["plan_id"], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", result["plan_id"])
                        or not isinstance(result["retain"], list) or len(result["retain"]) > keep
                        or any(not isinstance(name, str) or not re.fullmatch(r"proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz", name) for name in result["retain"])):
                    raise RuntimeError("清理计划无法识别。")
                self._backup_items(result["remove"])
                names = [item["name"] for item in result["remove"]] + result["retain"]
                if len(names) != len(set(names)) or (result["remove"] and not result["retain"]):
                    raise RuntimeError("清理计划必须保留有效备份，且不能包含重复文件。")
                return {"plan": result}
            except (ValueError, KeyError, TypeError) as exc:
                raise RuntimeError("备份管理输出无法识别。") from exc

    def maintenance(self, action: str, *, archive: str = "") -> str:
        """Explicit local-only maintenance; never restore over running services."""
        if action not in {"backup", "check", "drill", "renew_dry_run"}:
            raise ValueError("未知的共享代理维护操作。")
        with self.session.hold_lock(proxy_lock_command(), sudo=self.use_sudo):
            state = self.read_state()
            if action == "renew_dry_run":
                item = state["domains"].get(self.product.key)
                if not item:
                    raise RuntimeError("当前 Edition 尚未配置域名，不能演练续期。")
                domain = validate_domain(item["domain"])
                self.log("TG2CLOUD_STAGE=RENEW_DRY_RUN")
                task_id = uuid.uuid4().hex
                try:
                    code, output = self._run(renewal_dry_run_command(domain, task_id), timeout=600)
                except Exception:
                    try:
                        cleanup = "cleanup() { " + dry_run_cleanup_script(task_id) + " }; cleanup"
                        cleanup_code, cleanup_output = self._run("bash -c " + shlex.quote(cleanup), timeout=55)
                        if cleanup_code != 0 or parse_markers(cleanup_output).get("PROXY_TASK_CLEANUP") != "OK":
                            self.log("警告：本次维护任务清理未确认，请检查一次性续期容器。")
                    except Exception:  # noqa: BLE001 - disconnected SSH cannot confirm cleanup
                        self.log("警告：连接中断，暂时无法确认维护任务清理；远端任务设有 9 分钟执行时限，请恢复连接后检查。")
                    raise
                if parse_markers(output).get("PROXY_TASK_CLEANUP") != "OK":
                    raise RuntimeError("维护任务清理未确认，请检查本次一次性续期容器；不要重复演练。")
                if code != 0:
                    self.log("续期演练详情（已脱敏）：\n" + command_failure_summary(output))
                    raise RuntimeError("续期 dry-run 未通过；请检查 ACME 公网连通与 Certbot 日志。")
                return "续期 dry-run 通过；没有替换正式证书，也不代表长期自动续期已经验收。"
            markers = self._backup_helper(action, archive=archive)
            path = markers.get("PROXY_BACKUP_PATH", "")
            if not re.fullmatch(r"/opt/tg2cloud-proxy-backups/proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz", path):
                raise RuntimeError("备份输出路径无法识别。")
            title = {"backup": "私密备份及完整性检查通过", "check": "所选/最近备份完整性检查通过", "drill": "所选/最近备份隔离解包与文件校验通过"}[action]
            return f"{title}。\n备份仅保存在 VPS：{path}\n含证书私钥，不要上传至 GitHub。"

    def remove(self) -> ProxyReport:
        with self.session.hold_lock(proxy_lock_command(), sudo=self.use_sudo):
            return self._remove_locked()

    def _remove_locked(self) -> ProxyReport:
        previous = self.read_state()
        target = state_without_route(previous, self.product.key)
        if target == previous:
            return ProxyReport("", "not_configured", "当前 Edition 没有可移除的域名路由。", ())
        removed = previous["domains"][self.product.key]["domain"]
        try:
            if target["domains"]:
                self._activate(target)
                code, _ = self._compose("up -d certbot", timeout=180)
                if code != 0:
                    raise RuntimeError("剩余域名的证书续期容器更新失败；已开始回退。")
                self._verify_remaining_routes(target)
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
