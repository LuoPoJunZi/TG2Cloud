"""Allowlist diagnostics never echo arbitrary Docker output or user content."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tg2cloud.deployment import diagnostics as host
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.monitoring.diagnostics import collect
from tg2cloud.persistence.sqlite import TaskDB


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = TaskDB(self.root / "tg115.db")
        self.addCleanup(self.db.close)

    def test_readonly_whitelist_contains_no_names_credentials_raw_errors(self):
        task, _ = self.db.create_task(chat_id=1, sender_id=1, message_id=1, file_name="SYNTHETIC_PRIVATE_NAME.mp4", file_size=5)
        self.db.update(task["id"], state="download_failed", failure_kind="SYNTHETIC_PRIVATE_TYPE", error="PRIVATE_PASSWORD")
        before = self.db.get(task["id"])
        environment = {"TG2CLOUD_STORAGE_BACKEND": "openlist", "BOT_TOKEN_B64": "PRIVATE_TOKEN", "DATA_DIR": str(self.root)}
        value = collect(self.root, environment=environment)
        serialized = json.dumps(value)
        for forbidden in ("SYNTHETIC_PRIVATE", "PRIVATE_PASSWORD", "PRIVATE_TOKEN", str(self.root)):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(value["failures"], {"other": 1})
        self.assertEqual(self.db.get(task["id"]), before)
        self.assertEqual(value["configuration"], "incomplete")

    def test_hostile_subprocess_output_not_echoed_and_unknown_does_not_pass(self):
        session = SimpleNamespace(run=lambda *a, **k: (0, "PRIVATE_TOKEN_AND_PATH"))
        instance = SimpleNamespace(product=PRODUCTS["openlist"])
        result = host.collect(instance, session)
        self.assertNotIn("PRIVATE_TOKEN_AND_PATH", result)
        self.assertIn("未检查", result)
        self.assertLess(len(result), 32768)

    def test_export_private_and_link_refused(self):
        parent = self.root / "reports"
        result = host.save("# safe report", parent)
        self.assertEqual(result.read_text(), "# safe report")
        if os.name == "posix":
            self.assertEqual(result.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            host.save("x" * 40000, parent)
        with self.assertRaises(ValueError):
            host.save("x", Path("relative"))
