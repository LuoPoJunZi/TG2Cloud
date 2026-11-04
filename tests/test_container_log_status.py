"""Stdlib host inspection: effective logging, ownership and non-leaking output."""
from __future__ import annotations

import json
import shlex
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.cli.presentation import OperationReport
from tg2cloud.deployment import diagnostics, install, instances
from tg2cloud.deployment.profiles import PRODUCTS


class ContainerLogTests(unittest.TestCase):
    def fixture(self, edition="clouddrive2", mutation=None):
        product = PRODUCTS[edition]
        instance = instances.Instance(product, Path(product.install_dir), True, version="1.5.6")
        def run(command, **kwargs):
            name = shlex.split(command)[-1]
            shared = name in {"tg2cloud-proxy-nginx", "tg2cloud-proxy-certbot"}
            service = ("nginx" if name.endswith("nginx") else "certbot") if shared else (
                product.bot_service if name == product.bot_container else edition)
            value = {"driver": "json-file", "size": "10m", "files": "3",
                     "directory": "/opt/tg2cloud-proxy" if shared else str(instance.directory),
                     "service": service, "managed": "true",
                     "role": "reverse-proxy" if service == "nginx" else "certificate-manager"}
            if mutation:
                mutation(name, value)
            return 0, json.dumps(value)
        return instance, Mock(run=Mock(side_effect=run))

    def test_effective_limits_for_both_editions_only_inspect_selected_owned_containers(self):
        for edition in PRODUCTS:
            instance, session = self.fixture(edition)
            self.assertEqual(set(diagnostics.inspect_container_logs(instance, session).values()), {"ok"})
            commands = "\n".join(call.args[0] for call in session.run.call_args_list)
            for forbidden in (" restart ", " stop ", " rm ", "compose up", ".Config.Env", ".Config.Cmd", "logs "):
                self.assertNotIn(forbidden, commands)
            other = "openlist" if edition == "clouddrive2" else "clouddrive2"
            self.assertNotIn(PRODUCTS[other].bot_container, commands)
            self.assertEqual(session.run.call_count, 4)

    def test_old_gateway_is_pending_without_recreating_or_changing_anything(self):
        def old(name, value):
            if name == PRODUCTS["clouddrive2"].storage_container:
                value.update(size=None, files=None)
        instance, session = self.fixture(mutation=old)
        value = diagnostics.inspect_container_logs(instance, session)
        self.assertEqual(value["网关"], "pending")
        self.assertEqual(value["Bot"], "ok")
        text = "\n".join(diagnostics.log_rotation_lines(value))
        self.assertIn("旧容器需确认更新", text)
        self.assertIn("仅重启不会更新", text)

    def test_units_smaller_limits_custom_limits_and_other_drivers_are_distinct(self):
        for change, expected in (({"size": "10485760", "files": "3"}, "ok"),
                                 ({"size": "5MB", "files": "2"}, "ok"),
                                 ({"size": "100m", "files": "5"}, "custom"),
                                 ({"driver": "local"}, "other")):
            instance, session = self.fixture(mutation=lambda name, value, change=change: value.update(change))
            self.assertEqual(set(diagnostics.inspect_container_logs(instance, session).values()), {expected})

    def test_foreign_labels_errors_missing_and_untrusted_output_never_pass_or_leak(self):
        for mutation in (lambda name, value: value.update(directory="SYNTHETIC_PRIVATE_PATH"),
                         lambda name, value: value.update(service="foreign")):
            instance, session = self.fixture(mutation=mutation)
            self.assertEqual(set(diagnostics.inspect_container_logs(instance, session).values()), {"unknown"})
        instance, session = self.fixture(mutation=lambda name, value: value.update(role="foreign"))
        self.assertEqual(diagnostics.inspect_container_logs(instance, session)["共享 Nginx"], "unknown")
        for output in ((1, "PRIVATE_TOKEN"), (0, "PRIVATE_TOKEN"), (0, "x" * 9000), (0, "[]")):
            session = SimpleNamespace(run=Mock(return_value=output))
            values = diagnostics.inspect_container_logs(instance, session)
            self.assertEqual(set(values.values()), {"unknown"})
            self.assertNotIn("PRIVATE", "\n".join(diagnostics.log_rotation_lines(values)))
        session.run.side_effect = OSError("PRIVATE_TOKEN")
        self.assertEqual(set(diagnostics.inspect_container_logs(instance, session).values()), {"unknown"})
        self.assertNotIn("PRIVATE", "\n".join(diagnostics.log_rotation_lines({"Bot": ["PRIVATE_TOKEN"]})))

    def test_summary_uses_effective_results_and_never_turns_unknown_into_pass(self):
        report = OperationReport("clouddrive2", "CloudDrive2", "1.5.6", "1.5.6", "upgrade", "https")
        report.log_rotation = dict.fromkeys(diagnostics.LOG_CONTAINERS, "unknown")
        report.log_rotation["Bot"] = "ok"
        report.log_rotation["网关"] = "pending"
        report.completed = True
        lines = []
        report.render(lines.append)
        text = "\n".join(lines)
        self.assertIn("Bot：已生效", text)
        self.assertIn("网关：未采用", text)
        self.assertIn("共享 Nginx：未核实", text)
        self.assertIn("实际 Telegram 转存：待人工验收", text)

    def test_upgrade_collects_logging_after_entry_check_without_mutating_or_masking_failure(self):
        instance, session = self.fixture()
        plan = SimpleNamespace(instance=instance, action="upgrade")
        release = SimpleNamespace(version="1.5.6")
        logs = Mock()
        with patch.object(install.readiness, "inspect", return_value={}), \
                patch.object(install.diagnostics, "inspect_container_logs", return_value={"Bot": "pending"}) as inspect:
            with install.execution_feedback(plan, release, session, logs, mode="https") as report:
                report.checks["entry"] = "ok"
            self.assertEqual(report.log_rotation, {"Bot": "pending"})
            inspect.assert_called_once_with(plan.instance, session)
        with patch.object(install.diagnostics, "inspect_container_logs") as inspect, \
                self.assertRaisesRegex(RuntimeError, "original failure"), \
                install.execution_feedback(plan, release, session, logs, mode="https"):
            raise RuntimeError("original failure")
        inspect.assert_not_called()
