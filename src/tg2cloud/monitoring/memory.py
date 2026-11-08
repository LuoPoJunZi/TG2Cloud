"""Bounded cgroup memory observations shared by sampling and diagnostics."""
from __future__ import annotations

from pathlib import Path


def _text(path: Path) -> str:
    with path.open("r", encoding="ascii") as handle:
        value = handle.read(32769)
    if len(value) > 32768:
        raise ValueError("oversized cgroup observation")
    return value.strip()


def available(host_available: int, host_total: int, *, root: Path = Path("/sys/fs/cgroup")) -> tuple[int, int | None]:
    """Limit host availability by the container's own cgroup, without writes.

    Inactive file cache is reclaimable; current RSS alone is not a substitute
    for memory.current. Unlimited/unsupported controllers retain host sampling.
    """
    for directory, maximum, current, reclaimable in (
        (root, "memory.max", "memory.current", "inactive_file"),
        (root / "memory", "memory.limit_in_bytes", "memory.usage_in_bytes", "total_inactive_file"),
    ):
        try:
            raw = _text(directory / maximum)
            if raw == "max":
                return max(0, host_available), None
            limit = int(raw)
            usage = int(_text(directory / current))
            if limit <= 0 or usage < 0 or limit >= host_total:
                continue
            cache = 0
            try:
                stats = dict(line.split() for line in _text(directory / "memory.stat").splitlines())
                cache = max(0, min(usage, int(stats.get(reclaimable, "0"))))
            except (OSError, ValueError):
                pass
            return min(max(0, host_available), max(0, limit - usage + cache)), limit
        except (OSError, ValueError):
            continue
    return max(0, host_available), None
