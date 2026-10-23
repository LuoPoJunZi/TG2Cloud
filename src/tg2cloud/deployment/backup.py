"""Confirmed instance snapshots; no production restore, cloud copy or global stop.

The caller holds the selected Edition lock and revalidates instance ownership.
Only previously running, exact container IDs are restarted. Interrupted journals
remain private for manual review; they are never replayed automatically.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import closing
from pathlib import Path

from tg2cloud.deployment import runtime
from tg2cloud.persistence import bundle
from tg2cloud.persistence.backup import backup_database

ACTIVE = ("reserved", "downloading", "streaming", "uploading", "verifying", "finalizing", "cleanup_pending")


def mountpoints() -> set[Path]:
    if os.name != "posix":
        return set()
    with Path("/proc/self/mountinfo").open("r", encoding="utf-8", errors="surrogateescape") as source:
        body = source.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise ValueError("挂载信息过大，无法确认备份扫描边界")
    result = set()
    for line in body.splitlines():
        fields = line.split()
        if len(fields) < 6:
            raise ValueError("挂载信息不完整")
        result.add(Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields[4])))
    return result


def active_tasks(directory: Path) -> int:
    database = directory / "data/tg115.db"
    if database.is_symlink() or database.resolve() != database or not database.is_file():
        raise ValueError("业务数据库缺失或经过链接，无法确认备份条件")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
        return conn.execute("SELECT count(*) FROM tasks WHERE state IN (?, ?, ?, ?, ?, ?, ?)", ACTIVE).fetchone()[0]


def selected_files(instance) -> dict[str, Path]:
    root = instance.directory
    if root.resolve() != root:
        raise ValueError("实例路径经过链接")
    gateway = "openlist/data" if instance.product.is_openlist else "clouddrive/config"
    names = [*bundle.required(instance.product.key), "config", gateway]
    if (root / "tg2cloud-release.json").exists():
        names.append("tg2cloud-release.json")
    files = {}
    total = 0
    checked = 0
    mounts = mountpoints()

    def visit(path, device, top):
        nonlocal total, checked
        checked += 1
        if checked > bundle.MAX_FILES or len(path.relative_to(root).parts) > 64:
            raise ValueError("实例备份扫描数量或深度超过安全上限")
        relative = path.relative_to(root).as_posix()
        if relative.startswith(("openlist/data/log/", "openlist/data/temp/")) or relative in {"openlist/data/log", "openlist/data/temp"}:
            return
        if path.is_symlink() or path.resolve() != path or path.stat().st_dev != device or path in mounts and path != top:
            raise ValueError("备份范围包含链接或嵌套挂载；停止，不扩展扫描范围")
        if path.is_dir():
            with os.scandir(path) as entries:
                for item in entries:
                    visit(Path(item.path), device, top)
        elif path.is_file() and path.stat().st_nlink == 1:
            if relative.endswith(("-wal", "-shm", "-journal")):
                return  # Main SQLite files are copied through the backup API.
            total += path.stat().st_size
            if total > bundle.MAX_BYTES or len(files) >= bundle.MAX_FILES:
                raise ValueError("实例备份超过现有容量／文件数量上限")
            files[relative] = path
        else:
            raise ValueError("备份范围包含特殊文件或硬链接")

    for name in names:
        path = root / name
        if not path.exists():
            raise ValueError("实例备份覆盖不完整，请先核对配置、Session 和网关状态")
        visit(path, path.stat().st_dev, path)
    return files


def container(session, name: str) -> dict:
    template = '{"id":{{json .Id}},"running":{{json .State.Running}}}'
    code, output = session.run("docker inspect --format " + shlex.quote(template) + " " + shlex.quote(name), timeout=15)
    try:
        result = json.loads(output)
        if code or not re.fullmatch(r"[a-f0-9]{64}", result["id"]) or type(result["running"]) is not bool:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("无法核对备份容器身份／运行状态") from None
    return result


def snapshot_bytes(files: dict[str, Path]) -> int:
    total = sum(path.stat().st_size for path in files.values())
    for source in files.values():
        for suffix in ("-wal", "-journal"):
            sidecar = source.with_name(source.name + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                if sidecar.is_symlink() or sidecar.resolve() != sidecar or not sidecar.is_file():
                    raise ValueError("数据库日志路径不安全")
                total += sidecar.stat().st_size
    if total > bundle.MAX_BYTES:
        raise ValueError("包含数据库日志的备份容量超过安全上限")
    return total


def output_directory(path: Path, instance, *, create=False) -> Path:
    if not path.is_absolute():
        raise ValueError("备份目录必须使用绝对路径")
    runtime.safe_path(path, private=True)
    if path == instance.directory or path.is_relative_to(instance.directory) or instance.directory.is_relative_to(path):
        raise ValueError("备份位置不能位于实例或其父目录内")
    # Do not write into another Edition or shared infrastructure.
    if (path.parts[:2] == ("/", "opt") and len(path.parts) > 2
            and path.parts[2].startswith("tg2cloud-") and path.parts[2] != "tg2cloud-snapshots"):
        raise ValueError("备份位置不能复用其他 TG2Cloud 运行目录")
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        runtime.safe_path(path, private=True)
    return path


def create(instance, session, destination: Path) -> Path:
    """Maintenance-window backup, called only after explicit operator confirmation."""
    destination = output_directory(destination, instance)
    if instance.config.get("DATA_DIR", "/data") != "/data":
        raise ValueError("自定义数据路径暂不支持自动实例备份")
    files = selected_files(instance)
    if active_tasks(instance.directory):
        raise ValueError("存在活动传输，先等待完成；暂停调度不会停止当前任务")
    states = {name: container(session, name) for name in (instance.product.bot_container, instance.product.storage_container)}
    if states[instance.product.bot_container]["running"] and not states[instance.product.storage_container]["running"]:
        raise ValueError("Bot 与网关运行状态不一致，先人工核对")
    destination = output_directory(destination, instance, create=True)
    for pending in destination.glob("operation-*.jsonl"):
        runtime.safe_path(pending)
        if pending.stat().st_size > 1024 * 1024:
            raise ValueError("备份操作记录过大，先人工核对")
        lines = pending.read_text(encoding="utf-8").splitlines()
        last = json.loads(lines[-1]) if lines else {}
        if (last.get("schema") != 1 or last.get("owner") != "tg2cloud.instance-snapshot"
                or last.get("state") not in {"completed", "failed-services-restored"}):
            raise ValueError("存在未完成的实例备份记录，先核对容器与备份，不自动重放")
    total = snapshot_bytes(files)
    if shutil.disk_usage(destination).free < total * 3 + bundle.MIN_FREE:
        raise ValueError("实例备份临时副本／归档／校验空间不足")
    key = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    archive = destination / ("instance-" + instance.product.key + "-" + instance.version + "-" + key + ".tar.gz")
    journal = destination / ("operation-" + key + ".jsonl")
    stopped = []
    complete = False
    with journal.open("x", encoding="utf-8") as record:
        journal.chmod(0o600)

        def event(state):
            record.write(json.dumps({"schema": 1, "owner": "tg2cloud.instance-snapshot", "edition": instance.product.key,
                                     "state": state, "containers": states, "archive": archive.name}) + "\n")
            record.flush()
            os.fsync(record.fileno())

        event("prepared")
        try:
            for name, previous in states.items():
                if container(session, name) != previous:
                    raise ValueError("备份前容器已变化，请重新预检")
                if previous["running"]:
                    stopped.append(name)
                    event("stopping")
                    code, _ = session.run("docker stop -t 45 " + shlex.quote(previous["id"]), timeout=90)
                    if code or container(session, name) != {**previous, "running": False}:
                        raise RuntimeError("无法确认容器已停止，未生成备份")
            event("stopped")
            if active_tasks(instance.directory):
                raise ValueError("停止前出现活动传输，备份取消；保留数据并恢复原服务")
            files = selected_files(instance)
            if shutil.disk_usage(destination).free < snapshot_bytes(files) * 3 + bundle.MIN_FREE:
                raise ValueError("停止服务后容量发生变化，备份取消并恢复原服务")
            with tempfile.TemporaryDirectory(prefix="snapshot-", dir=destination) as temporary:
                snapshot = Path(temporary).resolve()
                snapshot.chmod(0o700)
                for name, source in files.items():
                    if source.resolve() != source or source.is_symlink() or not source.is_file():
                        raise ValueError("复制前备份对象发生变化")
                    target = snapshot / name
                    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                    with source.open("rb") as reader:
                        sqlite = reader.read(16) == b"SQLite format 3\x00"
                    if sqlite:
                        backup_database(source, target)
                    else:
                        if name.endswith((".db", ".session")):
                            raise ValueError("数据库／Session 格式不正确，未生成备份")
                        with source.open("rb") as reader, target.open("xb") as writer:
                            target.chmod(0o600)
                            shutil.copyfileobj(reader, writer, 1024 * 1024)
                for directory in ("config", "openlist/data" if instance.product.is_openlist else "clouddrive/config"):
                    (snapshot / directory).mkdir(parents=True, mode=0o700, exist_ok=True)
                event("copied")
                bundle.pack(snapshot, archive, instance.product.key, instance.version)
                event("packed")
            complete = True
        finally:
            failures = []
            # Gateway before Bot; never start something that was initially stopped.
            for name in reversed(stopped):
                previous = states[name]
                try:
                    current = container(session, name)
                    if current["id"] != previous["id"]:
                        raise ValueError("container replaced")
                    if not current["running"]:
                        code, _ = session.run("docker start " + shlex.quote(previous["id"]), timeout=90)
                        if code or container(session, name) != previous:
                            raise RuntimeError("restart failed")
                except Exception:  # noqa: BLE001 - record any ordinary failure during service restoration
                    failures.append(name)
                    if name == instance.product.storage_container:
                        break  # Do not start Bot against a failed gateway.
            if failures:
                event("needs-service-review")
                raise RuntimeError("实例备份结束但原服务恢复未确认；保留归档和操作记录，请人工检查") from None
            event("completed" if complete else "failed-services-restored")
    return archive
