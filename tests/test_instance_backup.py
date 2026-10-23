"""Real SQLite/archive checks with a simulated, Edition-scoped Docker boundary."""
from __future__ import annotations

import json
import os
import shlex
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tg2cloud.deployment import backup, instances
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence import bundle


class Docker:
    def __init__(self, product):
        self.states = {product.bot_container: {"id": "a" * 64, "running": True},
                       product.storage_container: {"id": "b" * 64, "running": True}}
        self.calls = []
        self.fail = None

    def inspect(self, session, name):
        return dict(self.states[name])

    def run(self, command, **kwargs):
        words = shlex.split(command)
        verb, identity = words[1], words[-1]
        self.calls.append((verb, identity))
        if self.fail == (verb, identity):
            return 1, "not disclosed"
        state = next(item for item in self.states.values() if item["id"] == identity)
        state["running"] = verb == "start"
        return 0, ""


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)

    def fixture(self, key="clouddrive2"):
        product = replace(PRODUCTS[key], install_dir=str(self.root / key))
        directory = Path(product.install_dir)
        for name in ("data", "config/rclone", "downloads", "logs", "openlist/data" if product.is_openlist else "clouddrive/config"):
            (directory / name).mkdir(parents=True, mode=0o700)
        for name in ("data/tg115.db", "data/bot.session"):
            with closing(sqlite3.connect(directory / name)) as conn, conn:
                conn.execute("CREATE TABLE tasks (state TEXT)")
                conn.execute("INSERT INTO tasks VALUES ('completed')")
        (directory / ".env").write_bytes(b"SYNTHETIC_BACKUP_FIXTURE=true\n")
        (directory / "docker-compose.yml").write_text("services: {}\n")
        (directory / "config/rclone/rclone.conf").write_text("[fixture]\n")
        gateway = directory / ("openlist/data" if product.is_openlist else "clouddrive/config")
        (gateway / "settings.json").write_text("{}")
        (directory / "tg2cloud-release.json").write_text('{"tag":"v1.4.2"}')
        (directory / "downloads/keep.bin").write_bytes(b"keep original")
        instance = instances.Instance(product, directory, True, "1.4.2", True)
        docker = Docker(product)
        return instance, docker, self.root / (key + "-snapshots")

    def create(self, instance, docker, target):
        with patch.object(backup, "container", side_effect=docker.inspect):
            return backup.create(instance, docker, target)

    def test_both_editions_backup_database_session_identity_and_restore_exact_services(self):
        for key in PRODUCTS:
            with self.subTest(edition=key):
                instance, docker, target = self.fixture(key)
                archive = self.create(instance, docker, target)
                result = bundle.preflight(archive, target, key, "1.4.2")
                self.assertGreaterEqual(result["files"], 7)
                self.assertEqual(docker.calls, [("stop", "a" * 64), ("stop", "b" * 64),
                                                ("start", "b" * 64), ("start", "a" * 64)])
                self.assertEqual((instance.directory / "downloads/keep.bin").read_bytes(), b"keep original")
                self.assertEqual((instance.directory / ".env").read_bytes(), b"SYNTHETIC_BACKUP_FIXTURE=true\n")
                self.assertTrue(all(state["running"] for state in docker.states.values()))
                lines = next(target.glob("operation-*.jsonl")).read_text().splitlines()
                self.assertEqual(json.loads(lines[-1])["state"], "completed")

    def test_originally_stopped_bot_is_not_started(self):
        instance, docker, target = self.fixture()
        docker.states[instance.product.bot_container]["running"] = False
        self.create(instance, docker, target)
        self.assertEqual(docker.calls, [("stop", "b" * 64), ("start", "b" * 64)])

    def test_busy_task_refuses_before_any_container_mutation(self):
        instance, docker, target = self.fixture()
        with closing(sqlite3.connect(instance.directory / "data/tg115.db")) as conn, conn:
            conn.execute("UPDATE tasks SET state='streaming'")
        with self.assertRaisesRegex(ValueError, "活动传输"):
            self.create(instance, docker, target)
        self.assertFalse(target.exists())
        self.assertFalse(docker.calls)

    def test_failure_or_normal_interrupt_restores_services_and_preserves_original_files(self):
        for failure in (ValueError("synthetic"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                instance, docker, target = self.fixture("openlist" if isinstance(failure, KeyboardInterrupt) else "clouddrive2")
                with patch.object(bundle, "pack", side_effect=failure), self.assertRaises(type(failure)):
                    self.create(instance, docker, target)
                self.assertTrue(all(state["running"] for state in docker.states.values()))
                self.assertFalse(list(target.glob("*.tar.gz")))
                self.assertEqual(json.loads(next(target.glob("operation-*.jsonl")).read_text().splitlines()[-1])["state"],
                                 "failed-services-restored")

    def test_restart_failure_keeps_archive_and_blocks_bot_and_next_backup(self):
        instance, docker, target = self.fixture()
        docker.fail = ("start", "b" * 64)
        with self.assertRaisesRegex(RuntimeError, "恢复未确认"):
            self.create(instance, docker, target)
        self.assertEqual(len(list(target.glob("*.tar.gz"))), 1)
        self.assertNotIn(("start", "a" * 64), docker.calls)
        docker.calls.clear()
        with self.assertRaisesRegex(ValueError, "未完成"):
            self.create(instance, docker, target)
        self.assertFalse(docker.calls)

    def test_symlink_output_overlap_low_space_and_custom_data_path_are_rejected(self):
        instance, docker, target = self.fixture()
        for output in (instance.directory, instance.directory / "snapshots", self.root):
            with self.subTest(output=output.name), self.assertRaises(ValueError):
                self.create(instance, docker, output)
        with patch.object(backup.shutil, "disk_usage", return_value=type("Usage", (), {"free": 1})()), self.assertRaisesRegex(ValueError, "空间不足"):
            self.create(instance, docker, target)
        instance.config["DATA_DIR"] = "/other"
        with self.assertRaisesRegex(ValueError, "自定义"):
            self.create(instance, docker, target)
        self.assertFalse(docker.calls)

    def test_unknown_special_file_and_added_busy_task_after_stop_abort(self):
        instance, docker, target = self.fixture()
        original = backup.active_tasks
        with patch.object(backup, "active_tasks", side_effect=[original(instance.directory), 1]), self.assertRaisesRegex(ValueError, "出现活动"):
            self.create(instance, docker, target)
        self.assertTrue(all(state["running"] for state in docker.states.values()))

    def test_replaced_container_is_never_restarted_by_name(self):
        instance, docker, target = self.fixture()
        original = bundle.pack

        def replace_after_pack(*args):
            original(*args)
            docker.states[instance.product.storage_container]["id"] = "c" * 64

        with patch.object(bundle, "pack", side_effect=replace_after_pack), self.assertRaisesRegex(RuntimeError, "恢复未确认"):
            self.create(instance, docker, target)
        self.assertFalse(any(verb == "start" for verb, _ in docker.calls))

    def test_relative_destination_hardlink_and_unknown_operation_are_rejected(self):
        instance, docker, target = self.fixture()
        with self.assertRaisesRegex(ValueError, "绝对路径"):
            self.create(instance, docker, Path("relative"))
        original = instance.directory / "config/rclone/rclone.conf"
        hardlink = original.with_name("another.conf")
        os.link(original, hardlink)
        try:
            with self.assertRaisesRegex(ValueError, "硬链接"):
                self.create(instance, docker, target)
        finally:
            hardlink.unlink()
        target.mkdir(mode=0o700)
        (target / "operation-unknown.jsonl").write_text('{"state":"completed"}\n')
        with self.assertRaisesRegex(ValueError, "未完成"):
            self.create(instance, docker, target)
        self.assertFalse(docker.calls)

    def test_nested_same_device_bind_mount_and_scan_limit_are_rejected(self):
        instance, docker, target = self.fixture()
        nested = instance.directory / "config/nested"
        nested.mkdir()
        with patch.object(backup, "mountpoints", return_value={nested}), self.assertRaisesRegex(ValueError, "嵌套挂载"):
            self.create(instance, docker, target)
        with patch.object(bundle, "MAX_FILES", 2), self.assertRaisesRegex(ValueError, "上限"):
            self.create(instance, docker, target)
        self.assertFalse(docker.calls)

    def test_wal_capacity_is_included_and_late_capacity_drop_restores_services(self):
        instance, docker, target = self.fixture()
        files = backup.selected_files(instance)
        before = backup.snapshot_bytes(files)
        wal = instance.directory / "data/tg115.db-wal"
        wal.write_bytes(b"synthetic-size-only" * 100)
        self.assertEqual(backup.snapshot_bytes(files), before + wal.stat().st_size)
        wal.unlink()  # Only a synthetic sizing fixture, not a live SQLite WAL.
        free = type("Usage", (), {"free": 10**12})()
        low = type("Usage", (), {"free": 1})()
        with patch.object(backup.shutil, "disk_usage", side_effect=[free, low]), self.assertRaisesRegex(ValueError, "容量发生变化"):
            self.create(instance, docker, target)
        self.assertTrue(all(state["running"] for state in docker.states.values()))
        self.assertFalse(list(target.glob("*.tar.gz")))
