"""Read-only HTTP probes. No writes, redirects, remote hosts or TLS bypass."""
from __future__ import annotations

import base64
import http.client
import re
import socket
import ssl
import xml.etree.ElementTree as ET  # nosec B405
from urllib.parse import quote, unquote, urlsplit


class LoopbackTLS(http.client.HTTPSConnection):
    def connect(self) -> None:
        # Preserve public hostname verification/SNI while probing this VPS.
        self.sock = self._context.wrap_socket(
            socket.create_connection(("127.0.0.1", self.port), self.timeout), server_hostname=self.host,
        )


def request(domain: str, port: int, method: str, path: str, *, credentials: tuple[str, str] | None = None,
            tls: bool = False, headers: dict | None = None) -> tuple[int, bytes, dict]:
    if method not in {"GET", "HEAD", "OPTIONS", "PROPFIND"}:
        raise ValueError("真实验收不发送写入方法。")
    connection = LoopbackTLS(domain, port, timeout=20, context=ssl.create_default_context()) if tls else http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    fields = {"Host": domain, "X-Forwarded-Proto": "https", "Depth": "0"}
    fields.update(headers or {})
    if credentials:
        fields["Authorization"] = "Basic " + base64.b64encode(":".join(credentials).encode()).decode()
    try:
        connection.request(method, path, headers=fields)
        response = connection.getresponse()
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            raise ValueError("目录响应超过只读验收上限。")
        return response.status, body, dict(response.getheaders())
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError("WebDAV 连接失败；未输出认证头或服务端原始响应。") from exc
    finally:
        connection.close()


def propfind(body: bytes, domain: str) -> tuple[str, ...]:
    if len(body) > 2 * 1024 * 1024 or b"\x00" in body:
        raise ValueError("目录 XML 过大或不是受支持的 UTF-8。")
    try:
        text = body.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise ValueError("目录 XML 不是 UTF-8。") from exc
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("目录 XML 含不支持的实体声明。")
    try:
        # Strict UTF-8, no NUL, bounded input, DTD/entities refused before parse.
        root = ET.fromstring(text)  # nosec B314
    except ET.ParseError as exc:
        raise ValueError("WebDAV 目录 XML 无效。") from exc
    if root.tag != "{DAV:}multistatus":
        raise ValueError("不是受支持的 WebDAV 目录响应。")
    hrefs = []
    for item in root.findall("{DAV:}response"):
        value = item.findtext("{DAV:}href") or ""
        parsed = urlsplit(value)
        if ((parsed.scheme and parsed.scheme != "https") or (parsed.scheme and not parsed.netloc)
                or (parsed.netloc and (parsed.hostname != domain or parsed.scheme != "https" or parsed.port not in (None, 443)))
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("目录 href 暴露内部地址或不可接受的跳转。")
        decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
        if (not (decoded == "/dav" or decoded.startswith("/dav/")) or "\\" in decoded or "//" in decoded
                or any(ord(char) < 32 for char in decoded)
                or any(part in {".", ".."} for part in decoded.split("/"))
                or re.search(r"%(?:25)*(?:2e|2f|5c|00)", decoded, re.IGNORECASE)):
            raise ValueError("目录 href 不在外部 /dav/ 范围。")
        statuses = item.findall("{DAV:}propstat/{DAV:}status")
        if not any(re.fullmatch(r"HTTP/\d(?:\.\d)? 200(?: .*)?", status.text or "") for status in statuses):
            raise ValueError("目录对象属性不是成功响应。")
        hrefs.append(parsed.path)
        if len(hrefs) > 5000:
            raise ValueError("目录响应条目过多。")
    if not hrefs:
        raise ValueError("目录响应缺少根目录，不能确认读取可用。")
    return tuple(hrefs)


def check_media(route: dict, secret: str, relative: str) -> None:
    """Optional user-selected existing file: no write or whole-file download."""
    if (not relative or relative.startswith("/") or any(c in relative for c in "\\?#")
            or re.search(r"%(?:25)*(?:2e|2f|5c|00)", relative, re.IGNORECASE)
            or any(ord(c) < 32 for c in relative)
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError("请使用目标根目录下真实文件的相对名称，不是 URL／编码路径。")
    path = "/dav/" + quote(relative, safe="/")
    options = {"tls": True, "credentials": (route["username"], secret)}
    status, _, headers = request(route["domain"], 443, "HEAD", path, **options)
    fields = {key.lower(): value for key, value in headers.items()}
    if status != 200 or not fields.get("content-length", "").isdigit() or int(fields["content-length"]) <= 0:
        raise ValueError("样本 HEAD 未确认是可读取的非空文件。")
    status, _, _ = request(route["domain"], 443, "OPTIONS", path, **options)
    if status not in {200, 204}:
        raise ValueError("样本 OPTIONS 未通过。")
    status, body, headers = request(route["domain"], 443, "GET", path, headers={"Range": "bytes=0-0"}, **options)
    fields = {key.lower(): value for key, value in headers.items()}
    if status != 206 or len(body) != 1 or not re.fullmatch(r"bytes 0-0/[1-9][0-9]*", fields.get("content-range", "")):
        raise ValueError("样本 Range 读取未通过，不能宣称视频拖动兼容。")


def check_backend(route: dict, secret: str) -> None:
    status, body, _ = request(route["domain"], route["backend_port"], "PROPFIND", "/dav/",
                              credentials=(route["username"], secret))
    if status != 207:
        hint = "请核对后台是否已创建并启用独立只读账号、用户名和密码是否一致，然后选择继续完成配置。" if status == 401 else "请核对外部专用账号的目录与读取权限。"
        raise ValueError(f"外部专用账号本地认证／列目录未通过（HTTP {status}）；" + hint + "不重置任何后端账号。")
    propfind(body, route["domain"])
    status, _, _ = request(route["domain"], route["backend_port"], "PROPFIND", "/dav/")
    if status not in {401, 403}:
        raise ValueError("后端允许匿名访问，不能确认独立账号权限；请先核对后端配置。")


def check_public_denials(route: dict) -> None:
    expected = 401 if route["enabled"] else 403
    status, _, _ = request(route["domain"], 443, "PROPFIND", "/dav/", tls=True)
    if status != expected:
        raise ValueError("外部入口拒绝访问自检未通过。")
    status, _, _ = request(route["domain"], 443, "GET", "/", tls=True)
    if status != 404:
        raise ValueError("外部域名不应暴露管理后台。")


def check_public(route: dict, secret: str, *, sample_file: str = "") -> None:
    check_public_denials(route)
    credentials = (route["username"], secret)
    for path in ("/dav", "/dav/"):
        status, body, _ = request(route["domain"], 443, "PROPFIND", path, tls=True, credentials=credentials)
        if status != 207:
            raise ValueError("外部入口认证或尾斜杠自检失败。")
        propfind(body, route["domain"])
    for user, bad_secret in ((route["username"], secret + "-invalid"), ("admin", secret)):
        status, _, _ = request(route["domain"], 443, "PROPFIND", "/dav/", tls=True, credentials=(user, bad_secret))
        if status != 401:
            raise ValueError("外部入口没有拒绝错误账号／密码。")
    if sample_file:
        check_media(route, secret, sample_file)
