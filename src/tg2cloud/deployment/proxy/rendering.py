"""Pure managed proxy rendering; no host commands or persistent writes."""
from __future__ import annotations

import json
from typing import Any

from .state import (
    EDITION_BACKEND_PORTS,
    SUPPORTED_EDITIONS,
    DomainRoute,
    certificate_domains,
    has_routes,
    normalize_state,
    routes_from_state,
    validate_domain,
)

PROXY_NGINX_CONTAINER = "tg2cloud-proxy-nginx"
PROXY_CERTBOT_CONTAINER = "tg2cloud-proxy-certbot"
NGINX_IMAGE = "nginx:1.30.5-alpine"
CERTBOT_IMAGE = "certbot/certbot:v5.8.0"

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
