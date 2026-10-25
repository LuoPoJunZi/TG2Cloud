"""Synthetic native-account records and loopback metadata; never real gateways."""
from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.addons.external_webdav import cli, config, scope
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.state import validate_domain, validate_email


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        self.directory = Path(self.private.name).resolve()
        self.native = self.directory / "clouddrive/config/webdav_config.json"
        self.native.parent.mkdir(parents=True)
        values = {"URL": "http://tg2cloud-clouddrive2:19798/dav", "USERNAME": "bot-reader",
                  "PASSWORD": "SYNTHETIC_BOT_ONLY", "TARGET_PATH": "电影/家庭"}
        self.settings = {"WEBDAV_" + key + "_B64": base64.b64encode(value.encode()).decode()
                         for key, value in values.items()}
        self.instance = SimpleNamespace(directory=self.directory, config=self.settings, gateway_image="fixture-image")
        actual = os.fstat
        def owned(fd):
            info = actual(fd)
            return SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_size=info.st_size)
        # Only temporary fixture ownership is normalized for non-root CI.
        owner = patch.object(scope.os, "fstat", side_effect=owned)
        owner.start()
        self.addCleanup(owner.stop)

    def write(self, users, **extra):
        item = dict(enabled=True, dav_users=users, **extra)
        self.native.write_text(json.dumps(item), encoding="utf-8")
        self.native.chmod(0o600)

    def test_exact_native_username_and_unicode_root_are_read_without_writing(self):
        self.write([{"user_name": "another", "root_path": "/other", "enabled": True},
                    {"user_name": "bot-reader", "root_path": "/资料/家庭", "enabled": True}])
        original = self.native.read_bytes()
        result = scope.resolve(self.instance, PRODUCTS["clouddrive2"])
        self.assertEqual(result.path, "/资料/家庭")
        self.assertEqual(result.source, "网关账号配置")
        self.assertEqual(self.native.read_bytes(), original)
        self.assertNotIn("SYNTHETIC_BOT_ONLY", repr(result))

    def test_unknown_encrypted_disabled_duplicate_and_unsafe_native_users_require_input(self):
        fixtures = [[], [{"username_encrypt": "opaque", "root_path": "/guess", "enabled": True}],
                    [{"user_name": "bot-reader", "root_path": "/root", "enabled": False}],
                    [{"user_name": "bot-reader", "root_path": "/a", "enabled": True}]*2,
                    [{"user_name": "bot-reader", "root_path": "/safe/../outside", "enabled": True}]]
        for users in fixtures:
            with self.subTest(users=users):
                self.write(users)
                result = scope.resolve(self.instance, PRODUCTS["clouddrive2"])
                self.assertEqual(result.path, "")
                self.assertIn("首次补充一次", result.reason)
                self.assertNotIn("opaque", result.reason)

    def test_root_is_not_inferred_from_a_relative_bot_subdirectory(self):
        self.write([])
        result = scope.resolve(self.instance, PRODUCTS["clouddrive2"])
        self.assertEqual(result.path, "")
        self.assertNotIn("电影", result.reason)

    def test_live_account_scope_takes_priority_over_saved_root(self):
        self.write([{"user_name": "bot-reader", "root_path": "/current", "enabled": True}])
        previous = {"instance_dir": str(self.directory), "binding": config.binding(self.settings),
                    "backend_image": self.instance.gateway_image, "bot_root": "/old"}
        self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"], previous).path, "/current")
        self.write([])
        self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"], previous).path, "/old")
        for field in ("instance_dir", "binding", "backend_image"):
            changed = dict(previous, **{field: "changed"})
            self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"], changed).path, "")

    def test_bad_json_extra_large_file_and_symlink_are_not_accepted(self):
        for text in ('{"enabled":true,"enabled":false}', 'not JSON', 'x'*(scope.LIMIT+1)):
            self.native.write_text(text, encoding="utf-8")
            self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"]).path, "")
        with (patch.object(Path, "resolve", return_value=self.directory / "elsewhere"),
              patch.object(scope.os, "open") as opened):
            self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"]).path, "")
            opened.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX owner/mode check; production protection remains enabled")
    def test_unowned_or_group_writable_native_configuration_is_rejected(self):
        self.write([{"user_name": "bot-reader", "root_path": "/a", "enabled": True}])
        for uid, mode in ((1000, 0o100600), (0, 0o100620)):
            info = SimpleNamespace(st_uid=uid, st_mode=mode, st_size=100)
            with patch.object(scope.os, "fstat", return_value=info):
                self.assertEqual(scope.resolve(self.instance, PRODUCTS["clouddrive2"]).path, "")

    def test_openlist_uses_only_bot_login_and_current_user_with_no_admin(self):
        with patch.object(scope, "openlist_json", side_effect=[{"token": "TEMPORARY_ONLY"},
                     {"username": "bot-reader", "disabled": False, "base_path": "/媒体"}]) as request:
            self.assertEqual(scope.openlist_root(self.instance, PRODUCTS["openlist"]), "/媒体")
        self.assertEqual(request.call_args_list[0].args, (5244, "POST", "/api/auth/login"))
        self.assertEqual(request.call_args_list[0].kwargs["payload"]["username"], "bot-reader")
        self.assertEqual(request.call_args_list[1].args, (5244, "GET", "/api/me"))
        self.assertEqual(request.call_args_list[1].kwargs, {"token": "TEMPORARY_ONLY"})

    def test_openlist_does_not_accept_guest_wrong_user_disabled_or_missing_root(self):
        for user in ({"username": "guest", "disabled": False, "base_path": "/"},
                     {"username": "bot-reader", "disabled": True, "base_path": "/a"},
                     {"username": "bot-reader", "disabled": False}):
            with patch.object(scope, "openlist_json", side_effect=[{"token": "TEMP"}, user]):
                self.assertEqual(scope.resolve(self.instance, PRODUCTS["openlist"]).path, "")

    def test_openlist_http_is_fixed_to_loopback_bounded_and_never_redirects(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"code":200,"data":{"base_path":"/media"}}'
        with patch.object(scope.http.client, "HTTPConnection", return_value=connection) as factory:
            result = scope.openlist_json(5244, "GET", "/api/me", token="PRIVATE_TOKEN")
        self.assertEqual(result, {"base_path": "/media"})
        factory.assert_called_once_with("127.0.0.1", 5244, timeout=4)
        response.read.assert_called_once_with(scope.LIMIT+1)
        connection.close.assert_called_once()
        for status, content in ((302, b""), (401, b"PRIVATE_TOKEN"), (500, b""),
                                (200, b"x"*(scope.LIMIT+1)), (200, b'{"code":401,"message":"PRIVATE_TOKEN"}')):
            response.status, response.read.return_value = status, content
            with patch.object(scope.http.client, "HTTPConnection", return_value=connection), self.assertRaises(ValueError) as error:
                scope.openlist_json(5244, "GET", "/api/me", token="PRIVATE_TOKEN")
            self.assertNotIn("PRIVATE_TOKEN", str(error.exception))

    def test_management_link_uses_selected_edition_and_cannot_be_external_dav_domain(self):
        state = {"domains": {"clouddrive2": {"domain": "manage.example.test"},
                              "openlist": {"domain": "list.example.test"}}}
        self.assertEqual(scope.management_address(self.instance, PRODUCTS["clouddrive2"], state),
                         "https://manage.example.test")
        self.assertEqual(scope.management_address(self.instance, PRODUCTS["openlist"], state),
                         "https://list.example.test")
        from tg2cloud.deployment.proxy import lan
        with patch.object(lan, "load_state", return_value={"install_dir": str(self.directory), "bind_ip": "192.168.26.5"}):
            self.assertEqual(scope.management_address(self.instance, PRODUCTS["openlist"], {"domains": {}}),
                             "http://192.168.26.5:5244")


