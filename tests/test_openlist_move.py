"""OpenList MOVE reconciliation must never repeat a potentially accepted rename."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "payload_clouddrive2"))

from app.rclone_client import MoveUncertainError, RcloneClient, RcloneError
from app.verify_destination import DestinationVerificationError, verify_destination


class OpenListMoveTests(unittest.IsolatedAsyncioTestCase):
    def client(self, backend: str = "openlist") -> RcloneClient:
        return RcloneClient(SimpleNamespace(
            storage_backend=backend, cd2_target="", rclone_remote_name="openlist",
        ))

    async def test_success_uses_one_move_and_cloud_drive_keeps_old_command(self) -> None:
        client = self.client()
        client.remote_size = AsyncMock(return_value=256)
        client._run = AsyncMock(return_value=(0, "", ""))
        await client.move("test.uploading", "test.ok")
        self.assertEqual(client._run.await_count, 1)
        self.assertEqual(client._run.await_args.args[-4:], (
            "--retries", "1", "--low-level-retries", "1",
        ))
        client.remote_size.assert_awaited_once_with("test.uploading")

        cloud = self.client("clouddrive2")
        cloud.remote_size = AsyncMock(side_effect=AssertionError("unexpected size probe"))
        cloud._run = AsyncMock(return_value=(0, "", ""))
        await cloud.move("test.uploading", "test.ok")
        self.assertEqual(cloud._run.await_args.args[-2:], ("--retries", "3"))
        cloud.remote_size.assert_not_awaited()

    async def test_accepted_move_with_delayed_metadata_is_confirmed_read_only(self) -> None:
        client = self.client()
        client.remote_size = AsyncMock(return_value=256)
        client._listed_file_sizes = AsyncMock(side_effect=[
            {"test.uploading": 256},
            {"test.ok": 256},
        ])
        client._run = AsyncMock(side_effect=RcloneError(
            "rclone 退出码 4：Copy NewObject failed: object not found"
        ))
        with patch("app.rclone_client.asyncio.sleep", new_callable=AsyncMock) as sleep:
            await client.move("test.uploading", "test.ok")
        self.assertEqual(client._run.await_count, 1)
        sleep.assert_awaited_once_with(2)
        client.remote_size.assert_awaited_once_with("test.uploading")

    async def test_unconfirmed_or_wrong_size_never_reissues_move(self) -> None:
        for destination_exists, final_size, source_exists in (
            (False, 256, True),
            (True, 255, False),
            (True, 256, True),
        ):
            with self.subTest(destination_exists=destination_exists,
                              final_size=final_size, source_exists=source_exists):
                client = self.client()
                client.remote_size = AsyncMock(return_value=256)
                listed = {}
                if destination_exists:
                    listed["test.ok"] = final_size
                if source_exists:
                    listed["test.uploading"] = 256
                client._listed_file_sizes = AsyncMock(return_value=listed)
                client._run = AsyncMock(side_effect=RcloneError("MOVE failed"))
                with (
                    patch("app.rclone_client.asyncio.sleep", new_callable=AsyncMock),
                    self.assertRaises(MoveUncertainError),
                ):
                    await client.move("test.uploading", "test.ok")
                self.assertEqual(client._run.await_count, 1)

    async def test_parent_listing_fallback_matches_exact_file_and_size(self) -> None:
        client = self.client()
        client._run = AsyncMock(return_value=(0, json.dumps([
            {"Name": "test.ok", "Size": 256, "IsDir": False},
            {"Name": "test.ok.extra", "Size": 999, "IsDir": False},
            {"Name": "folder", "Size": -1, "IsDir": True},
        ]), ""))
        sizes = await client._listed_file_sizes(
            "nested/test.uploading", "nested/test.ok"
        )
        self.assertEqual(sizes, {"nested/test.ok": 256})
        self.assertEqual(client._run.await_args.args[:3], (
            "lsjson", "openlist:nested", "--files-only",
        ))

    async def test_openlist_stat_and_exists_fall_back_to_parent_listing(self) -> None:
        client = self.client()
        client._run = AsyncMock(side_effect=[
            RcloneError("object not found"),
            (0, json.dumps([{"Name": "test.ok", "Size": 256}]), ""),
            (4, "", "object not found"),
            (0, json.dumps([{"Name": "test.ok", "Size": 256}]), ""),
        ])
        self.assertEqual(await client.remote_size("test.ok"), 256)
        self.assertTrue(await client.exists("test.ok"))


class OpenListVerificationTests(unittest.TestCase):
    def test_verification_writes_final_name_without_move_and_cleans_it(self) -> None:
        class FakeRclone:
            def __init__(self) -> None:
                self.files: dict[str, bytes] = {}
                self.removed: list[str] = []
                self.move_calls = 0

            async def verify_authentication(self) -> None:
                return None

            async def prepare_destination(self) -> None:
                return None

            async def upload(self, local_path: Path, remote_path: str) -> None:
                self.files[remote_path] = local_path.read_bytes()

            async def remote_size(self, remote_path: str) -> int:
                return len(self.files[remote_path])

            async def move(self, source: str, destination: str) -> None:
                self.move_calls += 1
                raise AssertionError(f"不应调用 MOVE：{source} -> {destination}")

            async def remove(self, remote_path: str) -> None:
                self.removed.append(remote_path)
                self.files.pop(remote_path, None)

            async def exists(self, remote_path: str) -> bool:
                return remote_path in self.files

        with tempfile.TemporaryDirectory() as temp:
            client = FakeRclone()
            settings = SimpleNamespace(
                data_dir=Path(temp), destination_label="OpenList",
                storage_backend="openlist",
            )
            reports: list[str] = []
            result = asyncio.run(
                verify_destination(settings, client, reports.append)  # type: ignore[arg-type]
            )
            self.assertTrue(result.endswith(".ok"))
            self.assertEqual(client.move_calls, 0)
            self.assertEqual(client.removed, [result])
            self.assertEqual(client.files, {})
            self.assertEqual(list(Path(temp).iterdir()), [])
            self.assertIn("TG2CLOUD_WEBDAV_FINALIZE_MODE=DIRECT", reports)
            self.assertIn("TG2CLOUD_WEBDAV_MOVE=NOT_REQUIRED", reports)
            self.assertIn("TG2CLOUD_RENAME=NOT_REQUIRED", reports)
            self.assertIn("TG2CLOUD_WEBDAV_DELETE=OK", reports)

    def test_direct_final_size_failure_cleans_only_final_name(self) -> None:
        class FakeRclone:
            def __init__(self) -> None:
                self.files: dict[str, bytes] = {}
                self.removed: list[str] = []

            async def verify_authentication(self) -> None:
                return None

            async def prepare_destination(self) -> None:
                return None

            async def upload(self, local_path: Path, remote_path: str) -> None:
                self.files[remote_path] = local_path.read_bytes()

            async def remote_size(self, _: str) -> int:
                return 255

            async def remove(self, remote_path: str) -> None:
                self.removed.append(remote_path)
                self.files.pop(remote_path, None)

        with tempfile.TemporaryDirectory() as temp:
            client = FakeRclone()
            settings = SimpleNamespace(
                data_dir=Path(temp), destination_label="OpenList",
                storage_backend="openlist",
            )
            with self.assertRaises(DestinationVerificationError) as raised:
                asyncio.run(verify_destination(settings, client))  # type: ignore[arg-type]
            self.assertEqual(raised.exception.stage, "SIZE")
            self.assertEqual(len(client.removed), 1)
            self.assertTrue(client.removed[0].endswith(".ok"))
            self.assertEqual(client.files, {})
            self.assertEqual(list(Path(temp).iterdir()), [])
