"""Standard-library host CLI and fixed in-container family endpoint contract."""
from __future__ import annotations

import copy
import json
import os
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.deployment import users as host
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence import users

ROOT = Path(__file__).resolve().parents[1]


class ManagementTests(unittest.TestCase):
    def record(self):
        return {"schema": 1, "admin_id": 123, "revision": "initial", "users": [], "events": []}

    def test_members_and_actions_have_separate_labels_without_logging_private_ids(self):
        record = self.record()
        record["users"] = [{"id": 456, "name": "合成成员", "enabled": True}]
        manager = SimpleNamespace(ui=Mock(), log=Mock(), session=Mock(), product=PRODUCTS["openlist"])
        manager.ui.ask.return_value = "0"
        with patch.object(host, "request", return_value=record):
            host.manage(manager, SimpleNamespace(running=True, version="1.4.4", config={"ALLOWED_USER_ID": "123"}))
        text = "\n".join(call.args[0] for call in manager.log.call_args_list)
        for label in ("OpenList · 版本 1.4.4", "成员列表", "管理操作", "0. 返回主菜单"):
            self.assertIn(label, text)
        manager.ui.private.assert_any_call("成员 1", "合成成员 · 456 · 启用")
        self.assertNotIn("456", text)

    def test_fixed_exec_request_is_quoted_and_never_executes_member_name(self):
        session = Mock()
        record = self.record()
        session.run.return_value = (0, json.dumps({"api": 1, "record": record}))
        label = "Family'; $(not-a-command)"
        self.assertEqual(host.request(session, PRODUCTS["openlist"], 123, action="add", name=label), record)
        args = shlex.split(session.run.call_args.args[0])
        self.assertEqual(json.loads(args[2])["name"], label)
        self.assertEqual(args[3:], ["|", "docker", "exec", "-i", "tg2cloud-openlist-bot", "python", "-B", "-m", "tg2cloud.persistence.users"])
        self.assertNotIn("restart", args)

    def test_old_or_unknown_protocol_fails_no_fallback_database_writes(self):
        session = Mock()
        for result in ((1, "No module"), (0, "not json"), (0, json.dumps({"api": 99, "record": self.record()})),
                       (0, json.dumps({"api": 1, "record": dict(self.record(), admin_id=999)}))):
            session.run.return_value = result
            with self.assertRaises(ValueError):
                host.request(session, PRODUCTS["clouddrive2"], 123, action="list")
        self.assertTrue(all("sqlite" not in call.args[0] for call in session.run.call_args_list))

    def test_declined_family_plan_only_lists_no_restart_or_config_writes(self):
        ui = Mock()
        ui.ask.side_effect = ["1", "456", "家人", "0"]
        ui.confirm.return_value = False
        session = Mock()
        session.run.return_value = (0, json.dumps({"api": 1, "record": self.record()}))
        manager = SimpleNamespace(ui=ui, log=Mock(), session=session, product=PRODUCTS["openlist"], recheck=Mock())
        host.manage(manager, SimpleNamespace(running=True, config={"ALLOWED_USER_ID": "123"}))
        self.assertEqual([json.loads(shlex.split(call.args[0])[2])["action"] for call in session.run.call_args_list], ["list", "list"])
        manager.recheck.assert_not_called()

    def test_confirmed_change_rechecks_edition_and_uses_cas(self):
        ui, session = Mock(), Mock()
        ui.ask.side_effect = ["1", "456", "家人", "0"]
        ui.confirm.return_value = True
        record = self.record()
        session.run.return_value = (0, json.dumps({"api": 1, "record": record}))
        manager = SimpleNamespace(ui=ui, log=Mock(), session=session, product=PRODUCTS["clouddrive2"], recheck=Mock())
        instance = SimpleNamespace(running=True, config={"ALLOWED_USER_ID": "123"})
        with patch.object(host, "edition_lock", return_value=nullcontext()):
            host.manage(manager, instance)
        manager.recheck.assert_called_once_with(instance)
        requests = [json.loads(shlex.split(call.args[0])[2]) for call in session.run.call_args_list]
        self.assertEqual(requests[1], {"admin_id": 123, "action": "add", "id": 456, "name": "家人", "revision": "initial"})
        self.assertTrue(all("openlist" not in call.args[0] for call in session.run.call_args_list))

    def test_endpoint_works_without_bot_dependencies_and_never_creates_missing_db(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tg115.db"
            environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"), DATA_DIR=directory, ALLOWED_USER_ID="123")
            command = [sys.executable, "-S", "-B", "-m", "tg2cloud.persistence.users"]
            def run(request):
                return subprocess.run(command, input=json.dumps(request), env=environment, cwd=directory,
                                      text=True, capture_output=True, check=False, timeout=20)
            self.assertEqual(run({"admin_id": 123, "action": "list"}).returncode, 1)
            self.assertFalse(path.exists())
            with closing(sqlite3.connect(path, isolation_level=None)) as connection:
                connection.execute("CREATE TABLE service_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            result = run({"admin_id": 123, "action": "add", "id": 456, "revision": "initial"})
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout)["record"]
            self.assertEqual(record["users"][0]["id"], 456)
            self.assertEqual(json.loads(run({"admin_id": 123, "action": "list"}).stdout)["record"], record)
            self.assertEqual(run({"admin_id": 999, "action": "remove", "id": 456, "revision": record["revision"]}).returncode, 1)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(users.read(connection, 123), record)

    def test_member_quota_actions_are_selected_directly_from_family_menu(self):
        for selected, action in (("5", "view"), ("6", "set"), ("7", "clear")):
            with self.subTest(action=action):
                record = self.record()
                record["users"] = [{"id": 456, "name": "家人", "enabled": True}]
                manager = SimpleNamespace(ui=Mock(), log=Mock(), session=Mock(), product=PRODUCTS["openlist"], recheck=Mock())
                manager.ui.ask.side_effect = [selected, "1", "0"]
                instance = SimpleNamespace(running=True, config={"ALLOWED_USER_ID": "123"})
                with patch.object(host, "request", return_value=record) as request, patch(
                    "tg2cloud.deployment.feature_settings.member_quota"
                ) as quota:
                    host.manage(manager, instance)
                quota.assert_called_once_with(manager, instance, record, 456, action=action)
                self.assertEqual([call.args[0] for call in manager.ui.ask.call_args_list],
                                 ["选择操作", "选择上方成员序号（0 返回）", "选择操作"])
                self.assertTrue(all(call.kwargs["action"] == "list" for call in request.call_args_list))
                manager.session.run.assert_not_called()

    def test_metadata_limits_and_malformed_records_never_expand_authorization(self):
        item = self.record()
        for value in (True, "1,2", "0", "-1", "9" * 16):
            with self.assertRaises(ValueError):
                host.numeric_id(str(value))
        for key, value in (("revision", 123), ("schema", True), ("users", [{}]), ("admin_id", True)):
            candidate = copy.deepcopy(item)
            candidate[key] = value
            with self.assertRaises(ValueError):
                users.validate(candidate, 123)
