from __future__ import annotations

import time


def _record_progress(
    self, task_id: int, stage: str, count: int, speed: float | None = None,
) -> None:
    if not hasattr(self, "_progress"):
        self._progress = {}
    now = time.monotonic()
    old = self._progress.get(task_id)
    if not old or old["stage"] != stage or count < old["bytes"]:
        old = {"stage": stage, "bytes": 0, "at": now, "started": now}
    measured = (max(0, count - old["bytes"]) / (now - old["at"])) if now > old["at"] else 0
    self._progress[task_id] = {
        "stage": stage, "bytes": count, "at": now, "started": old["started"],
        "speed": max(0, speed if speed is not None else measured),
    }


def _stage_rate(self, stage: str) -> float:
    return sum(p["speed"] for p in getattr(self, "_progress", {}).values()
               if p["stage"] == stage and time.monotonic() - p["at"] <= 20)
