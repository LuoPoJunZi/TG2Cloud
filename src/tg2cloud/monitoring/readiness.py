"""Small non-secret readiness observations; separate from container liveness.

Uses the existing destination probe and its cooldown, never performs another
WebDAV request or writes a test file. No Telegram client or Session is opened.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path

from tg2cloud.version import VERSION

CHECKS = ("heartbeat", "telegram", "destination", "queue", "capacity")
STATES = {"ok", "failed", "unknown", "paused", "cooldown", "partial"}


def publish(service, counts) -> None:
    settings = service.settings
    connected = getattr(service.client, "is_connected", None)
    connected = connected() if callable(connected) else None
    free = min([service.snapshot.disk_free, *(free for _, free in service.snapshot.filesystems)])
    destination = "ok" if service._destination_ready() else "failed"
    if service.destination_scope == "root_fallback" and destination == "ok":
        destination = "partial"
    if service.destination_last_checked <= 0:
        destination = "unknown"
    cooldown = max(0, int(getattr(service, "_destination_next_probe_at", 0) - time.monotonic()))
    if destination == "failed" and cooldown:
        destination = "cooldown"
    checks = {"telegram": "ok" if connected is True else "failed" if connected is False else "unknown",
              "destination": destination, "queue": "paused" if service.db.is_paused() else "ok",
              "capacity": "ok" if free > settings.min_free_disk_bytes
              and service.db.used_local_bytes() < settings.local_budget_bytes else "failed"}
    value = {"schema": 1, "version": VERSION, "edition": settings.storage_backend,
             "sampled_at": time.time(), "ttl": min(300, max(15, settings.control_interval * 3)),
             "checks": checks, "cooldown_seconds": cooldown,
             "queued": int(counts.get("queued", 0)),
             "active": len(service.download_tasks) + len(service.upload_tasks)}
    descriptor, name = tempfile.mkstemp(prefix=".readiness-", dir=settings.data_dir)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
            json.dump(value, writer)
        os.replace(temporary, settings.data_dir / "readiness.json")
    finally:
        temporary.unlink(missing_ok=True)


def read(data_dir: Path, *, now: float, started_at: float = 0) -> dict:
    checks = {key: "unknown" for key in CHECKS}
    checks["heartbeat"] = "ok"
    for name in ("heartbeat", "resource-heartbeat"):
        try:
            modified = (data_dir / name).stat().st_mtime
            if modified < started_at or not 0 <= now - modified < 90:
                checks["heartbeat"] = "failed"
        except OSError:
            checks["heartbeat"] = "failed"
    result = {"schema": 1, "checks": checks, "ready": False, "version": VERSION,
              "queued": 0, "active": 0, "cooldown_seconds": 0}
    try:
        path = data_dir / "readiness.json"
        if path.is_symlink() or path.stat().st_size > 16384:
            return result
        raw = json.loads(path.read_text(encoding="utf-8"))
        sampled, ttl = raw["sampled_at"], raw["ttl"]
        if (raw.get("schema") != 1 or raw.get("version") != VERSION
                or type(sampled) not in {int, float} or not math.isfinite(sampled)
                or type(ttl) not in {int, float} or not 15 <= ttl <= 300
                or sampled < started_at or not 0 <= now - sampled <= ttl
                or set(raw["checks"]) != set(CHECKS) - {"heartbeat"}
                or any(state not in STATES for state in raw["checks"].values())):
            return result
        for key in ("queued", "active", "cooldown_seconds"):
            if type(raw[key]) is not int or not 0 <= raw[key] <= 10**12:
                return result
        if raw.get("edition") not in {"clouddrive2", "openlist"}:
            return result
        checks.update(raw["checks"])
        result.update({key: raw[key] for key in ("edition", "queued", "active", "cooldown_seconds")})
        result["ready"] = all(state == "ok" for state in checks.values())
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return result


def main():
    # Executed INSIDE the selected Bot; the host CLI still needs only stdlib.
    import psutil
    try:
        value = read(Path(os.environ.get("DATA_DIR", "/data")), now=time.time(),
                     started_at=psutil.Process(1).create_time())
    except (OSError, psutil.Error):
        value = {"schema": 1, "checks": {key: "unknown" for key in CHECKS}, "ready": False, "version": VERSION}
    print(json.dumps(value))


if __name__ == "__main__":
    main()
