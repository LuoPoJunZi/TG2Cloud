"""Offline access choices retain Compose defaults, atomic setup and backup scope."""
from __future__ import annotations

import copy
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from test_compose import UI

from tg2cloud.compose import access, packaging, runtime
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence import bundle
from tg2cloud.version import VERSION

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/owner/tg2cloud@sha256:" + "a" * 64


class Answers(UI):
    def __init__(self, answers=None, confirmed=True):
        super().__init__()
        self.answers = answers or {}
        self.confirmed = confirmed

    def ask(self, prompt, default="", secret=False, validate=lambda value: value):
        if prompt in self.answers:
            self.questions.append(prompt)
            return validate(self.answers[prompt])
        return super().ask(prompt, default=default, secret=secret, validate=validate)

    def confirm(self, _):
        return self.confirmed


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        original = runtime.private_config_file
        def private_fixture(path):
            self.assertTrue(path.is_relative_to(self.root))
            info = path.stat()
            original(NS(stat=lambda: NS(st_uid=0, st_mode=info.st_mode)))
        permission = patch.object(runtime, "private_config_file", side_effect=private_fixture)
        permission.start()
        self.addCleanup(permission.stop)

    def candidate(self, edition="openlist"):
        path = self.root / edition
        path.mkdir()
        (path / "docker-compose.yml").write_text(packaging.render(ROOT, edition, IMAGE))
        (path / "compose-bundle.json").write_text(json.dumps({
            "format": 2, "https_tools": 1, "mode": "compose", "edition": edition,
            "version": VERSION, "image": IMAGE, "commit": "b" * 40}))
        return path

    def initialize(self, root, ui):
        with patch.object(runtime.shutil, "disk_usage", return_value=NS(free=100 * 1024**3)), \
                patch.object(runtime.os, "chown", create=True), redirect_stdout(io.StringIO()):
            return runtime.setup(root, ui)

    def plan(self, mode="managed", edition="openlist"):
        return {"format": 1, "owner": access.OWNER, "edition": edition,
                "mode": mode, "domain": "panel.example.com" if mode != "local" else "", "email": ""}

    def test_defaults_preserve_local_access_and_no_external_commands(self):
        for edition in PRODUCTS:
            ui = Answers()
            plan = {}
            with patch("subprocess.run", side_effect=AssertionError("offline setup")), \
                    patch("socket.create_connection", side_effect=AssertionError("offline setup")), \
                    redirect_stdout(io.StringIO()):
                config = runtime.collect(ui, PRODUCTS[edition], plan)
            self.assertEqual(config["TG2CLOUD_BIND_IP"], "127.0.0.1")
            self.assertEqual(plan, self.plan("local", edition))
            self.assertTrue(any("管理端口绑定" in prompt for prompt in ui.questions))

    def test_managed_and_existing_proxy_force_loopback_without_binding_prompt(self):
        for edition in PRODUCTS:
            for option, mode in (("2", "managed"), ("3", "external")):
                ui = Answers({"选择访问方式": option, "管理页域名（只填域名）": "panel.example.com"})
                plan = {}
                with redirect_stdout(io.StringIO()) as output:
                    config = runtime.collect(ui, PRODUCTS[edition], plan)
                self.assertEqual(config["TG2CLOUD_BIND_IP"], "127.0.0.1")
                self.assertEqual(plan, self.plan(mode, edition))
                self.assertFalse(any("管理端口绑定" in prompt for prompt in ui.questions))
                self.assertEqual("Let's Encrypt 邮箱（可留空）" in ui.questions, mode == "managed")
                self.assertIn("尚未配置", output.getvalue())

    def test_private_plan_saved_only_on_confirmation_and_setup_idempotent(self):
        root = self.candidate()
        self.assertFalse(self.initialize(root, Answers(confirmed=False)))
        self.assertFalse((root / access.ACCESS_FILE).exists())
        self.assertTrue(self.initialize(root, Answers()))
        path = root / access.ACCESS_FILE
        self.assertEqual(json.loads(path.read_text()), self.plan("local"))
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        before = {name: (root / name).read_bytes() for name in (".env", access.ACCESS_FILE, runtime.MARKER)}
        self.assertFalse(self.initialize(root, Answers({"选择访问方式": "2"})))
        self.assertEqual(before, {name: (root / name).read_bytes() for name in before})

    def test_interruption_cleans_all_private_files_and_retry_succeeds(self):
        root = self.candidate()
        original = runtime.write_exclusive
        def interrupt(path, content):
            if path.name == runtime.MARKER:
                raise KeyboardInterrupt()
            original(path, content)
        with patch.object(runtime, "write_exclusive", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            self.initialize(root, Answers())
        self.assertFalse(any((root / name).exists() for name in (".env", runtime.MARKER, access.ACCESS_FILE)))
        self.assertTrue(self.initialize(root, Answers()))

    def test_orphan_plan_not_overwritten_and_https_plan_rejects_lan_bind(self):
        root = self.candidate()
        plan_file = root / access.ACCESS_FILE
        plan_file.write_text(json.dumps(self.plan()))
        before = plan_file.read_bytes()
        with self.assertRaises(ValueError):
            self.initialize(root, Answers())
        self.assertEqual(plan_file.read_bytes(), before)
        plan_file.unlink()
        self.initialize(root, Answers())
        plan_file.write_text(json.dumps(self.plan()))
        config = root / ".env"
        config.write_text(config.read_text().replace("TG2CLOUD_BIND_IP=127.0.0.1", "TG2CLOUD_BIND_IP=192.168.1.5"))
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            runtime.saved_config(root, "openlist")

    def test_strict_schemas_and_legacy_metadata_without_access_plan(self):
        for changes in ({"format": True}, {"mode": []}, {"mode": "unknown"}, {"edition": "clouddrive2"},
                        {"domain": "https://panel.example.com"}, {"email": "invalid"}, {"extra": 1}):
            value = dict(self.plan(), **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                access.validate_access(value, "openlist")
        with self.assertRaises(ValueError):
            access.validate_access(dict(self.plan("local"), domain="panel.example.com"), "openlist")
        with self.assertRaises(ValueError):
            access.validate_access(dict(self.plan("external"), email="owner@example.com"), "openlist")
        root = self.candidate()
        self.initialize(root, Answers())
        (root / access.ACCESS_FILE).unlink()
        meta = root / "compose-bundle.json"
        value = json.loads(meta.read_text())
        value["format"] = 1
        del value["https_tools"]
        meta.write_text(json.dumps(value))
        self.assertEqual(runtime.metadata(root)["format"], 1)
        self.assertEqual(runtime.saved_config(root, "openlist")["TG2CLOUD_BIND_IP"], "127.0.0.1")
        value.update(format=2, https_tools=True)
        meta.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            runtime.metadata(root)

    def test_plan_rejects_duplicate_fields_oversize_and_hardlinks(self):
        path = self.root / access.ACCESS_FILE
        path.write_text('{"format":1,"format":1}')
        with self.assertRaisesRegex(ValueError, "重复"):
            access.read_access(self.root, "openlist", private_check=lambda _: None)
        path.write_text(" " * 8193)
        with self.assertRaises(ValueError):
            access.read_access(self.root, "openlist", private_check=lambda _: None)
        path.write_text(json.dumps(self.plan()))
        other = self.root / "copy.json"
        os.link(path, other)
        with self.assertRaises(ValueError):
            access.read_access(self.root, "openlist", private_check=lambda _: None)

    def test_plan_permission_protection_is_not_bypassed(self):
        if os.name == "posix":
            for uid, mode in ((1000, 0o600), (0, 0o644)):
                with self.subTest(uid=uid, mode=mode), self.assertRaises(ValueError):
                    access.private_access(NS(stat=lambda uid=uid, mode=mode: NS(st_uid=uid, st_mode=mode)))
        value = self.plan()
        before = copy.deepcopy(value)
        self.assertEqual(access.validate_access(value, "openlist"), value)
        self.assertEqual(value, before)

    def test_offline_backup_includes_access_plan_but_not_shared_proxy(self):
        root = self.candidate()
        self.initialize(root, Answers())
        for name in ("data/tg115.db", "data/bot.session"):
            with closing(sqlite3.connect(root / name)) as db:
                db.execute("CREATE TABLE synthetic (value TEXT)")
        (root / "config/synthetic.conf").write_text("no-secrets")
        (root / "openlist/data/config.json").write_text("{}")
        archive = self.root / "backup.tar.gz"
        before = (root / access.ACCESS_FILE).read_bytes()
        bundle.pack(root, archive, "openlist", VERSION)
        with bundle.verified_snapshot(archive, self.root, "openlist", VERSION) as (snapshot, _):
            self.assertEqual((snapshot / access.ACCESS_FILE).read_bytes(), before)
            self.assertFalse((snapshot / "https-tools").exists())
            self.assertFalse((snapshot / "certbot").exists())


if __name__ == "__main__":
    unittest.main()
