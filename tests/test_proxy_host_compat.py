"""Stdlib-only tests also run on the minimum supported VPS Python (3.10)."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.cli import terminal
from tg2cloud.deployment import install, instances, preflight, releases
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import certificates
from tg2cloud.deployment.proxy import maintenance as backups
from tg2cloud.deployment.proxy import manager as proxy
from tg2cloud.deployment.proxy import state as proxy_state


class HostCompatibilityTests(unittest.TestCase):
    def test_stream_hash_is_bounded_and_independent_of_file_digest(self):
        content = b"synthetic fixture" * 150000
        handle = io.BytesIO(content)
        reader = Mock(wraps=handle)
        with patch.object(backups, "hashlib", SimpleNamespace(sha256=hashlib.sha256)):
            self.assertEqual(backups.stream_digest(reader), hashlib.sha256(content).hexdigest())
        self.assertGreater(reader.read.call_count, 2)
        self.assertTrue(all(call.args == (1024 * 1024,) for call in reader.read.call_args_list))
        self.assertEqual(backups.stream_digest(io.BytesIO()), hashlib.sha256(b"").hexdigest())

    def test_backup_verify_and_drill_on_minimum_host_api(self):
        with tempfile.TemporaryDirectory() as private:
            root, destination = Path(private) / "proxy", Path(private) / "backups"
            fixtures = {
                "state/domains.json": json.dumps(proxy.empty_state()),
                "docker-compose.yml": "services: {}\n",
                "nginx/nginx.conf": "events {}\n",
                "certbot/letsencrypt/archive/example.test/privkey1.pem": "synthetic-test-material",
            }
            for relative, content in fixtures.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            # Emulate the 3.10 hashlib API even when run locally on newer Python.
            with patch.object(backups, "hashlib", SimpleNamespace(sha256=hashlib.sha256)):
                original = backups.snapshot(root)
                archive = backups.create_backup(root, destination)
                self.assertEqual(backups.verify_backup(archive), original)
                self.assertEqual(backups.recovery_drill(archive, destination), len(original))
                self.assertEqual(backups.snapshot(root), original)
                with archive.open("ab") as handle:
                    handle.write(b"tampered")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    backups.verify_backup(archive)

    def test_certificate_and_renewal_dates_do_not_require_datetime_utc_alias(self):
        api = SimpleNamespace(datetime=dt.datetime, timedelta=dt.timedelta, timezone=dt.timezone)
        now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
        with patch.object(certificates, "dt", api):
            for stamp in ("2026-10-23T00:00:00Z", "notAfter=Oct 23 00:00:00 2026 GMT"):
                self.assertEqual(proxy.parse_certificate_enddate(stamp, now=now), ("2026-10-23", 14))
                self.assertEqual(proxy.parse_certificate_enddate(stamp)[0], "2026-10-23")
            markers = {"PROXY_RENEW_ATTEMPT": str(int(now.timestamp())), "PROXY_RENEW_RESULT": "OK"}
            self.assertIn("2026-10-09", proxy.renewal_summary(markers))
            self.assertFalse(proxy.renewal_warnings(markers, now))
            self.assertIsInstance(proxy.renewal_warnings(markers), tuple)

    def test_qt_worker_does_not_install_signal_handlers(self):
        failures = []

        def worker():
            try:
                with proxy.defer_interruptions():
                    pass
            except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - collect worker test failures
                failures.append(type(exc).__name__)

        with patch.object(proxy.signal, "signal", side_effect=AssertionError("worker handler")):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures)

    def test_missing_tools_report_packages_before_generic_probe_failure(self):
        session = Mock()
        session.run.return_value = (3, "TG2CLOUD_PROXY_MISSING_TOOLS=ss ip python3\n")
        for product in PRODUCTS.values():
            manager = proxy.DomainProxyManager(session, product, {}, Mock())
            with self.subTest(edition=product.key), self.assertRaisesRegex(RuntimeError, "缺少宿主依赖.*ss.*ip.*python3.*apt-get install -y iproute2 python3"):
                manager.detect("files.example.test")
            with patch.object(manager, "_upload_files") as upload, self.assertRaisesRegex(RuntimeError, "缺少宿主依赖"):
                manager._backup_helper("list")
            upload.assert_not_called()

    def test_probe_stops_before_docker_or_dns_when_tools_are_missing(self):
        bash = os.environ.get("TG115_TEST_BASH") or shutil.which("bash")
        if not bash:
            self.skipTest("Bash is not available")
        script = shlex.split(proxy.environment_probe_command(PRODUCTS["openlist"], "files.example.test"))[2]
        for missing in ("ss", "ip", "python3", "curl", "getent", "timeout", "flock"):
            # Builtin-only fixture: all other tools are reported available, but
            # no real Docker, DNS or host mutation may run after preflight fails.
            stub = f'''command() {{ [[ "$2" != {missing} ]]; }}
docker() {{ printf 'UNEXPECTED_DOCKER_CALL\\n'; }}
getent() {{ printf 'UNEXPECTED_DNS_CALL\\n'; }}
'''
            with self.subTest(tool=missing):
                result = subprocess.run([bash, "-c", stub + script], capture_output=True, text=True, timeout=15, check=False)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(result.stdout.strip(), "TG2CLOUD_PROXY_MISSING_TOOLS=" + missing)

    def test_both_installers_include_host_dependencies(self):
        root = Path(__file__).resolve().parents[1]
        for edition in PRODUCTS:
            text = (root / "packaging/hooks" / edition / "remote_install.sh").read_text(encoding="utf-8")
            packages = text.split("install -y --no-install-recommends \\\n", 1)[1].splitlines()[0].split()
            self.assertIn("iproute2", packages)
            self.assertIn("python3", packages)


class NatProxyTests(unittest.TestCase):
    # Public resolver literals are synthetic NAT fixtures; no requests are sent.
    PUBLIC = "1.1.1.1"
    DOMAIN = "files.example.test"
    ENVIRONMENT = proxy.ProxyEnvironment("OK", "OK", "FREE", "FREE", (PUBLIC,), (), ("10.0.0.80", "172.17.0.1"))

    @staticmethod
    def output(environment):
        return "\n".join("TG2CLOUD_PROXY_" + key + "=" + value for key, value in (
            ("CORE", environment.core), ("DOCKER", environment.docker),
            ("PORT_80", environment.port_80), ("PORT_443", environment.port_443),
            ("DNS_A", ",".join(environment.dns_a)), ("DNS_AAAA", ",".join(environment.dns_aaaa)),
            ("LOCAL_IPS", ",".join(environment.local_addresses)),
        ))

    def manager(self, edition="clouddrive2", *, confirmed=PUBLIC):
        session = Mock()
        session.run.return_value = (0, self.output(self.ENVIRONMENT))
        session.hold_lock.side_effect = lambda *_args, **_kwargs: nullcontext()
        prompt = Mock(return_value=confirmed)
        manager = proxy.DomainProxyManager(session, PRODUCTS[edition], {"vps_host": "127.0.0.1"}, Mock(),
                                           confirm_public_ipv4=prompt)
        return manager, prompt

    def test_private_vnic_requires_explicit_confirmation_for_each_edition(self):
        for edition in PRODUCTS:
            with self.subTest(edition=edition):
                manager, prompt = self.manager(edition)
                self.assertFalse(proxy.dns_matches_environment(manager.probe(self.DOMAIN), "127.0.0.1"))
                self.assertEqual(manager.detect(self.DOMAIN).state, "detected")
                prompt.assert_called_once()
                confirmed = manager.probe(self.DOMAIN)
                manager._validate_environment(confirmed)
                self.assertEqual(confirmed.confirmed_public_ipv4, self.PUBLIC)
                self.assertIn("人工确认", proxy.dns_diagnostic(confirmed, "127.0.0.1"))

    def test_no_prompt_or_declined_confirmation_fails_closed(self):
        manager, prompt = self.manager(confirmed="")
        self.assertEqual(manager.detect(self.DOMAIN).state, "detected_error")
        with self.assertRaisesRegex(RuntimeError, "公网 NAT"):
            manager._validate_environment(manager.probe(self.DOMAIN))
        manager.confirm_public_ipv4 = None
        self.assertEqual(manager.detect(self.DOMAIN).state, "detected_error")
        self.assertEqual(prompt.call_count, 1)

    def test_wrong_console_address_does_not_authorize_any_dns(self):
        manager, _ = self.manager(confirmed="8.8.8.8")
        with self.assertRaisesRegex(ValueError, "不一致"):
            manager.detect(self.DOMAIN)
        self.assertEqual(manager.probe(self.DOMAIN).confirmed_public_ipv4, "")

    def test_malformed_private_reserved_ipv6_or_command_input_is_rejected(self):
        for value in ("10.0.0.80", "127.0.0.1", "203.0.113.10", "224.0.0.1", "0.0.0.0", "255.255.255.255",
                      "169.254.169.254", "100.64.0.1", "::1", "2606:4700:4700::1111", "example.com",
                      "https://1.1.1.1", "1.1.1.1; id", "1.1.1.1\n", " 1.1.1.1", "01.1.1.1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                proxy_state.validate_public_ipv4(value)

    def test_wrong_aaaa_multiple_a_public_vnic_or_missing_dns_never_offers_nat(self):
        changes = ({"dns_aaaa": ("2001:db8::99",)}, {"dns_a": (self.PUBLIC, "8.8.8.8")},
                   {"local_addresses": ("8.8.8.8", "10.0.0.80")}, {"local_addresses": ()},
                   {"dns_a": ()}, {"dns_a": ("127.0.0.1",)})
        for change in changes:
            with self.subTest(change=change):
                manager, prompt = self.manager()
                environment = replace(self.ENVIRONMENT, **change)
                manager.session.run.return_value = (0, self.output(environment))
                self.assertEqual(manager.detect(self.DOMAIN).state, "detected_error")
                prompt.assert_not_called()

    def test_foreign_unknown_or_unrecognized_port_cannot_be_overridden(self):
        for port, status in (("port_80", "FOREIGN"), ("port_443", "UNKNOWN"), ("port_443", "INVALID")):
            with self.subTest(port=port, status=status):
                manager, prompt = self.manager()
                environment = replace(self.ENVIRONMENT, **{port: status})
                manager.session.run.return_value = (0, self.output(environment))
                self.assertEqual(manager.detect(self.DOMAIN).state, "detected_error")
                with self.assertRaisesRegex(RuntimeError, "端口"):
                    manager._validate_environment(manager.probe(self.DOMAIN))
                prompt.assert_not_called()

    def test_direct_address_and_real_local_ipv6_keep_existing_behavior(self):
        manager, prompt = self.manager()
        direct = replace(self.ENVIRONMENT, local_addresses=(self.PUBLIC,))
        manager.session.run.return_value = (0, self.output(direct))
        self.assertEqual(manager.detect(self.DOMAIN).state, "detected")
        prompt.assert_not_called()
        dual = replace(self.ENVIRONMENT, dns_aaaa=("2001:db8::10",),
                       local_addresses=(*self.ENVIRONMENT.local_addresses, "2001:db8::10"))
        manager.session.run.return_value = (0, self.output(dual))
        self.assertEqual(manager.detect(self.DOMAIN).state, "detected")
        prompt.assert_called_once()

    def test_confirmation_is_not_accepted_from_probe_output_or_new_manager(self):
        manager, _ = self.manager()
        manager.session.run.return_value = (0, self.output(self.ENVIRONMENT) + "\nTG2CLOUD_PROXY_CONFIRMED_PUBLIC_IPV4=" + self.PUBLIC)
        self.assertEqual(manager.probe(self.DOMAIN).confirmed_public_ipv4, "")
        manager.detect(self.DOMAIN)
        other = proxy.DomainProxyManager(manager.session, PRODUCTS["openlist"], {"vps_host": "127.0.0.1"}, Mock())
        self.assertEqual(other.probe(self.DOMAIN).confirmed_public_ipv4, "")

    def test_reprobe_invalidates_confirmation_after_dns_domain_or_vnic_change(self):
        for domain, change in ((self.DOMAIN, {"dns_a": ("8.8.8.8",)}),
                               (self.DOMAIN, {"dns_aaaa": ("2001:db8::99",)}),
                               ("other.example.test", {}),
                               (self.DOMAIN, {"local_addresses": ("10.0.0.81", "172.17.0.1")})):
            with self.subTest(domain=domain, change=change):
                manager, prompt = self.manager()
                manager.detect(self.DOMAIN)
                manager.session.run.return_value = (0, self.output(replace(self.ENVIRONMENT, **change)))
                changed = manager.probe(domain)
                self.assertEqual(changed.confirmed_public_ipv4, "")
                with self.assertRaises(RuntimeError):
                    manager._validate_environment(changed)
                self.assertEqual(prompt.call_count, 1)

    def test_new_managed_bridge_does_not_lose_same_vnic_confirmation(self):
        manager, prompt = self.manager()
        manager.detect(self.DOMAIN)
        extended = replace(self.ENVIRONMENT, local_addresses=(*self.ENVIRONMENT.local_addresses, "172.18.0.1"))
        manager.session.run.return_value = (0, self.output(extended))
        manager._validate_environment(manager.probe(self.DOMAIN))
        self.assertEqual(prompt.call_count, 1)

    def test_terminal_requires_independent_input_and_default_no_confirmation(self):
        for answer, accepted in (("", True), (self.PUBLIC, False), (self.PUBLIC, True)):
            with self.subTest(answer=answer, accepted=accepted):
                ui = Mock()
                ui.ask.return_value = answer
                ui.confirm.return_value = accepted
                result = terminal.confirm_nat_public_ipv4(ui, self.DOMAIN, self.ENVIRONMENT, Mock())
                self.assertEqual(result, self.PUBLIC if answer and accepted else "")
                self.assertNotIn("default", ui.ask.call_args.kwargs)
                if not answer:
                    ui.confirm.assert_not_called()
        ui.ask.return_value = "8.8.8.8"
        with self.assertRaisesRegex(ValueError, "不一致"):
            terminal.confirm_nat_public_ipv4(ui, self.DOMAIN, self.ENVIRONMENT, Mock())

    def test_configure_rechecks_and_never_prompts_inside_write_lock(self):
        manager, prompt = self.manager()
        manager.detect(self.DOMAIN)
        manager.read_state = Mock(return_value=proxy.empty_state())
        manager._activate = Mock()
        manager._ensure_state_file = Mock()
        manager._commit_state = Mock()
        manager._obtain_certificate = Mock()
        manager.session.run.return_value = (0, self.output(replace(self.ENVIRONMENT, dns_a=("8.8.8.8",))))
        with self.assertRaisesRegex(RuntimeError, "DNS"):
            manager.configure(self.DOMAIN, "")
        manager._ensure_state_file.assert_not_called()
        manager._activate.assert_not_called()
        manager._obtain_certificate.assert_not_called()
        manager._commit_state.assert_not_called()
        self.assertEqual(prompt.call_count, 1)

    def test_nat_confirmation_still_requires_acme_and_rolls_back_its_failure(self):
        manager, prompt = self.manager()
        manager.detect(self.DOMAIN)
        manager.read_state = Mock(return_value=proxy.empty_state())
        manager._ensure_state_file = Mock()
        manager._activate = Mock()
        manager._obtain_certificate = Mock(side_effect=RuntimeError("synthetic ACME failure"))
        manager._install_config = Mock()
        manager._compose = Mock(return_value=(0, ""))
        manager._commit_state = Mock()
        with self.assertRaisesRegex(RuntimeError, "ACME"):
            manager.configure(self.DOMAIN, "")
        manager._obtain_certificate.assert_called_once_with(self.DOMAIN, "")
        manager._install_config.assert_called_once()
        manager._compose.assert_called_once_with("stop nginx certbot", timeout=60)
        manager._commit_state.assert_not_called()
        self.assertEqual(prompt.call_count, 1)

    def test_fresh_install_plans_nat_without_installing_before_confirmation(self):
        root = Path(__file__).resolve().parents[1]
        for edition in PRODUCTS:
            with self.subTest(edition=edition):
                product = PRODUCTS[edition]
                fresh = instances.Instance(product, Path(product.install_dir), False)
                session = Mock()
                session.run.return_value = (0, self.output(self.ENVIRONMENT))
                ui = Mock()
                ui.ask.side_effect = [self.DOMAIN, "", self.PUBLIC]
                ui.confirm.return_value = True
                created = []

                def factory(*args, _created=created, **kwargs):
                    manager = proxy.DomainProxyManager(*args, **kwargs)
                    manager.prepare = Mock()
                    manager.read_state = Mock(return_value=proxy.empty_state())
                    manager.status = Mock(return_value=proxy.ProxyReport("", "not_configured", "none", ()))
                    _created.append(manager)
                    return manager

                with (patch.object(install, "DomainProxyManager", side_effect=factory),
                      patch.object(instances, "docker_inventory", return_value=set()),
                      patch.object(preflight, "choose_storage", return_value=("8", "8")),
                      patch.object(preflight, "resource_check"),
                      patch.object(terminal, "collect_config", return_value={}),
                      patch.object(install, "apply_base") as apply):
                    plan = install.make_plan(fresh, releases.Release("v" + product.app_version, "a" * 40), root, None,
                                             session, SafeLog(Mock()), ui)
                self.assertTrue(plan.configure_https)
                self.assertEqual(plan.domain, self.DOMAIN)
                self.assertEqual(created[0].probe(self.DOMAIN).confirmed_public_ipv4, self.PUBLIC)
                apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
