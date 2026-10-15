"""Offline backup, filesystem and compatibility acceptance fixtures."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload_clouddrive2"))

import test_openlist_backup as shell_fixture
from app.backup_bundle import pack, preflight
from app.db import TaskDB
from app.recovery import redact_text
from app.resources import ResourceMonitor
from test_scenarios import make_settings


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        for name in (".env", "docker-compose.yml", "config/rclone/rclone.conf", "openlist/data/config.json"):
            path = self.snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private-fixture", encoding="utf-8")
        for name in ("data/tg115.db", "data/bot.session", "openlist/data/data.db"):
            path = self.snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("CREATE TABLE fixture(value TEXT)")
                conn.commit()
        self.archive = self.root / "bundle.tar.gz"

    def test_bundle_records_coverage_and_drills_without_changing_source(self):
        before = (self.snapshot / "data/tg115.db").read_bytes()
        pack(self.snapshot, self.archive, "openlist", "1.2.0")
        result = preflight(self.archive, self.root, "openlist", "1.2.1")
        self.assertEqual(result["files"], 7)
        self.assertEqual((self.snapshot / "data/tg115.db").read_bytes(), before)
        self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))
        with tarfile.open(self.archive) as tar:
            manifest = json.load(tar.extractfile("manifest.json"))
            self.assertEqual(manifest["excluded"], ["downloads", "logs", "shared-https"])
            self.assertIn("data/bot.session", manifest["files"])
        with self.assertRaises(FileExistsError):
            pack(self.snapshot, self.archive, "openlist", "1.2.0")
        self.assertTrue(self.archive.exists())

    def test_corrupt_database_and_live_sidecar_fail_before_bundle(self):
        (self.snapshot / "data/tg115.db-wal").write_bytes(b"fixture")
        with self.assertRaises(ValueError):
            pack(self.snapshot, self.archive, "openlist", "1.2.0")
        (self.snapshot / "data/tg115.db-wal").unlink()
        (self.snapshot / "data/bot.session").write_bytes(b"truncated")
        with self.assertRaises(sqlite3.DatabaseError):
            pack(self.snapshot, self.archive, "openlist", "1.2.0")
        self.assertFalse(self.archive.exists())

    def test_cross_edition_downgrade_and_low_space_rejected(self):
        pack(self.snapshot, self.archive, "openlist", "1.2.0")
        for edition, target in (("clouddrive2", "1.2.0"), ("openlist", "1.1.0"), ("openlist", "2.0.0")):
            with self.subTest(edition=edition, target=target), self.assertRaises(ValueError):
                preflight(self.archive, self.root, edition, target)
        with patch("app.backup_bundle.shutil.disk_usage", return_value=SimpleNamespace(free=1)), self.assertRaises(ValueError):
            preflight(self.archive, self.root, "openlist", "1.2.0")

    def test_tampering_traversal_and_links_fail_closed(self):
        pack(self.snapshot, self.archive, "openlist", "1.2.0")
        with tarfile.open(self.archive) as tar:
            entries = [(m, tar.extractfile(m).read()) for m in tar if m.isfile()]
        for kind in ("tamper", "traversal", "link", "duplicate", "missing"):
            candidate = self.root / f"{kind}.tar.gz"
            with tarfile.open(candidate, "w:gz") as tar:
                for member, data in entries:
                    if kind == "missing" and member.name == "data/bot.session":
                        continue
                    if kind == "tamper" and member.name == ".env":
                        data = b"x" * len(data)
                    tar.addfile(member, io.BytesIO(data))
                if kind in {"traversal", "link", "duplicate"}:
                    bad = tarfile.TarInfo("../outside" if kind == "traversal" else ".env")
                    if kind == "link":
                        bad.type, bad.linkname = tarfile.SYMTYPE, "../../outside"
                    tar.addfile(bad)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                preflight(candidate, self.root, "openlist", "1.2.0")
        self.assertFalse((self.root / "outside").exists())
        self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))


class ResourceAndMigrationTests(unittest.TestCase):
    def test_filesystem_sampling_groups_same_device_without_summing_capacity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            monitor = ResourceMonitor(root, database=root)
            snapshot = monitor.sample()
            self.assertEqual(len(snapshot.filesystems), 1)
            self.assertIn("database", snapshot.filesystems[0][0])
            self.assertGreater(snapshot.filesystems[0][1], 0)
            with patch.object(Path, "stat", side_effect=[SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2)]), \
                    patch("app.resources.psutil.disk_usage", side_effect=[SimpleNamespace(free=100), SimpleNamespace(free=100), SimpleNamespace(free=5)]):
                snapshot = monitor.sample()
            self.assertEqual([free for _, free in snapshot.filesystems], [100, 5])

    def test_additive_migration_keeps_legacy_data_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.db"
            db = TaskDB(path)
            task, _ = db.create_task(chat_id=1, message_id=1, sender_id=1, media_key="file:1", file_name="fixture", file_size=4)
            db.update(task["id"], state="completed")
            db.close()
            with closing(sqlite3.connect(path)) as conn:
                for name in ("failure_kind", "verified_at", "verification_method"):
                    conn.execute(f"ALTER TABLE tasks DROP COLUMN {name}")
                conn.execute("DROP TABLE task_recoveries")
                conn.execute("DROP TABLE retained_objects")
                conn.commit()
            db = TaskDB(path)
            try:
                saved = db.get(task["id"])
                self.assertEqual(saved["state"], "completed")
                self.assertIsNone(saved["verified_at"])
                self.assertEqual(len(db.events(task["id"])), 1)
                self.assertFalse(db.create_task(chat_id=1, message_id=2, sender_id=1, media_key="file:1", file_name="fixture", file_size=4)[1])
            finally:
                db.close()

    def test_exception_log_redaction_removes_plain_encoded_and_url_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = make_settings(Path(folder))
            text = redact_text(f"{settings.api_hash} {settings.bot_token} password=fixture https://user:fixture@example.invalid/dav?token=fixture", settings)
            for value in (settings.api_hash, settings.bot_token, "fixture", "example.invalid"):
                self.assertNotIn(value, text)


@unittest.skipUnless(shell_fixture.BASH, "Bash required for isolated rollback fixtures")
class CloudRollbackTests(unittest.TestCase):
    def setUp(self):
        self.fixture = shell_fixture.OpenListBackupTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        script = (shell_fixture.ROOT / "payload_clouddrive2/remote_install.sh").read_text(encoding="utf-8")
        self.prefix = script.split('[[ "$(id -u)" -eq 0 ]]', 1)[0]

    def run_rollback(self, mode="ok", extra=""):
        before = 'OLD_IMAGE_ID=old-bot\nOLD_IMAGE_TAG=old-bot:latest\nDATABASE_BACKUP="$test_root/good.db"\n' + extra
        with patch.object(shell_fixture, "PREFIX", self.prefix):
            return self.fixture.execute("rollback_install\n", mode=mode, before=before)

    def test_valid_snapshot_restores_and_starts_old_bot(self):
        result, calls = self.run_rollback()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.fixture.assert_database(self.fixture.database, 2)
        self.assertIn("compose up -d --no-deps --force-recreate tg2cloud-clouddrive2-bot", calls)

    def test_corrupt_copy_and_failed_stop_preserve_database_and_sidecars(self):
        original = self.fixture.database.read_bytes()
        for path, content in self.fixture.preserve_sidecars().items():
            path.write_bytes(content)
        for mode in ("restore-copy-fail", "cannot-stop-bot"):
            result, _ = self.run_rollback(mode)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.fixture.database.read_bytes(), original)
            for path, content in self.fixture.preserve_sidecars().items():
                self.assertEqual(path.read_bytes(), content)
        (self.fixture.root / "bad.db").write_bytes(b"partial")
        result, _ = self.run_rollback(extra='DATABASE_BACKUP="$test_root/bad.db"\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.fixture.database.read_bytes(), original)
