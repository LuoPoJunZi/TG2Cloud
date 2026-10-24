"""Allowlist diagnostics never echo arbitrary Docker output or user content."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def report_fixture(self, key="openlist"):
        value = {"schema": 1, "edition": key, "version": "1.4.4", "python": "3.12.0",
                 "checks": dict.fromkeys(host.readiness.LABELS, "ok"), "failures": {},
                 "configuration": "present", "disk_free_bytes": 100, "budget_bytes": 200}
        def run(command, **kwargs):
            if "monitoring.diagnostics" in command:
                return 0, json.dumps(value)
            if "inspect" in command:
                return 0, "running healthy"
            return 0, "1.2.3"
        return value, SimpleNamespace(product=PRODUCTS[key], directory=self.root), Mock(run=Mock(side_effect=run))

    def test_actionable_failure_advice_is_edition_scoped_and_readonly(self):
        for key in PRODUCTS:
            with self.subTest(edition=key):
                value, instance, session = self.report_fixture(key)
                value["checks"].update(destination="partial", queue="paused", capacity="failed")
                value["failures"] = {kind: 1 for kind in host.FAILURES if kind != "unchecked"}
                with patch.object(host, "inspect_entry", return_value=("HTTPS 管理入口", "未通过")):
                    report = host.collect(instance, session)
                for text in ("建议处理顺序", "Bot 专用账号", "写入权限", "冷却", "换名重传", "不要删除或覆盖", "容量不足", "手动暂停"):
                    self.assertIn(text, report)
                commands = "\n".join(call.args[0] for call in session.run.call_args_list)
                for forbidden in (" restart ", " stop ", " rm ", "curl", "verify_destination"):
                    self.assertNotIn(forbidden, commands)
                other = "clouddrive2" if key == "openlist" else "openlist"
                self.assertNotIn(PRODUCTS[other].bot_container, commands)

    def test_malformed_snapshot_types_never_leak_or_raise(self):
        for bad in ([], None, {"schema": True}, {"schema": 1, "edition": "openlist", "version": []}):
            with self.subTest(value=bad):
                _, instance, session = self.report_fixture()
                session.run.side_effect = None
                session.run.return_value = (0, json.dumps(bad))
                with patch.object(host, "inspect_entry", return_value=("HTTPS / LAN 入口", "未核实")):
                    report = host.collect(instance, session)
                self.assertIn("未核实", report)
                self.assertNotIn("Traceback", report)

    def test_entry_check_filters_private_messages_and_renewal_warning(self):
        _, instance, session = self.report_fixture()
        with patch("tg2cloud.deployment.proxy.lan.load_state", return_value=None), \
                patch("tg2cloud.deployment.proxy.manager.DomainProxyManager") as factory:
            manager = factory.return_value
            manager.status.return_value = SimpleNamespace(state="healthy", warnings=("PRIVATE_SECRET_URL",))
            self.assertEqual(host.inspect_entry(instance, session), ("HTTPS 管理入口", "本机检查通过；有维护提醒"))
            manager.status.side_effect = ValueError("PRIVATE_SECRET_URL")
            self.assertEqual(host.inspect_entry(instance, session), ("HTTPS / LAN 入口", "未核实"))
            manager.status.side_effect = None
            manager.status.return_value = SimpleNamespace(state="not_configured")
            self.assertEqual(host.inspect_entry(instance, session), ("HTTPS 管理入口", "未配置"))
            manager.configure.assert_not_called()

    def test_lan_identity_and_checks_are_required_without_proxy_mutations(self):
        _, instance, session = self.report_fixture()
        from tg2cloud.deployment.proxy import lan
        with patch.object(lan, "load_state", return_value={"install_dir": str(self.root), "bind_ip": "192.168.1.8"}), \
                patch.object(lan, "reject_https_route") as reject, \
                patch.object(lan, "inspect_lan", return_value={"running": True}), \
                patch("tg2cloud.deployment.instances.docker_inventory", return_value=set()), \
                patch.object(lan, "check_entry") as check:
            self.assertEqual(host.inspect_entry(instance, session), ("内网管理入口", "本机检查通过"))
            reject.assert_called_once_with(instance.product)
            check.assert_called_once_with(instance.product, "192.168.1.8")
            check.side_effect = ValueError("PRIVATE_ERROR")
            self.assertEqual(host.inspect_entry(instance, session)[1], "未核实")
            instance.directory = self.root / "other"
            check.reset_mock()
            self.assertEqual(host.inspect_entry(instance, session)[1], "未核实")
            check.assert_not_called()

    def test_good_recent_observations_do_not_claim_transfer_or_public_acceptance(self):
        _, instance, session = self.report_fixture()
        with patch.object(host, "inspect_entry", return_value=("HTTPS 管理入口", "本机检查通过")):
            report = host.collect(instance, session)
        self.assertIn("本次未发现明确处理项", report)
        self.assertIn("不把只读诊断当作完整验收", report)
        self.assertIn("不含公网", report)

    def test_snapshot_from_a_different_running_version_is_not_used_for_advice(self):
        value, instance, session = self.report_fixture()
        instance.version = "1.3.4"
        value["failures"] = {"authentication": 1}
        with patch.object(host, "inspect_entry", return_value=("HTTPS 管理入口", "本机检查通过")):
            report = host.collect(instance, session)
        self.assertIn("部分诊断未核实", report)
        self.assertNotIn("认证失败：在", report)
