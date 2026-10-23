from __future__ import annotations

import math
import time

DISPLAY_SAMPLE_TTL = 5


def _record_progress(
    self, task_id: int, stage: str, count: int, speed: float | None = None, *, reset: bool = False,
) -> None:
    if not hasattr(self, "_progress"):
        self._progress = {}
    now = time.monotonic()
    old = self._progress.get(task_id)
    if reset or not old or old["stage"] != stage or count < old["bytes"]:
        old = {"stage": stage, "bytes": 0, "at": now, "started": now}
    measured = (max(0, count - old["bytes"]) / (now - old["at"])) if now > old["at"] else None
    value = speed if speed is not None else measured
    self._progress[task_id] = {
        "stage": stage, "bytes": count, "at": now, "started": old["started"],
        "speed": value if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None,
    }


def _stage_rate(self, stage: str) -> float:
    # Preserve the scheduler's existing numeric API and 20-second observation
    # window. An unavailable display sample must not break resource control.
    return sum(p["speed"] for p in getattr(self, "_progress", {}).values()
               if p["stage"] == stage and 0 <= time.monotonic() - p["at"] <= 20
               and isinstance(p.get("speed"), (int, float)) and math.isfinite(p["speed"]) and p["speed"] >= 0)


def sample_rate(progress: dict | None, *, now: float | None = None) -> float | None:
    if not progress:
        return None
    now = time.monotonic() if now is None else now
    speed = progress.get("speed")
    if (not 0 <= now - progress["at"] <= DISPLAY_SAMPLE_TTL
            or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0):
        return None
    return float(speed)


def dashboard_rates(service, counts: dict, *, sender_id: int | None = None) -> tuple[float | None, float | None]:
    """Task rates, not NIC rates. Incomplete active totals stay unknown, not zero."""
    progress = getattr(service, "_progress", {})
    downloads = getattr(service, "download_tasks", {})
    uploads = getattr(service, "upload_tasks", {})
    active_ids = set(downloads) | set(uploads)
    values: dict[str, list[float | None]] = {"download": [], "upload": [], "stream": []}
    now = time.monotonic()
    for task_id in set(progress) | active_ids:
        task = service.db.get(task_id)
        if sender_id is not None and (not task or task["sender_id"] != sender_id):
            continue
        state = task.get("state") if task else None
        record = progress.get(task_id)
        if state == "streaming":
            stage = "stream"
        elif state in {"downloading", "uploading"}:
            stage = "download" if state == "downloading" else "upload"
        elif state in {"queued", "reserved"} and task_id in downloads:
            stage = "stream" if task.get("transfer_mode") == "stream" else "download"
        elif state in {"downloaded", "waiting_upload"} and task_id in uploads:
            stage = "upload"
        elif task is None and task_id in active_ids:
            stage = record["stage"] if record else "download" if task_id in downloads else "upload"
        else:
            continue  # Verification, cleanup and finished tasks are not byte transfer.
        if stage in values:
            values[stage].append(sample_rate(record, now=now) if record and record["stage"] == stage else None)
    for stage, state in (("download", "downloading"), ("upload", "uploading"), ("stream", "streaming")):
        if counts.get(state, 0) > len(values[stage]):
            values[stage].append(None)  # DB says active, but no live observation.
    def total(stage):
        samples = values[stage] + values["stream"]
        return None if any(value is None for value in samples) else sum(samples)
    return total("download"), total("upload")
