"""Open the independent, verified WebDAV manager from the selected main instance.

The main manager can be a partial bootstrap bundle. Never configure a route
using that bundle and only discover missing add-on resources after activation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from tg2cloud.addons.external_webdav import config, releases

COMMAND = Path("/usr/local/bin/tg2cloud-webdav")
HEADER = '#!/bin/sh\n# TG2Cloud external_webdav managed\n'


def _check_ownership(info, *, private: bool = False, sticky_parent: bool = False) -> None:
    if os.name == "posix":
        forbidden = 0o077 if private else 0o022
        if info.st_uid != 0 or (info.st_mode & forbidden and not sticky_parent):
            raise ValueError("外部 WebDAV 维护代码必须归 root 所有，且权限不可由其他用户修改。")


def _safe_path(path: Path, *, private: bool = False) -> None:
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("外部 WebDAV 维护路径经过链接或不是绝对路径。")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("外部 WebDAV 维护路径经过链接。")
        info = item.stat()
        _check_ownership(info, private=private and item == path,
                         sticky_parent=item == Path("/tmp") and bool(info.st_mode & stat.S_ISVTX))  # nosec B108


def installed(*, launcher: Path = COMMAND, root: Path = config.ROOT) -> Path | None:
    """Verify the historical add-on layout without requiring new marker fields.

    Existing releases record the digest of sorted relative host paths and file
    contents as both the directory name and installation.json.code_sha256.
    This is integrity/ownership verification, not a digital signature.
    """
    if not launcher.exists() and not launcher.is_symlink():
        return None
    _safe_path(launcher, private=True)
    if not launcher.is_file() or launcher.stat().st_size > 4096:
        raise ValueError("现有 tg2cloud-webdav 命令不属于受支持的受管入口。")
    text = launcher.read_text(encoding="utf-8")
    match = re.fullmatch(re.escape(HEADER) + r'exec python3 -B (.+) webdav "\$@"\n', text)
    arguments = shlex.split(match[1]) if match else []
    if len(arguments) != 1:
        raise ValueError("现有 tg2cloud-webdav 命令不属于受支持的受管入口。")
    entry = Path(arguments[0])
    bundle = entry.parent.parent
    if (bundle.parent != root / "runtime" or not re.fullmatch(r"[0-9a-f]{64}", bundle.name)
            or entry != bundle / "scripts/run_source.py"
            or text != HEADER + 'exec python3 -B ' + shlex.quote(str(entry)) + ' webdav "$@"\n'):
        raise ValueError("现有 tg2cloud-webdav 命令的代码位置不符合受管布局。")
    _safe_path(bundle, private=True)
    marker = bundle / "installation.json"
    _safe_path(marker, private=True)
    if not marker.is_file() or marker.stat().st_size > 128 * 1024:
        raise ValueError("外部 WebDAV 离线运行清单缺失或过大。")
    identity = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(identity, dict) or identity.get("code_sha256") != bundle.name:
        raise ValueError("外部 WebDAV 离线代码摘要与运行清单不一致。")
    releases.supported(bundle)
    paths = releases.host_files(bundle)
    if len(paths) > 2048:
        raise ValueError("外部 WebDAV 离线源码文件数量超过安全上限。")
    checksum, total = hashlib.sha256(), 0
    expected = {*paths, "installation.json"}
    directories = {parent.as_posix() for name in expected for parent in Path(name).parents if parent != Path(".")}
    for relative in paths:
        path = bundle / relative
        _safe_path(path, private=True)
        size = path.stat().st_size
        total += size
        if size > 2 * 1024 * 1024 or total > 32 * 1024 * 1024:
            raise ValueError("外部 WebDAV 离线源码超过安全大小上限。")
        checksum.update(relative.encode() + b"\0" + path.read_bytes())
    for path in bundle.rglob("*"):
        _safe_path(path)
        relative = path.relative_to(bundle).as_posix()
        if (path.is_file() and relative not in expected) or (path.is_dir() and relative not in directories):
            raise ValueError("外部 WebDAV 离线目录含未知资源；停止，不执行。")
        if not path.is_file() and not path.is_dir():
            raise ValueError("外部 WebDAV 离线目录含特殊文件。")
    if checksum.hexdigest() != bundle.name:
        raise ValueError("外部 WebDAV 离线源码摘要不匹配；停止，不执行。")
    return bundle


def _stop(process) -> None:
    """The interactive child shares the terminal group; never kill that group."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=150)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def _run(source: Path, instance, log) -> None:
    environment = os.environ.copy()
    environment.pop("TG2CLOUD_SOURCE_ROOT", None)
    environment["TG2CLOUD_MANAGER_MENU"] = "1"
    arguments = [sys.executable, "-B", str(source / "scripts/run_source.py"), "webdav",
                 "--edition", instance.product.key, "--install-dir", str(instance.directory)]
    process = subprocess.Popen(arguments, env=environment)  # nosec B603
    try:
        result = process.wait()
    except BaseException:
        _stop(process)
        raise
    if result:
        log("外部 WebDAV 管理已结束；请核对上方结果，未假定操作成功。")


