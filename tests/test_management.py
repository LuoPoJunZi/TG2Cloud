"""Offline CLI/UI contracts; fake instances and private temporary directories only."""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.cli import commands, management, terminal, vps
from tg2cloud.cli.presentation import InstallerLog, numbered_menu
from tg2cloud.deployment import (
    configuration,
    host,
    install,
    instances,
    releases,
    runtime,
)
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import lan

ROOT = Path(__file__).resolve().parents[1]


def enter_context(test, context):
    value = context.__enter__()
    test.addCleanup(context.__exit__, None, None, None)
    return value


class InputUI:
    friendly = True

    def __init__(self, **overrides):
        self.prompts = []
        self.overrides = overrides

    def ask(self, prompt, *, default="", secret=False, validate=configuration.plain):
        self.prompts.append((prompt, secret, default))
        for key, value in self.overrides.items():
            if key in prompt:
                return validate(value or default)
        defaults = {"Telegram API ID": "123456", "Telegram API Hash": "a" * 32,
                    "Bot Token": "123456:" + "x" * 25, "Telegram 用户 ID": "654321"}
        value = next((value for key, value in defaults.items() if key in prompt), default)
        return validate(value)


class InstallationUITests(unittest.TestCase):
    def test_number_and_label_columns_are_both_left_aligned(self):
        labels = ("安装外部 WebDAV", "查看运行状态", "检查连接与配置", "启用访问", "停用访问",
                  "修改域名或账号配置", "卸载外部 WebDAV", "升级附加功能", "查看手机连接配置", "用户管理")
        menu = numbered_menu((*enumerate(labels, 1), (0, "退出")))
        lines = menu.splitlines()
        self.assertEqual(lines[0], "1.  安装外部 WebDAV")
        self.assertEqual(lines[9], "10. 用户管理")
        self.assertEqual(lines[-1], "0.  退出")
        for line, label in zip(lines, (*labels, "退出")):
            self.assertFalse(line.startswith(" "))
            self.assertEqual(line.index(label), 4)
            self.assertNotIn("\t", line)
        self.assertEqual(numbered_menu(()), "")

    def test_short_submenus_and_long_dynamic_lists_keep_numbers_and_labels(self):
        self.assertEqual(numbered_menu(((1, "启用"), (2, "停用"), (0, "返回"))), "1. 启用\n2. 停用\n0. 返回")
        lines = numbered_menu((number, "用户") for number in range(1, 101)).splitlines()
        self.assertEqual(lines[0], "1.   用户")
        self.assertEqual(lines[-1], "100. 用户")
        self.assertEqual({line.index("用户") for line in lines}, {5})
        main = management.MENU.splitlines()
        self.assertEqual(main[0], "1.  安装与升级")
        self.assertEqual(main[9], "10. 业务就绪检查")
        self.assertEqual(main[-1], "0.  退出")

    def test_new_config_default_password_eight_chars_no_timezone_prompt_both_editions(self):
        for product in PRODUCTS.values():
            ui = InputUI()
            config = terminal.collect_config(ui, product, storage=("20", "8"))
            password = base64.b64decode(config["WEBDAV_PASSWORD_B64"]).decode()
            self.assertRegex(password, r"^[A-Za-z0-9]{8}$")
            for predicate in (str.islower, str.isupper, str.isdigit):
                self.assertTrue(any(predicate(char) for char in password))
            self.assertEqual(base64.b64decode(config["WEBDAV_USERNAME_B64"]), b"tg2cloud")
            self.assertEqual(base64.b64decode(config["WEBDAV_TARGET_PATH_B64"]), b"")
            self.assertEqual(config["TZ"], "Asia/Shanghai")
            self.assertFalse(any("时区" in prompt for prompt, *_ in ui.prompts))
            if product.is_openlist:
                self.assertGreater(len(config["OPENLIST_ADMIN_PASSWORD"]), 8)

    def test_manual_password_and_relative_subdir_preserved_no_native_root_guess(self):
        config = terminal.collect_config(InputUI(**{"WebDAV 密码": "my own $password", "Bot 保存子目录": "视频/本周"}), PRODUCTS["clouddrive2"], storage=("20", "8"))
        self.assertEqual(base64.b64decode(config["WEBDAV_PASSWORD_B64"]).decode(), "my own $password")
        self.assertEqual(base64.b64decode(config["WEBDAV_TARGET_PATH_B64"]).decode(), "视频/本周")
        for path in ("../bad", "bad/../next", "a\\b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                terminal.collect_config(InputUI(**{"Bot 保存子目录": path}), PRODUCTS["openlist"], storage=("20", "8"))

    def test_private_setup_only_after_friendly_flow_and_never_log_or_show_tokens(self):
        ui = InputUI()
        ui.private = Mock()
        config = terminal.collect_config(ui, PRODUCTS["openlist"], storage=("20", "8"))
        messages = []
        log = SafeLog(messages.append)
        log.register(config)
        terminal.show_setup_credentials(ui, PRODUCTS["openlist"], config, log)
        self.assertEqual(ui.private.call_count, 3)
        public = "\n".join(messages)
        private = str(ui.private.call_args_list)
        for key in ("WEBDAV_PASSWORD_B64", "BOT_TOKEN_B64", "TELEGRAM_API_HASH_B64"):
            secret = base64.b64decode(config[key]).decode()
            self.assertNotIn(secret, public)
            if key != "WEBDAV_PASSWORD_B64":
                self.assertNotIn(secret, private)

    def test_private_output_refuses_redirect_and_control_characters(self):
        ui = terminal.Terminal.__new__(terminal.Terminal)
        ui.output = io.StringIO()
        with self.assertRaises(RuntimeError):
            ui.private("密码", "FAKE_ONLY")
        ui.output = Mock()
        ui.output.isatty.return_value = True
        with self.assertRaises(ValueError):
            ui.private("密码", "FAKE\nINJECT")
        ui.output.write.assert_not_called()

    def test_interactive_log_hides_source_commit_but_does_not_claim_skipped_verification(self):
        messages = []
        log = InstallerLog(SafeLog(messages.append))
        log.register({"PASSWORD": "FAKE_PRIVATE"})
        log("正式 Release：v1.3.1；固定源码 commit：" + "a" * 40)
        log("TG2CLOUD_CLI_WEBDAV=NOT_RUN；not completed")
        log("TG2CLOUD_CLI_RESULT=FAILED：FAKE_PRIVATE")
        text = "\n".join(messages)
        self.assertNotIn("a" * 40, text)
        self.assertNotIn("FAKE_PRIVATE", text)
        self.assertIn("已跳过", text)
        self.assertNotIn("写入与大小复验通过", text)

    def test_help_stdlib_only_from_other_directory(self):
        with tempfile.TemporaryDirectory() as private:
            for args in (("manage", "--help"), ("--help",)):
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(ROOT / "scripts/run_source.py"), *args], cwd=private, capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("TG2Cloud", result.stdout)

    def test_no_args_dispatches_local_menu_not_installer(self):
        with patch.object(management, "main", return_value=0) as operation, patch.object(vps, "main") as installer:
            self.assertEqual(commands.main([]), 0)
        operation.assert_called_once_with([])
        installer.assert_not_called()

    def test_default_public_and_lan_commands_dispatch_unified_menu_but_flags_stay_compatible(self):
        for command, mode in (("install", "public"), ("lan", "lan")):
            with self.subTest(command=command), patch.object(management, "main", return_value=0) as menu:
                self.assertEqual(commands.main([command]), 0)
            menu.assert_called_once_with([], mode_hint=mode)
        with patch.object(management, "main") as menu, patch.object(vps, "main", return_value=0) as installer:
            self.assertEqual(commands.main(["install", "--edition", "openlist", "--check"]), 0)
        menu.assert_not_called()
        installer.assert_called_once_with(["--edition", "openlist", "--check"])

    def test_edition_number_two_selects_openlist_not_clouddrive2(self):
        ui = Mock()
        ui.ask.return_value = "2"
        with patch.object(management.preflight, "validate_host"), patch.object(terminal, "Terminal", return_value=ui), patch.object(management, "LocalSession"), patch.object(management, "SafeLog", return_value=SafeLog(lambda _: None)), patch.object(management, "Management") as selected:
            selected.return_value.run.return_value = 0
            self.assertEqual(management.main([]), 0)
        self.assertEqual(selected.call_args.args[0].key, "openlist")

    def test_runtime_directory_is_not_an_instance_directory(self):
        with self.assertRaises(ValueError):
            configuration.check_product_directory(PRODUCTS["openlist"], Path("/opt/tg2cloud-cli/runtime"))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.private = Path(temporary.name).resolve()
        self.root = self.private / "manager"
        self.command = self.private / "bin/tg2cloud"
        # Windows has no fcntl. Linux CI exercises the actual file lock and
        # private permission checks, all under the unique fixture directory.
        if os.name != "posix":
            enter_context(self, patch.object(host, "edition_lock", side_effect=lambda _: nullcontext()))

    def install(self):
        runtime.install(source=ROOT, root=self.root, command=self.command)
        return next((self.root / "runtime").iterdir())

    def test_immutable_offline_bundle_roundtrip_and_idempotence(self):
        bundle = self.install()
        first = self.command.read_bytes()
        self.assertEqual(self.install(), bundle)
        self.assertEqual(self.command.read_bytes(), first)
        data = runtime.verify(bundle)
        self.assertEqual(data["owner"], "tg2cloud.cli")
        self.assertIn("src/tg2cloud/cli/management.py", data["files"])
        self.assertFalse(any(".env" in name or name.startswith(("data/", "src/tg2cloud/telegram/")) for name in data["files"]))
        self.assertFalse((bundle / ".bootstrap-release.json").exists())
        self.assertNotIn("curl", first.decode())
        self.assertNotIn("main/", first.decode())
        runtime.check_destination(root=self.root, command=self.command)
        entry = bundle / "src/tg2cloud/deployment/runtime.py"
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(entry), "manage", "--help"], cwd=self.private, capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("离线本地管理", result.stdout)
        if os.name == "posix":
            self.assertEqual(self.command.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in bundle.rglob("*") if p.is_file()))

    def test_source_mutation_and_unknown_files_rejected(self):
        bundle = self.install()
        path = bundle / "src/tg2cloud/cli/management.py"
        original = path.read_bytes()
        path.write_bytes(original + b"\n# modified\n")
        with self.assertRaises(ValueError):
            runtime.check_destination(root=self.root, command=self.command)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(bundle / "src/tg2cloud/deployment/runtime.py"), "--help"], cwd=self.private, capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("未启动菜单", result.stderr)
        path.write_bytes(original)
        extra = bundle / "unknown.py"
        extra.write_text("# not in manifest", encoding="utf-8")
        with self.assertRaises(ValueError):
            runtime.verify(bundle)

    def test_foreign_command_and_partial_root_never_overwritten(self):
        self.command.parent.mkdir()
        self.command.write_text("#!/bin/sh\necho unrelated\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install()
        self.assertIn("unrelated", self.command.read_text())
        self.command.unlink()
        self.root.mkdir(mode=0o700)
        (self.root / "foreign.txt").write_text("KEEP", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual((self.root / "foreign.txt").read_text(), "KEEP")

    def test_failed_command_switch_preserves_previous_command_and_bundle(self):
        bundle = self.install()
        before = self.command.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("fixture switch failed")), self.assertRaises(OSError):
            self.install()
        self.assertEqual(self.command.read_bytes(), before)
        runtime.verify(bundle)
        self.assertFalse(list(self.command.parent.glob(".tg2cloud-*")))

    def test_unknown_schema_and_missing_files_refused(self):
        bundle = self.install()
        marker = bundle / "installation.json"
        data = json.loads(marker.read_text())
        data["schema"] = 99
        marker.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            runtime.verify(bundle)
        data["schema"] = 1
        marker.write_text(json.dumps(data))
        (bundle / "scripts/run_source.py").unlink()
        with self.assertRaises(ValueError):
            runtime.verify(bundle)

    def test_remove_only_verified_bundle_and_command_not_parent_or_neighbor(self):
        self.install()
        neighbor = self.private / "unrelated.txt"
        neighbor.write_text("KEEP", encoding="utf-8")
        self.assertTrue(runtime.remove(root=self.root, command=self.command))
        self.assertFalse(self.root.exists())
        self.assertFalse(self.command.exists())
        self.assertEqual(neighbor.read_text(), "KEEP")
        self.assertTrue(self.command.parent.exists())
        self.assertFalse(runtime.remove(root=self.root, command=self.command))

    def test_unknown_bundle_or_root_file_prevents_all_code_deletion(self):
        self.install()
        for path in (self.root / "unknown.txt", self.root / "runtime/unknown.txt"):
            path.write_text("KEEP", encoding="utf-8")
            with self.subTest(path=path), self.assertRaises(ValueError):
                runtime.remove(root=self.root, command=self.command)
            self.assertTrue(self.command.exists())
            self.assertTrue(self.root.exists())
            path.unlink()
class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.product = PRODUCTS["clouddrive2"]
        self.instance = instances.Instance(self.product, Path(self.product.install_dir), True, "1.3.1", True, "image", {"TZ": "Europe/London"}, b"TZ=Europe/London\n")
        self.messages = []
        self.log = SafeLog(self.messages.append)
        self.ui, self.session = Mock(), Mock()
        self.manager = management.Management(self.product, self.session, self.log, self.ui)
        self.session.run.return_value = (0, "done")
        enter_context(self, patch.object(management, "edition_lock", side_effect=lambda _: nullcontext()))

    def test_confirmed_menu_labels_order_and_alignment_without_naming_preview(self):
        labels = ("安装与升级", "查看运行状态", "查看运行日志", "服务启停管理", "Bot 用户管理",
                  "WebDAV 凭据", "HTTPS 与管理", "文件分类设置", "异常通知设置", "业务就绪检查",
                  "WebDAV 验收", "故障诊断报告", "数据备份管理", "卸载当前实例", "退出")
        expected = [str(number) for number in (*range(1, 15), 0)]
        self.assertEqual(list(management.MENU_ACTIONS), expected)
        self.assertEqual(management.MENU, numbered_menu(zip(expected, labels)) + "\n")
        self.assertTrue(all(line.index(label) == 4 for line, label in zip(management.MENU.splitlines(), labels)))
        self.assertNotIn("命名预览", management.MENU)
        self.assertNotIn(" / ", management.MENU)

    def test_unknown_number_is_rejected_before_any_operation(self):
        def ask(prompt, *, default, validate):
            self.assertEqual(default, "0")
            return validate("15")

        self.ui.ask.side_effect = ask
        with patch.object(self.manager, "discover", return_value=self.instance), patch(
            "tg2cloud.cli.naming.interactive"
        ) as preview, self.assertRaisesRegex(ValueError, "请选择菜单中的序号"):
            self.manager.run()
        preview.assert_not_called()
        self.session.run.assert_not_called()

    def test_every_number_dispatches_only_its_labelled_operation_both_editions(self):
        methods = {"1": "upgrade", "2": "status", "3": "logs", "4": "control",
                   "7": "entry", "11": "verify", "13": "backups", "14": "remove"}
        external = {"5": "tg2cloud.deployment.users.manage", "6": "tg2cloud.cli.terminal.show_credentials",
                    "8": "tg2cloud.deployment.feature_settings.manage_classification",
                    "9": "tg2cloud.deployment.feature_settings.manage_notifications",
                    "10": "tg2cloud.deployment.readiness.check", "12": "tg2cloud.deployment.diagnostics.collect"}
        for product in PRODUCTS.values():
            instance = replace(self.instance, product=product, directory=Path(product.install_dir))
            manager = management.Management(product, self.session, self.log, self.ui)
            for number in management.MENU_ACTIONS:
                with self.subTest(edition=product.key, number=number), ExitStack() as stack:
                    stack.enter_context(patch.object(manager, "discover", return_value=instance))
                    operations = {key: stack.enter_context(patch.object(manager, name, return_value=True))
                                  for key, name in methods.items()}
                    operations.update({key: stack.enter_context(patch(target, return_value="synthetic report"))
                                       for key, target in external.items()})
                    preview = stack.enter_context(patch("tg2cloud.cli.naming.interactive"))
                    self.ui.ask.side_effect = [number, "0"]
                    self.ui.confirm.return_value = False
                    self.assertEqual(manager.run(), 0)
                    for key, operation in operations.items():
                        if key != number:
                            operation.assert_not_called()
                        elif key in methods:
                            operation.assert_called_once_with(instance)
                        elif key == "6":
                            operation.assert_called_once_with(self.ui, product, instance.config, self.log)
                        elif key == "10":
                            operation.assert_called_once_with(instance, self.session, self.log)
                        elif key == "12":
                            operation.assert_called_once_with(instance, self.session)
                        else:
                            operation.assert_called_once_with(manager, instance)
                    preview.assert_not_called()
        self.session.run.assert_not_called()

    def test_main_title_precedes_actual_instance_summary_and_menu(self):
        self.manager.log = InstallerLog(self.log)
        self.ui.ask.return_value = "0"
        with patch.object(self.manager, "discover", return_value=self.instance):
            self.assertEqual(self.manager.run(), 0)
        text = "\n".join(self.messages)
        self.assertEqual(text.count("── TG2Cloud 本地管理 ──"), 1)
        self.assertLess(text.index("── TG2Cloud 本地管理 ──"), text.index("CloudDrive2 · 版本 1.3.1"))
        self.assertLess(text.index("安装目录："), text.index("1.  安装与升级"))
        expected = ("\n── TG2Cloud 本地管理 ──\n\nCloudDrive2 · 版本 1.3.1 · Bot 运行中\n"
                    + f"安装目录：{self.instance.directory}\n\n" + management.MENU)
        self.assertEqual(text, expected)

    def test_remote_docker_and_compose_overrides_rejected_before_command(self):
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "COMPOSE_FILE", "COMPOSE_ENV_FILES"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "foreign"}), self.assertRaises(ValueError):
                self.manager.discover()
        self.session.run.assert_not_called()

    def test_default_control_only_changes_selected_bot(self):
        self.ui.ask.side_effect = ["3"]
        self.ui.confirm.return_value = True
        with patch.object(self.manager, "recheck", return_value=self.instance) as check:
            self.manager.control(self.instance)
        check.assert_called_once_with(self.instance)
        self.assertEqual(self.ui.ask.call_count, 1)
        self.assertEqual(self.ui.ask.call_args_list[0].kwargs["default"], "0")
        command = self.session.run.call_args.args[0]
        self.assertEqual(command, "docker restart " + self.product.bot_container)
        self.assertNotIn("compose down", command)

    def test_cancel_or_changed_instance_does_not_stop_any_container(self):
        for confirmed in (False, True):
            self.ui.ask.side_effect = ["5"]
            self.ui.confirm.return_value = confirmed
            with patch.object(self.manager, "recheck", side_effect=ValueError("changed")):
                if confirmed:
                    with self.assertRaises(ValueError):
                        self.manager.control(self.instance)
                else:
                    self.manager.control(self.instance)
        self.session.run.assert_not_called()

    def test_each_service_action_targets_only_selected_container_in_one_prompt(self):
        for product in PRODUCTS.values():
            manager = management.Management(product, self.session, self.log, self.ui)
            for number in range(1, 7):
                with self.subTest(edition=product.key, action=number):
                    self.session.reset_mock()
                    self.ui.ask.reset_mock()
                    self.ui.ask.return_value, self.ui.ask.side_effect = str(number), None
                    self.ui.confirm.return_value = True
                    with patch.object(manager, "recheck", return_value=self.instance):
                        manager.control(self.instance)
                    verb = ("start", "stop", "restart")[(number - 1) % 3]
                    name = product.bot_container if number <= 3 else product.storage_container
                    self.session.run.assert_called_once_with("docker " + verb + " " + name, stream=self.log, timeout=90)
                    self.assertEqual(self.ui.ask.call_count, 1)

    def test_service_menu_return_does_not_confirm_or_execute(self):
        self.ui.ask.return_value = "0"
        self.manager.control(self.instance)
        self.ui.confirm.assert_not_called()
        self.session.run.assert_not_called()

    def test_revision_recheck_rejects_changes_and_custom_path_mismatch(self):
        changed = instances.Instance(self.product, self.instance.directory, True, "1.3.1", True, "image", {}, b"changed")
        with patch.object(self.manager, "discover", return_value=changed), self.assertRaises(ValueError):
            self.manager.recheck(self.instance)

    def test_logs_are_bounded_and_do_not_download_anything(self):
        self.manager.logs(self.instance)
        self.assertEqual(self.session.run.call_count, 2)
        for call in self.session.run.call_args_list:
            self.assertIn("docker logs --since 30m --tail 100", call.args[0])
            self.assertNotIn("curl", call.args[0])

    def test_verify_requires_confirm_exit_and_completion_marker(self):
        self.ui.confirm.return_value = False
        self.manager.verify(self.instance)
        self.session.run.assert_not_called()
        self.ui.confirm.return_value = True
        with patch.object(self.manager, "recheck", return_value=self.instance):
            for result in ((1, "TG2CLOUD_DESTINATION=OK"), (0, "partial")):
                self.session.run.return_value = result
                with self.assertRaises(RuntimeError):
                    self.manager.verify(self.instance)
            self.session.run.return_value = (0, "TG2CLOUD_DESTINATION=OK\n")
            self.manager.verify(self.instance)
        self.assertNotIn("写入与远端大小复验通过", "\n".join(self.messages[:-1]))
        self.assertIn("写入与远端大小复验通过", self.messages[-1])

    def test_lan_upgrade_uses_lan_preserves_saved_config_and_never_calls_public_installer(self):
        before = self.instance.raw_config
        with patch.object(self.manager, "mode", return_value={"bind_ip": "192.168.1.9"}), patch.object(lan, "main", return_value=0) as local, patch.object(vps, "main") as public:
            self.manager.upgrade(self.instance)
        local.assert_called_once_with(["--edition", self.product.key], friendly=True)
        public.assert_not_called()
        self.assertEqual(self.instance.raw_config, before)
        self.assertEqual(self.instance.config["TZ"], "Europe/London")

    def test_lan_entry_does_not_issue_certificate(self):
        with patch.object(self.manager, "mode", return_value={"bind_ip": "192.168.1.9"}), patch.object(self.manager, "status") as status, patch.object(self.manager, "proxy") as proxy:
            self.manager.entry(self.instance)
        status.assert_called_once()
        proxy.assert_not_called()

    def test_https_repair_never_queries_release_or_upgrades_bot_and_keeps_domain(self):
        self.ui.ask.return_value = "2"
        self.ui.confirm.return_value = True
        proxy = Mock()
        proxy.read_state.return_value = {"domains": {self.product.key: {"domain": "manage.example.test", "email": "admin@example.test"}}}
        proxy.detect.return_value = SimpleNamespace(state="detected", message="ready")
        proxy.configure.return_value = SimpleNamespace(state="healthy", message="healthy")
        with patch.object(self.manager, "mode", return_value=None), patch.object(self.manager, "proxy", return_value=proxy), patch.object(self.manager, "recheck", return_value=self.instance), patch.object(releases, "ReleaseClient") as client, patch.object(vps, "main") as installer:
            self.manager.entry(self.instance)
        proxy.configure.assert_called_once_with("manage.example.test", "admin@example.test")
        installer.assert_not_called()
        client.assert_not_called()

    def test_proxy_prune_requires_confirmation_and_forwards_exact_plan(self):
        self.ui.ask.return_value = "5"
        self.ui.confirm.return_value = True
        proxy = Mock()
        proxy.external_entry.return_value = None
        proxy.manage_backups.return_value = {"plan": {"remove": [{"name": "proxy-fixture.tar.gz"}], "plan_id": "a" * 64}}
        with patch.object(self.manager, "recheck", return_value=self.instance), patch.object(self.manager, "proxy", return_value=proxy):
            self.manager.backups(self.instance)
        self.assertEqual(proxy.manage_backups.call_args_list[-1].kwargs, {"keep": 5, "plan": "a" * 64})
        self.assertEqual(proxy.manage_backups.call_args_list[-1].args, ("prune",))

    def test_instance_snapshot_cancel_never_stops_services_or_creates_backup(self):
        from tg2cloud.deployment import backup
        self.ui.ask.side_effect = ["6", "/opt/tg2cloud-snapshots/clouddrive2"]
        self.ui.confirm.return_value = False
        with patch.object(backup, "output_directory"), patch.object(backup, "create") as create:
            self.manager.backups(self.instance)
        create.assert_not_called()
        self.session.run.assert_not_called()

    def test_external_proxy_does_not_use_managed_directory_prune(self):
        self.ui.ask.return_value = "5"
        proxy = Mock()
        proxy.external_entry.return_value = object()
        with patch.object(self.manager, "recheck", return_value=self.instance), patch.object(self.manager, "proxy", return_value=proxy):
            self.manager.backups(self.instance)
        proxy.manage_backups.assert_not_called()

    def test_uninstall_custom_dir_refused_standard_uses_existing_confirmations(self):
        custom = instances.Instance(self.product, Path("/opt/custom-fixture"), True)
        with patch.object(management.uninstall, "main", return_value=0) as remove:
            with self.assertRaises(ValueError):
                self.manager.remove(custom)
            remove.assert_not_called()
            self.ui.confirm.return_value = True
            self.manager.remove(self.instance)
        remove.assert_called_once_with(["--edition", self.product.key])

    def test_missing_selected_edition_enters_its_installer_only_after_confirmation(self):
        product = PRODUCTS["openlist"]
        instance = instances.Instance(product, Path(product.install_dir), False)
        manager = management.Management(product, self.session, self.log, self.ui, mode_hint="public")
        for confirmed in (False, True):
            self.ui.confirm.return_value = confirmed
            with self.subTest(confirmed=confirmed), patch.object(manager, "discover", return_value=instance), patch.object(manager, "upgrade") as installer:
                self.assertEqual(manager.run(), 0)
            self.assertEqual(installer.call_count, int(confirmed))
            if confirmed:
                installer.assert_called_once_with(instance)

    def test_entry_hint_controls_new_install_only_existing_lan_is_not_converted(self):
        for mode in ("public", "lan"):
            manager = management.Management(self.product, self.session, self.log, self.ui, mode_hint=mode)
            fresh = instances.Instance(self.product, self.instance.directory, False)
            with self.subTest(mode=mode), patch.object(manager, "mode", return_value=None), patch.object(lan, "main", return_value=0) as local, patch.object(vps, "main", return_value=0) as public:
                manager.upgrade(fresh)
            self.assertEqual(local.call_count, int(mode == "lan"))
            self.assertEqual(public.call_count, int(mode == "public"))
        manager = management.Management(self.product, self.session, self.log, self.ui, mode_hint="public")
        with patch.object(manager, "mode", return_value={"bind_ip": "192.168.1.9"}), patch.object(lan, "main", return_value=0) as local, patch.object(vps, "main") as public:
            manager.upgrade(self.instance)
        local.assert_called_once()
        public.assert_not_called()

    def test_successful_removal_exits_menu_without_reading_deleted_runtime_again(self):
        self.ui.ask.return_value = "14"
        with patch.object(self.manager, "discover", return_value=self.instance) as discover, patch.object(self.manager, "remove", return_value=True):
            self.assertEqual(self.manager.run(), 0)
        discover.assert_called_once()
        self.assertIn("14. 卸载当前实例", "\n".join(self.messages))

    def test_failed_or_partial_removal_exits_without_offering_reinstallation(self):
        self.ui.ask.return_value = "14"
        with patch.object(self.manager, "discover", return_value=self.instance) as discover, patch.object(self.manager, "remove", side_effect=RuntimeError("partial")), patch.object(self.manager, "upgrade") as installer:
            self.assertEqual(self.manager.run(), 1)
        discover.assert_called_once()
        installer.assert_not_called()


class ManagerCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.private = Path(temporary.name).resolve()
        self.root, self.command = self.private / "manager", self.private / "bin/tg2cloud"
        if os.name != "posix":
            enter_context(self, patch.object(host, "edition_lock", side_effect=lambda _: nullcontext()))
            enter_context(self, patch.object(management.uninstall, "edition_lock", side_effect=lambda _: nullcontext()))
        runtime.install(source=ROOT, root=self.root, command=self.command)
        enter_context(self, patch.object(runtime, "ROOT", self.root))
        enter_context(self, patch.object(runtime, "COMMAND", self.command))
        enter_context(self, patch.object(runtime, "LOCK_ROOT", self.private / "locks"))
        enter_context(self, patch.object(management.uninstall, "LOCK_ROOT", self.private / "locks"))
        enter_context(self, patch.object(management.uninstall, "LAN_ROOT", self.private / "lan"))
        enter_context(self, patch.object(management.uninstall, "PROXY_BACKUP_ROOT", self.private / "proxy-backups"))
        self.products = {key: replace(p, install_dir=str(self.private / key), backup_dir=str(self.private / (key + "-backups"))) for key, p in PRODUCTS.items()}
        enter_context(self, patch.dict(management.uninstall.PRODUCTS, self.products))
        self.snapshot = enter_context(self, patch.object(management.uninstall, "docker_snapshot", return_value=({}, {})))
        self.state = enter_context(self, patch.object(management.uninstall, "read_state", return_value=management.uninstall.empty_state()))
        enter_context(self, patch.object(management.uninstall, "mountpoints", return_value=()))
        self.session = Mock()
        self.session.hold_lock.side_effect = lambda *_: nullcontext()
        self.messages = []
        self.log = SafeLog(self.messages.append)

    def test_last_full_removal_deletes_only_owned_command_and_code(self):
        foreign = self.private / "unrelated.txt"
        foreign.write_text("KEEP", encoding="utf-8")
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertFalse(self.root.exists())
        self.assertFalse(self.command.exists())
        self.assertEqual(foreign.read_text(), "KEEP")
        self.assertIn("快捷命令及受管管理代码已移除", "\n".join(self.messages))

    def test_retained_other_edition_data_and_session_keep_management(self):
        directory = Path(self.products["openlist"].install_dir)
        directory.mkdir()
        session = directory / "bot.session"
        session.write_text("FAKE_KEEP_SESSION", encoding="utf-8")
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())
        self.assertTrue(self.root.exists())
        self.assertEqual(session.read_text(), "FAKE_KEEP_SESSION")

    def test_stopped_partial_container_or_managed_network_keeps_command(self):
        for value in (({"tg2cloud-openlist": {"running": False}}, {}), ({}, {"tg2cloud-openlist-net": {}})):
            self.snapshot.return_value = value
            management.uninstall.cleanup_manager(self.session, self.log)
            self.assertTrue(self.command.exists())
            self.assertTrue(self.root.exists())

    def test_addon_route_and_unknown_proxy_state_keep_command(self):
        self.state.return_value = {"domains": {}, "external_webdav": {"openlist": {}}}
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())
        self.state.side_effect = ValueError("unsupported state")
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())

    def test_busy_installation_and_foreign_command_are_not_cleaned(self):
        with patch.object(runtime, "lifecycle_lock", side_effect=RuntimeError("busy")):
            management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())
        self.command.write_text("#!/bin/sh\necho other-owner\n", encoding="utf-8")
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertIn("other-owner", self.command.read_text())
        self.assertTrue(self.root.exists())

    def test_foreign_parent_mount_and_unknown_files_do_not_get_deleted(self):
        self.snapshot.return_value = ({"foreign": {"mounts": [{"Type": "bind", "Source": str(self.private)}]}}, {})
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())
        self.snapshot.return_value = ({}, {})
        unknown = self.root / "user-data.txt"
        unknown.write_text("KEEP", encoding="utf-8")
        management.uninstall.cleanup_manager(self.session, self.log)
        self.assertTrue(self.command.exists())
        self.assertEqual(unknown.read_text(), "KEEP")


