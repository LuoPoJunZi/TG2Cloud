"""Bounded, read-only account-scope discovery; never infer a root from TARGET_PATH.

CloudDrive2's webdav_config.json is read only in the verified /Config bind.
Encrypted/unknown account layouts require one manual confirmation. OpenList
uses its documented login/current-user endpoints with the existing Bot account;
no administrator credentials are requested, retained, or put in process argv.
"""
from __future__ import annotations

import http.client
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from tg2cloud.addons.external_webdav import config

LIMIT = 1024 * 1024


@dataclass(frozen=True)
class Root:
    path: str = ""
    source: str = ""
    reason: str = ""


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("网关目录信息包含重复字段。")
        result[name] = value
    return result


def clouddrive2_root(instance) -> str:
    directory = Path(instance.directory) / "clouddrive/config"
    path = directory / "webdav_config.json"
    if path.resolve() != path or not path.is_file():
        raise ValueError("未找到可安全读取的 CloudDrive2 WebDAV 用户配置。")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT
                or (os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o022))):
            raise ValueError("CloudDrive2 WebDAV 配置归属、权限或大小无法核实。")
        content = stream.read(LIMIT + 1)
    if len(content) > LIMIT:
        raise ValueError("CloudDrive2 WebDAV 配置过大。")
    item = json.loads(content, object_pairs_hook=unique_object)
    if not isinstance(item, dict) or item.get("enabled") is not True:
        raise ValueError("CloudDrive2 WebDAV 配置格式未识别或服务未启用。")
    users = item.get("dav_users")
    if not isinstance(users, list) or len(users) > 4096:
        raise ValueError("CloudDrive2 WebDAV 用户格式未识别。")
    username = config.decode(instance.config, "USERNAME")
    matches = [user for user in users if isinstance(user, dict) and user.get("user_name") == username]
    if len(matches) != 1 or matches[0].get("enabled") is not True:
        raise ValueError("无法从 CloudDrive2 配置核实 Bot 用户；加密账号或未识别格式需首次补充目录。")
    return config.logical_path(matches[0].get("root_path"), allow_root=True)


def openlist_json(port: int, method: str, path: str, *, payload=None, token: str = "") -> dict:
    # HTTPConnection never follows redirects and ignores HTTP_PROXY. This is
    # always the preflight-verified local port, never a URL supplied by a user.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    try:
        connection.request(method, path, body=json.dumps(payload) if payload is not None else None, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("OpenList 账号目录接口未通过。")
        content = response.read(LIMIT + 1)
        if len(content) > LIMIT:
            raise ValueError("OpenList 账号目录响应过大。")
        result = json.loads(content, object_pairs_hook=unique_object)
        if not isinstance(result, dict) or type(result.get("code")) is not int or result["code"] != 200:
            raise ValueError("OpenList 账号目录接口未通过。")
        if not isinstance(result.get("data"), dict):
            raise TypeError("OpenList 账号目录格式未识别。")
        return result["data"]
    finally:
        connection.close()


def openlist_root(instance, product) -> str:
    username = config.decode(instance.config, "USERNAME")
    password = config.decode(instance.config, "PASSWORD")
    if not username or not password:
        raise ValueError("Bot WebDAV 凭据不完整，无法读取账号目录。")
    login = openlist_json(product.management_port, "POST", "/api/auth/login",
                          payload={"username": username, "password": password})
    token = login.get("token")
    if not isinstance(token, str) or not 1 <= len(token) <= 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("OpenList 临时认证结果未核实。")
    user = openlist_json(product.management_port, "GET", "/api/me", token=token)
    if user.get("username") != username or user.get("disabled") is not False:
        raise ValueError("OpenList 返回的账号与 Bot 配置不一致或已停用。")
    return config.logical_path(user.get("base_path"), allow_root=True)


def resolve(instance, product, previous=None) -> Root:
    try:
        root = openlist_root(instance, product) if product.is_openlist else clouddrive2_root(instance)
        return Root(root, "网关账号配置")
    except (ValueError, TypeError, OSError, http.client.HTTPException):
        # Raw backend JSON, error messages, token and configuration are private.
        # A previous confirmation is reusable only for this exact binding.
        if (previous and previous["instance_dir"] == str(instance.directory)
                and previous["binding"] == config.binding(instance.config)
                and previous["backend_image"] == instance.gateway_image):
            return Root(config.logical_path(previous["bot_root"], allow_root=True), "上次确认的账号根目录")
        return Root(reason="未能自动核实 Bot 账号根目录，请在管理页核对后首次补充一次。")


def management_address(instance, product, state) -> str:
    from tg2cloud.deployment.proxy.state import validate_domain
    route = state.get("domains", {}).get(product.key)
    if route:
        return "https://" + validate_domain(route["domain"])
    from tg2cloud.deployment.proxy import lan
    saved = lan.load_state(product)
    if saved and saved["install_dir"] == str(instance.directory):
        return f"http://{lan.validate_ip(saved['bind_ip'])}:{product.management_port}"
    return "未登记管理地址，请使用你原有的网关管理入口"
