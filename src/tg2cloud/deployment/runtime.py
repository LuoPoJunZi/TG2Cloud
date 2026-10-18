"""Install an immutable, host-only offline manager without copying instance data."""
from __future__ import annotations

import hashlib
import json
import os
import re
import runpy
import shlex
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/opt/tg2cloud-cli")
COMMAND = Path("/usr/local/bin/tg2cloud")
LOCK_ROOT = Path("/opt/tg2cloud-cli-locks")
HEADER = "#!/bin/sh\n# TG2Cloud Linux manager managed v1\n"


def lifecycle_lock():
    """Serialize confirmed manager installation with last-instance cleanup."""
    from tg2cloud.deployment.host import edition_lock
    return edition_lock(LOCK_ROOT / "manager-lifecycle.lock")


def publication_lock(root: Path):
    from tg2cloud.deployment.host import edition_lock
    # Locks live outside the removable runtime: never unlink a locked inode.
    path = LOCK_ROOT / "manager-code.lock" if root == ROOT else root.parent / (root.name + "-code.lock")
    return edition_lock(path)


def safe_path(path: Path, *, private: bool = False) -> None:
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("本地管理路径经过链接或不是绝对路径")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("本地管理路径经过链接")
        if item.exists():
            info = item.stat()
            if os.name == "posix" and (info.st_uid not in {0, os.getuid()} or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
                raise ValueError("本地管理路径的所有者/写入权限不安全")
    if private and path.exists() and os.name == "posix" and (path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise ValueError("本地管理目录必须为私有目录")


def files(source: Path) -> dict[str, bytes]:
    names = ["scripts/run_source.py", "src/tg2cloud/__init__.py", "src/tg2cloud/version.py", "src/tg2cloud/config.py"]
    for directory in ("cli", "deployment", "addons"):
        names.extend(p.relative_to(source).as_posix() for p in (source / "src/tg2cloud" / directory).rglob("*.py"))
    result = {}
    for name in sorted(set(names)):
        path = source / name
        if path.is_symlink() or path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("本地维护源码缺失、过大或经过链接")
        result[name] = path.read_bytes()
    if "src/tg2cloud/cli/management.py" not in result:
        raise ValueError("此代码来源尚不支持 tg2cloud 管理菜单")
    return result


def verify(bundle: Path) -> dict:
    safe_path(bundle, private=True)
    marker = bundle / "installation.json"
    safe_path(marker)
    if not marker.is_file() or marker.stat().st_size > 128 * 1024:
        raise ValueError("本地管理运行清单缺失/过大")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("owner") != "tg2cloud.cli" or not isinstance(data.get("files"), dict):
        raise ValueError("本地管理运行清单不受支持")
    actual = files(bundle)
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in actual.items()}
    if hashes != data["files"]:
        raise ValueError("本地管理源码与安装清单不一致；停止，不执行未知代码")
    expected = {*actual, "installation.json"}
    for path in bundle.rglob("*"):
        safe_path(path)
        if path.is_file() and path.relative_to(bundle).as_posix() not in expected:
            raise ValueError("本地管理目录含未知文件")
        if not path.is_file() and not path.is_dir():
            raise ValueError("本地管理目录含特殊文件")
    return data


def launcher(bundle: Path) -> str:
    return HEADER + "exec python3 -B " + shlex.quote(str(bundle / "src/tg2cloud/deployment/runtime.py")) + ' "$@"\n'


def check_destination(*, root: Path = ROOT, command: Path = COMMAND) -> None:
    """Read-only collision check, called before confirming installation."""
    safe_path(root, private=True)
    safe_path(command)
    if root.exists():
        if not root.is_dir() or any(p.name not in {"runtime", "install.lock"} for p in root.iterdir()):
            raise ValueError("本地管理目录含不明资源；不会覆盖")
        if not (root / "runtime").is_dir():
            raise ValueError("本地管理目录不是完整的受管目录")
    if command.exists():
        if not command.is_file() or command.stat().st_size > 4096:
            raise ValueError("tg2cloud 命令已被其他程序占用")
        text = command.read_text(encoding="utf-8")
        match = re.fullmatch(re.escape(HEADER) + r"exec python3 -B (.+) \"\$@\"\n", text)
        args = shlex.split(match[1]) if match else []
        if len(args) != 1:
            raise ValueError("tg2cloud 命令不属于本项目；不会覆盖")
        entry = Path(args[0])
        if len(entry.parents) < 4:
            raise ValueError("tg2cloud 命令的运行路径不符合受管布局")
        bundle = entry.parents[3]
        if (bundle.parent != root / "runtime" or not re.fullmatch(r"[a-f0-9]{64}", bundle.name)
                or entry != bundle / "src/tg2cloud/deployment/runtime.py" or text != launcher(bundle)):
            raise ValueError("tg2cloud 命令的运行路径不符合受管布局")
        verify(bundle)


def install(*, source: Path | None = None, root: Path = ROOT, command: Path = COMMAND) -> None:
    from tg2cloud.version import VERSION

    source = source or Path(__file__).resolve().parents[3]
    content = files(source)
    origin = {"kind": "local-source"}
    if (source / ".bootstrap-release.json").is_file():
        from tg2cloud.deployment.configuration import regular_private
        raw = json.loads(regular_private(source / ".bootstrap-release.json"))
        if not re.fullmatch(r"[0-9a-f]{40}", raw.get("installer_commit", "")):
            raise ValueError("安装辅助代码来源缺少固定提交")
        origin = {"kind": "pinned-helper", "commit": raw["installer_commit"]}
    elif (source / "installation.json").is_file():
        origin = verify(source)["origin"]
    metadata = {"schema": 1, "owner": "tg2cloud.cli", "version": VERSION, "origin": origin,
                "files": {name: hashlib.sha256(body).hexdigest() for name, body in content.items()}}
    manifest = (json.dumps(metadata, sort_keys=True, ensure_ascii=True) + "\n").encode()
    key = hashlib.sha256(manifest).hexdigest()
    check_destination(root=root, command=command)
    root.mkdir(mode=0o700, exist_ok=True)
    with publication_lock(root):
        target_root = root / "runtime"
        target_root.mkdir(mode=0o700, exist_ok=True)
        # A power loss before the command switch can leave a complete, unused
        # immutable bundle. Reuse only after full validation.
        check_destination(root=root, command=command)
        bundle = target_root / key
        if not bundle.exists():
            with tempfile.TemporaryDirectory(prefix=".candidate-", dir=root) as private:
                candidate = Path(private) / "bundle"
                candidate.mkdir(mode=0o700)
                for name, body in {**content, "installation.json": manifest}.items():
                    path = candidate / name
                    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    with path.open("xb") as writer:
                        path.chmod(0o600)
                        writer.write(body)
                        writer.flush()
                        os.fsync(writer.fileno())
                verify(candidate)
                candidate.rename(bundle)
        if verify(bundle) != metadata:
            raise ValueError("本地维护候选清单不一致")
        command.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".tg2cloud-", dir=command.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as writer:
                os.fchmod(writer.fileno(), 0o700) if hasattr(os, "fchmod") else temporary.chmod(0o700)
                writer.write(launcher(bundle).encode())
                writer.flush()
                os.fsync(writer.fileno())
            temporary.replace(command)
        finally:
            temporary.unlink(missing_ok=True)


def remove(*, root: Path = ROOT, command: Path = COMMAND) -> bool:
    """Remove only completely verified host code; caller holds lifecycle/dependency locks."""
    if not any(path.exists() or path.is_symlink() for path in (root, command)):
        return False
    with publication_lock(root):
        check_destination(root=root, command=command)
        if not root.is_dir():
            raise ValueError("命令缺少受管代码目录，不猜测归属删除")
        for bundle in (root / "runtime").iterdir():
            if not bundle.is_dir() or not re.fullmatch(r"[0-9a-f]{64}", bundle.name):
                raise ValueError("本地管理目录有未知资源，停止清理")
            verify(bundle)
        old_lock = root / "install.lock"
        if old_lock.exists() or old_lock.is_symlink():
            safe_path(old_lock, private=True)
            if not old_lock.is_file() or old_lock.stat().st_size:
                raise ValueError("旧管理锁文件身份不明，停止清理")
        paths = list(root.rglob("*"))
        for path in paths:
            safe_path(path)
            if not path.is_file() and not path.is_dir():
                raise ValueError("本地管理目录含特殊文件，停止清理")
        # All targets are enumerated, canonical, private and hash-verified.
        # Do not recursively delete an inferred path or any parent of this root.
        if command.exists():
            command.unlink()
        for path in paths:
            if path.is_file():
                path.unlink()
        for path in sorted((p for p in paths if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            path.rmdir()
        root.rmdir()
        return True


def run() -> int:
    """Validate the private bundle before importing the command dispatcher."""
    try:
        source = Path(__file__).resolve().parents[3]
        verify(source)
    except (ValueError, OSError):
        print("本地管理源码完整性/归属检查失败；未启动菜单，请核对后重新安装可信向导。", file=sys.stderr)
        return 1
    runpy.run_path(str(source / "scripts/run_source.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
