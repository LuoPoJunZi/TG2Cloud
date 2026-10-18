"""Read-only reverse proxy, not a WebDAV implementation or path sandbox."""
from __future__ import annotations

from tg2cloud.deployment.proxy.state import EDITION_BACKEND_PORTS, validate_domain


def render_route(route: dict) -> str:
    domain = validate_domain(route["domain"])
    edition = route["edition"]
    if edition not in EDITION_BACKEND_PORTS or route["auth_file"] != f"external-auth/{edition}.htpasswd":
        raise ValueError("Invalid external route")
    port = EDITION_BACKEND_PORTS[edition]
    prefix = "extdav_" + edition
    limits = f"""limit_req_zone $binary_remote_addr zone={prefix}_requests:1m rate=30r/s;
limit_conn_zone $binary_remote_addr zone={prefix}_connections:1m;
map $request_method ${prefix}_listing {{ default ""; PROPFIND $binary_remote_addr; }}
limit_req_zone ${prefix}_listing zone={prefix}_propfind:1m rate=2r/s;
"""
    http = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    if ($host != {domain}) {{ return 444; }}
    access_log off;
    error_log /dev/null;
    location ^~ /.well-known/acme-challenge/ {{ root /var/www/certbot; try_files $uri =404; }}
    location / {{ return 308 https://{domain}$uri; }}
}}
"""
    guards = r"""
    # Check original encoding as well as normalized location matching. Keep
    # normal Unicode/%20/%25 filenames; reject encoded separators and traversal.
    if ($args != "") { return 400; }
    if ($request_uri ~* "(?:\\|%(?:25)*5c|%(?:25)*2f|%25(?:25)*(?:2e|00)|%00)") { return 400; }
    if ($request_uri ~* "(?:^|/)(?:\.|%2e){1,2}(?:/|$)") { return 400; }
    if ($request_uri ~ "//") { return 400; }
"""
    locations = "    location / { return 404; }\n"
    for location in ("= /dav", "^~ /dav/"):
        policy = "return 403;" if not route["enabled"] else f"""
        if ($http_depth !~ ^(0|1|)$) {{ return 403; }}
        auth_basic "TG2Cloud external WebDAV";
        auth_basic_user_file /etc/nginx/{route['auth_file']};
        satisfy all;
        open_file_cache off;
        limit_except GET HEAD OPTIONS PROPFIND {{ deny all; }}
        limit_req zone={prefix}_requests burst=90 nodelay;
        limit_req zone={prefix}_propfind burst=10 nodelay;
        limit_conn {prefix}_connections 32;
        limit_req_status 429;
        limit_conn_status 429;
        proxy_pass http://127.0.0.1:{port}{'/dav/' if location.startswith('=') else ''};
        proxy_http_version 1.1;
        proxy_set_header Host {domain};
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host {domain};
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Cookie "";
        proxy_set_header Proxy-Authorization "";
        proxy_set_header Connection "";
        proxy_set_header Depth $http_depth;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_hide_header Location;
        proxy_hide_header Set-Cookie;
        proxy_ignore_headers X-Accel-Redirect;
        proxy_intercept_errors on;
        error_page 301 302 303 307 308 =502 @external_redirect_denied;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_max_temp_file_size 0;
        proxy_connect_timeout 10s;
        proxy_read_timeout 300s;
        proxy_send_timeout 60s;
"""
        locations += f"    location {location} {{\n        {policy}\n    }}\n"
    locations += "    location @external_redirect_denied { return 502; }\n"
    return limits + http + f"""server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {domain};
    if ($host != {domain}) {{ return 444; }}
    # Run before location selection: limit_except does not inherit location
    # rewrite directives, so a location-level return would be skipped there.
    if ($request_method !~ ^(GET|HEAD|OPTIONS|PROPFIND)$) {{ return 405; }}
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    access_log off;
    error_log /dev/null;
    client_max_body_size 16k;
    {guards}
{locations}
}}
"""
