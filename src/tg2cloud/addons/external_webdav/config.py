"""Strict metadata and salted password hashes; never store backend passwords."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess  # nosec B404
from pathlib import Path, PurePosixPath

OWNER = "tg2cloud.external_webdav"
ROOT = Path("/opt/tg2cloud-webdav")
HASH = re.compile(r"\$6\$rounds=200000\$[A-Za-z0-9./]{16}\$[A-Za-z0-9./]{86}")


def logical_path(value: str, *, allow_root: bool = False) -> str:
    if (not isinstance(value, str) or not value.startswith("/") or "\\" in value or "\x00" in value
            or any(ord(char) < 32 for char in value) or len(value.encode()) > 2048
            or any(part in {".", ".."} for part in value.split("/")) or "//" in value):
        raise ValueError("请填写规范的网关逻辑绝对目录，不是 URL 或 VPS 目录。")
    result = str(PurePosixPath(value))
    if result == "/" and not allow_root:
        raise ValueError("第一版拒绝暴露整个网关根目录 /。")
    return result


def decode(config: dict, key: str) -> str:
    # Match Settings._decode_b64_compatible exactly, including empty-primary
    # fallback and the historical TARGET key (without WEBDAV in its name).
    legacy = "CD2_TARGET_PATH_B64" if key == "TARGET_PATH" else "CD2_WEBDAV_" + key + "_B64"
    raw = config.get("WEBDAV_" + key + "_B64") or config.get(legacy, "")
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("实例的 WebDAV 配置无法安全解析。") from exc


def binding(config: dict) -> str:
    # No password digest: this detects configuration changes without retaining
    # secrets or pretending TARGET_PATH describes the native user's root.
    values = [decode(config, key) for key in ("URL", "USERNAME", "TARGET_PATH")]
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def username(value: str, bot_user: str = "") -> str:
    if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{2,47}", value)
            or value.casefold() in {"root", "admin", "administrator", "anonymous", "guest", bot_user.casefold()}):
        raise ValueError("使用新的专用用户名（3～48 位字母、数字、._-），不能是 Bot 或管理员。")
    return value


def password(value: str) -> str:
    classes = sum(bool(re.search(pattern, value)) for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))
    if (not 16 <= len(value) <= 128 or any(not 33 <= ord(c) <= 126 for c in value)
            or len(set(value)) < 10 or classes < (2 if len(value) >= 24 else 3)
            or any(word in value.casefold() for word in ("password", "123456", "qwerty"))):
        raise ValueError("密码过弱：请用 16～128 位无空白 ASCII 强密码，或使用安全随机生成。")
    return value


def new_password() -> str:
    while True:
        value = secrets.token_urlsafe(30)
        try:
            return password(value)
        except ValueError:
            continue


def password_hash(value: str, *, existing: str = "", executable: str = "openssl") -> str:
    password(value)
    if existing and not HASH.fullmatch(existing):
        raise ValueError("不支持的密码哈希格式。")
    salt = existing.rsplit("$", 1)[0].removeprefix("$6$") if existing else "rounds=200000$" + secrets.token_hex(8)
    # Fixed program; secret travels only through stdin.
    result = subprocess.run(  # nosec B603
        [executable, "passwd", "-6", "-salt", salt, "-stdin"], input=value.encode() + b"\n",
        capture_output=True, timeout=20, check=False,
    )
    output = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode or not HASH.fullmatch(output):
        raise ValueError("OpenSSL 无法生成受支持的 SHA512-crypt 哈希；未降级算法。")
    if existing and not hmac.compare_digest(existing, output):
        raise ValueError("外部账号密码与已保存哈希不一致。")
    return output


def canonical(path: Path) -> None:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError("附加功能路径经过链接或不规范。")
    for parent in (*path.parents, path):
        if parent.exists() and parent.is_symlink():
            raise ValueError("附加功能父目录经过链接。")
        # /tmp is a parent of isolated test/source trees, not persistent state.
        if (parent.exists() and os.name == "posix" and parent != Path("/tmp")  # nosec B108
                and (parent.stat().st_uid not in {0, os.geteuid()} or parent.stat().st_mode & 0o022)):
            raise ValueError("持久路径必须由 root 持有且不可由组／其他用户写入。")


def atomic(path: Path, content: bytes, *, mode: int = 0o600, gid: int | None = None) -> None:
    canonical(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    staged = path.with_name("." + path.name + "-" + secrets.token_hex(12))
    try:
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as writer:
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
        if gid is not None:
            os.chown(staged, 0, gid)
        staged.chmod(mode)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def read_record(path: Path) -> dict | None:
    canonical(path)
    if not path.exists():
        return None
    info = path.stat()
    if not path.is_file() or info.st_size > 32768 or (os.name == "posix" and (info.st_uid or info.st_mode & 0o077)):
        raise ValueError("附加功能记录的所有者、权限或大小不安全。")
    item = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema", "owner", "edition", "instance_dir", "domain", "username", "bot_root", "target_dir",
                "binding", "phase", "scope_verification", "backend_image", "revision"}
    if (not isinstance(item, dict) or set(item) != required or type(item["schema"]) is not int or item["schema"] != 1 or item["owner"] != OWNER
            or any(not isinstance(value, str) for key, value in item.items() if key != "schema")
            or item["edition"] not in {"clouddrive2", "openlist"}
            or item["phase"] not in {"pending", "disabled", "enabled", "needs_repair"}
            or item["scope_verification"] != "manual-native-readonly"
            or not re.fullmatch(r"[0-9a-f]{32}", item["revision"])
            or not re.fullmatch(r"[0-9a-f]{64}", item["binding"])):
        raise ValueError("附加功能状态不受支持或归属不符。")
    from tg2cloud.deployment.configuration import checked_directory
    from tg2cloud.deployment.proxy.state import validate_domain
    checked_directory(item["instance_dir"])
    validate_domain(item["domain"])
    username(item["username"])
    logical_path(item["bot_root"], allow_root=True)
    logical_path(item["target_dir"])
    return item


def write_record(path: Path, item: dict) -> None:
    atomic(path, (json.dumps(item, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode())
