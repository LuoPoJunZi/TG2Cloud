"""Hot-path regressions: bounded SQL work and unchanged durable task semantics."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tg2cloud.persistence.sqlite import TaskDB


class DatabaseHotpathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "tasks.db"
        self.db = TaskDB(self.path)
        self.addCleanup(self.db.close)

    def task(self, mid=1, size=100, owner=9):
        return self.db.create_task(chat_id=owner, message_id=mid, sender_id=owner,
                                   file_name="synthetic.bin", file_size=size)[0]

    def reserve(self, task, *, budget=100, free=1000):
        return self.db.reserve(task["id"], budget_bytes=budget,
                               current_free_bytes=free, minimum_free_bytes=100)

    def test_personal_global_and_selected_state_counts(self):
        self.task(owner=9)
        other = self.task(owner=10)
        self.db.update(other["id"], state="completed")
        self.assertEqual(self.db.counts(), {"queued": 1, "completed": 1})
        self.assertEqual(self.db.counts(sender_id=9), {"queued": 1})
        self.assertEqual(self.db.counts(sender_id=10), {"completed": 1})
        self.assertEqual(self.db.counts(sender_id=0), {})
        self.assertEqual(self.db.counts(sender_id=123), {})
        self.assertEqual(self.db.count_states(()), 0)
        self.assertEqual(self.db.count_states(iter(("queued", "queued"))), 1)
        self.assertEqual(self.db.count_states(("queued", "completed")), 2)
        self.assertEqual(self.db.count_states(("queued') OR 1=1 --",)), 0)
        self.db.update(other["id"], state="queued")
        self.assertEqual(self.db.count_states(("queued",)), 2)

    def test_filtered_counts_keep_owner_scope_and_retained_budget(self):
        from tg2cloud.domain.states import SCHEDULING_STATES

        queued = self.task(owner=9)
        other = self.task(owner=10)
        retained = self.task(mid=2, owner=9)
        self.db.update(retained["id"], state="upload_failed_retained")
        self.assertEqual(self.db.counts(states=SCHEDULING_STATES), {"queued": 2})
        self.assertEqual(self.db.counts(sender_id=9, states=SCHEDULING_STATES), {"queued": 1})
        self.assertEqual(self.db.counts(sender_id=9, states=()), {})
        self.assertEqual(self.db.counts(states=("queued') OR 1=1 --",)), {})
        self.assertEqual(self.db.used_local_bytes(), retained["file_size"])
        self.db.update(queued["id"], state="downloading")
        self.db.update(other["id"], state="completed")
        self.assertEqual(self.db.counts(states=SCHEDULING_STATES), {"downloading": 1})
        self.assertEqual(self.db.counts(sender_id=10, states=SCHEDULING_STATES), {})

    def test_history_does_not_force_scan_for_personal_or_active_counts(self):
        c = self.db._conn
        c.execute("BEGIN")
        c.executemany(
            "INSERT INTO tasks(chat_id,message_id,sender_id,file_name,file_size,state,created_at,updated_at) "
            "VALUES(1,?,?,'synthetic.bin',1,?,0,0)",
            ((i, 1 + i % 100, "queued" if i > 19990 else "completed") for i in range(1, 20001)),
        )
        c.execute("COMMIT")

        def work(call):
            steps = 0
            def tick():
                nonlocal steps
                steps += 1
                return 0
            c.set_progress_handler(tick, 100)
            try:
                result = call()
            finally:
                c.set_progress_handler(None, 0)
            return result, steps

        baseline, old_steps = work(lambda: dict(c.execute(
            "SELECT state,COUNT(*) FROM tasks WHERE (? IS NULL OR sender_id=?) GROUP BY state", (1, 1))))
        result, new_steps = work(lambda: self.db.counts(sender_id=1))
        self.assertEqual(result, baseline)
        self.assertLess(new_steps, old_steps / 4)
        all_counts, all_steps = work(self.db.counts)
        count, active_steps = work(lambda: self.db.count_states(("queued", "reserved", "downloading", "streaming")))
        self.assertEqual(count, all_counts["queued"])
        self.assertLess(active_steps, all_steps / 4)
        filtered, filtered_steps = work(lambda: self.db.counts(states=("queued", "reserved")))
        self.assertEqual(filtered, {"queued": all_counts["queued"]})
        self.assertLess(filtered_steps, all_steps / 4)

    def test_unchanged_wait_does_not_write_or_invalidate_revision(self):
        task = self.task()
        with patch("tg2cloud.persistence.sqlite.time.time", return_value=123):
            self.assertTrue(self.db.set_wait_reason(task["id"], "等待空间", states=("queued",)))
        changes = self.db._conn.total_changes
        with patch("tg2cloud.persistence.sqlite.time.time", return_value=456):
            for _ in range(100):
                self.assertFalse(self.db.set_wait_reason(task["id"], "等待空间", states=("queued",)))
        self.assertEqual(self.db._conn.total_changes, changes)
        self.assertEqual(self.db.get(task["id"])["updated_at"], 123)
        self.assertTrue(self.db.set_wait_reason(task["id"], "等待额度", states=("queued",)))
        self.assertEqual(self.db.get(task["id"])["wait_reason"], "等待额度")

    def test_wait_guard_rejects_missing_cancelled_and_advanced_tasks(self):
        task = self.task()
        for fields in ({"cancel_requested": 1}, {"cancel_requested": 0, "state": "completed"}):
            self.db.update(task["id"], **fields)
            before = self.db.get(task["id"])
            self.assertFalse(self.db.set_wait_reason(task["id"], "stale", states=("queued",)))
            self.assertEqual(self.db.get(task["id"]), before)
        self.assertFalse(self.db.set_wait_reason(99999, "stale", states=("queued",)))

    def test_wait_change_rolls_back_with_existing_transaction(self):
        task = self.task()
        self.db._conn.execute("BEGIN IMMEDIATE")
        self.db.set_wait_reason(task["id"], "等待空间", states=("queued",))
        self.db._conn.execute("ROLLBACK")
        self.assertEqual(self.db.get(task["id"])["wait_reason"], task["wait_reason"])

    def test_persisted_wait_survives_reopen_without_rewrite(self):
        task = self.task()
        self.db.set_wait_reason(task["id"], "等待空间", states=("queued",))
        second = TaskDB(self.path)
        self.addCleanup(second.close)
        changes = second._conn.total_changes
        self.assertFalse(second.set_wait_reason(task["id"], "等待空间", states=("queued",)))
        self.assertEqual(second._conn.total_changes, changes)

    def test_disk_waits_do_not_write_repeatedly_and_resume_when_space_returns(self):
        for size, budget in ((100, 100), (200, 100)):
            with self.subTest(size=size):
                task = self.task(mid=size, size=size)
                ok, reason = self.reserve(task, budget=budget, free=0)
                self.assertFalse(ok)
                self.assertIn("磁盘空间", reason)
                before = self.db.get(task["id"])
                changes = self.db._conn.total_changes
                for _ in range(20):
                    self.assertEqual(self.reserve(task, budget=budget, free=0), (False, reason))
                self.assertEqual(self.db._conn.total_changes, changes)
                self.assertEqual(self.db.get(task["id"]), before)
                self.assertTrue(self.reserve(task, budget=budget)[0])
                self.assertIsNone(self.db.get(task["id"])["wait_reason"])
                self.db.update(task["id"], state="completed")

    def test_budget_and_member_waits_resume_without_bypassing_limits(self):
        first, second = self.task(1), self.task(2)
        self.assertTrue(self.reserve(first)[0])
        for quota in (False, True):
            with self.subTest(quota=quota):
                if quota:
                    self.db._conn.execute("INSERT INTO member_quotas VALUES(9,0,0,1)")
                ok, reason = self.reserve(second)
                self.assertFalse(ok)
                self.assertIn("个人并发" if quota else "临时空间", reason)
                changes = self.db._conn.total_changes
                for _ in range(20):
                    self.assertEqual(self.reserve(second), (False, reason))
                self.assertEqual(self.db._conn.total_changes, changes)
        self.db.update(first["id"], state="completed")
        self.assertTrue(self.reserve(second)[0])
        self.assertIsNone(self.db.get(second["id"])["wait_reason"])

    def test_concurrent_reservations_still_share_atomic_budget(self):
        tasks = [self.task(i) for i in range(1, 9)]
        second = TaskDB(self.path)
        self.addCleanup(second.close)
        connections = (self.db, second)
        def reserve(index):
            return connections[index % 2].reserve(tasks[index]["id"], budget_bytes=200,
                                                  current_free_bytes=10000, minimum_free_bytes=100)[0]
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sum(executor.map(reserve, range(8))), 2)
        self.assertEqual(self.db.used_local_bytes(), 200)
        self.assertEqual(self.db._conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_cross_connection_cancellation_between_read_and_write_is_respected(self):
        task = self.task()
        other = sqlite3.connect(self.path, isolation_level=None)
        self.addCleanup(other.close)
        def cancel_before_write(sql):
            if sql.startswith("UPDATE tasks SET wait_reason"):
                other.execute("UPDATE tasks SET cancel_requested=1 WHERE id=?", (task["id"],))
        self.db._conn.set_trace_callback(cancel_before_write)
        try:
            self.assertFalse(self.db.set_wait_reason(task["id"], "stale", states=("queued",)))
        finally:
            self.db._conn.set_trace_callback(None)
        current = self.db.get(task["id"])
        self.assertEqual(current["cancel_requested"], 1)
        self.assertIsNone(current["wait_reason"])