class InputFeedbackTests(unittest.TestCase):
    def terminal(self):
        ui = cli.WebDAVTerminal.__new__(cli.WebDAVTerminal)
        ui.output = io.StringIO()
        return ui

    def test_blank_email_is_accepted_on_first_enter_with_no_error(self):
        ui = self.terminal()
        with patch.object(cli.Terminal, "ask", return_value="") as read:
            self.assertEqual(ui.ask("邮箱", validate=validate_email), "")
        self.assertEqual(read.call_count, 1)
        self.assertEqual(ui.output.getvalue(), "")
        self.assertFalse(read.call_args.kwargs["secret"])

    def test_domain_and_email_show_specific_reasons_but_never_repeat_raw_input(self):
        for validate, bad, good, hint in ((validate_domain, "https://dav.example.test", "dav.example.test", "只填写域名"),
                                         (validate_email, "bad-mail", "family@example.test", "邮箱格式不正确")):
            ui = self.terminal()
            with patch.object(cli.Terminal, "ask", side_effect=[bad, good]):
                self.assertEqual(ui.ask("PUBLIC", validate=validate), good)
            self.assertIn(hint, ui.output.getvalue())
            self.assertNotIn("不显示输入值", ui.output.getvalue())
            self.assertNotIn(bad, ui.output.getvalue())

    def test_unknown_validator_exception_never_leaks_a_password(self):
        ui = self.terminal()
        def invalid(value):
            raise ValueError("PRIVATE_SECRET: " + value)
        with patch.object(cli.Terminal, "ask", side_effect=["private", EOFError]), self.assertRaises(EOFError):
            ui.ask("PUBLIC", validate=invalid)
        self.assertNotIn("private", ui.output.getvalue())
        self.assertNotIn("PRIVATE_SECRET", ui.output.getvalue())
