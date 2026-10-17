from __future__ import annotations

# The tests insert the CloudDrive2 payload path before importing the shared app.
import asyncio
import base64
import os
import sqlite3
import sys
import tempfile
import unittest
from collections import deque
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from payload_fixture import payload

SOURCE = Path(__file__).resolve().parents[1]
PAYLOAD = payload("clouddrive2")
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(PAYLOAD))

from tg2cloud import __version__
from tg2cloud.app import TransferService, setup_logging
from tg2cloud.config import Settings
from tg2cloud.deployment.profiles import CLOUDDRIVE2_PRODUCT, RELEASE_VERSION
from tg2cloud.deployment.resources import (
    GIB,
    LEGACY_PROBE_BEGIN,
    LEGACY_PROBE_END,
    PROBE_BEGIN,
    PROBE_END,
    VpsResources,
    assess_storage_choice,
    build_probe_command,
    parse_probe_output,
    recommend_storage,
)
from tg2cloud.domain.naming import safe_file_name
from tg2cloud.monitoring.resources import AdaptiveWindow, ResourceSnapshot
from tg2cloud.persistence.backup import backup_database
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.storage.rclone import RcloneClient, RcloneError
from tg2cloud.storage.verify_destination import (
    DestinationVerificationError,
    verify_destination,
)
from tg2cloud.telegram.views import state_label


def encoded(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def sample_vps_resources(
    *,
    total_gb: int = 50,
    available_gb: int = 42,
    memory_gb: float = 4,
    cpu_cores: int = 2,
    install_present: bool = False,
    downloads_gb: int = 0,
    fuse_available: bool = True,
    inodes_total: int = 1_000_000,
    inodes_available: int = 900_000,
    docker_same_filesystem: bool = True,
    docker_available_gb: int = 42,
    docker_inodes_total: int = 1_000_000,
    docker_inodes_available: int = 900_000,
) -> VpsResources:
    return VpsResources(
        architecture="x86_64",
        cpu_cores=cpu_cores,
        memory_total_bytes=int(memory_gb * GIB),
        memory_available_bytes=int(memory_gb * GIB * 0.75),
        swap_total_bytes=GIB,
        filesystem_type="ext2/ext3",
        storage_total_bytes=total_gb * GIB,
        storage_available_bytes=available_gb * GIB,
        inodes_total=inodes_total,
        inodes_available=inodes_available,
        install_present=install_present,
        install_used_bytes=downloads_gb * GIB,
        downloads_used_bytes=downloads_gb * GIB,
        backups_used_bytes=0,
        docker_same_filesystem=docker_same_filesystem,
        docker_root_detected=True,
        docker_storage_total_bytes=50 * GIB,
        docker_storage_available_bytes=docker_available_gb * GIB,
        docker_inodes_total=docker_inodes_total,
        docker_inodes_available=docker_inodes_available,
        fuse_available=fuse_available,
    )


class VpsResourceRecommendationTests(unittest.TestCase):
    @staticmethod
    def probe_output() -> str:
        return "\n".join(
            (
                "unrelated login banner",
                PROBE_BEGIN,
                "PROBE_VERSION=2",
                "ARCHITECTURE=x86_64",
                "CPU_CORES=2",
                "MEMORY_TOTAL_KIB=4194304",
                "MEMORY_AVAILABLE_KIB=3145728",
                "SWAP_TOTAL_KIB=1048576",
                "FILESYSTEM_TYPE=ext2/ext3",
                f"STORAGE_TOTAL_BYTES={50 * GIB}",
                f"STORAGE_AVAILABLE_BYTES={42 * GIB}",
                "INODES_TOTAL=1000000",
                "INODES_AVAILABLE=900000",
                "INSTALL_PRESENT=0",
                "INSTALL_USED_KIB=0",
                "DOWNLOADS_USED_KIB=0",
                "BACKUPS_USED_KIB=0",
                "DOCKER_SAME_FILESYSTEM=1",
                "DOCKER_ROOT_DETECTED=1",
                f"DOCKER_STORAGE_TOTAL_BYTES={50 * GIB}",
                f"DOCKER_STORAGE_AVAILABLE_BYTES={42 * GIB}",
                "DOCKER_INODES_TOTAL=1000000",
                "DOCKER_INODES_AVAILABLE=900000",
                "FUSE_AVAILABLE=1",
                PROBE_END,
            )
        )

    def test_probe_output_is_strictly_parsed_between_markers(self) -> None:
        resources = parse_probe_output(self.probe_output())
        self.assertEqual(resources.cpu_cores, 2)
        self.assertEqual(resources.memory_total_bytes, 4 * GIB)
        self.assertEqual(resources.storage_available_bytes, 42 * GIB)
        self.assertEqual(resources.filesystem_type, "ext2/ext3")
        self.assertTrue(resources.docker_same_filesystem)
        self.assertTrue(resources.docker_root_detected)
        self.assertEqual(resources.docker_storage_available_bytes, 42 * GIB)

    def test_probe_prefers_current_boundary_and_accepts_legacy_output(self) -> None:
        legacy = self.probe_output().replace(PROBE_BEGIN, LEGACY_PROBE_BEGIN).replace(
            PROBE_END, LEGACY_PROBE_END
        )
        self.assertEqual(parse_probe_output(legacy).cpu_cores, 2)
        current = self.probe_output().replace("CPU_CORES=2", "CPU_CORES=4")
        self.assertEqual(parse_probe_output(legacy + "\n" + current).cpu_cores, 4)


    def test_probe_rejects_missing_or_duplicate_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "完整边界"):
            parse_probe_output("CPU_CORES=2")
        duplicate = self.probe_output().replace(
            "CPU_CORES=2", "CPU_CORES=2\nCPU_CORES=4"
        )
        with self.assertRaisesRegex(ValueError, "字段重复"):
            parse_probe_output(duplicate)

    def test_probe_command_accepts_only_safe_install_path(self) -> None:
        command = build_probe_command(
            "/opt/tg2cloud-clouddrive2",
            "/opt/tg2cloud-clouddrive2-backups",
        )
        self.assertIn(PROBE_BEGIN, command)
        self.assertIn("df -PB1", command)
        self.assertIn("timeout 5s du", command)
        self.assertIn("timeout 5s docker info", command)
        self.assertIn("/opt/tg2cloud-clouddrive2", command)
        self.assertIn("/opt/tg2cloud-clouddrive2-backups", command)
        with self.assertRaisesRegex(ValueError, "安装目录"):
            build_probe_command(
                "/opt/tg2cloud-clouddrive2;touch /tmp/pwned",
                "/opt/tg2cloud-clouddrive2-backups",
            )

    def test_small_vps_prefers_stream_first_without_changing_defaults(self) -> None:
        advice = recommend_storage(
            sample_vps_resources(total_gb=39, available_gb=30, memory_gb=2.4),
            managed_clouddrive=True,
        )
        self.assertEqual(advice.performance_profile, "保守")
        self.assertEqual(advice.preferred_key, "stream_first")
        self.assertEqual(
            (advice.stream_first.budget_gb, advice.stream_first.reserve_gb),
            (8, 8),
        )
        self.assertTrue(advice.stream_first.safe)

    def test_standard_and_large_vps_prefer_balanced_profile(self) -> None:
        standard = recommend_storage(
            sample_vps_resources(), managed_clouddrive=True
        )
        self.assertEqual(standard.preferred_key, "balanced")
        self.assertEqual(
            (standard.balanced.budget_gb, standard.balanced.reserve_gb),
            (15, 10),
        )
        large = recommend_storage(
            sample_vps_resources(
                total_gb=100, available_gb=90, memory_gb=8, cpu_cores=4
            ),
            managed_clouddrive=True,
        )
        self.assertEqual(large.performance_profile, "批量")
        self.assertEqual(large.preferred_key, "balanced")
        self.assertEqual(
            (large.balanced.budget_gb, large.balanced.reserve_gb),
            (20, 20),
        )

    def test_insufficient_disk_has_no_applicable_plan(self) -> None:
        advice = recommend_storage(
            sample_vps_resources(total_gb=20, available_gb=10),
            managed_clouddrive=True,
        )
        self.assertIsNone(advice.preferred)
        self.assertFalse(advice.balanced.safe)
        self.assertFalse(advice.stream_first.safe)

    def test_deploy_assessment_rejects_unsafe_defaults_and_accepts_advice(self) -> None:
        resources = sample_vps_resources(
            total_gb=39, available_gb=30, memory_gb=2.4
        )
        unsafe = assess_storage_choice(
            resources,
            budget_gb=20,
            reserve_gb=20,
            managed_clouddrive=True,
        )
        self.assertFalse(unsafe.safe)
        advice = recommend_storage(resources, managed_clouddrive=True)
        safe = assess_storage_choice(
            resources,
            budget_gb=advice.stream_first.budget_gb,
            reserve_gb=advice.stream_first.reserve_gb,
            managed_clouddrive=True,
        )
        self.assertTrue(safe.safe)

    def test_existing_downloads_are_not_counted_twice_during_upgrade(self) -> None:
        resources = sample_vps_resources(
            total_gb=40,
            available_gb=20,
            install_present=True,
            downloads_gb=15,
        )
        advice = recommend_storage(resources, managed_clouddrive=True)
        self.assertEqual(advice.balanced.budget_gb, 15)
        self.assertTrue(advice.balanced.safe)
        assessment = assess_storage_choice(
            resources,
            budget_gb=15,
            reserve_gb=8,
            managed_clouddrive=True,
        )
        self.assertTrue(assessment.safe)
        self.assertEqual(assessment.required_available_gb, 11)

    def test_managed_clouddrive_requires_memory_fuse_and_inodes(self) -> None:
        resources_without_fuse = sample_vps_resources(fuse_available=False)
        advice = recommend_storage(
            resources_without_fuse, managed_clouddrive=True
        )
        self.assertIsNone(advice.preferred)
        self.assertFalse(advice.balanced.safe)
        self.assertIn("/dev/fuse", advice.balanced.reason)
        no_fuse = assess_storage_choice(
            resources_without_fuse,
            budget_gb=15,
            reserve_gb=10,
            managed_clouddrive=True,
        )
        self.assertFalse(no_fuse.safe)
        self.assertIn("/dev/fuse", no_fuse.reason)
        low_memory = assess_storage_choice(
            sample_vps_resources(memory_gb=1.5),
            budget_gb=4,
            reserve_gb=8,
            managed_clouddrive=False,
        )
        self.assertFalse(low_memory.safe)
        low_inodes = assess_storage_choice(
            sample_vps_resources(inodes_available=100),
            budget_gb=15,
            reserve_gb=10,
            managed_clouddrive=True,
        )
        self.assertFalse(low_inodes.safe)
        self.assertIn("inode", low_inodes.reason)

    def test_deploy_assessment_keeps_remote_installer_eight_gb_floor(self) -> None:
        assessment = assess_storage_choice(
            sample_vps_resources(
                total_gb=20,
                available_gb=7,
                install_present=True,
            ),
            budget_gb=1,
            reserve_gb=1,
            managed_clouddrive=False,
        )
        self.assertFalse(assessment.safe)
        self.assertEqual(assessment.required_available_gb, 8)

    def test_separate_docker_filesystem_is_checked_independently(self) -> None:
        resources = sample_vps_resources(
            docker_same_filesystem=False,
            docker_available_gb=5,
        )
        advice = recommend_storage(resources, managed_clouddrive=True)
        self.assertIsNone(advice.preferred)
        self.assertIn("Docker 数据文件系统至少需要 6GB", advice.balanced.reason)
        assessment = assess_storage_choice(
            resources,
            budget_gb=15,
            reserve_gb=10,
            managed_clouddrive=True,
        )
        self.assertFalse(assessment.safe)
        healthy = sample_vps_resources(
            docker_same_filesystem=False,
            docker_available_gb=8,
        )
        self.assertTrue(
            assess_storage_choice(
                healthy,
                budget_gb=15,
                reserve_gb=10,
                managed_clouddrive=True,
            ).safe
        )

    def test_separate_docker_filesystem_inode_pressure_blocks_plan(self) -> None:
        resources = sample_vps_resources(
            docker_same_filesystem=False,
            docker_available_gb=8,
            docker_inodes_available=100,
        )
        advice = recommend_storage(resources, managed_clouddrive=True)
        self.assertIsNone(advice.preferred)
        self.assertIn("Docker 数据文件系统可用 inode", advice.balanced.reason)


