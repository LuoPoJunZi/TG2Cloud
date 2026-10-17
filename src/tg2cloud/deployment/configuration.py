from __future__ import annotations

import base64
import math
import os
import re
from pathlib import Path

from tg2cloud.deployment.profiles import PRODUCTS, ProductProfile
from tg2cloud.deployment.resources import (
    validate_install_dir,
)


def regular_private(path: Path) -> bytes:
    if path.is_symlink() or path.resolve() != path or not path.is_file():
        raise ValueError("必要文件缺失或经过链接：" + path.name)
    info = path.stat()
    if info.st_size > 128 * 1024:
        raise ValueError("配置文件异常过大")
    if os.name == "posix" and (info.st_uid != 0 or info.st_mode & 0o077):
        raise ValueError("配置必须归 root 所有，且不允许组/其他用户读取")
    return path.read_bytes()


def parse_config(raw: bytes) -> dict[str, str]:
    result = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
            raise ValueError("配置存在无效/重复项目；不会执行配置内容")
        result[key] = value
    if result.get("TG2CLOUD_REDEPLOY_APPLY_CONFIG") not in (None, "true", "false"):
        raise ValueError("配置覆盖标记无效")
    return result


def checked_directory(value: str) -> Path:
    validate_install_dir(value)
    path = Path(value)
    if path.resolve() != path or path.is_symlink():
        raise ValueError("安装目录经过链接；不会操作")
    return path


def check_product_directory(product: ProductProfile, directory: Path) -> None:
    protected = [Path("/opt/tg2cloud-proxy"), Path("/opt/tg2cloud-cli-locks"), Path("/opt/tg2cloud-webdav")]
    for profile in PRODUCTS.values():
        protected += [Path(profile.backup_dir), *(Path(name) for name in profile.legacy_install_dirs)]
        if profile.key != product.key:
            protected.append(Path(profile.install_dir))
    if any(directory == root or directory.is_relative_to(root) or root.is_relative_to(directory) for root in protected):
        raise ValueError("安装目录与其他 Edition、代理、锁、备份或 TG115 路径重叠")


def encoded(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def new_config(product: ProductProfile, values: dict[str, str]) -> dict[str, str]:
    result = {
        "TELEGRAM_API_ID": values["api_id"], "ALLOWED_USER_ID": values["user_id"],
        "TELEGRAM_API_HASH_B64": encoded(values["api_hash"]), "BOT_TOKEN_B64": encoded(values["bot_token"]),
        "LOCAL_TEMP_BUDGET_GB": values["budget"], "MIN_FREE_DISK_GB": values["reserve"],
        "CONTROL_INTERVAL_SECONDS": "3", "CPU_TARGET_LOW_PERCENT": "60", "CPU_TARGET_HIGH_PERCENT": "80",
        "CPU_PRESSURE_PERCENT": "90", "MEMORY_SOFT_MIN_MB": "1024", "MEMORY_HARD_MIN_MB": "512",
        "RAMP_UP_STEP": "1", "RAMP_DOWN_FACTOR": "0.5", "MAX_RETRIES": "3",
        "REMOTE_HEALTH_INTERVAL_SECONDS": "30", "TZ": values["timezone"],
        "DEPLOY_CLOUDDRIVE2": "false" if product.is_openlist else "true",
        "TG2CLOUD_REDEPLOY_APPLY_CONFIG": "false",
    }
    for prefix in ("TG2CLOUD", "TG115"):
        result[prefix + "_STORAGE_BACKEND"] = product.key
        result[prefix + "_DESTINATION_LABEL"] = product.display_name
        result[prefix + "_RCLONE_REMOTE_NAME"] = "openlist" if product.is_openlist else "cd2"
    for key, value in (("URL", product.webdav_url), ("USERNAME", values["webdav_user"]), ("PASSWORD", values["webdav_password"])):
        result["WEBDAV_" + key + "_B64"] = encoded(value)
        result["CD2_WEBDAV_" + key + "_B64"] = encoded(value)
    result["WEBDAV_TARGET_PATH_B64"] = result["CD2_TARGET_PATH_B64"] = encoded(values["target"])
    if product.is_openlist:
        result["OPENLIST_ADMIN_PASSWORD"] = values["admin_password"]
        result["TG2CLOUD_PRESERVE_WEBDAV"] = result["TG115_PRESERVE_WEBDAV"] = "false"
    return result


def positive(value: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,14}", value):
        raise ValueError("请输入大于零的整数")
    return value


def size_gb(value: str) -> str:
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 100000:
        raise ValueError("请输入有限的正数 GB")
    return value


def plain(value: str) -> str:
    if not value or len(value) > 1024 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("输入为空、过长或含控制字符")
    return value
