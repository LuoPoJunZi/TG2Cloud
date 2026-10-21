"""Shared, transactional HTTPS management for both TG2Cloud editions.

Rendering and parsing helpers are deterministic. Offline Linux CLI regressions
exercise safety decisions without contacting Docker, DNS, Nginx, Certbot or
Let's Encrypt; the host execution boundary is injected.
"""

from __future__ import annotations

from .certificates import (
    _CERTIFICATE_CHECK_SCRIPT,
    PROXY_ROOT,
    dry_run_cleanup_script,
    parse_certificate_enddate,
    renewal_dry_run_command,
    renewal_summary,
    renewal_warnings,
)
from .state import (
    _EMAIL_RE,
    _FQDN_RE,
    _MARKER_RE,
    EDITION_BACKEND_PORTS,
    STATE_VERSION,
    SUPPORTED_EDITIONS,
    DomainRoute,
    ProxyEnvironment,
    ProxyReport,
    _marker_addresses,
    certificate_domains,
    dns_diagnostic,
    dns_matches_environment,
    empty_state,
    has_routes,
    nat_public_ipv4_candidate,
    normalize_state,
    parse_environment,
    parse_markers,
    public_endpoint_error,
    routes_from_state,
    state_with_route,
    state_without_route,
    validate_domain,
    validate_email,
    validate_public_ipv4,
)

__all__ = ['EDITION_BACKEND_PORTS', 'PROXY_ROOT', 'STATE_VERSION', 'SUPPORTED_EDITIONS', '_CERTIFICATE_CHECK_SCRIPT', '_EMAIL_RE', '_FQDN_RE', '_MARKER_RE', 'DomainProxyManager', 'DomainRoute', 'ProxyEnvironment', 'ProxyReport', '_marker_addresses', 'dns_diagnostic', 'dns_matches_environment', 'dry_run_cleanup_script', 'empty_state', 'normalize_state', 'parse_certificate_enddate', 'parse_environment', 'parse_markers', 'renewal_dry_run_command', 'renewal_summary', 'renewal_warnings', 'routes_from_state', 'state_with_route', 'state_without_route', 'validate_domain', 'validate_email']

import json
import re
import shlex
import signal
import sys
import tempfile
import threading
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from tg2cloud.deployment.profiles import PRODUCTS, ProductProfile

PROXY_NGINX_CONTAINER = "tg2cloud-proxy-nginx"
PROXY_CERTBOT_CONTAINER = "tg2cloud-proxy-certbot"
NGINX_IMAGE = "nginx:1.30.5-alpine"
CERTBOT_IMAGE = "certbot/certbot:v5.8.0"
HOST_TOOL_PACKAGES = {
    "ss": "iproute2", "ip": "iproute2", "curl": "curl",
    "getent": "libc-bin", "python3": "python3", "timeout": "coreutils",
    "flock": "util-linux",
}


@contextmanager
def defer_interruptions():
    """Finish bounded commit/rollback commands before honoring CLI cancellation.

    Background workers never install signal handlers. SIGKILL and lost connections are
    not recoverable here; ordinary INT/TERM/HUP must not split a state commit.
    """
    previous = {}
    pending = False

    def defer(_signum, _frame):
        nonlocal pending
        pending = True

    try:
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGTERM", "SIGHUP"):
                number = getattr(signal, name, None)
                if number is not None and signal.getsignal(number) != signal.SIG_IGN:
                    previous[number] = signal.signal(number, defer)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        if pending and sys.exc_info()[0] is None:
            raise KeyboardInterrupt


def host_tools_check_script(tools: tuple[str, ...]) -> str:
    if not tools or any(tool not in HOST_TOOL_PACKAGES for tool in tools):
        raise ValueError("未知宿主依赖。")
    return f"""
missing_tools=""
for tool in {shlex.join(tools)}; do
  if ! command -v "$tool" >/dev/null 2>&1; then missing_tools="$missing_tools $tool"; fi
done
if [[ -n "$missing_tools" ]]; then
  printf 'TG2CLOUD_PROXY_MISSING_TOOLS=%s\\n' "${{missing_tools# }}"
  exit 3
fi
"""


def raise_missing_host_tools(output: str) -> None:
    missing = parse_markers(output).get("PROXY_MISSING_TOOLS", "").split()
    if missing:
        tools = [tool for tool in missing if tool in HOST_TOOL_PACKAGES]
        packages = sorted({HOST_TOOL_PACKAGES[tool] for tool in tools})
        raise RuntimeError(
            "VPS 缺少宿主依赖：" + ", ".join(tools or ["未知工具"])
            + "。尚未执行 HTTPS 变更；这不是 DNS 或端口冲突。"
            + ("请以 root 手动执行 apt-get update && apt-get install -y "
               + " ".join(packages) + "，然后重新检测。" if packages else "请核对系统依赖。")
        )

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")



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


