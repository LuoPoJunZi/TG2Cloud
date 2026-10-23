"""Shallow settings menus retain confirmation, instance checks and SQLite CAS."""
from __future__ import annotations

import copy
import json
import os
import shlex
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.deployment import feature_settings as host
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.persistence import features
from tg2cloud.persistence.sqlite import TaskDB


class PromptUI:
    def __init__(self, answers=(), confirmations=()):
        self.answers, self.confirmations = iter(answers), iter(confirmations)
        self.prompts, self.confirms = [], []

    def ask(self, prompt, *, default="", validate=lambda value: value):
        self.prompts.append((prompt, default))
        return validate(next(self.answers) or default)

    def confirm(self, prompt):
        self.confirms.append(prompt)
        return next(self.confirmations)


class SettingsMenuTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = TaskDB(Path(temporary.name) / "test.db")
        self.addCleanup(self.db.close)
        patch.dict(os.environ, {"TZ": "UTC"}).start()
        self.messages = []
        self.manager = SimpleNamespace(ui=PromptUI(), log=self.messages.append, product=PRODUCTS["clouddrive2"],
                                       recheck=Mock(), session=Mock())
        self.instance = SimpleNamespace(running=True, config={"ALLOWED_USER_ID": "123"})
        self.request = patch.object(host, "request", side_effect=self.dispatch).start()
        self.addCleanup(patch.stopall)
        self.lock = patch.object(host, "edition_lock", side_effect=lambda _: nullcontext()).start()

    def dispatch(self, manager, instance, action, **values):
        if action == "settings-read":
            settings = self.db.feature_settings()
        elif action == "settings-write":
            settings = features.change(self.db._conn, values["revision"], values["updates"])
        else:
            raise AssertionError(action)
        return {"api": 1, "settings": settings}

    def writes(self):
        return [call for call in self.request.call_args_list if call.args[2] == "settings-write"]

    def test_all_classification_modes_are_direct_choices_with_no_nested_menu(self):
        for index, mode in enumerate(host.MODES, 1):
            with self.subTest(mode=mode):
                self.request.reset_mock()
                self.manager.ui = PromptUI([str(index), "0"], [True])
                before = self.db.feature_settings()
                host.manage_classification(self.manager, self.instance)
                self.assertEqual(self.db.feature_settings()["classification"], mode)
                self.assertEqual(self.writes()[0].kwargs, {"revision": before["revision"], "updates": {"classification": mode}})
                self.assertEqual(self.manager.ui.prompts, [("选择规则", "0"), ("选择规则", "0")])
                self.assertFalse(self.db.feature_settings()["notifications"])
                self.assertEqual(self.lock.call_args.args[0].name, "clouddrive2.lock")
        self.assertIn("只影响新任务，不移动历史文件", "\n".join(self.messages))

    def test_return_and_declined_changes_leave_preferences_untouched(self):
        for operation in (host.manage_classification, host.manage_notifications):
            for answers, confirms in ((["0"], []), (["1", "0"], [False])):
                with self.subTest(operation=operation.__name__, answers=answers):
                    self.request.reset_mock()
                    self.manager.ui = PromptUI(answers, confirms)
                    before = self.db.feature_settings()
                    operation(self.manager, self.instance)
                    self.assertEqual(self.db.feature_settings(), before)
                    self.assertFalse(self.writes())
        self.manager.recheck.assert_not_called()
        self.lock.assert_not_called()

    def test_notification_toggles_and_threshold_save_without_another_menu(self):
        self.manager.product = PRODUCTS["openlist"]
        self.manager.ui = PromptUI(["1", "2", "3", "25", "0"], [True, True, True])
        host.manage_notifications(self.manager, self.instance)
        current = self.db.feature_settings()
        self.assertTrue(current["notifications"])
        self.assertFalse(current["recovery_notifications"])
        self.assertEqual(current["disk_threshold_bytes"], 25 * 1024**3)
        self.assertEqual(current["classification"], "off")
        self.assertEqual([call.kwargs["updates"] for call in self.writes()], [
            {"notifications": True}, {"recovery_notifications": False}, {"disk_threshold_bytes": 25 * 1024**3},
        ])
        self.assertEqual([prompt for prompt, _ in self.manager.ui.prompts], ["选择操作"] * 3 + ["提醒阈值", "选择操作"])
        text = "\n".join(self.messages)
        for label in ("开启异常通知", "关闭异常通知", "关闭恢复通知", "开启恢复通知", "25 GB", "异常通知开启后生效"):
            self.assertIn(label, text)
        self.assertEqual(self.manager.recheck.call_count, 3)
        self.assertTrue(all(call.args[0].name == "openlist.lock" for call in self.lock.call_args_list))
        self.manager.session.run.assert_not_called()

    def test_zero_threshold_means_existing_safety_line_not_disabling_protection(self):
        self.manager.ui = PromptUI(["3", "", "0"], [True])
        host.manage_notifications(self.manager, self.instance)
        self.assertEqual(self.writes()[0].kwargs["updates"], {"disk_threshold_bytes": 0})
        self.assertIn("不能降低原磁盘保护", "\n".join(self.messages))

    def test_invalid_threshold_or_choice_is_never_written(self):
        for answers in (["3", "-1"], ["3", "1.5"], ["3", "100001"], ["3", "１２"], ["4"]):
            with self.subTest(answers=answers):
                self.manager.ui = PromptUI(answers)
                with self.assertRaises(ValueError):
                    host.manage_notifications(self.manager, self.instance)
        self.assertFalse(self.writes())
        self.manager.recheck.assert_not_called()

    def test_stopped_bot_and_unknown_settings_stop_before_any_change(self):
        self.instance.running = False
        for operation in (host.manage_classification, host.manage_notifications):
            with self.assertRaisesRegex(ValueError, "先启动"):
                operation(self.manager, self.instance)
        self.request.assert_not_called()
        self.instance.running = True
        original = self.db.feature_settings()
        for key, value in (("classification", []), ("classification", "unknown"), ("notifications", 1),
                           ("recovery_notifications", None), ("revision", True), ("disk_threshold_bytes", -1),
                           ("cooldown_seconds", True), ("blocked_seconds", "30")):
            current = copy.deepcopy(original)
            current[key] = value
            self.request.side_effect = None
            self.request.return_value = {"settings": current}
            for operation in (host.manage_classification, host.manage_notifications):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "协议"):
                    operation(self.manager, self.instance)
        self.assertFalse(self.writes())
        self.lock.assert_not_called()

    def test_instance_change_or_revision_race_cannot_overwrite_other_settings(self):
        self.manager.ui = PromptUI(["4"], [True])
        self.manager.recheck.side_effect = ValueError("instance changed")
        with self.assertRaisesRegex(ValueError, "instance changed"):
            host.manage_classification(self.manager, self.instance)
        self.assertFalse(self.writes())
        self.manager.recheck.side_effect = lambda _: features.change(
            self.db._conn, self.db.feature_settings()["revision"], {"classification": "year"})
        self.manager.ui = PromptUI(["4"], [True])
        with self.assertRaises(ValueError):
            host.manage_classification(self.manager, self.instance)
        self.assertEqual(self.db.feature_settings()["classification"], "year")
        self.assertNotIn("设置已保存。", self.messages)


