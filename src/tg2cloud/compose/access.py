"""Offline Compose access choices; shared proxy changes run in the host wizard."""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.state import validate_domain, validate_email

ACCESS_FILE = "compose-access.json"
OWNER = "tg2cloud.compose.access"
MODES = {"1": "local", "2": "managed", "3": "external"}
LABELS = {"local": "本机或可信内网", "managed": "自动配置 HTTPS", "external": "接入已有反向代理"}


def validate_access(value: object, edition: str) -> dict:
    fields = {"format", "owner", "edition", "mode", "domain", "email"}
    if (edition not in PRODUCTS or not isinstance(value, dict) or set(value) != fields
            or type(value.get("format")) is not int or value["format"] != 1
            or value.get("owner") != OWNER or value.get("edition") != edition
            or not isinstance(value.get("mode"), str) or value["mode"] not in LABELS
            or not isinstance(value.get("domain"), str) or not isinstance(value.get("email"), str)):
        raise ValueError("Compose 访问方案无法识别；保留文件，请核对")
    result = dict(value)
    if result["mode"] == "local":
        if result["domain"] or result["email"]:
            raise ValueError("本机／内网方案不能夹带域名或证书配置")
    else:
        result["domain"] = validate_domain(result["domain"]) if result["domain"] else ""
        result["email"] = validate_email(result["email"])
        if result["mode"] == "managed" and not result["domain"]:
            raise ValueError("自动 HTTPS 需要管理页域名")
        if result["mode"] == "external" and result["email"]:
            raise ValueError("已有代理的证书由原管理方式负责，不另存签发邮箱")
    return result


def private_access(path: Path) -> None:
    info = path.stat()
    if os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o077):
        raise ValueError("Compose 访问方案必须归 root 所有且权限为 600")


def read_access(root: Path, edition: str, *, private_check: Callable[[Path], None] = private_access) -> dict | None:
    path = root / ACCESS_FILE
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError("Compose 访问方案经过链接；停止")
    if not path.exists():
        return None  # Historical direct-Compose installations have no plan.
    if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 8192:
        raise ValueError("Compose 访问方案不是受支持的小型配置文件")
    private_check(path)
    try:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Compose 访问方案含重复字段；不会覆盖")
                result[key] = value
            return result
        return validate_access(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs), edition)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Compose 访问方案无法解析；不会覆盖") from None


def choose_access(ui, edition: str, current: dict | None = None) -> dict:
    if edition not in PRODUCTS:
        raise ValueError("未知 Edition")
    current = validate_access(current, edition) if current is not None else None
    selected = next((key for key, mode in MODES.items() if current and mode == current["mode"]), "1")
    print("\n── 管理页访问方式 ──")
    print("1. 本机或可信内网")
    print("2. 自动配置 HTTPS")
    print("3. 接入已有反向代理")

    def selection(value):
        if value not in MODES:
            raise ValueError("请选择 1、2 或 3")
        return value

    mode = MODES[ui.ask("选择访问方式", default=selected, validate=selection)]
    domain = email = ""
    if mode != "local":
        domain = ui.ask("管理页域名（只填域名）", default=current["domain"] if current else "", validate=validate_domain)
        if mode == "managed":
            email = ui.ask("Let's Encrypt 邮箱（可留空）", default=current["email"] if current else "", validate=validate_email)
        print("管理端口保持 127.0.0.1；本步只保存计划，尚未配置反代或签发证书。")
        print("自动 HTTPS 使用共享 Nginx＋Certbot；已有代理只生成接入配置，不自动修改原站点。")
    return validate_access({"format": 1, "owner": OWNER, "edition": edition, "mode": mode,
                            "domain": domain, "email": email}, edition)


def next_steps(plan: dict) -> None:
    print("管理入口方案：" + LABELS[plan["mode"]])
    if plan["mode"] != "local":
        print("网关启动并完成后台设置后，在宿主机部署目录运行：bash https.sh")
        print("HTTPS 向导需要宿主机 Python 3.10+ 和本机 Docker；不向初始化容器挂载 Docker Socket。")
        if plan["mode"] == "external":
            print("已有代理的网络、证书及接入需按导出计划确认；未完成前不显示 HTTPS 已启用。")