class FriendlyInstallTests(unittest.TestCase):
    def setUp(self):
        enter_context(self, patch.object(vps.architecture, "check_docker"))
        enter_context(self, patch.object(runtime, "lifecycle_lock", side_effect=lambda: nullcontext()))

    def test_confirmed_installer_creates_offline_command_but_check_and_cancel_do_not(self):
        product = PRODUCTS["openlist"]
        instance = instances.Instance(product, Path(product.install_dir), True, "1.3.1")
        release = releases.Release("v1.3.1", "a" * 40)
        plan = install.Plan(instance, "upgrade", Mock())
        for mode in ("check", "cancel", "execute", "no-change", "removed"):
            with self.subTest(mode=mode):
                client, ui = Mock(), Mock()
                client.resolve.return_value, client.download.return_value = release, ROOT
                ui.confirm.return_value = mode not in {"cancel", "check"}
                plan.action = "current" if mode in {"no-change", "removed"} else "upgrade"
                discovery = [instance, instances.Instance(product, instance.directory, False)] if mode == "removed" else None
                with patch.object(vps.preflight, "validate_host"), patch.object(instances, "docker_inventory", return_value=set()), patch.object(instances, "discover", return_value=instance, side_effect=discovery), patch.object(releases, "ReleaseClient", return_value=client), patch.object(terminal, "Terminal", return_value=ui), patch.object(install, "make_plan", return_value=plan), patch.object(install, "execute_plan") as execute, patch.object(runtime, "check_destination") as check, patch.object(runtime, "install") as local, patch.object(vps, "SafeLog", return_value=SafeLog(lambda _: None)):
                    args = ["--edition", product.key] + (["--check"] if mode == "check" else [])
                    self.assertEqual(vps.main(args, friendly=True), 1 if mode == "removed" else 0)
                    self.assertEqual(local.call_count, int(mode in {"execute", "no-change"}))
                    self.assertEqual(execute.call_count, int(mode == "execute"))
                    self.assertEqual(check.call_count, int(mode != "check"))

    def test_fresh_setup_render_occurs_only_after_https_success(self):
        product = PRODUCTS["openlist"]
        instance = instances.Instance(product, Path(product.install_dir), False)
        manager = Mock()
        plan = install.Plan(instance, "install", manager, {})
        manager.status.return_value = SimpleNamespace(state="failed", message="HTTPS failed")
        session, log, ui = Mock(), SafeLog(lambda _: None), Mock()
        with patch.object(install, "edition_lock", return_value=nullcontext()), patch.object(instances, "discover", return_value=instance), patch.object(instances, "docker_inventory", return_value=set()), patch.object(instances, "check_foreign_gateway"), patch.object(install.preflight, "resource_check"), patch.object(install, "apply_base"), patch.object(terminal, "show_setup_credentials") as show, self.assertRaises(RuntimeError):
            install.execute_plan(plan, releases.Release("v1.3.1", "a" * 40), ROOT, None, session, log, ui)
        show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