class RequestAndQuotaTests(unittest.TestCase):
    def setUp(self):
        self.manager = SimpleNamespace(ui=Mock(), log=Mock(), product=PRODUCTS["openlist"], session=Mock(), recheck=Mock())
        self.instance = SimpleNamespace(running=True, config={"ALLOWED_USER_ID": "123"})
        self.usage = {"daily_bytes": 10, "max_queued": 2, "max_active": 1, "completed_bytes": 3, "reserved_bytes": 4}

    def test_control_request_keeps_fixed_endpoint_and_quoted_json(self):
        self.manager.session.run.return_value = (0, '{"api":1}')
        value = "not shell'; $(no-command)"
        host.request(self.manager, self.instance, "settings-write", revision="initial", updates={"classification": value})
        args = shlex.split(self.manager.session.run.call_args.args[0])
        self.assertEqual(json.loads(args[2])["updates"]["classification"], value)
        self.assertEqual(args[3:], ["|", "docker", "exec", "-i", "tg2cloud-openlist-bot", "python", "-B", "-m", "tg2cloud.persistence.control"])
        for code, output in ((1, "FAKE_PRIVATE"), (0, "FAKE_PRIVATE"), (0, '{"api":99}')):
            self.manager.session.run.return_value = (code, output)
            with self.assertRaises(ValueError) as caught:
                host.request(self.manager, self.instance, "settings-read")
            self.assertNotIn("FAKE_PRIVATE", str(caught.exception))

    def test_quota_view_is_read_only_and_does_not_open_another_menu(self):
        with patch.object(host, "request", return_value={"usage": self.usage}) as request:
            host.member_quota(self.manager, self.instance, {"revision": "initial"}, 456, action="view")
        request.assert_called_once_with(self.manager, self.instance, "quota-read", user_id=456)
        self.manager.ui.ask.assert_not_called()
        self.manager.ui.confirm.assert_not_called()

    def test_quota_set_and_clear_keep_confirmation_lock_and_expected_values(self):
        for action in ("set", "clear"):
            with self.subTest(action=action), patch.object(host, "request", return_value={"usage": self.usage}) as request, patch.object(
                host, "edition_lock", return_value=nullcontext()
            ) as lock:
                self.manager.ui.ask.side_effect = ["20", "3", "2"]
                self.manager.ui.confirm.return_value = True
                host.member_quota(self.manager, self.instance, {"revision": "initial"}, 456, action=action)
                expected = {key: self.usage[key] for key in ("daily_bytes", "max_queued", "max_active")}
                values = {"daily_bytes": 20 * 1024**3, "max_queued": 3, "max_active": 2} if action == "set" else dict.fromkeys(expected, 0)
                self.assertEqual(request.call_args.kwargs, {"user_id": 456, "revision": "initial", "expected": expected, "values": values})
                self.assertEqual(request.call_args.args[2], "quota-write")
                self.assertEqual(lock.call_args.args[0].name, "openlist.lock")
        self.assertEqual(self.manager.recheck.call_count, 2)

    def test_invalid_quota_action_and_declined_clear_cannot_write(self):
        with patch.object(host, "request", return_value={"usage": self.usage}) as request:
            with self.assertRaises(ValueError):
                host.member_quota(self.manager, self.instance, {"revision": "initial"}, 456, action="unknown")
            request.assert_not_called()
            self.manager.ui.confirm.return_value = False
            host.member_quota(self.manager, self.instance, {"revision": "initial"}, 456, action="clear")
            self.assertEqual(request.call_count, 1)
        self.manager.recheck.assert_not_called()


if __name__ == "__main__":
    unittest.main()
