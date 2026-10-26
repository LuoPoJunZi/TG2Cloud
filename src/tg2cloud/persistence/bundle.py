"""Offline snapshot bundles and isolated restore preflight; never restore live data.

Input must be an operator-prepared, quiescent copy. Downloads and shared HTTPS
are explicitly outside this bundle. Existing online proxy backup remains separate.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path, PurePosixPath

MAX_BYTES = 2 * 1024**3
MAX_FILES = 20000
MIN_FREE = 256 * 1024**2


def checksum(handle):
    value = hashlib.sha256()
    while chunk := handle.read(1024 * 1024):
        value.update(chunk)
    return value.hexdigest()


def check_database(path: Path) -> None:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("database integrity failed")


def validate_name(name: str) -> None:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
            or str(path) != name or any(ord(c) < 32 for c in name)):
        raise ValueError("unsafe archive path")


def version(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("invalid version")
    return tuple(map(int, value.split(".")))


def required(edition: str) -> tuple[str, ...]:
    if edition not in {"clouddrive2", "openlist"}:
        raise ValueError("invalid edition")
    return (".env", "docker-compose.yml", "data/tg115.db", "data/bot.session")


def pack(snapshot: Path, archive: Path, edition: str, source_version: str) -> None:
    """Package a stopped-instance snapshot; never follow links or overwrite archives."""
    required(edition)
    version(source_version)
    snapshot = snapshot.absolute()
    archive = archive.absolute()
    if snapshot.is_symlink() or not snapshot.is_dir() or archive.is_relative_to(snapshot):
        raise ValueError("invalid offline snapshot/destination")
    selected = [*required(edition), "config", "clouddrive/config" if edition == "clouddrive2" else "openlist/data"]
    if (snapshot / "data/listener/personal.session").is_file():
        selected.append("data/listener/personal.session")
    if (snapshot / "tg2cloud-release.json").is_file():
        selected.append("tg2cloud-release.json")
    records = {}
    total = 0
    for name in selected:
        source = snapshot / name
        if not source.exists() or source.is_symlink():
            raise ValueError("snapshot coverage incomplete")
        paths = [source] if source.is_file() else source.rglob("*")
        for path in paths:
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != snapshot.parent):
                raise ValueError("snapshot links unsupported")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError("special file unsupported")
            relative = path.relative_to(snapshot).as_posix()
            validate_name(relative)
            if relative.startswith(("openlist/data/log/", "openlist/data/temp/")):
                continue
            if relative.endswith(("-wal", "-shm", "-journal")):
                if path.stat().st_size:
                    raise ValueError("database is not a standalone snapshot")
                continue
            total += path.stat().st_size
            if total > MAX_BYTES or len(records) >= MAX_FILES:
                raise ValueError("snapshot resource limit")
            if relative.endswith((".db", ".session")):
                check_database(path)
            with path.open("rb") as handle:
                records[relative] = {"size": path.stat().st_size, "sha256": checksum(handle)}
    # SQLite sidecars for the individually selected DB/session are not in rglob.
    for relative in ("data/tg115.db", "data/bot.session", "data/listener/personal.session"):
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = snapshot / (relative + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                raise ValueError("snapshot contains live SQLite sidecars")
    manifest = {"format": 1, "edition": edition, "version": source_version, "files": records,
                "excluded": ["downloads", "logs", "shared-https"], "source": "operator-offline-copy"}
    if shutil.disk_usage(archive.parent).free < total + MIN_FREE:
        raise ValueError("insufficient backup capacity")
    descriptor = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, tarfile.open(fileobj=output, mode="w:gz") as tar:
            content = json.dumps(manifest, ensure_ascii=False).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(content), 0o600
            tar.addfile(info, io.BytesIO(content))
            for relative, record in records.items():
                path = snapshot / relative
                with path.open("rb") as handle:
                    if checksum(handle) != record["sha256"]:
                        raise ValueError("snapshot changed")
                    handle.seek(0)
                    info = tarfile.TarInfo(relative)
                    info.size, info.mode = record["size"], 0o600
                    tar.addfile(info, handle)
        # Also catch mutations during tar.addfile; validates the actual archive.
        preflight(archive, archive.parent, edition, source_version)
    except BaseException:
        archive.unlink(missing_ok=True)  # Only the exclusive file created above.
        raise


@contextmanager
def verified_snapshot(archive: Path, scratch: Path, edition: str, target_version: str):
    """Expose only a fully verified private copy; remove it even on interruption."""
    required(edition)
    target = version(target_version)
    if archive.is_symlink() or scratch.is_symlink() or not scratch.is_dir():
        raise ValueError("invalid archive/scratch")
    with tarfile.open(archive, "r:gz") as tar:
        first = tar.next()
        if first is None or first.name != "manifest.json" or not first.isfile() or first.size > 8 * 1024**2:
            raise ValueError("missing manifest")
        manifest = json.load(tar.extractfile(first))
        source_version = version(manifest["version"])
        if (manifest.get("format") != 1 or manifest["edition"] != edition
                or source_version > target or source_version[0] != target[0]):
            raise ValueError("edition/version incompatible")
        records = manifest["files"]
        if not isinstance(records, dict) or len(records) > MAX_FILES or not all(k in records for k in required(edition)):
            raise ValueError("incomplete manifest")
        gateway = "clouddrive/config/" if edition == "clouddrive2" else "openlist/data/"
        if not any(k.startswith("config/") for k in records) or not any(k.startswith(gateway) for k in records):
            raise ValueError("configuration/gateway coverage incomplete")
        total = 0
        for name, record in records.items():
            validate_name(name)
            if (name not in {*required(edition), "tg2cloud-release.json", "data/listener/personal.session"}
                    and not name.startswith(("config/", gateway))):
                raise ValueError("entry outside declared snapshot scope")
            if name.endswith(("-wal", "-shm", "-journal")):
                raise ValueError("database is not a standalone snapshot")
            if type(record["size"]) is not int or record["size"] < 0:
                raise ValueError("invalid size")
            total += record["size"]
        if total > MAX_BYTES or shutil.disk_usage(scratch).free < total + MIN_FREE:
            raise ValueError("restore capacity limit")
        with tempfile.TemporaryDirectory(prefix="tg2cloud-restore-check-", dir=scratch) as private:
            root = Path(private)
            root.chmod(0o700)
            seen = set()
            for item in iter(tar.next, None):
                validate_name(item.name)
                if item.name not in records or item.name in seen or not item.isfile():
                    raise ValueError("unexpected/duplicate/link entry")
                record = records[item.name]
                if item.size != record["size"]:
                    raise ValueError("size mismatch")
                path = root / item.name
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with tar.extractfile(item) as source, path.open("xb") as out:
                    path.chmod(0o600)
                    shutil.copyfileobj(source, out, length=1024 * 1024)
                with path.open("rb") as content:
                    if checksum(content) != record["sha256"]:
                        raise ValueError("checksum mismatch")
                if path.suffix in {".db", ".session"}:
                    check_database(path)
                seen.add(item.name)
            if seen != set(records):
                raise ValueError("missing entries")
            # Close the archive before a caller inspects its verified copy. No
            # caller observes partially checked files or controls extraction.
            tar.close()
            yield root, {"files": len(records), "bytes": total, "scope": "offline-structure-and-database-only"}


def preflight(archive: Path, scratch: Path, edition: str, target_version: str) -> dict:
    with verified_snapshot(archive, scratch, edition, target_version) as (_, report):
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="离线备份包与隔离恢复预检；不覆盖运行实例")
    parser.add_argument("action", choices=("pack", "check"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--edition", required=True, choices=("clouddrive2", "openlist"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--offline-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "pack":
            if not args.offline_confirmed or args.snapshot is None:
                raise ValueError("operator must confirm offline snapshot")
            pack(args.snapshot, args.archive, args.edition, args.version)
        else:
            if args.scratch is None:
                raise ValueError("scratch directory required")
            preflight(args.archive, args.scratch, args.edition, args.version)
    except Exception:  # noqa: BLE001 - private CLI boundary must not print backup contents
        print("TG2CLOUD_BACKUP_PREFLIGHT=FAILED；请核对备份范围、版本、完整性及隔离目录空间")
        return 1
    print("TG2CLOUD_BACKUP_PREFLIGHT=OK；仅结构和数据库通过，不代表服务恢复验收")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
