"""Durable, administrator-only alerts with no extra WebDAV requests."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tg2cloud.monitoring import notifications
from tg2cloud.persistence import features
from tg2cloud.persistence.sqlite import TaskDB


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"TZ": "UTC"}).start()
        self.path = Path(self.temp.name) / "tasks.db"
        self.db = TaskDB(self.path)
        self.addCleanup(self.db.close)
        self.service = SimpleNamespace(db=self.db, settings=SimpleNamespace(allowed_user_id=11,
            min_free_disk_bytes=100, control_interval=3, remote_health_interval=30),
            snapshot=SimpleNamespace(sampled_at=10000, disk_free=50, filesystems=()),
            destination_last_checked=10000, destination_failure_kind="", destination_healthy=True,
            destination_label="OpenList", client=SimpleNamespace(send_message=AsyncMock()),
            log=Mock(),
            rclone=SimpleNamespace(probe=Mock(side_effect=AssertionError("must not probe"))))

    def configure(self, **values):
        return features.change(self.db._conn, self.db.feature_settings()["revision"], values)

    async def test_default_off_and_admin_only_cooldown_restart_one_recovery(self):
        await notifications.tick(self.service, now=10000)
        self.service.client.send_message.assert_not_awaited()
        self.configure(notifications=True)
        await notifications.tick(self.service, now=10000)
        await notifications.tick(self.service, now=10001)
        self.assertEqual(self.service.client.send_message.await_count, 1)
        self.assertEqual(self.service.client.send_message.await_args.args[0], 11)
        reopened = TaskDB(self.path)
        try:
            self.service.db = reopened
            await notifications.tick(self.service, now=10002)
            self.service.snapshot.disk_free = 200
            await notifications.tick(self.service, now=10003)
            await notifications.tick(self.service, now=10004)
        finally:
            reopened.close()
        self.assertEqual(self.service.client.send_message.await_count, 2)
        self.assertIn("恢复通知", self.service.client.send_message.await_args.args[1])
        self.service.rclone.probe.assert_not_called()

    async def test_unknown_samples_do_not_recover_and_destination_requires_duration(self):
        self.configure(notifications=True, sustained_seconds=30)
        self.service.snapshot.disk_free = 200
        self.service.destination_healthy = False
        await notifications.tick(self.service, now=10000)
        self.service.client.send_message.assert_not_awaited()
        await notifications.tick(self.service, now=10031)
        self.assertEqual(self.service.client.send_message.await_count, 1)
        self.service.snapshot = None
        self.service.destination_last_checked = 0
        await notifications.tick(self.service, now=10032)
        self.assertEqual(self.service.client.send_message.await_count, 1)

    async def test_send_failure_is_cooled_and_no_secrets_persist(self):
        self.configure(notifications=True)
        self.service.client.send_message.side_effect = RuntimeError("SYNTHETIC_PASSWORD")
        await notifications.tick(self.service, now=10000)
        await notifications.tick(self.service, now=10001)
        self.assertEqual(self.service.client.send_message.await_count, 1)
        row = self.db._conn.execute("SELECT value FROM service_meta WHERE key=?", (notifications.KEY,)).fetchone()
        self.assertNotIn("SYNTHETIC", row[0])
        self.assertEqual(set(json.loads(row[0])), set(notifications.EVENTS))

    def test_config_validation_cas_and_old_config_defaults(self):
        self.assertEqual(self.db.feature_settings()["classification"], "off")
        self.assertFalse(self.db.feature_settings()["notifications"])
        for values in ({"notifications": "true"}, {"cooldown_seconds": 1}, {"classification": "../bad"},
                       {"timezone": "../UTC"}, {"unknown": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.configure(**values)
        self.configure(notifications=True)
        with self.assertRaises(ValueError):
            features.change(self.db._conn, "initial", {"notifications": False})

    async def test_member_task_auth_error_alerts_admin_not_member_and_403_probe_is_classified(self):
        from tg2cloud.domain.actors import user_scope
        from tg2cloud.storage.rclone import RcloneClient
        self.configure(notifications=True)
        task, _ = self.db.create_task(chat_id=22, sender_id=22, message_id=1, file_name="PRIVATE_NAME.mp4", file_size=5)
        self.db.update(task["id"], state="upload_failed_retained", failure_kind="authentication")
        with user_scope(22):
            await notifications.tick(self.service, now=10000)
        for call in self.service.client.send_message.await_args_list:
            self.assertEqual(call.args[0], 11)
            self.assertNotIn("PRIVATE_NAME", call.args[1])
        for label in ("CloudDrive2", "OpenList"):
            for status, kind in ((401, "unauthorized"), (403, "permission"), (429, "rate_limited")):
                result = RcloneClient._openlist_probe_failure(f"HTTP {status} PRIVATE_SECRET", "target", label=label)
                self.assertEqual(result.failure_kind, kind)
                self.assertNotIn("PRIVATE_SECRET", result.detail)