def render_compose(active_domains: tuple[str, ...] = (), *, external_auth: bool = False) -> str:
    certificate_names = " ".join(validate_domain(domain) for domain in active_domains)
    certbot_command = render_certbot_loop().replace("$", "$$")
    auth_mount = "      - ./external-auth:/etc/nginx/external-auth:ro\n" if external_auth else ""
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
{auth_mount}\
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
        "conf.d/00-default.conf": render_default_conf(tls_enabled=has_routes(state)),
    }
    if state.get("version") == 2:
        files["nginx.conf"] = "worker_shutdown_timeout 10s;\n" + files["nginx.conf"]
    for route in routes:
        files[f"conf.d/20-{route.edition}.conf"] = render_route_conf(route)
    for edition, route in normalize_state(json.dumps(state)).get("external_webdav", {}).items():
        from tg2cloud.addons.external_webdav.nginx import render_route
        files[f"conf.d/30-external-webdav-{edition}.conf"] = render_route(route)
    if candidate_domain:
        candidate = validate_domain(candidate_domain)
        if candidate not in certificate_domains(state):
            files["conf.d/10-acme-bootstrap.conf"] = render_bootstrap_conf(candidate)
    return files














def environment_probe_command(product: ProductProfile, domain: str) -> str:
    domain = validate_domain(domain)
    return "bash -c " + shlex.quote(
        f"""
set -u
{host_tools_check_script(tuple(HOST_TOOL_PACKAGES))}
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


def install_config_command(remote: str, *, external_auth: bool = False) -> str:
    """Render the privileged, syntax-checkable config installation transaction."""
    # The remote path is random, privately created with mode 0700, and never user supplied.
    if not re.fullmatch(  # nosec B108
        r"/tmp/tg2cloud-proxy-[0-9a-f]{32}", remote
    ):
        raise ValueError("共享代理临时目录格式不正确。")
    auth_mount = '-v "$root/external-auth:/etc/nginx/external-auth:ro"' if external_auth else ""
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
  {auth_mount} \
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
        *,
        confirm_public_ipv4: Callable[[str, ProxyEnvironment], str] | None = None,
    ) -> None:
        self.session = session
        self.product = product
        self.values = values
        self.log = log
        self.use_sudo = False
        self.confirm_public_ipv4 = confirm_public_ipv4
        self._nat_confirmation: tuple[str, str, tuple[str, ...], tuple[str, ...], frozenset[str]] | None = None

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
        raise_missing_host_tools(output)
        if code != 0:
            raise RuntimeError("无法完成域名、Docker 与端口环境检测。")
        environment = parse_environment(output)
        if self._nat_confirmation is not None:
            saved_domain, address, dns_a, dns_aaaa, local = self._nat_confirmation
            if (domain == saved_domain and environment.dns_a == dns_a and environment.dns_aaaa == dns_aaaa
                    and local <= set(environment.local_addresses)
                    and nat_public_ipv4_candidate(environment) == address):
                return replace(environment, confirmed_public_ipv4=address)
            self._nat_confirmation = None
        return environment

    def confirm_nat(self, domain: str, environment: ProxyEnvironment) -> ProxyEnvironment:
        """Confirm only during interactive preflight, before the write lock."""
        if (dns_matches_environment(environment, self.values["vps_host"]) or not environment.ports_safe
                or self.confirm_public_ipv4 is None or not nat_public_ipv4_candidate(environment)):
            return environment
        supplied = self.confirm_public_ipv4(domain, environment)
        if not supplied:
            return environment
        address = validate_public_ipv4(supplied)
        if address != nat_public_ipv4_candidate(environment):
            raise ValueError("云控制台公网 IPv4 与域名 A 记录不一致；未放行 HTTPS。")
        self._nat_confirmation = (domain, address, environment.dns_a, environment.dns_aaaa,
                                  frozenset(environment.local_addresses))
        return replace(environment, confirmed_public_ipv4=address)

    def _validate_environment(self, environment: ProxyEnvironment) -> None:
        if environment.core != "OK":
            raise RuntimeError(f"请先完成 {self.product.display_name} 基础部署并确认管理页在 VPS 回环端口可访问。")
        if environment.docker != "OK":
            raise RuntimeError("VPS 上的 Docker Compose 不可用，请先完成基础环境部署。")
        error = public_endpoint_error(environment, self.values["vps_host"])
        if error:
            raise RuntimeError(error + "\n" + dns_diagnostic(environment, self.values["vps_host"]))

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
        from tg2cloud.deployment import architecture
        architecture.check_docker(self.session)
        for image in (NGINX_IMAGE, CERTBOT_IMAGE):
            architecture.ensure_image(self.session, image)
        files = render_config_set(state, candidate_domain=candidate)
        active_domains = certificate_domains(state)
        external_auth = state.get("version") == 2
        files["docker-compose.yml"] = render_compose(active_domains, external_auth=external_auth)
        remote = self._upload_files(files)
        try:
            code, _ = self._run(install_config_command(remote, external_auth=external_auth), timeout=180)
            if code != 0:
                raise RuntimeError("无法安装共享代理配置。")
        finally:
            self.session.run(f"rm -rf -- {remote}", timeout=20)

    def _compose(self, arguments: str, *, timeout: float = 180) -> tuple[int, str]:
        result = self._run(
            f"docker compose -f {PROXY_ROOT}/docker-compose.yml {arguments}",
            timeout=timeout,
        )
        if result[0] == 0 and arguments.startswith("up "):
            from tg2cloud.deployment import architecture
            if "certbot" in arguments:
                architecture.check_container(self.session, PROXY_CERTBOT_CONTAINER, require_running=True)
            if "nginx" in arguments:
                architecture.check_container(self.session, PROXY_NGINX_CONTAINER, require_running=True)
        return result

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
        environment = self.confirm_nat(domain, self.probe(domain))
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
        committed = False
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
            with defer_interruptions():
                self._commit_state(target)
                committed = True
            return report
        except (Exception, KeyboardInterrupt):
            if committed:
                # Cancellation after the atomic commit must not restore an old
                # runtime while domains.json already describes the new route.
                raise
            try:
                with defer_interruptions():
                    if has_routes(previous):
                        try:
                            self._activate(previous)
                        except Exception:
                            if not repairing_existing_certificate:
                                raise
                            self._activate(bootstrap_state, candidate=domain)
                        code, _ = self._compose("up -d certbot", timeout=120)
                    else:
                        self._install_config(previous)
                        code, _ = self._compose("stop nginx certbot", timeout=60)
                    if code:
                        raise RuntimeError("代理回退容器操作失败")
            except (Exception, KeyboardInterrupt) as rollback_error:  # noqa: BLE001 - rollback boundary
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
        if state.get("external_webdav"):
            from tg2cloud.addons.external_webdav.verification import (
                check_public_denials,
            )
            for route in state["external_webdav"].values():
                check_public_denials(route)

    def apply_shared_state_locked(self, target: dict[str, Any], *, domain: str = "", email: str = "", verify=None,
                                  verify_remaining: bool = True) -> None:
        """Called under the existing proxy lock; preserve every other owner.

        External callers revoke authentication before changing credentials. A
        failed activation never restores an enabled external route.
        """
        target = normalize_state(json.dumps(target))
        previous = self.read_state()
        fallback = normalize_state(json.dumps(previous))
        key = self.product.key
        if key in fallback.get("external_webdav", {}):
            fallback["external_webdav"][key]["enabled"] = False
        self._ensure_state_file(previous)
        committed = False
        try:
            if domain and not self._certificate_valid(domain):
                self._validate_environment(self.probe(domain))
                self._activate(previous, candidate=domain)
                self._obtain_certificate(domain, validate_email(email))
            self._activate(target)
            code, _ = self._compose("up -d certbot", timeout=180)
            if code:
                raise RuntimeError("共享续期配置未启动。")
            if verify_remaining:
                self._verify_remaining_routes(target)
            if verify:
                verify()
            with defer_interruptions():
                self._commit_state(target)
                committed = True
        except (Exception, KeyboardInterrupt):
            if not committed:
                with defer_interruptions():
                    try:
                        if has_routes(fallback):
                            self._activate(fallback)
                            self._compose("up -d certbot", timeout=180)
                        else:
                            self._install_config(fallback)
                            self._compose("stop nginx certbot", timeout=60)
                        self._commit_state(fallback)
                    except Exception:  # noqa: BLE001 - rollback failure must not mask original error
                        self.log("外部入口变更失败且代理回退未确认；认证已撤销，请核对共享代理。")
            raise

    def _backup_helper(self, action: str, *, archive: str = "", keep: int = 5, plan: str = "") -> dict[str, str]:
        if action not in {"backup", "check", "drill", "list", "prune-preview", "prune"}:
            raise ValueError("未知备份操作。")
        if archive and not re.fullmatch(r"proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz", archive):
            raise ValueError("备份文件名无效。")
        if type(keep) is not int or not 1 <= keep <= 50:
            raise ValueError("保留份数必须为 1～50。")
        if action == "prune" and not re.fullmatch(r"[0-9a-f]{64}", plan):
            raise ValueError("请先预览并确认清理计划。")
        code, output = self._run(
            "bash -c " + shlex.quote(host_tools_check_script(("python3", "timeout"))), timeout=15
        )
        raise_missing_host_tools(output)
        if code:
            raise RuntimeError("无法完成共享代理维护的宿主依赖检查。")
        self.log("TG2CLOUD_STAGE=PROXY_BACKUP")
        source = Path(__file__).with_name("maintenance.py").read_text(encoding="utf-8")
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
            if has_routes(target):
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
            if has_routes(previous):
                self._activate(previous)
                self._compose("up -d certbot", timeout=120)
            raise
        return ProxyReport(
            "",
            "not_configured",
            f"已移除 {removed} 的 {self.product.display_name} 路由；证书文件默认保留。",
            (),
        )