def open_menu(instance, ui, log) -> None:
    """Use the independent lifecycle; returning never resumes obsolete code."""
    from tg2cloud.deployment.configuration import checked_directory
    from tg2cloud.deployment.profiles import PRODUCTS

    if instance.product.key not in PRODUCTS or instance.present is not True:
        raise ValueError("请先安装并核验当前 Edition，再打开外部 WebDAV 管理。")
    checked_directory(str(instance.directory))
    if os.name == "posix" and os.geteuid() != 0:
        raise ValueError("外部 WebDAV 管理需要 Linux root 权限。")
    record_path = config.ROOT / instance.product.key / "config.json"
    if record_path.exists() or record_path.is_symlink():
        record = config.read_record(record_path)
        if record is None or record["edition"] != instance.product.key or record["instance_dir"] != str(instance.directory):
            raise ValueError("外部 WebDAV 记录与当前实例目录不一致；请先核对附加功能配置，不自动切换实例。")
    previous = installed()
    from tg2cloud.deployment.releases import source_version, version_tuple
    from tg2cloud.version import VERSION
    outdated = previous is not None and version_tuple(source_version(previous)) < version_tuple(VERSION)
    legacy = previous is not None and releases.contract(previous) == releases.LEGACY_CONTRACT
    if previous is not None and not legacy and not outdated:
        _run(previous, instance, log)
        return
    if legacy or outdated:
        log("当前外部 WebDAV 维护工具较旧；可先更新代码，再继续账号配置。更新不启用访问，不要求后台账号认证。")
        if not ui.confirm("是否下载正式稳定版并更新维护代码？拒绝则进入旧版离线菜单"):
            _run(previous, instance, log)
            return
    else:
        log("首次打开需要下载并校验正式稳定版的外部 WebDAV 管理组件；不会自动启用文件访问。")
        if not ui.confirm("是否下载并进入外部 WebDAV 管理？"):
            return
    with tempfile.TemporaryDirectory(prefix="tg2cloud-webdav-menu-") as temporary:
        directory = Path(temporary)
        directory.chmod(0o700)
        source, identity = releases.download(directory)
        if previous is not None and version_tuple(source_version(source)) < version_tuple(source_version(previous)):
            raise ValueError("拒绝将外部 WebDAV 维护工具降级。")
        if releases.contract(source) != releases.CONTRACT:
            raise ValueError("当前正式稳定版尚未包含统一入口布局；请等待新版发布，已有工具仍可离线使用。")
        if legacy or outdated:
            from tg2cloud.addons.external_webdav.service import Service
            from tg2cloud.deployment.host import LocalSession

            service = Service(instance.product, LocalSession(log), log, ui)
            with service.locked():
                if installed() != previous:
                    raise ValueError("确认期间外部 WebDAV 管理代码已变化；停止，请刷新。")
                current = service.record()
                if current is not None and current["instance_dir"] != str(instance.directory):
                    raise ValueError("外部 WebDAV 记录与当前实例目录不一致；停止迁移。")
                service.preflight(str(instance.directory), require_running=False)
                service.install_runtime(source, identity)
            source = installed()
            if source is None:
                raise ValueError("迁移后的外部 WebDAV 离线命令不可验证；未确认迁移成功。")
        else:
            config.atomic(source / ".external-webdav-source.json", (json.dumps(identity) + "\n").encode())
        _run(source, instance, log)
