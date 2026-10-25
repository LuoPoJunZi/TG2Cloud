"""Fresh managed HTTPS must read back mounts before reporting success."""
from __future__ import annotations

import copy
import hashlib
import json
import shlex
import subprocess
import sys
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from test_uninstaller import proxy_container

from tg2cloud.deployment import uninstall
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import manager as proxy
from tg2cloud.deployment.proxy.manager import (
    PROXY_ROOT,
    DomainProxyManager,
    empty_state,
    render_compose,
)


class CertbotStartupTests(unittest.TestCase):
    def setUp(self):
        self.messages, self.commands = [], []
        session = Mock()
        session.hold_lock.return_value = nullcontext()
        self.manager = DomainProxyManager(session, PRODUCTS["clouddrive2"], {}, self.messages.append)
        self.manager._run = Mock(side_effect=self.run_command)
        self.item = proxy_container(nginx=False)
        self.expected = hashlib.sha256(render_compose().encode()).hexdigest()
        self.disk_hash = self.expected
        self.force_code, self.inspect_code = 0, 0
        self.repair_works = True
        architecture = patch("tg2cloud.deployment.architecture.check_container")
        self.architecture = architecture.start()
        self.addCleanup(architecture.stop)

    def run_command(self, command, **_kwargs):
        self.commands.append(command)
        if command.startswith("docker container inspect"):
            return self.inspect_code, json.dumps(self.item)
        if command.startswith("sha256sum "):
            return 0, self.disk_hash + "  " + PROXY_ROOT + "/docker-compose.yml\n"
        if "--force-recreate certbot" in command:
            if self.force_code == 0 and self.repair_works:
                self.item = proxy_container(nginx=False)
            return self.force_code, ""
        return 0, ""

    def missing_status(self):
        self.item["mounts"] = [m for m in self.item["mounts"] if m["Destination"] != "/status"]

    def force_calls(self):
        return [c for c in self.commands if "--force-recreate certbot" in c]

    def test_config_install_records_only_successfully_installed_compose(self):
        self.manager._upload_files = Mock(return_value="/tmp/tg2cloud-proxy-" + "a" * 32)
        with patch("tg2cloud.deployment.architecture.check_docker"), patch("tg2cloud.deployment.architecture.ensure_image"):
            self.manager._install_config(empty_state())
        self.assertEqual(self.manager._expected_compose_sha256, self.expected)
        self.assertTrue(any(c.startswith("bash -c ") for c in self.commands))

    def test_correct_fresh_mounts_succeed_without_recreation(self):
        self.assertEqual(self.manager._compose("up -d certbot")[0], 0)
        self.assertEqual(self.force_calls(), [])
        self.assertFalse(any(c.startswith("sha256sum ") for c in self.commands))

    def test_failed_config_install_clears_any_previous_recreation_authority(self):
        self.manager._expected_compose_sha256 = self.expected
        self.manager._upload_files = Mock(return_value="/tmp/tg2cloud-proxy-" + "a" * 32)
        self.manager._run = Mock(return_value=(1, "PRIVATE_FIXTURE_ERROR"))
        with (patch("tg2cloud.deployment.architecture.check_docker"),
              patch("tg2cloud.deployment.architecture.ensure_image"),
              self.assertRaisesRegex(RuntimeError, "无法安装共享代理配置")):
            self.manager._install_config(empty_state())
        self.assertIsNone(self.manager._expected_compose_sha256)

    def test_readonly_health_check_uses_same_mount_contract_and_never_changes_container(self):
        command = proxy._certbot_mount_check_command()
        parts = shlex.split(command)
        self.assertEqual(parts[-3:-1], ["python3", "-c"])
        self.assertNotIn("--force-recreate", command)
        complete = proxy_container(nginx=False)["mounts"]
        for mounts, expected in ((complete, 0), ([m for m in complete if m["Destination"] != "/status"], 1),
                                 (complete + [copy.deepcopy(complete[0])], 1),
                                 (complete + [{"Type": "bind", "Source": "/SECRET", "Destination": "/extra"}], 1)):
            result = subprocess.run([sys.executable, "-B", "-c", parts[-1]], input=json.dumps(mounts),
                                    capture_output=True, text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, expected)
            self.assertEqual(result.stdout + result.stderr, "")

    def test_https_health_requires_mount_readback_in_addition_to_running(self):
        script = shlex.split(proxy.status_command(PRODUCTS["clouddrive2"], "admin.example.test"))[2]
        self.assertIn(proxy._certbot_mount_check_command(), script)
        self.assertIn("then certbot=OK; else certbot=FAILED", script)

    def test_exact_incomplete_owned_layout_is_recreated_once_and_rechecked(self):
        self.missing_status()
        self.manager._expected_compose_sha256 = self.expected
        self.assertEqual(self.manager._compose("up -d certbot")[0], 0)
        self.assertEqual(len(self.force_calls()), 1)
        self.assertEqual(self.architecture.call_count, 2)
        uninstall.proxy_identity(uninstall.PROXY_CERTBOT_CONTAINER, self.item)
        self.assertLess(next(i for i, c in enumerate(self.commands) if c.startswith("sha256sum ")),
                        next(i for i, c in enumerate(self.commands) if "--force-recreate" in c))

    def test_unknown_or_changed_compose_cannot_authorize_recreation(self):
        for candidate, actual in ((None, self.expected), (self.expected, "0" * 64)):
            with self.subTest(candidate=candidate):
                self.missing_status()
                self.manager._expected_compose_sha256 = candidate
                self.disk_hash = actual
                with self.assertRaises((uninstall.MissingCertbotStatusMount, RuntimeError)):
                    self.manager._compose("up -d certbot")
                self.assertEqual(self.force_calls(), [])

    def test_foreign_mounts_labels_network_and_volumes_never_trigger_recreation(self):
        original = copy.deepcopy(self.item)
        for case in ("source", "extra", "owner", "network", "volume", "duplicate"):
            self.item = copy.deepcopy(original)
            self.missing_status()
            if case == "source":
                self.item["mounts"][0]["Source"] = "/private/SECRET"
            elif case == "extra":
                self.item["mounts"].append({"Type": "bind", "Source": "/private/SECRET", "Destination": "/foreign"})
            elif case == "owner":
                self.item["labels"][uninstall.MANAGED] = "false"
            elif case == "network":
                self.item["network"] = "foreign-network"
            elif case == "volume":
                self.item["mounts"][0]["Type"] = "volume"
            else:
                self.item["mounts"].append(copy.deepcopy(self.item["mounts"][0]))
            self.manager._expected_compose_sha256 = self.expected
            with self.subTest(case=case), self.assertRaises(uninstall.UninstallError) as caught:
                self.manager._compose("up -d certbot")
            self.assertEqual(self.force_calls(), [])
            self.assertNotIn("SECRET", str(caught.exception))

    def test_failed_recreation_or_failed_readback_never_reports_success(self):
        for code in (0, 9):
            self.item = proxy_container(nginx=False)
            self.missing_status()
            self.manager._expected_compose_sha256 = self.expected
            self.repair_works, self.force_code = False, code
            self.commands.clear()
            with self.subTest(code=code), self.assertRaises((uninstall.MissingCertbotStatusMount, RuntimeError)):
                self.manager._compose("up -d certbot")
            self.assertEqual(len(self.force_calls()), 1)

    def test_inspect_failure_never_recreates_or_leaks_output(self):
        for item, code in (([], 0), ({"mounts": None}, 0), ({}, 5)):
            self.item, self.inspect_code = item, code
            with self.subTest(code=code), self.assertRaises((RuntimeError, uninstall.UninstallError)):
                self.manager._compose("up -d certbot")
            self.assertEqual(self.force_calls(), [])

    def test_failed_startup_cannot_commit_fresh_https_route(self):
        self.missing_status()
        self.manager.read_state = Mock(return_value=empty_state())
        self.manager.probe = Mock()
        self.manager._validate_environment = Mock()
        self.manager._ensure_state_file = Mock()
        self.manager._activate = Mock()
        self.manager._obtain_certificate = Mock()
        self.manager._install_config = Mock()
        self.manager._commit_state = Mock()
        self.manager.status = Mock()
        with self.assertRaises(uninstall.MissingCertbotStatusMount):
            self.manager.configure("admin.example.test", "")
        self.manager._commit_state.assert_not_called()
        self.manager.status.assert_not_called()
        self.assertTrue(any("stop nginx certbot" in c for c in self.commands))
