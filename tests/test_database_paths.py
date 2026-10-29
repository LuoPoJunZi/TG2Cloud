"""Fresh TG2Cloud naming and safe legacy data compatibility, without services."""
from __future__ import annotations

import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import test_openlist_backup as shell

from tg2cloud.deployment import configuration
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence import bundle, paths, rehearsal
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class DatabaseNameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)

    def database(self, name):
        path = self.root / name
        db = TaskDB(path)
        try:
            task, _ = db.create_task(chat_id=1, message_id=1, sender_id=1, file_name="synthetic.txt", file_size=4, media_key="synthetic:1")
            db.update(task["id"], state="completed")
        finally:
            db.close()
        return path

    def test_new_database_uses_project_name_without_creating_files_during_selection(self):
        self.assertEqual(paths.database_path(self.root), self.root / "tg2cloud.db")
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(ValueError):
            paths.database_path(self.root, require_existing=True)

    def test_existing_legacy_is_used_without_renaming_or_new_empty_history(self):
        path = self.database("tg115.db")
        before = path.read_bytes()
        self.assertEqual(paths.database_path(self.root), path)
        self.assertEqual(paths.database_path(self.root, require_existing=True), path)
        self.assertEqual(path.read_bytes(), before)
        db = TaskDB(paths.database_path(self.root))
        try:
            self.assertEqual(db.get(1)["state"], "completed")
        finally:
            db.close()
        self.assertFalse((self.root / "tg2cloud.db").exists())

    def test_canonical_existing_database_remains_selected(self):
        path = self.database("tg2cloud.db")
        self.assertEqual(paths.database_path(self.root, require_existing=True), path)
        self.assertFalse((self.root / "tg115.db").exists())

    def test_both_names_are_ambiguous_and_untouched(self):
        for name in paths.DATABASE_NAMES:
            self.database(name)
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with self.assertRaisesRegex(ValueError, "同时"):
            paths.database_path(self.root)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})
        with self.assertRaises(ValueError):
            paths.database_entry("data/" + name for name in paths.DATABASE_NAMES)

    def test_orphan_sidecars_never_create_replacement_database(self):
        for name in paths.DATABASE_NAMES:
            for suffix in paths.SIDECARS:
                path = self.root / (name + suffix)
                path.write_bytes(b"synthetic")
                with self.subTest(name=path.name), self.assertRaises(ValueError):
                    paths.database_path(self.root)
                self.assertEqual(path.read_bytes(), b"synthetic")
                path.unlink()
        self.assertFalse(any((self.root / name).exists() for name in paths.DATABASE_NAMES))

    def test_hardlinks_and_nonfiles_are_rejected(self):
        target = self.root / "tg2cloud.db"
        other = self.root / "alias"
        other.write_bytes(b"synthetic")
        os.link(other, target)
        with self.assertRaises(ValueError):
            paths.database_path(self.root)
        target.unlink()
        target.mkdir()
        with self.assertRaises(ValueError):
            paths.database_path(self.root)

    def test_symlink_rejected_even_if_other_database_exists(self):
        self.database("tg115.db")
        link = self.root / "tg2cloud.db"
        link.write_bytes(b"synthetic link stand-in")
        original = Path.is_symlink
        # Covers the same refusal where Windows disallows creating a real link.
        with patch.object(Path, "is_symlink", lambda path: path == link or original(path)), self.assertRaises(ValueError):
            paths.database_path(self.root)

    def test_standalone_selector_works_without_site_or_bot_dependencies(self):
        code = ROOT / "src/tg2cloud/persistence/paths.py"
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(code), str(self.root)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "tg2cloud.db")
        for name in paths.DATABASE_NAMES:
            (self.root / name).write_bytes(b"synthetic")
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(paths.main([str(self.root)]), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn(str(self.root), stderr.getvalue())

    def test_new_generated_config_has_no_old_project_variables(self):
        values = {"api_id":"123456", "api_hash":"a"*32, "bot_token":"123456789:SYNTHETIC_TEST_TOKEN_ONLY",
                  "user_id":"123456789", "webdav_user":"tg2cloud", "webdav_password":"SYNTHETIC", "target":"",
                  "budget":"20", "reserve":"8", "timezone":"Asia/Shanghai", "admin_password":"SYNTHETIC"}
        for product in PRODUCTS.values():
            config = configuration.new_config(product, values)
            self.assertFalse(any(key.startswith("TG115_") for key in config))
            self.assertEqual(config["TG2CLOUD_STORAGE_BACKEND"], product.key)

    def test_new_and_legacy_backup_rehearsal_for_both_editions(self):
        for edition in PRODUCTS:
            for database_name in paths.DATABASE_NAMES:
                root = self.root / (edition + "-" + database_name)
                for name in ("data", "config", "openlist/data" if edition == "openlist" else "clouddrive/config"):
                    (root / name).mkdir(parents=True)
                (root / ".env").write_text("SYNTHETIC=true\n")
                (root / "docker-compose.yml").write_text("services: {}\n")
                (root / "config/settings.conf").write_text("synthetic")
                gateway = root / ("openlist/data" if edition == "openlist" else "clouddrive/config")
                (gateway / "settings.json").write_text("{}")
                with closing(sqlite3.connect(root / "data/bot.session")) as connection:
                    connection.execute("CREATE TABLE synthetic (value TEXT)")
                database = TaskDB(root / "data" / database_name)
                database.close()
                archive = self.root / (root.name + ".tar.gz")
                bundle.pack(root, archive, edition, VERSION)
                with bundle.verified_snapshot(archive, self.root, edition, VERSION) as (copy, _):
                    self.assertEqual(paths.database_path(copy / "data", require_existing=True).name, database_name)
                report = rehearsal.rehearse(archive, self.root, edition)
                self.assertEqual(report["tasks"], 0)
                self.assertEqual(report["session"], "not-loaded")


@unittest.skipUnless(shell.BASH, "Requires Bash for isolated upgrade and rollback fixtures")
class CanonicalShellTests(unittest.TestCase):
    def fixture(self):
        fixture = shell.OpenListBackupTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        canonical = fixture.database.with_name("tg2cloud.db")
        fixture.database.rename(canonical)  # Only our synthetic isolated fixture.
        fixture.database = canonical
        return fixture

    def test_canonical_upgrade_snapshot_and_manual_backup(self):
        for action in (shell.UPGRADE, shell.MANUAL + "\ncreate_backup\n"):
            fixture = self.fixture()
            result, _ = fixture.execute(action)
            self.assertEqual(result.returncode, 0, result.stderr)
            archives = list((fixture.root / "backups").glob("database-*.db"))
            self.assertEqual(len(archives), 1)
            fixture.assert_database(archives[0], 1)
            self.assertFalse((fixture.installation / "data/tg115.db").exists())

    def test_clouddrive_upgrade_snapshot_uses_canonical_name(self):
        fixture = self.fixture()
        script = (ROOT / "packaging/hooks/clouddrive2/remote_install.sh").read_text(encoding="utf-8")
        prefix = script.split('[[ "$(id -u)" -eq 0 ]]', 1)[0]
        marker = 'if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then\n  BACKUP='
        action = marker + script.split(marker, 1)[1].split('\nlog "提交已预检的程序和配置"', 1)[0]
        with patch.object(shell, "PREFIX", prefix):
            # The reusable Docker stub has an optional OpenList branch.
            result, _ = fixture.execute(action, before="OPENLIST_CONTAINER=synthetic-openlist\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        archives = list((fixture.root / "backups").glob("database-*.db"))
        self.assertEqual(len(archives), 1)
        fixture.assert_database(archives[0], 1)
        self.assertFalse((fixture.installation / "data/tg115.db").exists())

    def test_each_edition_rollback_preserves_canonical_identity(self):
        for edition in PRODUCTS:
            fixture = self.fixture()
            script = (ROOT / "packaging/hooks" / edition / "remote_install.sh").read_text(encoding="utf-8")
            prefix = script.split('[[ "$(id -u)" -eq 0 ]]', 1)[0]
            before = 'DATABASE_BACKUP="$test_root/good.db"\nDATABASE_NAME=tg2cloud.db\n'
            with patch.object(shell, "PREFIX", prefix):
                result, _ = fixture.execute("rollback_install\n", before=before)
            self.assertEqual(result.returncode, 0, result.stderr)
            fixture.assert_database(fixture.database, 2)
            self.assertFalse((fixture.installation / "data/tg115.db").exists())


if __name__ == "__main__":
    unittest.main()
