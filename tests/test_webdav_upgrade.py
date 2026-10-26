"""Offline maintenance code upgrade is independent from WebDAV credentials."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from tg2cloud.addons.external_webdav import cli
from tg2cloud.cli import management
from tg2cloud.deployment import listening
from tg2cloud.deployment.profiles import PRODUCTS


class UpgradeRecoveryTests(unittest.TestCase):
    def test_each_state_upgrades_code_without_authentication_or_route_writes(self):
        for edition in PRODUCTS:
            for phase in ("pending", "needs_repair", "disabled", "enabled"):
                with (
                    self.subTest(edition=edition, phase=phase),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    root = Path(temp)
                    version = root / "src/tg2cloud/version.py"
                    version.parent.mkdir(parents=True)
                    version.write_text('VERSION="1.4.9"\n')
                    item = {
                        "phase": phase,
                        "instance_dir": "/opt/custom-test",
                        "revision": "fixed",
                    }
                    service = Mock(assert_record=Mock())
                    service.product = PRODUCTS[edition]
                    service.record.return_value = item
                    service.locked.side_effect = lambda: nullcontext()
                    service.ui.confirm.return_value = True
                    args = Namespace(
                        action="upgrade",
                        edition=edition,
                        install_dir=None,
                        sample_file="",
                    )
                    with (
                        patch.object(cli, "source_root", return_value=root),
                        patch(
                            "tg2cloud.addons.external_webdav.releases.download",
                            return_value=(root, {"version": "1.4.9"}),
                        ),
                        patch.object(
                            cli.subprocess, "run", return_value=NS(returncode=0)
                        ) as execute,
                    ):
                        cli.perform(service, args)
                    command = execute.call_args.args[0]
                    self.assertIn("status", command)
                    self.assertIn("--runtime-check", command)
                    self.assertEqual(
                        command[command.index("--install-dir") + 1], "/opt/custom-test"
                    )
                    service.install_runtime.assert_called_once()
                    service.assert_record.assert_called_once_with(item)
                    service.maintain.assert_not_called()
                    service.configure.assert_not_called()
                    service.ui.ask.assert_not_called()
                    service.manager.apply_shared_state_locked.assert_not_called()
                    self.assertEqual(
                        item,
                        {
                            "phase": phase,
                            "instance_dir": "/opt/custom-test",
                            "revision": "fixed",
                        },
                    )

    def test_failed_candidate_keeps_old_tool_and_changed_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            v = root / "src/tg2cloud/version.py"
            v.parent.mkdir(parents=True)
            v.write_text('VERSION="1.4.9"\n')
            for failure in ("candidate", "revision"):
                service = Mock(assert_record=Mock())
                service.record.return_value = {
                    "phase": "needs_repair",
                    "instance_dir": "/opt/test",
                }
                service.product = PRODUCTS["clouddrive2"]
                service.ui.confirm.return_value = True
                service.locked.side_effect = lambda: nullcontext()
                if failure == "revision":
                    service.assert_record.side_effect = ValueError("changed")
                with (
                    patch.object(cli, "source_root", return_value=root),
                    patch(
                        "tg2cloud.addons.external_webdav.releases.download",
                        return_value=(root, {}),
                    ),
                    patch.object(
                        cli.subprocess,
                        "run",
                        return_value=NS(returncode=1 if failure == "candidate" else 0),
                    ),
                    self.assertRaises(ValueError),
                ):
                    cli.perform(
                        service,
                        Namespace(
                            action="upgrade", edition="clouddrive2", sample_file=""
                        ),
                    )
                service.install_runtime.assert_not_called()

    def test_candidate_preflight_accepts_stopped_gateway_but_rejects_route_drift(self):
        for active in (False, True):
            service = Mock(assert_record=Mock())
            service.product = PRODUCTS["clouddrive2"]
            service.record.return_value = {
                "phase": "needs_repair",
                "instance_dir": "/opt/test",
            }
            service.preflight.return_value = (
                NS(),
                {"external_webdav": {"clouddrive2": {"enabled": active}}},
            )
            args = Namespace(action="status", runtime_check=True)
            if active:
                with self.assertRaises(ValueError):
                    cli.perform(service, args)
            else:
                cli.perform(service, args)
            service.preflight.assert_called_once_with(
                "/opt/test", require_running=False
            )
            service.maintain.assert_not_called()
            service.ui.ask.assert_not_called()

    def test_repair_menu_offers_continue_configuration_by_default(self):
        service = Mock(assert_record=Mock())
        service.product = PRODUCTS["clouddrive2"]
        service.record.return_value = {"phase": "needs_repair"}
        service.ui.ask.side_effect = lambda prompt, **kwargs: kwargs["validate"]("0")
        cli.interactive(service, Namespace(action=None))
        menu = "\n".join(str(c.args[0]) for c in service.log.call_args_list)
        self.assertIn("继续完成配置", menu)
        self.assertEqual(service.ui.ask.call_args.kwargs["default"], "6")

    def test_unauthorized_account_explains_recovery_without_raw_response(self):
        from tg2cloud.addons.external_webdav import verification

        route = {
            "domain": "files.example.test",
            "backend_port": 19798,
            "username": "external-test",
        }
        with (
            patch.object(
                verification,
                "request",
                return_value=(401, b"PRIVATE_BACKEND_RESPONSE", {}),
            ),
            self.assertRaises(ValueError) as failure,
        ):
            verification.check_backend(route, "SYNTHETIC_PASSWORD")
        self.assertIn("后台是否已创建", str(failure.exception))
        self.assertIn("继续完成配置", str(failure.exception))
        self.assertNotIn("PRIVATE_BACKEND_RESPONSE", str(failure.exception))
        self.assertNotIn("SYNTHETIC_PASSWORD", str(failure.exception))


class ListeningMenuTests(unittest.TestCase):
    def test_selected_edition_custom_path_and_three_actions_are_reused(self):
        for edition, product in PRODUCTS.items():
            manager = Mock()
            instance = NS(product=product, directory=Path("/opt/custom-test"))
            manager.recheck.side_effect = lambda item: item
            answers = iter(("1", "0", "2", "0", "3", "0", "0"))
            manager.ui.ask.side_effect = lambda prompt, answers=answers, **kw: kw[
                "validate"
            ](next(answers))
            with patch.object(listening, "main", return_value=0) as operation:
                listening.manage(manager, instance)
            self.assertEqual(
                [c.args[0][0] for c in operation.call_args_list],
                ["login", "status", "disable"],
            )
            for c in operation.call_args_list:
                self.assertEqual(
                    c.args[0][1:],
                    ["--edition", edition, "--install-dir", str(instance.directory)],
                )
            self.assertIn((16, "监听管理"), management.MENU_ITEMS)
