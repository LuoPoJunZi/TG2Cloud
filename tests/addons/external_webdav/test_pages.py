"""Result navigation cannot repeat mutations or inspect a removed runtime."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.addons.external_webdav import cli, discovery
from tg2cloud.deployment.profiles import PRODUCTS


class PageTests(unittest.TestCase):
    def service(self, answers):
        messages, values = [], iter(answers)
        service = Mock(product=PRODUCTS["openlist"], log=messages.append)
        service.record.return_value = {"phase": "enabled"}
        service.ui.ask.side_effect = lambda *a, **kw: kw["validate"](next(values))
        return service, messages

    def test_host_validation_is_silent_but_all_platform_and_daemon_checks_run(self):
        with (patch.object(discovery.preflight, "validate_host") as host,
              patch.object(discovery.architecture, "check_environment") as environment,
              patch.object(discovery.architecture, "check_docker") as docker,
              patch.object(discovery.shutil, "which", return_value="fixture-tool")):
            session, log = Mock(), Mock()
            discovery.host(session, log=log)
        host.assert_called_once_with()
        environment.assert_called_once_with()
        docker.assert_called_once_with(session)
        log.assert_not_called()

    def args(self):
        return SimpleNamespace(action=None, edition="openlist", install_dir=None, sample_file="")

    def test_status_refresh_and_return_then_exit(self):
        service, messages = self.service(("2", "1", "0", "0"))
        cli.interactive(service, self.args())
        self.assertEqual(service.maintain.call_count, 2)
        self.assertTrue(all(call.args[0] == "status" for call in service.maintain.call_args_list))
        self.assertIn("返回功能菜单", "\n".join(messages))
        self.assertIn("OpenList · 版本", "\n".join(messages))
        service.configure.assert_not_called()

    def test_check_refresh_keeps_read_only_action(self):
        service, _ = self.service(("3", "1", "0", "0"))
        cli.interactive(service, self.args())
        self.assertEqual([call.args[0] for call in service.maintain.call_args_list], ["check", "check"])

    def test_mutation_result_has_no_refresh_action(self):
        service, messages = self.service(("5", "0", "0"))
        cli.interactive(service, self.args())
        service.maintain.assert_called_once_with("disable", sample_file="")
        self.assertNotIn("刷新状态", "\n".join(messages))

    def test_uninstall_never_reads_removed_record_again(self):
        service, _ = self.service(("7",))
        service.maintain.side_effect = lambda *a, **kw: setattr(service.record, "side_effect", AssertionError("removed runtime"))
        cli.interactive(service, self.args())
        service.maintain.assert_called_once_with("uninstall", sample_file="")

    def test_user_menu_returns_without_an_extra_pause(self):
        service, _ = self.service(("10", "0"))
        with patch("tg2cloud.addons.external_webdav.users.menu") as menu:
            cli.interactive(service, self.args())
        menu.assert_called_once_with(service, sample_file="")

    def test_failure_does_not_automatically_repeat_operation(self):
        service, _ = self.service(("4",))
        service.maintain.side_effect = ValueError("authentication unavailable")
        with self.assertRaises(ValueError):
            cli.interactive(service, self.args())
        service.maintain.assert_called_once()