class FileNameSafetyTests(unittest.TestCase):
    def test_long_utf8_name_stays_below_filesystem_byte_limit(self) -> None:
        result = safe_file_name("测试视频" * 80 + ".mp4", "fallback.bin")
        self.assertLessEqual(len(result.encode("utf-8")), 180)
        self.assertTrue(result.endswith(".mp4"))
        self.assertFalse(result.encode("utf-8").endswith(b"\xef\xbf\xbd"))


class StatusTextTests(unittest.TestCase):
    def test_queue_and_completed_states_are_user_facing_chinese(self) -> None:
        self.assertEqual(state_label("queued"), "在排队")
        self.assertEqual(
            state_label("completed"),
            "Bot 传输已完成（CloudDrive2 已接收）",
        )
        self.assertEqual(
            state_label("confirmed"),
            "Bot 传输已完成（CloudDrive2 已接收）",
        )
        self.assertNotIn("正在上传", state_label("completed"))
        self.assertNotIn("后台处理中", state_label("completed"))


class SettingsTests(unittest.TestCase):
    def test_settings_decode_and_create_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {
                "TELEGRAM_API_ID": "12345",
                "TELEGRAM_API_HASH_B64": encoded("a" * 32),
                "BOT_TOKEN_B64": encoded("12345:abcdefghijklmnopqrstuvwxyz"),
                "ALLOWED_USER_ID": "987654321",
                "CD2_WEBDAV_URL_B64": encoded("http://clouddrive2:19798/dav"),
                "CD2_WEBDAV_USERNAME_B64": encoded("user@example.com"),
                "CD2_WEBDAV_PASSWORD_B64": encoded("secret"),
                "CD2_TARGET_PATH_B64": encoded("115/Telegram"),
                "DATA_DIR": str(root / "data"),
                "DOWNLOAD_DIR": str(root / "downloads"),
                "LOG_DIR": str(root / "logs"),
                "RCLONE_CONFIG_PATH": str(root / "config" / "rclone.conf"),
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()
            self.assertEqual(settings.api_hash, "a" * 32)
            self.assertEqual(settings.cd2_target, "115/Telegram")
            self.assertEqual(settings.local_budget_bytes, 20 * 1024**3)
            self.assertEqual(settings.min_free_disk_bytes, 8 * 1024**3)
            with patch.dict(
                os.environ,
                env | {"LOCAL_TEMP_BUDGET_GB": "12", "MIN_FREE_DISK_GB": "9"},
                clear=True,
            ):
                custom = Settings.from_env(create_directories=False)
            self.assertEqual(custom.local_budget_bytes, 12 * 1024**3)
            self.assertEqual(custom.min_free_disk_bytes, 9 * 1024**3)
            self.assertTrue(settings.download_dir.is_dir())
            self.assertTrue(settings.rclone_config_path.parent.is_dir())

    def test_blank_target_means_webdav_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {
                "TELEGRAM_API_ID": "12345",
                "TELEGRAM_API_HASH_B64": encoded("a" * 32),
                "BOT_TOKEN_B64": encoded("12345:abcdefghijklmnopqrstuvwxyz"),
                "ALLOWED_USER_ID": "987654321",
                "CD2_WEBDAV_URL_B64": encoded(CLOUDDRIVE2_PRODUCT.webdav_url),
                "CD2_WEBDAV_USERNAME_B64": encoded("user"),
                "CD2_WEBDAV_PASSWORD_B64": encoded("secret"),
                "CD2_TARGET_PATH_B64": "",
                "DATA_DIR": str(root / "data"),
                "DOWNLOAD_DIR": str(root / "downloads"),
                "LOG_DIR": str(root / "logs"),
                "RCLONE_CONFIG_PATH": str(root / "config" / "rclone.conf"),
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()
            self.assertEqual(settings.cd2_target, "")

    def test_non_finite_budget_is_rejected_even_if_env_is_edited_manually(
        self,
    ) -> None:
        env = {
            "TELEGRAM_API_ID": "12345",
            "TELEGRAM_API_HASH_B64": encoded("a" * 32),
            "BOT_TOKEN_B64": encoded("12345:abcdefghijklmnopqrstuvwxyz"),
            "ALLOWED_USER_ID": "987654321",
            "CD2_WEBDAV_URL_B64": encoded("http://clouddrive2:19798/dav"),
            "CD2_WEBDAV_USERNAME_B64": encoded("user"),
            "CD2_WEBDAV_PASSWORD_B64": encoded("secret"),
            "CD2_TARGET_PATH_B64": encoded("115/Telegram"),
            "LOCAL_TEMP_BUDGET_GB": "nan",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(RuntimeError, "有限数字"),
        ):
            Settings.from_env()


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = TaskDB(self.root / "tasks.db")

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def make_task(self, message_id: int, size: int) -> dict:
        task, created = self.db.create_task(
            chat_id=1,
            message_id=message_id,
            sender_id=9,
            file_name=f"{message_id}.bin",
            file_size=size,
        )
        self.assertTrue(created)
        return task

    def test_duplicate_message_returns_original_task(self) -> None:
        first = self.make_task(100, 1000)
        second, created = self.db.create_task(
            chat_id=1,
            message_id=100,
            sender_id=9,
            file_name="changed.bin",
            file_size=9999,
        )
        self.assertFalse(created)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["file_size"], 1000)

    def test_online_database_backup_includes_wal_and_passes_integrity_check(self) -> None:
        task = self.make_task(77, 10)
        destination = self.root / "backups" / "tg115.db"
        backup_database(self.db.path, destination)
        with closing(sqlite3.connect(destination)) as copied:
            self.assertEqual(copied.execute("PRAGMA quick_check").fetchone()[0], "ok")
            row = copied.execute(
                "SELECT file_name FROM tasks WHERE id=?", (task["id"],)
            ).fetchone()
            self.assertEqual(row[0], task["file_name"])

    def test_same_telegram_media_id_is_not_downloaded_twice(self) -> None:
        first, created = self.db.create_task(
            chat_id=1,
            message_id=1,
            sender_id=9,
            media_key="document:123456",
            file_name="first.mp4",
            file_size=1000,
        )
        self.assertTrue(created)
        second, created = self.db.create_task(
            chat_id=1,
            message_id=2,
            sender_id=9,
            media_key="document:123456",
            file_name="second.mp4",
            file_size=1000,
        )
        self.assertFalse(created)
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(self.db.counts(), {"queued": 1})

    def test_existing_v1_database_is_migrated_without_losing_tasks(self) -> None:
        self.db.close()
        legacy_path = self.root / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                state TEXT NOT NULL,
                local_path TEXT,
                remote_path TEXT,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                uploaded_bytes INTEGER NOT NULL DEFAULT 0,
                download_retries INTEGER NOT NULL DEFAULT 0,
                upload_retries INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                wait_reason TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                next_retry_at REAL NOT NULL DEFAULT 0,
                UNIQUE(chat_id, message_id)
            );
            INSERT INTO tasks (
                chat_id, message_id, sender_id, file_name, file_size,
                state, created_at, updated_at
            ) VALUES (1, 1, 9, 'legacy.bin', 10, 'queued', 1, 1);
            """
        )
        connection.commit()
        connection.close()

        migrated = TaskDB(legacy_path)
        columns = {
            row[1]
            for row in migrated._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        self.assertIn("media_key", columns)
        self.assertIn("transfer_mode", columns)
        self.assertEqual(migrated.get(1)["transfer_mode"], "local")
        self.assertEqual(migrated.get(1)["file_name"], "legacy.bin")
        migrated.close()
        self.db = TaskDB(self.root / "tasks.db")

    def test_atomic_budget_reservation(self) -> None:
        gb = 1024**3
        first = self.make_task(1, 4 * gb)
        second = self.make_task(2, 4 * gb)
        ok, _ = self.db.reserve(
            first["id"],
            budget_bytes=6 * gb,
            current_free_bytes=50 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertTrue(ok)
        ok, reason = self.db.reserve(
            second["id"],
            budget_bytes=6 * gb,
            current_free_bytes=50 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertFalse(ok)
        self.assertIn("本地临时空间", reason)
        self.assertEqual(self.db.used_local_bytes(), 4 * gb)

    def test_twenty_gb_budget_batches_fifteen_four_gb_tasks(self) -> None:
        gb = 1024**3
        tasks = [self.make_task(index, 4 * gb) for index in range(1, 16)]
        results = [
            self.db.reserve(
                task["id"],
                budget_bytes=20 * gb,
                current_free_bytes=50 * gb,
                minimum_free_bytes=20 * gb,
            )
            for task in tasks
        ]
        self.assertEqual(sum(ok for ok, _ in results), 5)
        self.assertEqual(self.db.counts()["queued"], 10)

    def test_twenty_gb_budget_batches_seven_three_gb_tasks(self) -> None:
        gb = 1024**3
        tasks = [self.make_task(index, 3 * gb) for index in range(1, 8)]
        results = [
            self.db.reserve(
                task["id"],
                budget_bytes=20 * gb,
                current_free_bytes=50 * gb,
                minimum_free_bytes=20 * gb,
            )
            for task in tasks
        ]
        self.assertEqual(sum(ok for ok, _ in results), 6)
        self.assertEqual(self.db.counts()["queued"], 1)

    def test_real_disk_safety_line(self) -> None:
        gb = 1024**3
        task = self.make_task(1, 4 * gb)
        ok, reason = self.db.reserve(
            task["id"],
            budget_bytes=20 * gb,
            current_free_bytes=22 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertFalse(ok)
        self.assertIn("磁盘", reason)

    def test_single_file_larger_than_budget_switches_to_stream_mode(self) -> None:
        gb = 1024**3
        task = self.make_task(1, 21 * gb)
        ok, reason = self.db.reserve(
            task["id"],
            budget_bytes=20 * gb,
            current_free_bytes=50 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertTrue(ok)
        self.assertIn("流式模式", reason)
        reserved = self.db.get(task["id"])
        self.assertEqual(reserved["state"], "reserved")
        self.assertEqual(reserved["transfer_mode"], "stream")
        self.assertEqual(self.db.used_local_bytes(), 0)

    def test_large_stream_file_waits_at_real_disk_safety_line(self) -> None:
        gb = 1024**3
        task = self.make_task(1, 100 * gb)
        ok, reason = self.db.reserve(
            task["id"],
            budget_bytes=20 * gb,
            current_free_bytes=20 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertFalse(ok)
        self.assertIn("磁盘", reason)
        self.assertEqual(self.db.get(task["id"])["transfer_mode"], "local")

    def test_disk_safety_counts_reserved_growth_in_same_cycle(self) -> None:
        gb = 1024**3
        tasks = [self.make_task(index, 4 * gb) for index in range(1, 6)]
        results = [
            self.db.reserve(
                task["id"],
                budget_bytes=20 * gb,
                current_free_bytes=35 * gb,
                minimum_free_bytes=20 * gb,
            )
            for task in tasks
        ]
        self.assertEqual(sum(ok for ok, _ in results), 3)
        self.assertEqual(self.db.used_local_bytes(), 12 * gb)
        self.assertIn("磁盘", results[3][1])

    def test_disk_safety_does_not_double_count_complete_local_file(self) -> None:
        gb = 1024**3
        first = self.make_task(1, 4 * gb)
        second = self.make_task(2, 4 * gb)
        ok, _ = self.db.reserve(
            first["id"],
            budget_bytes=20 * gb,
            current_free_bytes=50 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertTrue(ok)
        self.db.update(
            first["id"],
            state="waiting_upload",
            downloaded_bytes=4 * gb,
        )
        ok, _ = self.db.reserve(
            second["id"],
            budget_bytes=20 * gb,
            current_free_bytes=46 * gb,
            minimum_free_bytes=20 * gb,
        )
        self.assertTrue(ok)

    def test_restart_recovery_keeps_complete_local_file(self) -> None:
        task = self.make_task(1, 10)
        local = self.root / "downloads" / "1-file.bin"
        local.parent.mkdir()
        local.write_bytes(b"0123456789")
        self.db.update(
            task["id"], state="uploading", local_path=str(local)
        )
        result = self.db.recover(local.parent)
        recovered = self.db.get(task["id"])
        self.assertEqual(result["waiting_upload"], 1)
        self.assertEqual(recovered["state"], "waiting_upload")
        self.assertEqual(recovered["upload_retries"], 0)

    def test_restart_recovery_requeues_truncated_local_file(self) -> None:
        task = self.make_task(1, 10)
        local = self.root / "downloads" / "1-file.bin"
        local.parent.mkdir()
        local.write_bytes(b"too-short")
        self.db.update(
            task["id"],
            state="uploading",
            local_path=str(local),
            downloaded_bytes=9,
            download_retries=2,
            upload_retries=2,
        )
        result = self.db.recover(local.parent)
        recovered = self.db.get(task["id"])
        self.assertEqual(result["queued"], 1)
        self.assertEqual(recovered["state"], "queued")
        self.assertIsNone(recovered["local_path"])
        self.assertEqual(recovered["downloaded_bytes"], 0)
        self.assertEqual(recovered["download_retries"], 0)
        self.assertEqual(recovered["upload_retries"], 0)

    def test_restart_recovers_file_renamed_before_database_commit(self) -> None:
        task = self.make_task(1, 10)
        downloads = self.root / "downloads"
        downloads.mkdir()
        part = downloads / f"{task['id']}.part"
        final = downloads / f"{task['id']}-{task['file_name']}"
        self.db.update(
            task["id"],
            state="downloading",
            local_path=str(part),
            downloaded_bytes=10,
        )
        final.write_bytes(b"0123456789")

        result = self.db.recover(downloads)
        recovered = self.db.get(task["id"])

        self.assertEqual(result["waiting_upload"], 1)
        self.assertEqual(recovered["state"], "waiting_upload")
        self.assertEqual(recovered["local_path"], str(final))
        self.assertTrue(final.exists())

    def test_missing_retained_file_is_requeued_and_releases_budget(self) -> None:
        gb = 1024**3
        task = self.make_task(1, 8 * gb)
        self.db.update(
            task["id"],
            state="verification_failed_retained",
            local_path=str(self.root / "missing.bin"),
        )
        self.assertEqual(self.db.used_local_bytes(), 8 * gb)

        result = self.db.recover(self.root / "downloads")

        self.assertEqual(result["queued"], 1)
        self.assertEqual(self.db.get(task["id"])["state"], "queued")
        self.assertEqual(self.db.used_local_bytes(), 0)

    def test_only_completed_task_can_be_confirmed_for_115(self) -> None:
        completed = self.make_task(20, 10)
        active = self.make_task(21, 10)
        self.db.update(
            completed["id"],
            state="completed",
            remote_path="video.mp4",
            uploaded_bytes=10,
        )
        self.db.update(active["id"], state="uploading")

        result, confirmed = self.db.confirm_115(completed["id"])
        self.assertEqual(result, "confirmed")
        self.assertEqual(confirmed["state"], "confirmed")
        self.assertEqual(confirmed["remote_path"], "video.mp4")

        result, repeated = self.db.confirm_115(completed["id"])
        self.assertEqual(result, "already")
        self.assertEqual(repeated["state"], "confirmed")

        result, unchanged = self.db.confirm_115(active["id"])
        self.assertEqual(result, "invalid")
        self.assertEqual(unchanged["state"], "uploading")
        self.assertEqual(self.db.get(active["id"])["state"], "uploading")

    def test_restart_recovery_does_not_change_confirmed_task(self) -> None:
        task = self.make_task(30, 10)
        self.db.update(
            task["id"],
            state="completed",
            remote_path="confirmed.mp4",
            uploaded_bytes=10,
        )
        result, _ = self.db.confirm_115(task["id"])
        self.assertEqual(result, "confirmed")

        recovered = self.db.recover(self.root / "downloads")

        self.assertEqual(recovered, {"queued": 0, "waiting_upload": 0, "failed": 0})
        current = self.db.get(task["id"])
        self.assertEqual(current["state"], "confirmed")
        self.assertEqual(current["remote_path"], "confirmed.mp4")


class AdaptiveWindowTests(unittest.TestCase):
    def settings(self) -> Settings:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {
                "TELEGRAM_API_ID": "1",
                "TELEGRAM_API_HASH_B64": encoded("a" * 32),
                "BOT_TOKEN_B64": encoded("1:" + "a" * 25),
                "ALLOWED_USER_ID": "2",
                "CD2_WEBDAV_URL_B64": encoded("http://cd2/dav"),
                "CD2_WEBDAV_USERNAME_B64": encoded("u"),
                "CD2_WEBDAV_PASSWORD_B64": encoded("p"),
                "CD2_TARGET_PATH_B64": encoded("115/T"),
                "DATA_DIR": str(root / "data"),
                "DOWNLOAD_DIR": str(root / "downloads"),
                "LOG_DIR": str(root / "logs"),
                "RCLONE_CONFIG_PATH": str(root / "rclone.conf"),
            }
            with patch.dict(os.environ, env, clear=True):
                return Settings.from_env()

    @staticmethod
    def snapshot(cpu: float, memory_mb: int = 2048) -> ResourceSnapshot:
        return ResourceSnapshot(
            cpu_percent=cpu,
            memory_available=memory_mb * 1024**2,
            swap_used=0,
            disk_free=30 * 1024**3,
            network_bytes_per_second=100 * 1024**2,
            sampled_at=0,
        )

    def test_ramps_up_and_stops_when_destination_unhealthy(self) -> None:
        window = AdaptiveWindow(self.settings(), "download")
        self.assertEqual(
            window.update(
                self.snapshot(20),
                recent_errors=0,
                destination_healthy=True,
                demand_present=True,
            ),
            2,
        )
        self.assertEqual(
            window.update(
                self.snapshot(20),
                recent_errors=0,
                destination_healthy=False,
                demand_present=True,
            ),
            0,
        )

    def test_sustained_pressure_shrinks_window(self) -> None:
        window = AdaptiveWindow(self.settings(), "upload")
        window.value = 8
        window.update(
            self.snapshot(95),
            recent_errors=0,
            destination_healthy=True,
            demand_present=True,
        )
        reduced = window.update(
            self.snapshot(95),
            recent_errors=0,
            destination_healthy=True,
            demand_present=True,
        )
        self.assertEqual(reduced, 4)

    def test_download_stops_but_upload_continues_at_disk_safety_line(self) -> None:
        settings = self.settings()
        download = AdaptiveWindow(settings, "download")
        upload = AdaptiveWindow(settings, "upload")
        snapshot = self.snapshot(20)
        snapshot = ResourceSnapshot(
            cpu_percent=snapshot.cpu_percent,
            memory_available=snapshot.memory_available,
            swap_used=snapshot.swap_used,
            disk_free=settings.min_free_disk_bytes,
            network_bytes_per_second=snapshot.network_bytes_per_second,
            sampled_at=snapshot.sampled_at,
        )
        self.assertEqual(
            download.update(
                snapshot,
                recent_errors=0,
                destination_healthy=True,
                demand_present=True,
            ),
            0,
        )
        self.assertGreater(
            upload.update(
                snapshot,
                recent_errors=0,
                destination_healthy=True,
                demand_present=True,
            ),
            0,
        )

    def test_idle_service_does_not_preinflate_concurrency_window(self) -> None:
        window = AdaptiveWindow(self.settings(), "download")
        for _ in range(1000):
            window.update(
                self.snapshot(5),
                recent_errors=0,
                destination_healthy=True,
                demand_present=False,
            )
        self.assertEqual(window.value, 1)

    def test_memory_ceiling_has_no_fixed_256_task_cap(self) -> None:
        self.assertEqual(
            AdaptiveWindow._memory_derived_ceiling(16 * 1024**3),
            512,
        )


class RcloneConfigTests(unittest.TestCase):
    def test_blank_target_writes_directly_to_webdav_root(self) -> None:
        settings = SimpleNamespace(
            rclone_config_path=Path("rclone.conf"),
            cd2_target="",
            cd2_password="password",  # pragma: allowlist secret
        )
        client = RcloneClient(settings)
        self.assertEqual(client.remote(), "cd2:")
        self.assertEqual(client.remote("video.mp4"), "cd2:video.mp4")

    def test_target_path_normalization_and_root_preparation(self) -> None:
        for target, expected in (
            ("", "cd2:video.mp4"),
            ("Telegram", "cd2:Telegram/video.mp4"),
            ("Media/Telegram", "cd2:Media/Telegram/video.mp4"),
            ("/Telegram", "cd2:Telegram/video.mp4"),
        ):
            with self.subTest(target=target):
                settings = SimpleNamespace(cd2_target=target)
                client = RcloneClient(settings)
                client.ensure_config = AsyncMock()
                client._run = AsyncMock(return_value=(0, "", ""))
                self.assertEqual(client.remote("video.mp4"), expected)
                asyncio.run(client.prepare_destination())
                commands = [call.args[0] for call in client._run.call_args_list]
                self.assertEqual(commands, ["lsd"] if not target else ["mkdir", "lsd"])
                client._run.reset_mock()
                client.prepare_destination = AsyncMock()
                asyncio.run(client.upload(Path("sample.bin"), "video.mp4"))
                self.assertEqual(client._run.call_args.args[2], expected)

    def test_existing_config_is_reconciled_with_new_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "rclone.conf"
            config_path.write_text(
                "[cd2]\nurl = http://old.example/dav\nuser = old\n",
                encoding="utf-8",
            )
            settings = SimpleNamespace(
                rclone_config_path=config_path,
                cd2_url="http://new.example/dav",
                cd2_user="new-user",
                cd2_password="new-password",  # pragma: allowlist secret
                cd2_target="115/Telegram",
            )
            client = RcloneClient(settings)
            calls: list[tuple[str, ...]] = []

            async def fake_run(
                *args: str,
                timeout: float | None = None,
                check: bool = True,
            ) -> tuple[int, str, str]:
                calls.append(args)
                return 0, "", ""

            client._run = fake_run  # type: ignore[method-assign]
            asyncio.run(client.ensure_config())

            self.assertTrue(calls)
            flattened = [item for call in calls for item in call]
            self.assertIn("update", flattened)
            self.assertIn("http://new.example/dav", flattened)
            self.assertIn("new-user", flattened)
            self.assertIn("new-password", flattened)

    def test_exists_distinguishes_missing_from_remote_failure(self) -> None:
        settings = SimpleNamespace(
            rclone_config_path=Path("rclone.conf"),
            cd2_target="115/Telegram",
            cd2_password="password",  # pragma: allowlist secret
        )
        client = RcloneClient(settings)

        async def missing_run(*args: str, **_: object) -> tuple[int, str, str]:
            return 3, "", "directory not found"

        client._run = missing_run  # type: ignore[method-assign]
        self.assertFalse(asyncio.run(client.exists("missing.mp4")))

        async def missing_file_run(*args: str, **_: object) -> tuple[int, str, str]:
            return 4, "", "file not found"

        client._run = missing_file_run  # type: ignore[method-assign]
        self.assertFalse(asyncio.run(client.exists("missing-file.mp4")))

        async def failed_run(*args: str, **_: object) -> tuple[int, str, str]:
            return 1, "", "connection refused"

        client._run = failed_run  # type: ignore[method-assign]
        with self.assertRaisesRegex(RcloneError, "connection refused"):
            asyncio.run(client.exists("unknown.mp4"))

    def test_stream_upload_uses_rcat_with_exact_size_and_backpressure(self) -> None:
        settings = SimpleNamespace(
            rclone_config_path=Path("rclone.conf"),
            cd2_target="Telegram",
            cd2_password="password",  # pragma: allowlist secret
        )
        client = RcloneClient(settings)
        client._config_ready = True
        client.prepare_destination = AsyncMock()

        class Stdin:
            def __init__(self) -> None:
                self.data = bytearray()

            def write(self, data: bytes) -> None:
                self.data.extend(data)

            async def drain(self) -> None:
                return None

            def close(self) -> None:
                return None

            async def wait_closed(self) -> None:
                return None

        class Process:
            def __init__(self) -> None:
                self.stdin = Stdin()
                self.stdout = asyncio.StreamReader()
                self.stderr = asyncio.StreamReader()
                self.stdout.feed_eof()
                self.stderr.feed_eof()
                self.returncode = None

            async def wait(self) -> int:
                self.returncode = 0
                return 0

        async def scenario() -> tuple[tuple[object, ...], bytearray]:
            process = Process()
            spawn = AsyncMock(return_value=process)
            with patch(
                "tg2cloud.storage.rclone.asyncio.create_subprocess_exec",
                new=spawn,
            ):
                stream = await client.open_upload_stream("large.bin", 7)
                await stream.write(b"123")
                await stream.write(b"4567")
                await stream.finish()
            return spawn.await_args.args, process.stdin.data

        arguments, data = asyncio.run(scenario())
        self.assertIn("rcat", arguments)
        self.assertIn("cd2:Telegram/large.bin", arguments)
        size_index = arguments.index("--size")
        self.assertEqual(arguments[size_index + 1], "7")
        self.assertEqual(data, b"1234567")


class DestinationVerificationTests(unittest.TestCase):
    class FakeRclone:
        def __init__(self, *, wrong_size: bool = False):
            self.files: dict[str, bytes] = {}
            self.authenticated = False
            self.prepared = False
            self.wrong_size = wrong_size
            self.removed: list[str] = []

        async def verify_authentication(self) -> None:
            self.authenticated = True

        async def prepare_destination(self) -> None:
            self.prepared = True

        async def upload(self, local_path: Path, remote_path: str) -> None:
            self.files[remote_path] = local_path.read_bytes()

        async def remote_size(self, remote_path: str) -> int:
            size = len(self.files[remote_path])
            return size - 1 if self.wrong_size else size

        async def move(self, source: str, destination: str) -> None:
            self.files[destination] = self.files.pop(source)

        async def remove(self, remote_path: str) -> None:
            self.removed.append(remote_path)
            self.files.pop(remote_path, None)

        async def exists(self, remote_path: str) -> bool:
            return remote_path in self.files

    def test_real_destination_verification_writes_moves_checks_and_cleans(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(data_dir=Path(temp))
            client = self.FakeRclone()
            reports: list[str] = []
            remote_path = asyncio.run(
                verify_destination(settings, client, reports.append)  # type: ignore[arg-type]
            )
            self.assertTrue(client.authenticated)
            self.assertTrue(client.prepared)
            self.assertTrue(remote_path.endswith(".ok"))
            self.assertEqual(client.files, {})
            self.assertEqual(client.removed, [remote_path])
            self.assertEqual(list(Path(temp).iterdir()), [])
            for marker in (
                "TG2CLOUD_WEBDAV=OK",
                "TG2CLOUD_UPLOAD=OK",
                "TG2CLOUD_RENAME=OK",
                "TG2CLOUD_DELETE=OK",
            ):
                self.assertIn(marker, reports)
            self.assertTrue(all(marker.startswith("TG2CLOUD_") for marker in reports))

    def test_real_destination_verification_fails_closed_and_cleans(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(data_dir=Path(temp))
            client = self.FakeRclone(wrong_size=True)
            with self.assertRaisesRegex(RuntimeError, "大小错误"):
                asyncio.run(
                    verify_destination(settings, client)  # type: ignore[arg-type]
                )
            self.assertEqual(client.files, {})
            self.assertTrue(any(path.endswith(".uploading") for path in client.removed))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_destination_verification_reports_auth_failure_before_listing(
        self,
    ) -> None:
        class AuthenticationFailure(self.FakeRclone):
            async def verify_authentication(self) -> None:
                raise RcloneError("401 Unauthorized")

        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(data_dir=Path(temp))
            client = AuthenticationFailure()
            report: list[str] = []
            with self.assertRaises(DestinationVerificationError) as raised:
                asyncio.run(
                    verify_destination(  # type: ignore[arg-type]
                        settings, client, report.append
                    )
                )
            self.assertEqual(raised.exception.stage, "AUTH")
            self.assertEqual(report, [])
            self.assertFalse(client.prepared)
            self.assertEqual(client.removed, [])
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_destination_verification_does_not_cleanup_uncreated_remote_files(
        self,
    ) -> None:
        class ListingFailure(self.FakeRclone):
            async def prepare_destination(self) -> None:
                raise RcloneError("429 Too Many Requests")

        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(data_dir=Path(temp))
            client = ListingFailure()
            report: list[str] = []
            with self.assertRaises(DestinationVerificationError) as raised:
                asyncio.run(
                    verify_destination(  # type: ignore[arg-type]
                        settings, client, report.append
                    )
                )
            self.assertEqual(raised.exception.stage, "LIST")
            self.assertEqual(report, ["TG2CLOUD_WEBDAV_AUTH=OK"])
            self.assertEqual(client.removed, [])
            self.assertEqual(list(Path(temp).iterdir()), [])


class FlatDestinationTests(unittest.TestCase):
    class FakeRclone:
        def __init__(self, existing: set[str]):
            self.existing = existing

        async def exists(self, remote_path: str) -> bool:
            return remote_path in self.existing

    def service(self, existing: set[str]) -> TransferService:
        service = TransferService.__new__(TransferService)
        service.rclone = self.FakeRclone(existing)  # type: ignore[assignment]
        return service

    def test_new_file_is_saved_directly_in_configured_target(self) -> None:
        service = self.service(set())
        remote = asyncio.run(
            service._choose_remote_final("video.mp4", task_id=7)
        )
        self.assertEqual(remote, "video.mp4")

    def test_duplicate_name_gets_task_suffix_without_date_folders(self) -> None:
        service = self.service({"video.mp4"})
        remote = asyncio.run(
            service._choose_remote_final("video.mp4", task_id=7)
        )
        self.assertEqual(remote, "video (task-7).mp4")

    def test_repeated_duplicate_gets_incremented_suffix(self) -> None:
        service = self.service({"video.mp4", "video (task-7).mp4"})
        remote = asyncio.run(
            service._choose_remote_final("video.mp4", task_id=7)
        )
        self.assertEqual(remote, "video (task-7-2).mp4")


class UploadRecoveryTests(unittest.TestCase):
    class FakeDB:
        def __init__(self, task: dict[str, object]):
            self.task = task

        def get(self, _: int) -> dict[str, object]:
            return dict(self.task)

        def update(self, _: int, **fields: object) -> None:
            self.task.update(fields)

        def transition(self, _: int, new_state: str, **fields: object) -> None:
            self.task.update(state=new_state, **fields)

    @staticmethod
    def service(task: dict[str, object]) -> TransferService:
        service = TransferService.__new__(TransferService)
        service.settings = SimpleNamespace(max_retries=1)
        service.db = UploadRecoveryTests.FakeDB(task)  # type: ignore[assignment]
        service.db.staging_name = lambda task_id, name: f".uploading-{task_id}-{name}"
        service._finalize_lock = asyncio.Lock()
        service.recent_upload_errors = deque(maxlen=50)
        service.log = Mock()

        async def notify(_: str) -> None:
            return None

        service._notify = notify  # type: ignore[method-assign]
        return service

    def test_truncated_file_is_removed_and_automatically_requeued(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "1-video.mp4"
            local.write_bytes(b"123")
            task: dict[str, object] = {
                "id": 1,
                "file_name": "video.mp4",
                "file_size": 4,
                "local_path": str(local),
                "remote_path": None,
                "upload_retries": 0,
            }
            service = self.service(task)
            asyncio.run(service._upload_one(1))
            self.assertFalse(local.exists())
            self.assertEqual(service.db.task["state"], "queued")
            self.assertIn("自动重新排队", str(service.db.task["wait_reason"]))

    def test_completed_remote_move_is_resumed_without_reupload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "1-video.mp4"
            local.write_bytes(b"1234")
            task: dict[str, object] = {
                "id": 1,
                "file_name": "video.mp4",
                "file_size": 4,
                "local_path": str(local),
                "remote_path": "video.mp4",
                "upload_retries": 0,
            }
            service = self.service(task)

            class FakeRclone:
                async def exists(self, _: str) -> bool:
                    return True

                async def remote_size(self, _: str) -> int:
                    return 4

                async def upload(self, *_: object) -> None:
                    raise AssertionError("不应重新上传")

                async def remove(self, _: str) -> None:
                    return None

            service.rclone = FakeRclone()  # type: ignore[assignment]
            asyncio.run(service._upload_one(1))
            self.assertFalse(local.exists())
            self.assertEqual(service.db.task["state"], "completed")
            self.assertEqual(service.db.task["remote_path"], "video.mp4")

    def test_restart_after_local_delete_finishes_cleanup_without_reupload(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing_local = Path(temp) / "already-deleted.mp4"
            task: dict[str, object] = {
                "id": 1,
                "state": "cleanup_pending",
                "file_name": "video.mp4",
                "file_size": 4,
                "local_path": str(missing_local),
                "remote_path": "video.mp4",
                "upload_retries": 0,
            }
            service = self.service(task)

            class FakeRclone:
                async def exists(self, _: str) -> bool:
                    return True

                async def remote_size(self, _: str) -> int:
                    return 4

                async def upload(self, *_: object) -> None:
                    raise AssertionError("不应重新上传")

            service.rclone = FakeRclone()  # type: ignore[assignment]
            asyncio.run(service._upload_one(1))
            self.assertEqual(service.db.task["state"], "completed")
            self.assertIsNone(service.db.task["local_path"])

    def test_local_cleanup_failure_is_persisted_and_automatically_retryable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "1-video.mp4"
            local.write_bytes(b"1234")
            task: dict[str, object] = {
                "id": 1,
                "state": "finalizing",
                "file_name": "video.mp4",
                "file_size": 4,
                "local_path": str(local),
                "remote_path": "video.mp4",
                "upload_retries": 0,
            }
            service = self.service(task)
            with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
                asyncio.run(
                    service._complete_cloud_receive(
                        1, task, local, "video.mp4"
                    )
                )
            self.assertEqual(service.db.task["state"], "cleanup_pending")
            self.assertIn("本地文件暂时无法清理", str(service.db.task["error"]))
            self.assertGreater(float(service.db.task["next_retry_at"]), 0)

    def test_failed_upload_preserves_uncertain_remote_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "1-video.mp4"
            local.write_bytes(b"1234")
            task: dict[str, object] = {
                "id": 1,
                "file_name": "video.mp4",
                "file_size": 4,
                "local_path": str(local),
                "remote_path": None,
                "upload_retries": 0,
            }
            service = self.service(task)

            class FakeRclone:
                def __init__(self) -> None:
                    self.removed: list[str] = []

                async def upload(self, *_: object, **__: object) -> None:
                    raise RuntimeError("simulated upload failure")

                async def remove(self, remote: str) -> None:
                    self.removed.append(remote)

            fake = FakeRclone()
            service.rclone = fake  # type: ignore[assignment]
            asyncio.run(service._upload_one(1))
            self.assertEqual(service.db.task["state"], "upload_failed_retained")
            self.assertEqual(fake.removed, [])
            self.assertTrue(local.exists())


class PayloadTests(unittest.TestCase):
    def test_active_container_namespace_and_code_read_permissions(self) -> None:
        dockerfile = (PAYLOAD / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("PYTHONPATH=/opt/tg2cloud", dockerfile)
        self.assertIn("WORKDIR /opt/tg2cloud", dockerfile)
        self.assertIn("groupadd --system --gid 10001 tg2cloud", dockerfile)
        self.assertIn("--shell /usr/sbin/nologin tg2cloud", dockerfile)
        self.assertNotIn("tg115", dockerfile)
        self.assertLess(dockerfile.index("COPY app ./app"), dockerfile.index("RUN chmod -R a+rX app"))
        self.assertLess(dockerfile.index("RUN chmod -R a+rX app"), dockerfile.index("USER 10001:10001"))
        self.assertNotIn("chmod -R 777", dockerfile)

    def test_runtime_logger_is_tg2cloud_and_persistent_paths_are_unchanged(self) -> None:
        settings = SimpleNamespace(
            log_dir=Mock(), data_dir=Path("/data"), download_dir=Path("/downloads"),
            rclone_config_path=Path("/config/rclone/rclone.conf"),
            api_id=123456, api_hash="FAKE_LOCAL_TEST_API_HASH",
        )
        with patch("tg2cloud.app.setup_logging"), patch("tg2cloud.transfer.service.logging.getLogger") as get_logger, \
                patch("tg2cloud.app.TaskDB") as database, patch("tg2cloud.telegram.client.TelegramClient") as telegram, \
                patch("tg2cloud.app.RcloneClient"), patch("tg2cloud.app.ResourceMonitor"), \
                patch("tg2cloud.transfer.service.AdaptiveWindow"), patch.object(TransferService, "_register_handlers"):
            TransferService(settings)
        get_logger.assert_called_once_with("tg2cloud")
        database.assert_called_once_with(Path("/data/tg115.db"))
        self.assertEqual(telegram.call_args.args[0], str(Path("/data/bot")))

    def test_new_log_name_does_not_rename_or_delete_old_logs(self) -> None:
        with tempfile.TemporaryDirectory() as private:
            directory = Path(private)
            legacy = directory / "tg115.log"
            legacy.write_text("retained old log", encoding="utf-8")
            with patch("tg2cloud.transfer.service.logging.getLogger"), patch("tg2cloud.logging_setup.RotatingFileHandler") as handler:
                setup_logging(SimpleNamespace(log_dir=directory))
            self.assertEqual(handler.call_args.args[0], directory / "tg2cloud.log")
            self.assertEqual(legacy.read_text(encoding="utf-8"), "retained old log")

    def test_script_and_server_versions_match(self) -> None:
        self.assertRegex(RELEASE_VERSION, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertEqual(__version__, RELEASE_VERSION)

    def test_required_payload_files_exist(self) -> None:
        for relative in (
            "Dockerfile",
            ".dockerignore",
            "docker-compose.yml",
            "remote_install.sh",
            "repair_clouddrive_network.sh",
            "manage.sh",
            "backup_retention.sh",
            "app/main.py",
            "app/tg2cloud/telegram/commands.py",
            "app/tg2cloud/transfer/ports.py",
            "app/tg2cloud/domain/states.py",
            "app/deployment_check.py",
            "app/backup_database.py",
            "app/tg2cloud/persistence/sqlite.py",
            "app/tg2cloud/domain/naming.py",
            "app/tg2cloud/monitoring/resources.py",
            "app/tg2cloud/storage/rclone.py",
            "app/verify_destination.py",
        ):
            self.assertTrue((PAYLOAD / relative).is_file(), relative)


    def test_container_images_are_pinned_and_redeploy_does_not_pull_latest(self) -> None:
        compose = (PAYLOAD / "docker-compose.yml").read_text(encoding="utf-8")
        dockerfile = (PAYLOAD / "Dockerfile").read_text(encoding="utf-8")
        remote_install = (PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        manage = (PAYLOAD / "manage.sh").read_text(encoding="utf-8")
        self.assertRegex(
            compose,
            r"cloudnas/clouddrive2@sha256:[0-9a-f]{64}",
        )
        self.assertNotIn("cloudnas/clouddrive2:latest", compose)
        self.assertRegex(
            dockerfile.splitlines()[0],
            r"^FROM python:3\.12-slim-trixie@sha256:[0-9a-f]{64}$",
        )
        self.assertNotIn("build --pull", remote_install)
        self.assertNotIn("build --pull", manage)
        self.assertNotIn("get.docker.com", remote_install)
        self.assertIn("download.docker.com/linux/${ID}", remote_install)

    def test_existing_clouddrive_is_migrated_and_hard_checked(self) -> None:
        remote_install = (PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        repair = (PAYLOAD / "repair_clouddrive_network.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("sed -i 's/\\r$//'", remote_install)
        self.assertIn("{{.Names}}|{{.Image}}|{{.Ports}}", remote_install)
        self.assertIn("tolower($2) ~ /cloudnas\\/clouddrive2", remote_install)
        self.assertIn("拒绝自动修改", remote_install)
        self.assertNotIn(
            "tolower($0) ~ /clouddrive2/ || $0 ~ /:19798->/",
            remote_install,
        )
        self.assertIn("repair_clouddrive_network.sh", remote_install)
        self.assertLess(
            repair.index("{{.Names}}|{{.Image}}|{{.Ports}}"),
            repair.index("当前配置没有启用由 VPS 管理 CloudDrive2"),
        )
        self.assertIn('DEPLOY_CLOUDDRIVE2="${DEPLOY_CLOUDDRIVE2%$\'\\r\'}"', repair)
        self.assertIn('CD2_NETWORK_MODE="$(', repair)
        self.assertIn("{{.HostConfig.NetworkMode}}", repair)
        self.assertIn('network_mode: " network_mode', repair)
        self.assertIn("http://127.0.0.1:19798/dav", repair)
        self.assertIn("for url_key in WEBDAV_URL_B64 CD2_WEBDAV_URL_B64", repair)
        self.assertIn('CD2_ENDPOINT_HOST="127.0.0.1"', repair)
        self.assertIn("recover_webdav_credentials", repair)
        self.assertIn("/opt/tg2cloud-clouddrive2-backups", repair)
        self.assertIn("保留当前根目录设置", repair)
        self.assertIn('docker network connect --alias "$CD2_MANAGED_CONTAINER"', repair)
        self.assertNotIn("docker network connect --alias clouddrive2 tg115", repair)
        self.assertIn("socket.create_connection((h,19798),5)", repair)
        self.assertIn("python -m app.verify_destination", repair)
        self.assertIn("TG2CLOUD_REPAIR=SUCCESS", repair)
        self.assertIn("remove_program_files", remote_install)

    def test_bot_container_is_non_root_and_restricted(self) -> None:
        compose = (PAYLOAD / "docker-compose.yml").read_text(encoding="utf-8")
        dockerfile = (PAYLOAD / "Dockerfile").read_text(encoding="utf-8")
        remote_install = (PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        self.assertIn('user: "10001:10001"', compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("chown -R 10001:10001", remote_install)
        self.assertIn("umask 077", remote_install)
        self.assertIn('BACKUP_DIR="/opt/tg2cloud-clouddrive2-backups"', remote_install)
        self.assertIn('install -d -m 700 "$BACKUP_DIR"', remote_install)

    def test_legacy_tg115_runtime_is_detected_without_destructive_migration(self) -> None:
        remote_install = (PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        repair = (PAYLOAD / "repair_clouddrive_network.sh").read_text(
            encoding="utf-8"
        )
        for script in (remote_install, repair):
            self.assertIn("/opt/tg115", script)
            self.assertIn("tg115-bot", script)
            self.assertIn("tg115-clouddrive2", script)
            self.assertIn("保留不动", script)
            self.assertIn("重新检测", script)
            self.assertNotIn("docker network connect --alias clouddrive2 tg115", script)
            self.assertNotIn("docker network disconnect tg115", script)
        self.assertIn("不会静默覆盖", remote_install)
        self.assertIn("不会迁移、覆盖或修复", repair)


    def test_docker_build_context_excludes_secrets_and_runtime_data(self) -> None:
        dockerignore = (PAYLOAD / ".dockerignore").read_text(encoding="utf-8")
        self.assertEqual(
            dockerignore.splitlines(),
            ["*", "!Dockerfile", "!requirements.txt", "!app/", "!app/**"],
        )
        self.assertNotIn("!.env", dockerignore)
        self.assertNotIn("!downloads", dockerignore)
        self.assertNotIn("!clouddrive", dockerignore)

    def test_remote_installer_defends_install_path_even_without_gui(self) -> None:
        remote_install = (PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        self.assertIn(
            "^/opt/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$",
            remote_install,
        )
        self.assertIn("安装目录不能包含 . 或 .. 路径段", remote_install)
        self.assertIn('df -Pk -- "$INSTALL_PROBE_PATH"', remote_install)


if __name__ == "__main__":
    unittest.main()
