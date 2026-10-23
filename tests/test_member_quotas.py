"""Atomic admission, durable accounting and authorization using temporary DBs."""
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tg2cloud.persistence import control, features, quotas
from tg2cloud.persistence.sqlite import TaskDB


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.zone = patch.dict(os.environ, {"TZ": "UTC"})
        self.zone.start()
        self.addCleanup(self.zone.stop)
        self.path = Path(self.temp.name) / "tasks.db"
        self.db = TaskDB(self.path)
        self.addCleanup(self.db.close)

    def task(self, number=1, owner=22, size=6):
        return self.db.create_task(chat_id=owner, sender_id=owner, message_id=number,
                                   media_key=f"file:{number}", file_name="private.mp4", file_size=size)

    def limit(self, **values):
        quotas.configure(self.db._conn, 22, {"daily_bytes": 0, "max_queued": 0, "max_active": 0, **values})

    def test_defaults_unlimited_duplicates_once_and_two_editions_separate(self):
        task, created = self.task()
        self.assertTrue(created)
        self.assertFalse(self.task()[1])
        self.assertEqual(self.db._conn.execute("SELECT COUNT(*) FROM quota_ledger").fetchone()[0], 1)
        self.assertEqual(self.db.quota_usage(22)["reserved_bytes"], 6)
        other = TaskDB(self.path.parent / "other-edition.db")
        try:
            self.assertEqual(other.quota_usage(22)["reserved_bytes"], 0)
        finally:
            other.close()
        self.assertEqual(self.db.get(task["id"])["id"], 1)

    def test_daily_limit_includes_reservations_and_queue_limit(self):
        self.limit(daily_bytes=10)
        self.task()
        with self.assertRaises(quotas.QuotaExceeded):
            self.task(2)
        self.limit(max_queued=1)
        with self.assertRaises(quotas.QuotaExceeded):
            self.task(2)
        # Other family members and administrator are not implicitly limited.
        self.task(1, owner=33, size=100)
        self.task(1, owner=11, size=100)

    def test_two_connections_concurrent_admission_cannot_overbook(self):
        self.limit(daily_bytes=10)
        connections = [TaskDB(self.path), TaskDB(self.path)]
        try:
            def create(index):
                try:
                    connections[index].create_task(chat_id=22, sender_id=22, message_id=index + 1,
                        file_name="movie.mp4", file_size=6)
                    return True
                except quotas.QuotaExceeded:
                    return False
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(create, (0, 1)))
            self.assertEqual(sum(results), 1)
        finally:
            for connection in connections:
                connection.close()

    def test_cancel_releases_failed_retains_retry_not_double_counted(self):
        self.limit(daily_bytes=10)
        task, _ = self.task()
        self.db.update(task["id"], state="download_failed")
        failed = self.db.get(task["id"])
        self.assertEqual(self.db.quota_usage(22)["reserved_bytes"], 6)
        self.assertTrue(self.db.requeue(task["id"], sender_id=22, expected_updated_at=failed["updated_at"], local_complete=False))
        self.assertEqual(self.db.quota_usage(22)["reserved_bytes"], 6)
        self.db.update(task["id"], state="cancelled")
        self.assertEqual(self.db.quota_usage(22)["reserved_bytes"], 0)
        self.task(2, size=9)
        cancelled = self.db.get(task["id"])
        self.assertFalse(self.db.requeue(task["id"], sender_id=22, expected_updated_at=cancelled["updated_at"],
                                        local_complete=False, restart_cancelled=True))

    def test_completion_once_cross_day_pending_reservation_and_restart(self):
        self.limit(daily_bytes=10)
        task, _ = self.task()
        self.db.update(task["id"], state="cleanup_pending", verification_method="size", verified_at=time.time())
        self.db.update(task["id"], state="completed")
        self.db.update(task["id"], state="confirmed")
        self.assertEqual(self.db.quota_usage(22)["completed_bytes"], 6)
        self.assertEqual(self.db.quota_usage(22)["reserved_bytes"], 0)
        # Yesterday's pending reservation is carried into today's admission.
        pending, _ = self.task(2, size=4)
        tomorrow = time.time() + 86400
        value = quotas.usage(self.db._conn, 22, tomorrow, "UTC")
        self.assertEqual(value["completed_bytes"], 0)
        self.assertEqual(value["reserved_bytes"], 4)
        self.assertEqual(value["available_bytes"], 6)
        reopened = TaskDB(self.path)
        try:
            self.assertEqual(reopened.quota_usage(22)["reserved_bytes"], 4)
            self.assertEqual(reopened.get(pending["id"])["sender_id"], 22)
        finally:
            reopened.close()

    def test_download_and_upload_share_member_slot_stream_counts_once(self):
        self.limit(max_active=1)
        a, _ = self.task()
        b, _ = self.task(2)
        self.assertTrue(self.db.reserve(a["id"], budget_bytes=100, current_free_bytes=1000, minimum_free_bytes=10)[0])
        self.assertFalse(self.db.reserve(b["id"], budget_bytes=100, current_free_bytes=1000, minimum_free_bytes=10)[0])
        self.db.update(a["id"], state="waiting_upload")
        self.assertTrue(self.db.admit_upload(a["id"]))
        self.assertFalse(self.db.reserve(b["id"], budget_bytes=100, current_free_bytes=1000, minimum_free_bytes=10)[0])
        self.db.update(a["id"], state="upload_failed_retained")
        self.assertTrue(self.db.reserve(b["id"], budget_bytes=1, current_free_bytes=1000, minimum_free_bytes=10)[0])
        self.db.update(b["id"], state="streaming")
        self.assertEqual(self.db.quota_usage(22)["active"], 1)
        self.assertFalse(self.db.admit_upload(a["id"]))

    def test_queue_config_changes_do_not_cancel_running_and_unknown_size_is_refused(self):
        task, _ = self.task()
        self.db.update(task["id"], state="streaming")
        self.limit(daily_bytes=1, max_active=1)
        self.assertEqual(self.db.get(task["id"])["state"], "streaming")
        with self.assertRaises(quotas.QuotaExceeded):
            self.task(2, size=0)

    def test_control_authorization_revision_and_no_raw_credentials(self):
        record = self.db.change_family_user(11, {"id": 22, "action": "add", "revision": "initial"})
        base = {"admin_id": 11, "action": "quota-write", "user_id": 22, "revision": record["revision"],
                "expected": quotas.limits(self.db._conn, 22), "values": {"daily_bytes": 10, "max_queued": 2, "max_active": 1}}
        for change in ({"admin_id": 22}, {"user_id": 11}, {"user_id": 99}, {"revision": "old"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                control.handle(self.db._conn, 11, {**base, **change})
        result = control.handle(self.db._conn, 11, base)
        self.assertEqual(result["usage"]["daily_bytes"], 10)
        with self.assertRaises(ValueError):
            control.handle(self.db._conn, 11, base)
        self.assertFalse(features.read(self.db._conn)["notifications"])

    def test_day_bounds_are_calendar_days(self):
        start, end = quotas.day_bounds(1791028800, "UTC")
        self.assertEqual(end - start, 86400)
        self.assertLessEqual(start, 1791028800)
        self.assertGreater(end, 1791028800)

    def test_v1_migration_preserves_rows_and_seeds_pending_not_completed(self):
        import ast
        import subprocess
        from contextlib import closing
        root = Path(__file__).resolve().parents[1]
        # Read static original DDL from an existing local Git object; do not
        # execute the old Python or download any code.
        old = subprocess.run(["git", "show", "42e2c372823a085c36a7a7597ce775441598aaf9:src/tg2cloud/persistence/sqlite.py"],
                             cwd=root, check=True, capture_output=True, text=True).stdout
        tree = ast.parse(old)
        ddl = next(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "executescript"
                   and node.args and isinstance(node.args[0], ast.Constant))
        path = self.path.parent / "old.db"
        with closing(sqlite3.connect(path)) as connection:
            connection.executescript(ddl)
            for number, state in ((1, "queued"), (2, "completed")):
                connection.execute("INSERT INTO tasks(id,chat_id,message_id,sender_id,file_name,file_size,state,created_at,updated_at) "
                                   "VALUES(?,22,?,22,'old.mp4',5,?,1,1)", (number, number, state))
            connection.execute("PRAGMA user_version=1")
            connection.commit()
        for _ in range(2):
            migrated = TaskDB(path)
            try:
                self.assertEqual(migrated.get(1)["file_name"], "old.mp4")
                self.assertEqual(migrated.get(1)["target_directory"], "")
                self.assertEqual(migrated.get(2)["state"], "completed")
                self.assertEqual(migrated.quota_usage(22)["reserved_bytes"], 5)
                self.assertEqual(migrated.quota_usage(22)["completed_bytes"], 0)
                self.assertEqual(migrated._conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
            finally:
                migrated.close()
