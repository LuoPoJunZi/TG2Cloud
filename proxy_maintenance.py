"""Private VPS-local proxy backups and isolated recovery drills (stdlib only).

Archives contain ACME account data/private keys. Never download them to the public
repository. This tool deliberately has no operation that restores over a live VPS.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import signal
import stat
import tarfile
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import BinaryIO

PROXY_ROOT = Path("/opt/tg2cloud-proxy")
BACKUP_ROOT = Path("/opt/tg2cloud-proxy-backups")
SELECTION = ("state/domains.json", "docker-compose.yml", "nginx", "certbot/letsencrypt", "certbot/status")
ARCHIVE_NAME = re.compile(r"proxy-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.tar\.gz")
MAX_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 20000


def stream_digest(handle: BinaryIO) -> str:
    """Bounded-memory SHA256 for host Python 3.10 as well as newer runtimes."""
    checksum = hashlib.sha256()
    while chunk := handle.read(1024 * 1024):
        checksum.update(chunk)
    return checksum.hexdigest()


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return stream_digest(handle)


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("refuse symlink directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt" and path.stat().st_uid != os.geteuid():
        raise ValueError("directory has a different owner")
    path.chmod(0o700)


def safe_link(name: str, target: str) -> bool:
    if not target or target.startswith("/") or "\\" in target or ":" in target:
        return False
    parts = list(PurePosixPath(name).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == "..":
            if len(parts) <= 1:
                return False
            parts.pop()
        elif part != ".":
            parts.append(part)
    return bool(parts) and parts[0] == "proxy"


def snapshot(root: Path) -> dict[str, dict]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid proxy root")
    records: dict[str, dict] = {}
    total = 0
    for relative in SELECTION:
        start = root / relative
        if not start.exists() and not start.is_symlink():
            if relative == "certbot/status":  # Existing installations have no renewal history yet.
                continue
            raise ValueError("required proxy resource missing")
        for path in (start, *sorted(start.rglob("*"))):
            for parent in path.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ValueError("source traverses symlink")
            name = "proxy/" + path.relative_to(root).as_posix()
            info = path.lstat()
            record = {"mode": stat.S_IMODE(info.st_mode)}
            if path.is_symlink():
                target = os.readlink(path)
                if not safe_link(name, target):
                    raise ValueError("unsafe certificate symlink")
                record.update(kind="symlink", target=target)
            elif path.is_file():
                total += info.st_size
                if total > MAX_BYTES:
                    raise ValueError("backup too large")
                record.update(kind="file", size=info.st_size, sha256=digest(path))
            elif path.is_dir():
                record.update(kind="directory")
            else:
                raise ValueError("unsupported proxy file")
            records[name] = record
            if len(records) > MAX_ENTRIES:
                raise ValueError("too many backup entries")
    return records


def verify_backup(archive: Path) -> dict[str, dict]:
    if archive.is_symlink() or not ARCHIVE_NAME.fullmatch(archive.name):
        raise ValueError("invalid archive")
    checksum = archive.with_name(archive.name + ".sha256")
    if checksum.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}\n?", checksum.read_text(encoding="ascii")):
        raise ValueError("invalid checksum")
    if digest(archive) != checksum.read_text(encoding="ascii").strip():
        raise ValueError("archive checksum mismatch")
    records: dict[str, dict] = {}
    manifest = None
    total = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = member.name
            parts = PurePosixPath(name).parts
            if (not parts or parts[0] != "proxy" or ".." in parts or "\\" in name
                    or ":" in name or str(PurePosixPath(name)) != name
                    or name.startswith("/") or name in records or len(records) >= MAX_ENTRIES):
                raise ValueError("unsafe or duplicate archive entry")
            record = {"mode": member.mode}
            if member.isfile():
                total += member.size
                if total > MAX_BYTES:
                    raise ValueError("archive too large")
                handle = tar.extractfile(member)
                if handle is None:
                    raise ValueError("missing archive contents")
                with handle:
                    if name == "proxy/manifest.json":
                        if manifest is not None or member.size > 8 * 1024 * 1024:
                            raise ValueError("invalid manifest")
                        manifest = json.load(handle)
                        continue
                    content_hash = stream_digest(handle)
                record.update(kind="file", size=member.size, sha256=content_hash)
            elif member.isdir():
                record.update(kind="directory")
            elif member.issym() and safe_link(name, member.linkname):
                record.update(kind="symlink", target=member.linkname)
            else:
                raise ValueError("unsupported archive entry")
            records[name] = record
    if not isinstance(manifest, dict) or manifest.get("version") != 1 or manifest.get("files") != records:
        raise ValueError("manifest mismatch")
    if any("/".join(PurePosixPath(name).parts[:i]) in records
           and records["/".join(PurePosixPath(name).parts[:i])]["kind"] == "symlink"
           for name in records for i in range(1, len(PurePosixPath(name).parts))):
        raise ValueError("archive entry traverses symlink")
    required = ("proxy/state/domains.json", "proxy/docker-compose.yml", "proxy/nginx/nginx.conf")
    if any(records.get(name, {}).get("kind") != "file" for name in required):
        raise ValueError("required resources missing")
    return records


def create_backup(root: Path, backup_root: Path) -> Path:
    private_directory(backup_root)
    before = snapshot(root)
    name = f"proxy-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex}.tar.gz"
    archive = backup_root / name
    checksum = archive.with_name(name + ".sha256")
    try:
        # Exclusive creation, private permissions from the first byte, no published partial file.
        fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle, tarfile.open(fileobj=handle, mode="w:gz", dereference=False) as tar:
            for entry in sorted(before):
                tar.add(root / entry.removeprefix("proxy/"), arcname=entry, recursive=False)
            content = json.dumps({"version": 1, "files": before}, sort_keys=True).encode()
            info = tarfile.TarInfo("proxy/manifest.json")
            info.size, info.mode = len(content), 0o600
            tar.addfile(info, io.BytesIO(content))
        if snapshot(root) != before:
            raise ValueError("source changed during backup; retry after renewal completes")
        fd = os.open(checksum, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(digest(archive) + "\n")
        verify_backup(archive)
        return archive
    except Exception:
        archive.unlink(missing_ok=True)
        checksum.unlink(missing_ok=True)
        raise


def recovery_drill(archive: Path, backup_root: Path) -> int:
    """Extract only into a new private directory; never launch or replace services."""
    records = verify_backup(archive)
    private_directory(backup_root)
    destination = Path(tempfile.mkdtemp(prefix="recovery-drill-", dir=backup_root))
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for name, record in records.items():
                target = destination.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if record["kind"] == "directory":
                    target.mkdir(mode=0o700, exist_ok=True)
                elif record["kind"] == "file":
                    source = tar.extractfile(name)
                    if source is None:
                        raise ValueError("missing entry")
                    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with source, os.fdopen(fd, "wb") as handle:
                        shutil.copyfileobj(source, handle)
                    if digest(target) != record["sha256"]:
                        raise ValueError("recovery checksum mismatch")
            for name, record in records.items():
                if record["kind"] == "symlink":
                    destination.joinpath(*PurePosixPath(name).parts).symlink_to(record["target"])
        state = json.loads((destination / "proxy/state/domains.json").read_text(encoding="utf-8"))
        if state.get("version") != 1 or not isinstance(state.get("domains"), dict):
            raise ValueError("unrecognized recovered state")
        return len(records)
    finally:
        # Exact newly-created child, never a caller supplied recursive target.
        if destination.parent.resolve() != backup_root.resolve() or destination.is_symlink():
            raise ValueError("unexpected recovery directory")
        shutil.rmtree(destination)


def selected_archive(backup_root: Path, name: str = "") -> Path:
    if backup_root.is_symlink():
        raise ValueError("unsafe backup root")
    if name:
        if not ARCHIVE_NAME.fullmatch(name):
            raise ValueError("invalid archive name")
        archive = backup_root / name
        if archive.is_symlink() or not archive.is_file():
            raise ValueError("archive unavailable")
        return archive
    candidates = sorted(p for p in backup_root.iterdir() if ARCHIVE_NAME.fullmatch(p.name) and not p.is_symlink() and p.is_file())
    if not candidates:
        raise ValueError("no backup")
    return candidates[-1]


def backup_inventory(backup_root: Path) -> list[dict]:
    if backup_root.is_symlink():
        raise ValueError("unsafe backup root")
    if not backup_root.exists():
        return []
    archives = sorted((p for p in backup_root.iterdir() if ARCHIVE_NAME.fullmatch(p.name) and not p.is_symlink() and p.is_file()), reverse=True)
    if len(archives) > 500:
        raise ValueError("too many archives")
    items = []
    for archive in archives:
        size = archive.stat().st_size
        valid = False
        try:
            if size > MAX_BYTES * 2:
                raise ValueError("archive too large")
            verify_backup(archive)
            valid = True
        except (ValueError, OSError, tarfile.TarError, EOFError):
            pass  # Inventory displays failure without exposing private exception contents.
        items.append({"name": archive.name, "created_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.strptime(archive.name[6:22], "%Y%m%dT%H%M%SZ")), "size_bytes": size, "integrity": "OK" if valid else "FAILED"})
    return items


def prune_plan(backup_root: Path, keep: int) -> dict:
    if type(keep) is not int or not 1 <= keep <= 50:
        raise ValueError("keep must be between 1 and 50")
    items = backup_inventory(backup_root)
    if any(item["integrity"] != "OK" for item in items):
        raise ValueError("verify failed archive before pruning")
    identity = [(item, digest(backup_root / item["name"])) for item in items]
    plan_id = hashlib.sha256(json.dumps({"keep": keep, "archives": identity}, sort_keys=True).encode()).hexdigest()
    return {"keep": keep, "retain": [item["name"] for item in items[:keep]], "remove": items[keep:], "plan_id": plan_id}


def prune_backups(backup_root: Path, keep: int, expected_plan: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_plan):
        raise ValueError("missing confirmed plan")
    plan = prune_plan(backup_root, keep)
    if plan["plan_id"] != expected_plan:
        raise ValueError("backup inventory changed; preview again")
    # Only validated, checksum-verified leaf files from the confirmed plan.
    # At least one archive remains; unrelated files/symlinks are never targets.
    for item in plan["remove"]:
        archive = selected_archive(backup_root, item["name"])
        checksum = archive.with_name(archive.name + ".sha256")
        archive.unlink()
        checksum.unlink()
    return plan


def interrupt_maintenance(_signal, _frame) -> None:
    # Raise through create_backup/recovery_drill so their exact partial/temp
    # cleanup runs when the remote timeout sends TERM or SSH sends HUP.
    raise InterruptedError("maintenance interrupted")


def main() -> int:
    parser = argparse.ArgumentParser(description="VPS 本机私密代理备份；不提供在线覆盖恢复")
    parser.add_argument("action", choices=("backup", "check", "drill", "list", "prune-preview", "prune"))
    parser.add_argument("--archive", default="")
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--plan", default="")
    args = parser.parse_args()
    os.umask(0o077)
    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), interrupt_maintenance)
    try:
        if args.action == "list":
            print("TG2CLOUD_PROXY_BACKUP_ITEMS=" + json.dumps(backup_inventory(BACKUP_ROOT)))
        elif args.action in {"prune-preview", "prune"}:
            plan = prune_plan(BACKUP_ROOT, args.keep) if args.action == "prune-preview" else prune_backups(BACKUP_ROOT, args.keep, args.plan)
            print("TG2CLOUD_PROXY_BACKUP_PLAN=" + json.dumps(plan))
        else:
            archive = create_backup(PROXY_ROOT, BACKUP_ROOT) if args.action == "backup" else selected_archive(BACKUP_ROOT, args.archive)
            records = verify_backup(archive)
            if args.action == "drill":
                recovery_drill(archive, BACKUP_ROOT)
            print(f"TG2CLOUD_PROXY_BACKUP_PATH={archive}")
            print(f"TG2CLOUD_PROXY_BACKUP_ENTRIES={len(records)}")
        print(f"TG2CLOUD_PROXY_BACKUP={args.action.upper().replace('-', '_')}_OK")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI privacy boundary: no exception contents/keys
        print(f"TG2CLOUD_PROXY_BACKUP=FAILED:{type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
