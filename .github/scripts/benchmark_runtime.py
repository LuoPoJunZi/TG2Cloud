"""Opt-in, stdlib-only synthetic DB benchmark. Never opens an existing instance."""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections import deque
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tg2cloud.domain.states import SCHEDULING_STATES
from tg2cloud.persistence.sqlite import TaskDB


def bounded_integer(low: int, high: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("expected an integer") from exc
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"expected {low}..{high}")
        return number
    return parse


def median_ms(operation, repetitions: int = 20) -> float:
    elapsed = []
    for _ in range(repetitions):
        started = time.perf_counter()
        operation()
        elapsed.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(elapsed), 4)


def run(*, tasks: int, cycles: int, duration_seconds: int, interval_ms: int) -> dict:
    # No user-selectable DB path: all writes and schema checks stay in this directory.
    with tempfile.TemporaryDirectory(prefix="tg2cloud-benchmark-") as directory:
        path = Path(directory) / "synthetic.db"
        with closing(TaskDB(path)) as seed:
            seed._conn.execute("BEGIN IMMEDIATE")
            try:
                seed._conn.executemany(
                    "INSERT INTO tasks(chat_id,message_id,sender_id,file_name,file_size,state,created_at,updated_at) "
                    "VALUES(1,?,?, 'synthetic.bin',100,'completed',1,1)",
                    ((i, i % 100 + 1) for i in range(tasks)),
                )
                seed._conn.execute("COMMIT")
            except BaseException:
                seed._conn.execute("ROLLBACK")
                raise
            waiting = seed.create_task(chat_id=2, message_id=1, sender_id=1,
                                       file_name="waiting.bin", file_size=100)[0]
            retained = seed.create_task(chat_id=2, message_id=2, sender_id=1,
                                        file_name="retained.bin", file_size=100)[0]
            seed.update(retained["id"], state="upload_failed_retained")

        def reopen():
            with closing(TaskDB(path)):
                pass

        first = median_ms(reopen, 1)
        warm = median_ms(reopen, 3)
        with closing(TaskDB(path)) as db:
            expected = {state: count for state, count in db.counts().items() if state in SCHEDULING_STATES}
            if db.counts(states=SCHEDULING_STATES) != expected or db.used_local_bytes() != 100:
                raise RuntimeError("synthetic count/budget invariant failed")
            query_ms = {
                "all_states": median_ms(db.counts),
                "scheduling_states": median_ms(lambda: db.counts(states=SCHEDULING_STATES)),
                "personal_states": median_ms(lambda: db.counts(sender_id=1)),
            }

            def blocked_reserve():
                if db.reserve(waiting["id"], budget_bytes=1000,
                              current_free_bytes=0, minimum_free_bytes=100)[0]:
                    raise RuntimeError("synthetic disk guard failed")

            blocked_reserve()  # Persist initial wait reason, then measure unchanged waits.
            changes = db._conn.total_changes
            recent = deque(maxlen=4096)
            gc.collect()
            tracemalloc.start()
            try:
                baseline, _ = tracemalloc.get_traced_memory()
                started = time.monotonic()
                iterations = 0
                # Duration mode is explicitly opt-in; otherwise finish after cycles.
                while ((time.monotonic() - started < duration_seconds) if duration_seconds else iterations < cycles):
                    tick = time.perf_counter()
                    db.counts(states=SCHEDULING_STATES)
                    db.used_local_bytes()
                    db.counts(sender_id=1)
                    blocked_reserve()
                    recent.append((time.perf_counter() - tick) * 1000)
                    iterations += 1
                    if interval_ms:
                        time.sleep(interval_ms / 1000)
                elapsed = time.monotonic() - started
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            delta = db._conn.total_changes - changes
            if delta != 0:
                raise RuntimeError("unchanged synthetic waits unexpectedly wrote rows")
            integrity = db._conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError("synthetic database integrity check failed")
            return {
                "scope": "synthetic database only; no Telegram, Docker or gateway",
                "history_tasks": tasks, "active_tasks": 1, "retained_tasks": 1,
                "first_reopen_ms": first, "warm_reopen_median_ms": warm,
                "query_median_ms": query_ms,
                "cycles": iterations, "elapsed_seconds": round(elapsed, 3),
                "recent_cycle_median_ms": round(statistics.median(recent), 4),
                "recent_samples": len(recent), "row_changes_during_cycles": delta,
                "python_traced_growth_bytes": current - baseline,
                "python_traced_peak_bytes": peak,
                "db_bytes": path.stat().st_size,
                "wal_bytes": Path(str(path) + "-wal").stat().st_size,
                "integrity_check": integrity,
            }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=bounded_integer(1, 1_000_000), default=100_000,
                        help="synthetic completed history rows (default: 100000)")
    parser.add_argument("--cycles", type=bounded_integer(1, 1_000_000), default=1000)
    parser.add_argument("--duration-seconds", type=bounded_integer(0, 3600), default=0,
                        help="opt-in duration mode; overrides cycles, at most one hour")
    parser.add_argument("--interval-ms", type=bounded_integer(0, 10_000), default=10)
    args = parser.parse_args(argv)
    print(json.dumps(run(**vars(args)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
