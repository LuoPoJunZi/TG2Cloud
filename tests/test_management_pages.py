"""Terminal page navigation and rendering; synthetic instances, no real Docker."""
from __future__ import annotations

import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from tg2cloud.cli import management
from tg2cloud.cli.presentation import page_heading, terminal_report
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.instances import Instance
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.state import ProxyReport


class ManagementPagesTests(unittest.TestCase):
    def setUp(self):
        self.product = PRODUCTS["clouddrive2"]
        self.instance = Instance(self.product, Path(self.product.install_dir), True, "1.4.4", True)
        self.output = []
        self.ui, self.session = Mock(), Mock()
        self.log = SafeLog(self.output.append)
        self.log.register({"WEBDAV_PASSWORD": "PRIVATE_FIXTURE_PASSWORD"})
        self.manager = management.Management(self.product, self.session, self.log, self.ui)
        self.session.run.return_value = (0, "running healthy")
        self.ui.ask.return_value = "0"
        self.ui.confirm.return_value = False
        self.proxy = Mock()
        self.proxy.status.return_value = ProxyReport("manage.example.test", "healthy", "not rendered as a paragraph", (), (
            ("PROXY_CERT_END", "Mar 01 00:00:00 2027 GMT"),
            ("PROXY_RENEW_ATTEMPT", "1792796400"), ("PROXY_RENEW_RESULT", "OK")))
        for context in (patch.object(self.manager, "mode", return_value=None),
                        patch.object(self.manager, "proxy", return_value=self.proxy),
                        patch.object(self.manager, "discover", return_value=self.instance),
                        patch.object(self.manager, "recheck", side_effect=lambda value: value),
                        patch.object(management, "edition_lock", side_effect=lambda _: nullcontext())):
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    def text(self):
        return "\n".join(self.output)

    def test_status_uses_real_version_chinese_fields_and_preserves_local_only_boundary(self):
        self.manager.status(self.instance)
        for label in ("── 查看运行状态 ──", "CloudDrive2 · 版本 1.4.4", "请稍候", "Bot 状态：运行中",
                      "Bot 健康：通过（容器检查）", "网关状态：运行中", "管理地址：https://manage.example.test",
                      "证书到期：2027-03-01", "续期检查：", "不代表外网可达", "不代表实际续签"):
            self.assertIn(label, self.text())
        self.assertNotIn("not rendered as a paragraph", self.text())
        self.assertNotIn("running / healthy", self.text())
        self.assertEqual(self.session.run.call_count, 2)

    def test_unknown_container_response_does_not_become_healthy_or_leak_raw_output(self):
        self.session.run.return_value = (1, "PRIVATE_FIXTURE_PASSWORD")
        self.manager.status(self.instance)
        self.assertIn("Bot 状态：未核实", self.text())
        self.assertIn("网关状态：未核实", self.text())
        self.assertNotIn("PRIVATE_FIXTURE", self.text())

    def test_stopped_container_does_not_reuse_stale_healthy_check_as_current_success(self):
        self.session.run.return_value = (0, "exited healthy")
        self.manager.status(self.instance)
        self.assertIn("Bot 状态：已停止", self.text())
        self.assertIn("Bot 健康：未检查（容器未运行）", self.text())
        self.assertNotIn("Bot 健康：通过", self.text())

    def test_failed_proxy_fields_and_renewal_reminders_are_visible(self):
        self.proxy.status.return_value = ProxyReport("manage.example.test", "certificate_error", "summary", (
            ("HTTPS 管理页", "失败"), ("证书域名与有效期", "失败")), (), ("最近续期检查失败",))
        self.manager.status(self.instance)
        for label in ("入口检查：证书检查未通过", "未通过项目：", "HTTPS 管理页", "证书域名与有效期", "最近续期检查失败"):
            self.assertIn(label, self.text())

    def test_refresh_stays_in_page_and_rediscovers_actual_version(self):
        self.ui.ask.side_effect = ["1", "0"]
        new = replace(self.instance, version="1.4.5")
        self.manager.discover.return_value = new
        self.manager.read_page(self.instance, self.manager.status, "重新检查")
        self.assertIn("版本 1.4.4", self.text())
        self.assertIn("版本 1.4.5", self.text())
        self.assertEqual(self.text().count("── 查看运行状态 ──"), 2)
        self.assertNotIn("── TG2Cloud 本地管理 ──", self.text())
        self.manager.discover.assert_called_once()
        self.assertTrue(all(call.kwargs["default"] == "0" for call in self.ui.ask.call_args_list))

    def test_read_error_is_kept_on_the_result_page_and_never_passed(self):
        operation = Mock(side_effect=ValueError("synthetic check failure"))
        self.manager.read_page(self.instance, operation, "重新检查")
        self.assertIn("检查未完成", self.text())
        self.assertIn("0. 返回主菜单", self.text())
        self.assertNotIn("检查通过", self.text())
        self.manager.discover.assert_not_called()

    def test_removed_instance_after_refresh_never_enters_installer(self):
        self.ui.ask.side_effect = ["1"]
        self.manager.discover.return_value = replace(self.instance, present=False)
        with patch.object(self.manager, "upgrade") as install:
            self.manager.read_page(self.instance, Mock(), "重新检查")
        install.assert_not_called()
        self.assertIn("不会自动安装或重建", self.text())

    def test_lan_status_has_no_certificate_fields_or_public_proxy_calls(self):
        from tg2cloud.deployment.proxy import lan
        self.manager.mode.return_value = {"bind_ip": "192.168.1.9"}
        with patch.object(management.instances, "docker_inventory", return_value=set()), \
                patch.object(lan, "inspect_lan", return_value={"running": True}), patch.object(lan, "check_entry"):
            self.manager.status(self.instance)
        self.assertIn("访问模式：内网 HTTP", self.text())
        self.assertIn("证书：不适用", self.text())
        self.assertNotIn("证书到期", self.text())
        self.proxy.status.assert_not_called()

    def test_log_sources_are_separated_redacted_and_never_followed(self):
        self.session.run.side_effect = [(0, "safe bot line\nPRIVATE_FIXTURE_PASSWORD\n"), (0, "safe gateway line\n")]
        self.manager.logs(self.instance)
        self.assertLess(self.text().index("── Bot 日志 ──"), self.text().index("safe bot line"))
        self.assertLess(self.text().index("── CloudDrive2 日志 ──"), self.text().index("safe gateway line"))
        self.assertNotIn("PRIVATE_FIXTURE_PASSWORD", self.text())
        self.assertIn("不持续刷新", self.text())
        for call in self.session.run.call_args_list:
            self.assertIn("--since 30m --tail 100", call.args[0])
            self.assertNotIn("--follow", call.args[0])

    def test_empty_log_and_one_source_failure_do_not_hide_the_other_service(self):
        for failure in ((1, "PRIVATE_FIXTURE_PASSWORD"), TimeoutError("PRIVATE_FIXTURE_PASSWORD")):
            self.output.clear()
            self.session.run.reset_mock()
            self.session.run.side_effect = [failure, (0, "")]
            self.manager.logs(self.instance)
            self.assertIn("Bot 日志读取失败", self.text())
            self.assertIn("── CloudDrive2 日志 ──", self.text())
            self.assertIn("最近 30 分钟暂无日志", self.text())
            self.assertNotIn("PRIVATE_FIXTURE_PASSWORD", self.text())
            self.assertEqual(self.session.run.call_count, 2)

    def test_page_return_is_one_action_and_no_extra_pause_on_submenu_cancel(self):
        for number in ("4", "7", "13"):
            with self.subTest(number=number):
                self.ui.ask.reset_mock()
                self.ui.ask.side_effect = [number, "0", "0"]
                self.assertEqual(self.manager.run(), 0)
                self.assertEqual(self.ui.ask.call_count, 3)
        self.ui.confirm.assert_not_called()

    def test_upgrade_result_waits_for_explicit_return_before_showing_main_again(self):
        self.ui.ask.side_effect = ["1", "0", "0"]
        with patch.object(self.manager, "upgrade") as upgrade:
            self.assertEqual(self.manager.run(), 0)
        upgrade.assert_called_once_with(self.instance)
        self.assertEqual(self.ui.ask.call_count, 3)
        first = self.text().index("── TG2Cloud 本地管理 ──")
        second = self.text().index("── TG2Cloud 本地管理 ──", first + 1)
        self.assertLess(self.text().index("0. 返回主菜单"), second)

    def test_diagnostic_terminal_is_plain_but_export_keeps_original_markdown(self):
        from tg2cloud.deployment import diagnostics
        original = "# TG2Cloud 故障诊断报告\n\n## 建议处理顺序\n1. synthetic advice\n"
        self.ui.ask.side_effect = ["12", "/private/reports", "0", "0"]
        self.ui.confirm.return_value = True
        with patch.object(diagnostics, "collect", return_value=original), patch.object(diagnostics, "save", return_value=Path("report.md")) as save:
            self.assertEqual(self.manager.run(), 0)
        save.assert_called_once_with(original, Path("/private/reports"))
        self.assertNotIn("# TG2Cloud", self.text())
        self.assertIn("── 建议处理顺序 ──", self.text())
        self.assertEqual(self.text().count("── 故障诊断报告 ──"), 1)

    def test_backup_group_labels_match_execution_and_keep_confirmation(self):
        from tg2cloud.deployment import backup
        self.ui.ask.side_effect = ["2", "/private/snapshots"]
        with patch.object(backup, "output_directory"), patch.object(backup, "create") as create:
            self.assertFalse(self.manager.backups(self.instance))
        create.assert_not_called()
        self.assertIn("实例备份\n1. 查看历史备份\n2. 创建实例快照\n3. 校验实例快照", self.text())
        self.assertIn("共享代理\n4. 创建代理备份\n5. 查看代理备份\n6. 校验代理备份\n7. 清理代理备份", self.text())
        self.assertIn("短暂停止所选 Bot 与网关", self.ui.confirm.call_args.args[0])

    def test_heading_and_report_helpers_do_not_need_runtime_dependencies(self):
        self.assertEqual(page_heading("查看运行日志", PRODUCTS["openlist"]), "\n── 查看运行日志 ──\n\nOpenList\n")
        original = "# Title\n\n## Heading\ntext\n"
        self.assertEqual(terminal_report(original), "── Heading ──\ntext")
        self.assertEqual(original, "# Title\n\n## Heading\ntext\n")

    def test_both_editions_render_only_their_own_services(self):
        for product in PRODUCTS.values():
            with self.subTest(edition=product.key):
                self.output.clear()
                self.session.run.reset_mock()
                self.session.run.side_effect = None
                self.session.run.return_value = (0, "running healthy")
                current = replace(self.instance, product=product, directory=Path(product.install_dir))
                manager = management.Management(product, self.session, self.log, self.ui)
                with patch.object(manager, "mode", return_value=None), patch.object(manager, "proxy", return_value=self.proxy):
                    manager.status(current)
                    manager.logs(current)
                self.assertIn(product.display_name + " · 版本 1.4.4", self.text())
                self.assertIn("── " + product.display_name + " 日志 ──", self.text())
                for call in self.session.run.call_args_list:
                    self.assertTrue(call.args[0].endswith((product.bot_container, product.storage_container)))
