"""Installation feedback never substitutes log wording for execution evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from tg2cloud.cli import vps
from tg2cloud.cli.presentation import (
    InstallerLog,
    OperationReport,
    classify_install_line,
)
from tg2cloud.deployment import configuration, install, instances, readiness, releases
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.version import VERSION

ROOT = Path(__file__).resolve().parents[1]
RELEASE = releases.Release("v" + VERSION, "a" * 40)
PIP_WARNING = "#12 1.3 WARNING: Running pip as the 'root' user can result in broken permissions"
SUCCESS = "\n".join(("TG2CLOUD_DATABASE_BACKUP=OK", "TG2CLOUD_CODE=OK", "TG2CLOUD_VERSION=" + VERSION,
                     "TG2CLOUD_BOT_HEALTH=healthy", "TG2CLOUD_RESULT=SUCCESS")) + "\n"


def feedback(**values):
    return OperationReport(**{"edition": "clouddrive2", "label": "CloudDrive2", "previous": "1.4.2",
                              "target": VERSION, "action": "upgrade", "mode": "https", **values})


class LogClassificationTests(unittest.TestCase):
    def test_known_warnings_require_managed_base_and_build_context(self):
        lines = (PIP_WARNING,
                 "#8 0.5 rehash: warning: skipping ca-certificates.crt,it does not contain exactly one certificate or CRL",
                 "#9 1.2 useradd warning: app's uid 10001 is greater than SYS_UID_MAX 999")
        for line, key in zip(lines, ("pip", "ca", "uid")):
            with self.subTest(key=key):
                self.assertEqual(classify_install_line(line, base=True)[:2], ("提醒", key))
                self.assertEqual(classify_install_line(line, base=False)[0], "待核对")
                self.assertEqual(classify_install_line(line.split(" ", 2)[2], base=True)[0], "待核对")
        for capacity in (20, 50):
            line = f"[TG2Cloud] 警告：安装文件系统总容量低于推荐的 {capacity}GB"
            self.assertEqual(classify_install_line(line, base=True)[:2], ("提醒", "capacity"))
        self.assertEqual(classify_install_line("WARNING: unknown certificate problem", base=True)[0], "待核对")

    def test_actual_errors_take_precedence_and_do_not_make_ordinary_error_words_fatal(self):
        for line in ("[TG2Cloud][ERROR] 构建失败", "E: Repository has no Release file", "Err:2 repository unavailable",
                     "ERROR: build failed after WARNING", "Permission denied", "No space left on device"):
            with self.subTest(line=line):
                self.assertEqual(classify_install_line(line, base=True)[0], "错误")
        self.assertEqual(classify_install_line("[TG2Cloud] 安装基础软件")[0], "信息")
        self.assertEqual(classify_install_line('configuration contains "error": false')[0], "")

    def test_ansi_and_repeated_warnings_do_not_create_unbounded_or_duplicate_summary(self):
        report = feedback()
        report.stage = "基础安装与升级"
        for _ in range(200):
            report.observe_line("\x1b[33m" + PIP_WARNING + "\x1b[0m")
        report.observe_base(0, PIP_WARNING + "\n" + SUCCESS)
        self.assertEqual(report.alerts, {"pip"})
        for index in range(1000):
            report.observe_line("WARNING: FAKE_PRIVATE_" + str(index))
        self.assertEqual(report.alerts, {"pip", "unknown"})
        self.assertNotIn("FAKE_PRIVATE", repr(report))

    def test_raw_protocol_markers_remain_exact_in_nonfriendly_mode(self):
        messages = []
        log = InstallerLog(SafeLog(messages.append), friendly=False)
        log.operation = feedback()
        for line in SUCCESS.splitlines():
            log(line)
        self.assertEqual("\n".join(messages) + "\n", SUCCESS)
        log.operation.stage = "基础安装与升级"
        log(PIP_WARNING)
        self.assertTrue(messages[-1].startswith("[提醒]"))

    def test_sensitive_output_is_redacted_before_display_and_never_stored_in_report(self):
        messages = []
        safe = SafeLog(messages.append)
        safe.register({"PASSWORD": "FAKE_PRIVATE_PASSWORD"})
        log = InstallerLog(safe)
        report = feedback()
        report.stage = "基础安装与升级"
        log.operation = report
        log("WARNING: password=FAKE_PRIVATE_PASSWORD")
        log("TG2CLOUD_CLI_RESULT=FAILED：FAKE_PRIVATE_PASSWORD")
        self.assertNotIn("FAKE_PRIVATE_PASSWORD", "\n".join(messages))
        self.assertNotIn("FAKE_PRIVATE_PASSWORD", repr(report))
        self.assertTrue(messages[-1].startswith("[错误]"))

    def test_repeated_log_lines_keep_original_warning_but_only_explain_once(self):
        messages = []
        log = InstallerLog(SafeLog(messages.append))
        log.operation = feedback()
        log.operation.stage = "基础安装与升级"
        for _ in range(10):
            log(PIP_WARNING)
        self.assertEqual("\n".join(messages).count(PIP_WARNING), 10)
        self.assertEqual("\n".join(messages).count("不代表 Bot 的运行身份"), 1)


class EvidenceTests(unittest.TestCase):
    def test_nonzero_missing_conflicting_or_wrong_version_markers_never_confirm_code(self):
        for code, output in ((1, SUCCESS), (0, "TG2CLOUD_RESULT=SUCCESS\n"),
                             (0, SUCCESS + "TG2CLOUD_CODE=MISMATCH\n"),
                             (0, SUCCESS + "TG2CLOUD_VERSION=0.0.0\n")):
            with self.subTest(code=code, output=output[-40:]):
                report = feedback()
                report.observe_base(code, output)
                self.assertNotEqual(report.checks.get("code"), "ok")
        report = feedback()
        report.observe_base(0, SUCCESS)
        self.assertEqual(report.checks, {"backup": "ok", "code": "ok", "health": "ok"})
        report.observe_base(1, "TG2CLOUD_DATABASE_BACKUP=FAILED\n")
        self.assertEqual(report.checks["backup"], "failed")

    def test_render_separates_skipped_unknown_failed_and_manual_checks(self):
        report = feedback()
        report.completed = True
        report.checks.update(base="ok", config="ok", entry="ok", webdav="not_run")
        report.readiness = dict.fromkeys(readiness.LABELS, "ok")
        messages = []
        report.render(messages.append)
        text = "\n".join(messages)
        for expected in ("基础安装与升级：通过", "升级前数据库备份：未核实", "WebDAV 写入与大小复验：未执行",
                         "实际 Telegram 转存：待人工验收", "公网访问：待外部网络验收", "不等于哈希校验"):
            self.assertIn(expected, text)
        self.assertNotIn("全部验收通过", text)
        report.mode = "lan"
        report.render(messages.append)
        self.assertIn("公网 HTTPS：不适用（内网模式）", messages[-1])
        self.assertIn("局域网客户端访问：待其他设备验收", messages[-1])
        self.assertNotIn("公网访问：待外部网络验收", messages[-1])

    def test_known_warning_is_not_called_nonfatal_until_base_is_confirmed(self):
        report = feedback()
        report.alerts = {"pip", "unknown"}
        messages = []
        report.render(messages.append)
        self.assertIn("基础步骤未确认通过，不能判作本次无害", messages[-1])
        self.assertIn("有未识别的 WARNING", messages[-1])
        report.checks["base"] = "ok"
        report.render(messages.append)
        self.assertIn("本次未阻断基础步骤", messages[-1])


class ExecutionSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.product = PRODUCTS["clouddrive2"]
        self.instance = instances.Instance(self.product, self.root, True, "1.4.2", True, "image", {}, b"KEEP=1\n")
        (self.root / ".env").write_bytes(self.instance.raw_config)
        self.messages = []
        self.log = InstallerLog(SafeLog(self.messages.append))
        self.ui, self.session = Mock(), Mock()
        self.ui.confirm.return_value = False
        self.session.run.return_value = (0, json.dumps({"schema": 1, "version": VERSION, "edition": self.product.key,
            "checks": dict.fromkeys(readiness.LABELS, "ok"), "ready": True}))

    def plan(self, action="upgrade"):
        manager = Mock()
        manager.status.return_value = Mock(state="healthy", domain="manage.example.test", message="local entry OK")
        return install.Plan(self.instance, action, manager)

    def run_plan(self, plan, **options):
        with ExitStack() as stack:
            stack.enter_context(patch.object(install, "edition_lock", return_value=nullcontext()))
            stack.enter_context(patch.object(instances, "docker_inventory", return_value=set()))
            stack.enter_context(patch.object(instances, "discover", return_value=self.instance))
            stack.enter_context(patch.object(instances, "check_foreign_gateway"))
            stack.enter_context(patch.object(install.upgrade, "assert_unmodified"))
            stack.enter_context(patch.object(install.preflight, "resource_check"))
            stack.enter_context(patch.object(install, "apply_base"))
            install.execute_plan(plan, RELEASE, ROOT, ROOT, self.session, self.log, self.ui, **options)

    def test_upgrade_reads_readiness_once_with_new_version_but_never_writes_webdav(self):
        for product in PRODUCTS.values():
            with self.subTest(edition=product.key):
                self.session.reset_mock()
                self.instance = replace(self.instance, product=product)
                self.session.run.return_value = (0, json.dumps({"schema": 1, "version": VERSION, "edition": product.key,
                    "checks": dict.fromkeys(readiness.LABELS, "ok"), "ready": True}))
                plan = self.plan()
                self.run_plan(plan)
                self.assertEqual(plan.feedback.readiness, dict.fromkeys(readiness.LABELS, "ok"))
                self.session.run.assert_called_once_with("docker exec " + product.bot_container + " python -B -m tg2cloud.monitoring.readiness", timeout=20)
                self.ui.confirm.assert_not_called()
                self.ui.reveal.assert_not_called()
                self.assertEqual(plan.feedback.checks["webdav"], "not_run")
                self.assertIsNone(self.log.operation)

    def test_entry_failure_retains_base_success_and_does_not_attempt_later_checks(self):
        plan = self.plan()
        plan.manager.status.return_value.state = "failed"
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            self.run_plan(plan, verify=True)
        self.assertEqual(plan.feedback.checks["base"], "ok")
        self.assertEqual(plan.feedback.checks["entry"], "failed")
        self.session.run.assert_not_called()
        self.ui.confirm.assert_not_called()
        self.assertIn("停止阶段：管理入口检查", "\n".join(self.messages))
        self.assertNotIn("本次执行完成", "\n".join(self.messages))

    def test_credentials_failure_does_not_erase_already_verified_entry(self):
        plan = self.plan(action="current")
        plan.configure_https = True
        with patch.object(install.terminal, "show_credentials", side_effect=ValueError("invalid saved value")), self.assertRaises(ValueError):
            self.run_plan(plan)
        self.assertEqual(plan.feedback.checks["entry"], "ok")
        self.assertEqual(plan.feedback.failure_stage, "后台账号设置")
        self.assertIn("本机 HTTPS：通过", self.messages[-1])
        self.assertNotIn("本次执行完成", self.messages[-1])

    def test_readiness_timeout_stale_or_unknown_protocol_does_not_fail_base_or_claim_readiness(self):
        for output in ("PRIVATE_TRACEBACK", json.dumps({"schema": 99}), json.dumps({
            "schema": 1, "version": "0.0.0", "ready": True, "checks": dict.fromkeys(readiness.LABELS, "ok")})):
            with self.subTest(output=output):
                self.session.run.return_value = (0, output)
                plan = self.plan()
                self.run_plan(plan)
                self.assertTrue(plan.feedback.completed)
                self.assertIsNone(plan.feedback.readiness)
        self.session.run.side_effect = TimeoutError("PRIVATE_TIMEOUT")
        plan = self.plan()
        self.run_plan(plan)
        self.assertTrue(plan.feedback.completed)
        self.assertIsNone(plan.feedback.readiness)
        self.assertNotIn("PRIVATE_", "\n".join(self.messages))

    def test_paused_partial_and_cooldown_observations_are_not_presented_as_success(self):
        for key, state in (("queue", "paused"), ("destination", "cooldown"), ("destination", "partial"), ("capacity", "failed")):
            with self.subTest(key=key, state=state):
                checks = dict.fromkeys(readiness.LABELS, "ok")
                checks[key] = state
                self.session.run.return_value = (0, json.dumps({"schema": 1, "version": VERSION, "ready": False, "checks": checks}))
                plan = self.plan()
                self.run_plan(plan)
                self.assertIn(readiness.STATES[state], self.messages[-1])
                self.assertIn("尚未全部确认", self.messages[-1])
                self.assertTrue(plan.feedback.completed)

    def test_verified_skipped_and_failed_webdav_keep_existing_confirmation_and_errors(self):
        for confirmed, result in ((False, (0, "unused")), (True, (0, "TG2CLOUD_DESTINATION=OK\n")),
                                  (True, (1, "TG2CLOUD_DESTINATION=OK\n")), (True, (0, "incomplete"))):
            with self.subTest(confirmed=confirmed, result=result):
                self.ui.confirm.reset_mock()
                self.ui.confirm.return_value = confirmed
                self.session.run.side_effect = lambda command, _result=result, **_: _result if "manage.sh verify" in command else (
                    0, json.dumps({"schema": 1, "version": VERSION, "ready": True, "checks": dict.fromkeys(readiness.LABELS, "ok")}))
                plan = self.plan()
                failed = confirmed and (result[0] or "TG2CLOUD_DESTINATION=OK" not in result[1])
                if failed:
                    with self.assertRaisesRegex(RuntimeError, "WebDAV"):
                        self.run_plan(plan, verify=True)
                else:
                    self.run_plan(plan, verify=True)
                self.ui.confirm.assert_called_once()
                self.assertEqual(plan.feedback.checks["webdav"], "failed" if failed else "ok" if confirmed else "not_run")
                self.assertEqual(plan.feedback.checks["base"], "ok")

    def test_interruption_does_not_probe_or_claim_rollback_and_original_exception_survives(self):
        plan = self.plan()
        with patch.object(install.readiness, "inspect") as inspect, self.assertRaises(KeyboardInterrupt), install.execution_feedback(
            plan, RELEASE, self.session, self.log, mode="https"
        ) as report:
            report.stage = "WebDAV 写入验收"
            report.checks.update(base="ok", entry="ok")
            raise KeyboardInterrupt
        inspect.assert_not_called()
        self.assertIsNone(self.log.operation)
        self.assertIn("操作中断", self.messages[-1])
        self.assertIn("不假定已回退", self.messages[-1])

    def test_interruption_during_readiness_and_closed_terminal_do_not_erase_state(self):
        plan = self.plan()
        with patch.object(install.readiness, "inspect", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt), install.execution_feedback(
            plan, RELEASE, self.session, self.log, mode="https"
        ) as report:
            report.checks["entry"] = "ok"
        self.assertTrue(plan.feedback.interrupted)
        self.assertIsNone(self.log.operation)
        with self.assertRaisesRegex(RuntimeError, "original failure"), install.execution_feedback(
            plan, RELEASE, self.session, Mock(side_effect=OSError("closed")), mode="https"
        ):
            raise RuntimeError("original failure")

    def test_base_requires_original_success_exit_markers_and_preserved_env(self):
        for result in ((1, PIP_WARNING + "\nE: broken repository\n" + SUCCESS),
                       (0, "TG2CLOUD_BOT_HEALTH=healthy\n"), (0, "TG2CLOUD_RESULT=SUCCESS\n")):
            with self.subTest(result=result):
                plan = self.plan()
                plan.feedback = feedback()
                self.session.run.return_value = result
                with patch.object(install.architecture, "check_docker"), patch.object(install.payload, "build_payload"), patch(
                    "tg2cloud.deployment.proxy.external_entry.apply_payload_network"
                ), patch.object(install.upgrade, "record_release") as record, self.assertRaises(RuntimeError):
                    install.apply_base(plan, RELEASE, ROOT, self.session, self.log)
                record.assert_not_called()
        plan = self.plan()
        plan.feedback = feedback()
        self.session.run.return_value = (0, SUCCESS)
        with patch.object(install.architecture, "check_docker"), patch.object(install.architecture, "check_container"), patch.object(
            install.payload, "build_payload"
        ), patch("tg2cloud.deployment.proxy.external_entry.apply_payload_network"), patch.object(install.upgrade, "record_release") as record:
            install.apply_base(plan, RELEASE, ROOT, self.session, self.log)
            self.assertEqual(plan.feedback.checks["config"], "ok")
            record.assert_called_once()
            record.reset_mock()
            with patch.object(configuration, "regular_private", return_value=b"CHANGED"), self.assertRaisesRegex(RuntimeError, ".env"):
                install.apply_base(plan, RELEASE, ROOT, self.session, self.log)
            self.assertEqual(plan.feedback.checks["config"], "failed")
            record.assert_not_called()

    def test_cli_exit_codes_distinguish_skipped_passed_and_failed_webdav(self):
        for verify, confirmation, verify_result, expected in (
            (False, None, (0, ""), 0), (True, False, (0, ""), 0),
            (True, True, (0, "TG2CLOUD_DESTINATION=OK\n"), 0),
            (True, True, (1, "TG2CLOUD_DESTINATION=OK\n"), 1),
        ):
            with self.subTest(verify=verify, confirmation=confirmation), ExitStack() as stack:
                instance = replace(self.instance, version=VERSION)
                plan = install.Plan(instance, "upgrade", self.plan().manager)
                session, ui, client = Mock(), Mock(), Mock()
                ui.confirm.side_effect = [True] + ([confirmation] if verify else [])
                session.run.side_effect = lambda command, _result=verify_result, **_: _result if "manage.sh verify" in command else (0, "unknown")
                client.resolve.return_value, client.download.return_value = RELEASE, ROOT
                for target, name, value in (
                    (vps.preflight, "validate_host", None), (vps.architecture, "check_docker", None),
                    (instances, "docker_inventory", set()), (instances, "discover", instance),
                    (instances, "check_foreign_gateway", None), (install.preflight, "resource_check", None),
                    (install.upgrade, "assert_unmodified", None), (install, "apply_base", None),
                    (install, "make_plan", plan), (vps, "LocalSession", session),
                    (vps.releases, "ReleaseClient", client), (vps.terminal, "Terminal", ui),
                    (vps, "SafeLog", SafeLog(self.messages.append)), (install, "edition_lock", nullcontext()),
                ):
                    stack.enter_context(patch.object(target, name, return_value=value))
                arguments = ["--edition", self.product.key] + (["--verify"] if verify else [])
                self.assertEqual(vps.main(arguments), expected)
                self.assertEqual(ui.confirm.call_count, 2 if verify else 1)
                writes = [call for call in session.run.call_args_list if "manage.sh verify" in call.args[0]]
                self.assertEqual(len(writes), int(verify and confirmation is True))


if __name__ == "__main__":
    unittest.main()
