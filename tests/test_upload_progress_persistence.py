"""Real task flow with synthetic gateways: progress writes do not gate live rates."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_scenarios import FakeRclone, make_service, make_settings

from tg2cloud.persistence.sqlite import TaskDB


class UploadProgressPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setup_transfer(self, backend, *, retries=1):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = replace(make_settings(Path(temporary.name)), storage_backend=backend, max_retries=retries)
        db = TaskDB(settings.data_dir / "tasks.db")
        self.addCleanup(db.close)
        local = settings.download_dir / "synthetic.bin"
        local.write_bytes(b"1234567890")
        task, _ = db.create_task(chat_id=1, message_id=1, sender_id=settings.allowed_user_id,
                                 file_name="synthetic.bin", file_size=10)
        db.update(task["id"], state="waiting_upload", local_path=str(local), downloaded_bytes=10)
        service = make_service(settings, db)
        service._notify = AsyncMock()
        service.rclone = FakeRclone()
        return service, db, task, local

    async def test_duplicate_reports_skip_writes_but_all_rates_remain_live(self):
        for backend in ("clouddrive2", "openlist"):
            with self.subTest(backend=backend):
                service, db, task, local = self.setup_transfer(backend)
                original_upload = service.rclone.upload
                async def upload(path, remote, *, progress, service=service, task=task, original_upload=original_upload):
                    for value, speed in ((2, 1), (2, 0), (2, 4), (5, 3), (10, 3), (10, 0)):
                        progress(value, speed)
                        self.assertEqual(service._progress[task["id"]]["speed"], speed)
                    await original_upload(path, remote)
                service.rclone.upload = upload
                with patch.object(db, "update", wraps=db.update) as update:
                    await service._upload_one(task["id"])
                writes = [c.kwargs["uploaded_bytes"] for c in update.call_args_list if "uploaded_bytes" in c.kwargs]
                self.assertEqual(writes, [2, 5, 10])
                completed = db.get(task["id"])
                self.assertEqual(completed["state"], "completed")
                self.assertEqual(completed["uploaded_bytes"], 10)
                self.assertEqual(completed["verification_method"], "size")
                self.assertFalse(local.exists())

    async def test_retry_persists_same_first_value_again(self):
        service, db, task, local = self.setup_transfer("clouddrive2", retries=2)
        original_upload = service.rclone.upload
        attempts = 0
        async def upload(path, remote, *, progress):
            nonlocal attempts
            attempts += 1
            progress(4, 1)
            progress(4, 0)
            if attempts == 1:
                raise ConnectionError("synthetic disconnect")
            progress(10, 2)
            await original_upload(path, remote)
        service.rclone.upload = upload
        with patch.object(db, "update", wraps=db.update) as update, patch("tg2cloud.transfer.upload.asyncio.sleep", new=AsyncMock()):
            await service._upload_one(task["id"])
        writes = [c.kwargs["uploaded_bytes"] for c in update.call_args_list if "uploaded_bytes" in c.kwargs]
        self.assertEqual(writes, [4, 4, 10])
        self.assertEqual(db.get(task["id"])["state"], "completed")
        self.assertFalse(local.exists())

    async def test_cancel_or_error_keeps_last_progress_and_local_copy(self):
        for error in (asyncio.CancelledError, ConnectionError):
            with self.subTest(error=error.__name__):
                service, db, task, local = self.setup_transfer("clouddrive2")
                async def upload(path, remote, *, progress, error=error):
                    progress(6, 2)
                    progress(6, 0)
                    raise error()
                service.rclone.upload = upload
                if error is asyncio.CancelledError:
                    with self.assertRaises(asyncio.CancelledError):
                        await service._upload_one(task["id"])
                else:
                    await service._upload_one(task["id"])
                current = db.get(task["id"])
                self.assertEqual(current["uploaded_bytes"], 6)
                self.assertEqual(current["state"], "waiting_upload" if error is asyncio.CancelledError else "upload_failed_retained")
                self.assertTrue(local.exists())

    async def test_completion_without_progress_callback_is_still_persisted(self):
        service, db, task, local = self.setup_transfer("openlist")
        await service._upload_one(task["id"])
        self.assertEqual(db.get(task["id"])["uploaded_bytes"], 10)
        self.assertEqual(db.get(task["id"])["state"], "completed")
        self.assertFalse(local.exists())
