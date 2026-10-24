"""Real SQLite startup/recovery on verified copies; no Docker, Session or network."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tarfile
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tg2cloud.persistence import bundle, rehearsal
from tg2cloud.persistence.migrations import SCHEMA_VERSION
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.version import VERSION


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)

    def fixture(self, edition="openlist"):
        root = self.root / edition
        for name in ("data", "config", "openlist/data" if edition == "openlist" else "clouddrive/config"):
            (root / name).mkdir(parents=True, mode=0o700)
        (root / ".env").write_text("SYNTHETIC_PRIVATE_TOKEN=do-not-execute\n")
        (root / "docker-compose.yml").write_text("services: {}\n")
        (root / "config/rclone.conf").write_text("PRIVATE_FIXTURE_PASSWORD\n")
        gateway = root / ("openlist/data" if edition == "openlist" else "clouddrive/config")
        (gateway / "settings.json").write_text("{}")
        with closing(sqlite3.connect(root / "data/bot.session")) as conn:
            conn.execute("CREATE TABLE synthetic_session (value TEXT)")
        db = TaskDB(root / "data/tg115.db")
        try:
            for number, state in enumerate(("completed", "cancelled", "uploading", "streaming", "upload_failed_retained"), 1):
                task, _ = db.create_task(chat_id=1, sender_id=1, message_id=number,
                                         file_name="PRIVATE_FILE.mp4", file_size=4, media_key=f"media:{number}")
                db.update(task["id"], state=state, local_path=str(self.root / "PRIVATE_OUTSIDE.mp4"),
                          transfer_mode="stream" if state == "streaming" else "local",
                          failure_kind="remote_conflict" if state == "upload_failed_retained" else None)
        finally:
            db.close()
        archive = self.root / (edition + ".tar.gz")
        bundle.pack(root, archive, edition, VERSION)
        return root, archive

    def test_both_editions_rehearse_real_recovery_without_accessing_original_paths(self):
        for edition in ("clouddrive2", "openlist"):
            with self.subTest(edition=edition):
                source, archive = self.fixture(edition)
                before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in source.rglob("*") if path.is_file()}
                original = Path.is_file
                def guard(path, original=original):
                    if path.name == "PRIVATE_OUTSIDE.mp4":
                        raise AssertionError("production local_path must not be inspected")
                    return original(path)
                with patch.object(Path, "is_file", guard), \
                        patch("socket.create_connection", side_effect=AssertionError("no network")), \
                        patch("subprocess.run", side_effect=AssertionError("no services")):
                    report = rehearsal.rehearse(archive, self.root, edition)
                self.assertEqual(report["tasks"], 5)
                self.assertEqual(report["schema"], SCHEMA_VERSION)
                self.assertEqual(report["recovery"], {"queued": 2, "waiting_upload": 0, "failed": 1})
                self.assertEqual(report["session"], "not-loaded")
                serialized = json.dumps(report)
                self.assertNotIn("PRIVATE_", serialized)
                self.assertNotIn(str(source), serialized)
                self.assertEqual(before, {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                          for path in source.rglob("*") if path.is_file()})
                self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))

    def test_temporary_copy_is_removed_on_interrupt_without_touching_archive(self):
        _, archive = self.fixture()
        before = archive.read_bytes()
        with self.assertRaises(KeyboardInterrupt), \
                bundle.verified_snapshot(archive, self.root, "openlist", VERSION) as (copy, _):
            self.assertTrue(copy.is_dir())
            raise KeyboardInterrupt
        self.assertFalse(copy.exists())
        self.assertEqual(before, archive.read_bytes())

    def test_failed_integrity_never_exposes_an_unverified_copy(self):
        _, archive = self.fixture()
        with patch.object(bundle, "checksum", return_value="0" * 64), self.assertRaises(ValueError), \
                bundle.verified_snapshot(archive, self.root, "openlist", VERSION):
            self.fail("unverified copy exposed")
        self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))

    def test_edition_future_version_task_limit_and_private_permissions_fail_closed(self):
        _, archive = self.fixture()
        with self.assertRaises(ValueError):
            rehearsal.rehearse(archive, self.root, "clouddrive2")
        with self.assertRaises(ValueError):
            rehearsal.rehearse(archive, self.root, "openlist", "99.0.0")
        with patch.object(rehearsal, "MAX_TASKS", 1), self.assertRaisesRegex(ValueError, "resource limit"):
            rehearsal.rehearse(archive, self.root, "openlist")
        if os.name == "posix":
            archive.chmod(0o644)
            with self.assertRaises(ValueError):
                rehearsal.rehearse(archive, self.root, "openlist")
        self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))

    def test_cli_uses_safe_summary_and_errors_never_echo_backup_contents(self):
        _, archive = self.fixture()
        out = io.StringIO()
        with redirect_stdout(out):
            code = rehearsal.main([str(archive), "--scratch", str(self.root), "--edition", "openlist", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["tasks"], 5)
        out = io.StringIO()
        with redirect_stdout(out), patch.object(rehearsal, "rehearse", side_effect=ValueError("PRIVATE_CREDENTIAL")):
            self.assertEqual(rehearsal.main([str(archive), "--scratch", str(self.root), "--edition", "openlist"]), 1)
        self.assertNotIn("PRIVATE_CREDENTIAL", out.getvalue())

    def test_future_schema_refused_and_original_archive_preserved(self):
        source, archive = self.fixture()
        with closing(sqlite3.connect(source / "data/tg115.db")) as conn:
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
        future = self.root / "future.tar.gz"
        bundle.pack(source, future, "openlist", VERSION)
        original = future.read_bytes()
        with self.assertRaises(RuntimeError):
            rehearsal.rehearse(future, self.root, "openlist")
        self.assertEqual(future.read_bytes(), original)
        self.assertTrue(archive.exists())

    def test_unrelated_database_is_not_replaced_by_empty_task_history(self):
        path = self.root / "unrelated.db"
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("CREATE TABLE tasks (state TEXT)")
        with self.assertRaisesRegex(ValueError, "unsupported business"):
            rehearsal.task_count(path)

    def test_original_schema_is_migrated_only_in_the_private_copy(self):
        source, _ = self.fixture()
        original = source / "data/tg115.db"
        original.unlink()  # Only this test's disposable synthetic database.
        with closing(sqlite3.connect(original)) as conn:
            conn.execute("""CREATE TABLE tasks (
                id INTEGER PRIMARY KEY, chat_id INTEGER, message_id INTEGER, sender_id INTEGER,
                file_name TEXT, file_size INTEGER, state TEXT, local_path TEXT, remote_path TEXT,
                downloaded_bytes INTEGER DEFAULT 0, uploaded_bytes INTEGER DEFAULT 0,
                download_retries INTEGER DEFAULT 0, upload_retries INTEGER DEFAULT 0,
                error TEXT, wait_reason TEXT, created_at REAL, updated_at REAL, next_retry_at REAL DEFAULT 0)""")
            conn.execute("INSERT INTO tasks(id,chat_id,message_id,sender_id,file_name,file_size,state,created_at,updated_at) "
                         "VALUES(1,1,1,1,'synthetic.mp4',4,'completed',1,1)")
            conn.commit()
        before = original.read_bytes()
        archive = self.root / "legacy-schema.tar.gz"
        bundle.pack(source, archive, "openlist", "1.3.4")
        report = rehearsal.rehearse(archive, self.root, "openlist")
        self.assertEqual(report["schema"], SCHEMA_VERSION)
        self.assertEqual(report["tasks"], 1)
        self.assertEqual(original.read_bytes(), before)

    def test_rehearsal_help_needs_no_bot_dependencies_or_current_directory(self):
        import subprocess
        import sys
        script = Path(__file__).resolve().parents[1] / "src"
        code = ("import sys;sys.path.insert(0," + repr(str(script)) + ");"
                "from tg2cloud.persistence.rehearsal import main;"
                "assert 'telethon' not in sys.modules and 'psutil' not in sys.modules;main(['--help'])")
        result = subprocess.run([sys.executable, "-S", "-B", "-c", code], cwd=self.root,
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_database_startup_closes_connection_before_cleaning_the_copy(self):
        _, archive = self.fixture()
        opened = []
        def fail(db):
            opened.append(db._conn)
            raise ValueError("synthetic failed startup")
        with patch.object(TaskDB, "_initialize", fail), self.assertRaises(ValueError):
            rehearsal.rehearse(archive, self.root, "openlist")
        self.assertEqual(len(opened), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")
        self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))

    def test_cli_interruption_is_explicit_and_does_not_claim_success(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(rehearsal, "rehearse", side_effect=KeyboardInterrupt):
            code = rehearsal.main(["synthetic.tar.gz", "--scratch", str(self.root), "--edition", "openlist"])
        self.assertEqual(code, 130)
        self.assertIn("已中断", output.getvalue())
        self.assertNotIn("通过", output.getvalue())

    def test_manifest_cannot_smuggle_live_sqlite_sidecars_or_undeclared_files(self):
        _, archive = self.fixture()
        with tarfile.open(archive, "r:gz") as tar:
            content = {item.name: tar.extractfile(item).read() for item in tar}
        for name in ("data/tg115.db-wal", "data/bot.session-journal", "config/state.db-shm",
                     "downloads/private.bin", "rehearsal-downloads/private.bin", "untrusted.py"):
            with self.subTest(path=name):
                manifest = json.loads(content["manifest.json"])
                extra = b"synthetic"
                manifest["files"][name] = {"size": len(extra), "sha256": hashlib.sha256(extra).hexdigest()}
                candidate = self.root / "invalid.tar.gz"
                with tarfile.open(candidate, "w:gz") as tar:
                    records = {**content, "manifest.json": json.dumps(manifest).encode(), name: extra}
                    for path, body in records.items():
                        info = tarfile.TarInfo(path)
                        info.size = len(body)
                        tar.addfile(info, io.BytesIO(body))
                with self.assertRaises(ValueError):
                    bundle.preflight(candidate, self.root, "openlist", VERSION)
                self.assertFalse(list(self.root.glob("tg2cloud-restore-check-*")))
