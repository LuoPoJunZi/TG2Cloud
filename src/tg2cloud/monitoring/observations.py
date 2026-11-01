"""Bounded, non-secret listener and transient-error observations; stdlib only."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from collections import deque

from tg2cloud.deployment.readiness import (
    EVENT_LABELS,
    PER_KIND,
    listener_line,
    unknown_listener,
    validate_events,
    validate_listener,
)

__all__ = [
    "EVENT_LABELS",
    "listener_line",
    "listener_observation",
    "recent_events",
    "record_event",
    "unknown_listener",
    "validate_events",
    "validate_listener",
]

WINDOW = 86400


def listener_observation(service, *, now=None):
    now = time.time() if now is None else now
    value = unknown_listener()
    try:
        listener = service.listener
        with service.db._lock:
            row = service.db._conn.execute(
                "SELECT value FROM service_meta WHERE key='listener_account'"
            ).fetchone()
            account = json.loads(row[0]) if row else {"enabled": False}
            if type(account.get("enabled")) is not bool:
                return value
            value["enabled"] = account["enabled"]
            if not value["enabled"]:
                return value | {"state": "disabled"}
            sources = service.db._conn.execute(
                "SELECT polled_at,next_retry,gap FROM listener_sources WHERE enabled=1 AND deleted=0 LIMIT 33"
            ).fetchall()
        if len(sources) > 32:
            return unknown_listener()
        value["sources"] = len(sources)
        ages = [now - row[0] if row[0] > 0 else -1 for row in sources]
        if any(not math.isfinite(age) for age in ages):
            return unknown_listener()
        value["poll_age_seconds"] = max((int(age) for age in ages), default=-1)
        value["stale_sources"] = sum(age < 0 or age > 180 for age in ages)
        value["gap_sources"] = sum(bool(row[2]) for row in sources)
        value["retrying_sources"] = sum(row[1] > now for row in sources)
        tick = getattr(listener, "_last_loop_at", None)
        loop_age = time.monotonic() - tick if tick is not None else -1
        if not math.isfinite(loop_age) or tick is not None and loop_age < 0:
            return unknown_listener()
        value["loop_age_seconds"] = max(-1, int(loop_age))
        cooldown = account.get("cooldown_until", 0)
        if type(cooldown) not in {int, float} or not math.isfinite(cooldown):
            return unknown_listener()
        value["cooldown_seconds"] = max(0, int(cooldown - now))
        client = listener.client
        if loop_age > 90:
            state = "stale"
        elif tick is None or not client or not client.is_connected():
            state = "cooldown" if value["cooldown_seconds"] else "connecting"
        elif value["cooldown_seconds"]:
            state = "cooldown"
        elif value["stale_sources"]:
            state = "stale"
        elif value["gap_sources"] or value["retrying_sources"]:
            state = "partial"
        else:
            state = "healthy"
        value["state"] = state
        return validate_listener(value) or unknown_listener()
    except (AttributeError, KeyError, TypeError, ValueError, OSError, sqlite3.Error):
        return unknown_listener()


def record_event(service, kind):
    if kind not in EVENT_LABELS:
        return
    records = getattr(service, "_diagnostic_events", None)
    if not isinstance(records, dict):
        records = service._diagnostic_events = {}
    entry = records.setdefault(kind, {"times": deque(maxlen=PER_KIND), "evicted_at": 0})
    if len(entry["times"]) == PER_KIND:
        entry["evicted_at"] = entry["times"][0]
    entry["times"].append(time.time())


def recent_events(service, *, now=None):
    now = time.time() if now is None else now
    result = {}
    for key, entry in getattr(service, "_diagnostic_events", {}).items():
        if key not in EVENT_LABELS:
            continue
        times = [stamp for stamp in entry["times"] if 0 <= now - stamp <= WINDOW]
        if times:
            result[key] = {
                "count": len(times),
                "last_at": max(times),
                "bounded": 0 <= now - entry["evicted_at"] <= WINDOW,
            }
    return result
