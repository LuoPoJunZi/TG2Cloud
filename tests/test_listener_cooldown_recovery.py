"""Synthetic local downloads: durable cooldown, bounded retries and safe refusal."""
from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tg2cloud.listening import account
from tg2cloud.listening.service import ListenerRateLimited, ListenerReadError
from tg2cloud.persistence.plans import Plans
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.transfer.download import _download_one


class CooldownRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = TaskDB(self.root / "tasks.db")
        self.addCleanup(lambda: self.db.close())
        self.clock = time.time()

    def create(self, **fields):
        account.write_state(self.db, account=42, enabled=True)
        source = Plans(self.db, 1).save_source(1, account=42, chat=-1001, title="synthetic", cursor=0,
                                                config={"rules": {"groups": [{"types": ["视频"]}]}})
        task, _ = self.db.create_task(chat_id=-1001, message_id=1, sender_id=1,
                                     file_name="synthetic.mp4", file_size=4,
                                     read_identity=fields.pop("read_identity", "listener:42"), source_id=source["id"])
        self.db.update(task["id"], **fields)
        self.db.transition(task["id"], "reserved")
        return self.db.get(task["id"])

    def owner(self, backend="clouddrive2"):
        return SimpleNamespace(db=self.db, settings=SimpleNamespace(
            allowed_user_id=1, download_dir=self.root, max_retries=3, storage_backend=backend),
            log=Mock(), _record_progress=Mock(), _notify=AsyncMock())

    async def partial_limit(self, message, *, file, progress_callback):
        Path(file).write_bytes(b"ab")
        progress_callback(2, 4)
        raise ListenerRateLimited("Telegram 限流，需等待至少 5 秒", retry_after_seconds=5)

    async def test_short_limit_requeues_twice_and_never_runs_before_due_for_each_backend(self):
        for backend in ("clouddrive2", "openlist"):
            with self.subTest(backend=backend):
                if self.db.count_states(("download_failed",)):
                    # Isolate each Edition's task identity without deleting history.
                    self.db.close()
                    self.db = TaskDB(self.root / "second.db")
                task = self.create()
                owner = self.owner(backend)
                source = SimpleNamespace(get_messages=AsyncMock(return_value=SimpleNamespace(media=True)),
                                         download_media=AsyncMock(side_effect=self.partial_limit))
                with patch("tg2cloud.persistence.sqlite.time.time", side_effect=lambda: self.clock), \
                        patch("tg2cloud.listening.service.task_source", return_value=source):
                    for attempt in (1, 2, 3):
                        await _download_one(owner, task["id"])
                        saved = self.db.get(task["id"])
                        self.assertFalse((self.root / "1.part").exists())
                        if attempt == 3:
                            self.assertEqual(saved["state"], "download_failed")
                            self.assertEqual(saved["download_retries"], 2)
                            break
                        self.assertEqual(saved["state"], "queued")
                        self.assertEqual(saved["download_retries"], attempt)
                        self.assertEqual(saved["next_retry_at"], self.clock + 5)
                        self.assertFalse(self.db.list_states(("queued",), ready_only=True))
                        limits = {"budget_bytes": 100, "current_free_bytes": 1000, "minimum_free_bytes": 10}
                        self.assertFalse(self.db.reserve(task["id"], **limits)[0])
                        self.assertEqual(self.db._conn.execute("SELECT COUNT(*) FROM quota_slots").fetchone()[0], 0)
                        self.clock += 6
                        self.assertTrue(self.db.reserve(task["id"], **limits)[0])
                        self.assertIsNone(self.db.get(task["id"])["failure_kind"])
                self.assertEqual(source.download_media.await_count, 3)
                self.assertEqual(self.db._conn.execute("SELECT count(*) FROM tasks").fetchone()[0], 1)
                self.assertEqual(self.db._conn.execute("SELECT count(*) FROM task_events WHERE new_state='queued'").fetchone()[0], 2)
                self.assertIn("上限", owner._notify.await_args.args[0])

    def defer(self, task, **extra):
        return self.db.defer_listener_download(task["id"], **{
            "sender_id": task["sender_id"], "expected_updated_at": task["updated_at"],
            "retry_after_seconds": 5, "maximum_attempts": 3, **extra})

    def test_restart_preserves_due_time_and_budget_before_and_after_admission(self):
        task = self.create()
        self.assertTrue(self.defer(task))
        saved = self.db.get(task["id"])
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.db.recover(self.root)
        self.assertEqual(self.db.get(task["id"]), saved)
        limits = {"budget_bytes": 100, "current_free_bytes": 1000, "minimum_free_bytes": 10}
        with patch("tg2cloud.persistence.sqlite.time.time", return_value=saved["next_retry_at"] + 1):
            self.assertTrue(self.db.reserve(task["id"], **limits)[0])
        (self.root / "1.part").write_bytes(b"ab")
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.db.recover(self.root)
        resumed = self.db.get(task["id"])
        self.assertEqual(resumed["state"], "queued")
        self.assertEqual(resumed["download_retries"], 1)
        self.assertFalse((self.root / "1.part").exists())

    def test_concurrent_recovery_only_changes_one_revision_and_preserves_identity(self):
        task = self.create()
        peer = TaskDB(self.root / "tasks.db")
        self.addCleanup(peer.close)
        args = {"sender_id": 1, "expected_updated_at": task["updated_at"], "retry_after_seconds": 5, "maximum_attempts": 3}
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda db: db.defer_listener_download(task["id"], **args), (self.db, peer)))
        self.assertEqual(sorted(results), [False, True])
        saved = self.db.get(task["id"])
        for key in ("id", "chat_id", "message_id", "sender_id", "media_key", "read_identity", "file_name"):
            self.assertEqual(saved[key], task[key])
        self.assertEqual(saved["download_retries"], 1)

    def test_refuses_cancelled_foreign_stale_stream_remote_and_long_wait_cases(self):
        task = self.create()
        for fields, extra in (({}, {"sender_id": 2}), ({}, {"expected_updated_at": task["updated_at"] - 1}),
                              ({}, {"retry_after_seconds": 90}), ({"cancel_requested": 1}, {}),
                              ({"transfer_mode": "stream"}, {}), ({"remote_temp_path": ".uploading-owned.part"}, {})):
            with self.subTest(fields=fields, extra=extra):
                if fields:
                    self.db.update(task["id"], **fields)
                current = self.db.get(task["id"])
                before = current.copy()
                self.assertFalse(self.defer(current, **extra))
                self.assertEqual(self.db.get(task["id"]), before)
                self.db.update(task["id"], cancel_requested=0, transfer_mode="local", remote_temp_path=None)
        self.db._conn.execute("UPDATE tasks SET read_identity='bot' WHERE id=?", (task["id"],))
        self.assertFalse(self.defer(self.db.get(task["id"])))

    def test_durable_account_revocation_or_source_deletion_prevents_automatic_recovery(self):
        task = self.create()
        account.write_state(self.db, enabled=False)
        self.assertFalse(self.defer(task))
        account.write_state(self.db, account=43, enabled=True)
        self.assertFalse(self.defer(task))
        account.write_state(self.db, account=42, enabled=True)
        self.db._conn.execute("UPDATE listener_sources SET deleted=1 WHERE id=?", (task["source_id"],))
        self.assertFalse(self.defer(task))
        self.assertEqual(self.db.get(task["id"])["state"], "reserved")
        self.assertEqual(self.db.get(task["id"])["download_retries"], 0)

    async def test_cancel_and_source_error_do_not_automatically_requeue(self):
        task = self.create()
        owner = self.owner()
        source = SimpleNamespace(get_messages=AsyncMock(side_effect=ListenerReadError("来源消息或附件暂不可读")))
        with patch("tg2cloud.listening.service.task_source", return_value=source):
            await _download_one(owner, task["id"])
        self.assertEqual(self.db.get(task["id"])["state"], "download_failed")
        self.assertIn("附件暂不可读", owner._notify.await_args.args[0])
        self.assertNotIn("重新登录", owner._notify.await_args.args[0])

    async def test_late_duplicate_failure_does_not_overwrite_a_deferred_task(self):
        task = self.create()
        owner = self.owner()
        entered = 0
        ready = asyncio.Event()
        async def fail(message, **options):
            nonlocal entered
            entered += 1
            if entered == 2:
                ready.set()
            await ready.wait()
            raise ListenerRateLimited("Telegram 限流", retry_after_seconds=5)
        source = SimpleNamespace(get_messages=AsyncMock(return_value=SimpleNamespace(media=True)),
                                 download_media=AsyncMock(side_effect=fail))
        with patch("tg2cloud.listening.service.task_source", return_value=source):
            await asyncio.wait_for(asyncio.gather(_download_one(owner, task["id"]),
                                                _download_one(owner, task["id"])), 3)
        saved = self.db.get(task["id"])
        self.assertEqual(saved["state"], "queued")
        self.assertEqual(saved["download_retries"], 1)
        owner._notify.assert_awaited_once()

    async def test_cleanup_failure_after_durable_defer_does_not_reset_the_budget(self):
        task = self.create()
        owner = self.owner()
        source = SimpleNamespace(get_messages=AsyncMock(return_value=SimpleNamespace(media=True)),
                                 download_media=AsyncMock(side_effect=self.partial_limit))
        with patch("tg2cloud.listening.service.task_source", return_value=source), \
                patch.object(Path, "unlink", side_effect=OSError("synthetic cleanup denial")):
            await _download_one(owner, task["id"])
        saved = self.db.get(task["id"])
        self.assertEqual(saved["state"], "queued")
        self.assertEqual(saved["download_retries"], 1)
        self.assertTrue((self.root / "1.part").exists())
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.db.recover(self.root)
        self.assertEqual(self.db.get(task["id"]), saved)

    async def test_waited_attempt_can_finish_without_duplicate_task(self):
        task = self.create()
        owner = self.owner()
        source = SimpleNamespace(get_messages=AsyncMock(return_value=SimpleNamespace(media=True)),
                                 download_media=AsyncMock(side_effect=self.partial_limit))
        with patch("tg2cloud.listening.service.task_source", return_value=source):
            await _download_one(owner, task["id"])
        saved = self.db.get(task["id"])
        with patch("tg2cloud.persistence.sqlite.time.time", return_value=saved["next_retry_at"] + 1):
            self.assertTrue(self.db.reserve(task["id"], budget_bytes=100, current_free_bytes=1000, minimum_free_bytes=10)[0])
        async def completed(message, *, file, progress_callback):
            Path(file).write_bytes(b"abcd")
            progress_callback(4, 4)
            return file
        source.download_media.side_effect = completed
        with patch("tg2cloud.listening.service.task_source", return_value=source):
            await _download_one(owner, task["id"])
        saved = self.db.get(task["id"])
        self.assertEqual(saved["state"], "waiting_upload")
        self.assertEqual(Path(saved["local_path"]).read_bytes(), b"abcd")
        self.assertEqual(saved["next_retry_at"], 0)
        self.assertEqual(self.db._conn.execute("SELECT count(*) FROM tasks").fetchone()[0], 1)
