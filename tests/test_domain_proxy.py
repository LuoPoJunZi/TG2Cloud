from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from deployer_products import CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT
from domain_proxy import (
    _CERTIFICATE_CHECK_SCRIPT,
    CERTBOT_IMAGE,
    NGINX_IMAGE,
    DomainProxyManager,
    DomainRoute,
    ProxyEnvironment,
    ProxyReport,
    command_failure_summary,
    dns_diagnostic,
    dns_matches_environment,
    empty_state,
    environment_probe_command,
    install_config_command,
    normalize_state,
    parse_certificate_enddate,
    parse_environment,
    parse_markers,
    render_bootstrap_conf,
    render_certbot_loop,
    render_compose,
    render_config_set,
    render_default_conf,
    render_route_conf,
    state_with_route,
    state_without_route,
    status_command,
    validate_domain,
    validate_email,
    verification_statuses,
)


class DomainValidationTests(unittest.TestCase):
    def test_valid_ascii_fqdn_is_normalized(self) -> None:
        self.assertEqual(validate_domain("Cloud.Example.COM."), "cloud.example.com")

    def test_single_label_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "完整"):
            validate_domain("localhost")

    def test_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "只填写域名"):
            validate_domain("https://cloud.example.com/path")

    def test_ipv4_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能填写"):
            validate_domain("203.0.113.10")

    def test_ipv6_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_domain("2001:db8::1")

    def test_shell_metacharacters_are_rejected(self) -> None:
        for value in ("a.example.com;id", "a.example.com$(id)", "*.example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_domain(value)

    def test_unicode_requires_punycode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Punycode"):
            validate_domain("云.example.com")

    def test_optional_email(self) -> None:
        self.assertEqual(validate_email(""), "")
        self.assertEqual(validate_email("ops@example.com"), "ops@example.com")
        with self.assertRaises(ValueError):
            validate_email("not an email")

    def test_command_failure_summary_is_bounded_and_redacts_secrets(self) -> None:
        secret = "ops@example.com"
        output = "\x1b[31merror\x1b[0m\n" + secret + "\n" + ("x" * 2000)
        summary = command_failure_summary(output, secrets=(secret,), max_chars=120)
        self.assertNotIn(secret, summary)
        self.assertNotIn("\x1b", summary)
        self.assertLessEqual(len(summary), 121)


class RenderTests(unittest.TestCase):
    def test_openlist_route_targets_loopback(self) -> None:
        rendered = render_route_conf(DomainRoute("openlist", "ol.example.com", 5244))
        self.assertIn("proxy_pass http://127.0.0.1:5244", rendered)

    def test_clouddrive_route_targets_loopback(self) -> None:
        rendered = render_route_conf(
            DomainRoute("clouddrive2", "cd.example.com", 19798)
        )
        self.assertIn("proxy_pass http://127.0.0.1:19798", rendered)

    def test_public_dav_is_blocked(self) -> None:
        rendered = render_route_conf(DomainRoute("openlist", "ol.example.com", 5244))
        self.assertIn("location = /dav { return 403; }", rendered)
        self.assertIn("location ^~ /dav/ { return 403; }", rendered)

    def test_http_redirect_is_permanent(self) -> None:
        rendered = render_route_conf(DomainRoute("openlist", "ol.example.com", 5244))
        self.assertIn("return 308 https://$host$request_uri", rendered)

    def test_route_rejects_mismatched_host_header(self) -> None:
        rendered = render_route_conf(DomainRoute("openlist", "ol.example.com", 5244))
        self.assertEqual(rendered.count("if ($host != ol.example.com) { return 444; }"), 2)

    def test_default_http_host_is_dropped(self) -> None:
        self.assertIn("return 444", render_default_conf(tls_enabled=False))

    def test_unknown_tls_sni_is_rejected(self) -> None:
        rendered = render_default_conf(tls_enabled=True)
        self.assertIn("listen 443 ssl default_server", rendered)
        self.assertIn("ssl_reject_handshake on", rendered)

    def test_bootstrap_only_serves_acme(self) -> None:
        rendered = render_bootstrap_conf("new.example.com")
        self.assertIn("/.well-known/acme-challenge/", rendered)
        self.assertIn("location / { return 404; }", rendered)
        self.assertNotIn("proxy_pass", rendered)

    def test_compose_has_one_shared_proxy_pair(self) -> None:
        rendered = render_compose()
        self.assertEqual(rendered.count("container_name: tg2cloud-proxy-nginx"), 1)
        self.assertEqual(rendered.count("container_name: tg2cloud-proxy-certbot"), 1)
        self.assertIn("network_mode: host", rendered)

    def test_images_are_version_pinned(self) -> None:
        self.assertNotIn(":latest", render_compose())
        self.assertEqual(NGINX_IMAGE, "nginx:1.30.5-alpine")
        self.assertEqual(CERTBOT_IMAGE, "certbot/certbot:v5.8.0")
        self.assertIn(f"image: {NGINX_IMAGE}", render_compose())
        self.assertIn(f"image: {CERTBOT_IMAGE}", render_compose())

    def test_compose_is_read_only_without_docker_socket(self) -> None:
        rendered = render_compose()
        self.assertGreaterEqual(rendered.count("read_only: true"), 2)
        self.assertNotIn("docker.sock", rendered)
        self.assertNotIn("privileged:", rendered)

    def test_compose_has_renewal_and_reload_loops(self) -> None:
        rendered = render_compose(("ol.example.com",))
        self.assertIn("certbot renew", rendered)
        self.assertIn('--cert-name "$$cert"', rendered)
        self.assertIn('TG2CLOUD_CERT_NAMES: "ol.example.com"', rendered)
        self.assertIn("sleep 43200", rendered)
        self.assertIn("sleep 21600", rendered)

    def test_compose_renews_only_active_domains(self) -> None:
        rendered = render_compose(("active.example.com",))
        self.assertIn("active.example.com", rendered)
        self.assertNotIn("retired.example.com", rendered)

    def test_config_set_renders_two_routes_and_no_second_nginx(self) -> None:
        state = state_with_route(empty_state(), CLOUDDRIVE2_PRODUCT, "cd.example.com")
        state = state_with_route(state, OPENLIST_PRODUCT, "ol.example.com")
        files = render_config_set(state)
        self.assertIn("conf.d/20-clouddrive2.conf", files)
        self.assertIn("conf.d/20-openlist.conf", files)
        self.assertNotIn("docker-compose.yml", files)


class StateTests(unittest.TestCase):
    def test_dual_edition_state(self) -> None:
        state = state_with_route(empty_state(), CLOUDDRIVE2_PRODUCT, "cd.example.com")
        state = state_with_route(state, OPENLIST_PRODUCT, "ol.example.com")
        self.assertEqual(set(state["domains"]), {"clouddrive2", "openlist"})

    def test_duplicate_domain_is_rejected(self) -> None:
        state = state_with_route(empty_state(), CLOUDDRIVE2_PRODUCT, "same.example.com")
        with self.assertRaisesRegex(ValueError, "另一个"):
            state_with_route(state, OPENLIST_PRODUCT, "same.example.com")

    def test_remove_one_preserves_the_other(self) -> None:
        state = state_with_route(empty_state(), CLOUDDRIVE2_PRODUCT, "cd.example.com")
        state = state_with_route(state, OPENLIST_PRODUCT, "ol.example.com")
        state = state_without_route(state, "openlist")
        self.assertEqual(list(state["domains"]), ["clouddrive2"])

    def test_remove_last_route_leaves_empty_state(self) -> None:
        state = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        self.assertEqual(state_without_route(state, "openlist"), empty_state())

    def test_existing_state_is_normalized(self) -> None:
        raw = json.dumps(
            {
                "version": 1,
                "domains": {
                    "openlist": {"domain": "OL.Example.COM", "backend_port": 5244}
                },
            }
        )
        self.assertEqual(
            normalize_state(raw)["domains"]["openlist"]["domain"],
            "ol.example.com",
        )

    def test_state_rejects_an_edition_port_mismatch(self) -> None:
        raw = json.dumps(
            {
                "version": 1,
                "domains": {
                    "openlist": {"domain": "ol.example.com", "backend_port": 19798}
                },
            }
        )
        with self.assertRaisesRegex(ValueError, "应为 5244"):
            normalize_state(raw)

    def test_utf8_bytes_state_is_supported(self) -> None:
        self.assertEqual(normalize_state(b'{"version": 1, "domains": {}}'), empty_state())

    def test_unknown_state_is_not_overwritten(self) -> None:
        with self.assertRaisesRegex(ValueError, "无法识别"):
            normalize_state('{"version": 99, "domains": {}}')


class ProbeAndStatusTests(unittest.TestCase):
    SAMPLE = """TG2CLOUD_PROXY_CORE=OK
TG2CLOUD_PROXY_DOCKER=OK
TG2CLOUD_PROXY_PORT_80=OWN
TG2CLOUD_PROXY_PORT_443=FREE
TG2CLOUD_PROXY_DNS_A=203.0.113.10
TG2CLOUD_PROXY_DNS_AAAA=2001:db8::10
TG2CLOUD_PROXY_LOCAL_IPS=203.0.113.10,2001:db8::10
"""

    def test_port_80_owner_is_parsed(self) -> None:
        self.assertEqual(parse_environment(self.SAMPLE).port_80, "OWN")

    def test_port_443_owner_is_parsed(self) -> None:
        self.assertEqual(parse_environment(self.SAMPLE).port_443, "FREE")

    def test_foreign_port_is_unsafe(self) -> None:
        value = self.SAMPLE.replace("PORT_443=FREE", "PORT_443=FOREIGN")
        self.assertFalse(parse_environment(value).ports_safe)

    def test_correct_a_and_aaaa_match(self) -> None:
        environment = parse_environment(self.SAMPLE)
        self.assertTrue(dns_matches_environment(environment, "203.0.113.10"))

    def test_wrong_aaaa_blocks_configuration(self) -> None:
        value = self.SAMPLE.replace("2001:db8::10", "2001:db8::99", 1)
        environment = parse_environment(value)
        self.assertFalse(dns_matches_environment(environment, "203.0.113.10"))

    def test_ipv4_mapped_aaaa_is_not_treated_as_a_real_aaaa_record(self) -> None:
        value = self.SAMPLE.replace(
            "PROXY_DNS_AAAA=2001:db8::10", "PROXY_DNS_AAAA=::ffff:203.0.113.10"
        )
        environment = parse_environment(value)
        self.assertEqual(environment.dns_aaaa, ())
        self.assertTrue(dns_matches_environment(environment, "203.0.113.10"))

    def test_dns_diagnostic_shows_resolved_and_expected_addresses(self) -> None:
        detail = dns_diagnostic(parse_environment(self.SAMPLE), "203.0.113.10")
        self.assertIn("DNS A：203.0.113.10", detail)
        self.assertIn("AAAA：2001:db8::10", detail)
        self.assertIn("当前 VPS：", detail)
        self.assertIn("203.0.113.10", detail)

    def test_environment_command_uses_edition_backend(self) -> None:
        self.assertIn("127.0.0.1:5244", environment_probe_command(OPENLIST_PRODUCT, "ol.example.com"))
        self.assertIn("127.0.0.1:19798", environment_probe_command(CLOUDDRIVE2_PRODUCT, "cd.example.com"))

    def test_port_owner_requires_managed_container_pid_match(self) -> None:
        command = environment_probe_command(OPENLIST_PRODUCT, "ol.example.com")
        self.assertIn("docker top tg2cloud-proxy-nginx -eo pid", command)
        self.assertIn("ss -H -ltnp", command)

    def test_unknown_port_owner_hard_stops(self) -> None:
        manager = DomainProxyManager(
            object(), OPENLIST_PRODUCT, {"vps_host": "203.0.113.10"}, lambda _line: None
        )
        environment = ProxyEnvironment(
            "OK", "OK", "UNKNOWN", "FREE", ("203.0.113.10",), (), ("203.0.113.10",)
        )
        with self.assertRaisesRegex(RuntimeError, "无法确认端口 80"):
            manager._validate_environment(environment)

    def test_status_command_checks_https_dav_and_local_binding(self) -> None:
        command = status_command(OPENLIST_PRODUCT, "ol.example.com")
        self.assertIn("https://ol.example.com/dav/", command)
        self.assertIn("sport = :5244", command)
        self.assertIn("PROXY_PORTS", command)
        self.assertIn("docker top tg2cloud-proxy-nginx -eo pid", command)
        self.assertIn("docker exec tg2cloud-proxy-certbot python -c", command)
        self.assertNotIn("nginx openssl", command)

    def test_status_uses_loopback_with_real_host_and_tls_name(self) -> None:
        command = status_command(OPENLIST_PRODUCT, "ol.example.com")
        self.assertIn("--resolve ol.example.com:80:127.0.0.1", command)
        self.assertEqual(command.count("--resolve ol.example.com:443:127.0.0.1"), 2)
        self.assertEqual(command.count("--noproxy"), 3)
        self.assertIn("set +u", command)
        self.assertIn("TG2CLOUD_PROXY_STATUS=OK", command)

    def test_status_calls_port_helpers_outside_double_bracket_expression(self) -> None:
        command = status_command(OPENLIST_PRODUCT, "ol.example.com")
        self.assertRegex(command, r"== host \]\]\s+&& owns_port 80 && owns_port 443; then")
        self.assertNotIn("owns_port 80 && owns_port 443 ]]", command)

    def test_incomplete_status_script_is_not_reported_as_all_checks_failed(self) -> None:
        class BrokenStatusSession:
            def run(self, _command, **_kwargs):
                return 2, "bash: simulated syntax error"

        logs: list[str] = []
        manager = DomainProxyManager(
            BrokenStatusSession(), OPENLIST_PRODUCT, {}, logs.append
        )
        state = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        report = manager.status(state)
        self.assertEqual(report.statuses, (("状态检查脚本", "失败"),))
        self.assertIn("未完整执行", report.message)
        self.assertTrue(any("exit=2" in line for line in logs))

    def test_certificate_expiry_parser(self) -> None:
        expires, days = parse_certificate_enddate(
            "notAfter=Oct 23 00:00:00 2026 GMT",
            now=dt.datetime(2026, 9, 23, tzinfo=dt.UTC),
        )
        self.assertEqual(expires, "2026-10-23")
        self.assertEqual(days, 30)

    def test_iso_certificate_expiry_parser(self) -> None:
        expires, days = parse_certificate_enddate(
            "2026-10-23T00:00:00Z",
            now=dt.datetime(2026, 9, 23, tzinfo=dt.UTC),
        )
        self.assertEqual(expires, "2026-10-23")
        self.assertEqual(days, 30)

    def test_only_tg2cloud_markers_are_parsed(self) -> None:
        markers = parse_markers("TOKEN=secret\nTG2CLOUD_PROXY_HTTPS=OK\nnoise")
        self.assertEqual(markers, {"PROXY_HTTPS": "OK"})

    def test_structured_statuses(self) -> None:
        keys = (
            "PROXY_CORE", "PROXY_PORTS", "PROXY_NGINX", "PROXY_CERTBOT",
            "PROXY_RENEWAL", "PROXY_NGINX_TEST", "PROXY_HTTPS", "PROXY_REDIRECT",
            "PROXY_DAV_BLOCK", "PROXY_BACKEND_LOCAL", "PROXY_CERT",
        )
        statuses = verification_statuses({key: "OK" for key in keys})
        self.assertTrue(all(value == "通过" for _, value in statuses))


class TransactionManager(DomainProxyManager):
    def __init__(self, product=OPENLIST_PRODUCT) -> None:
        super().__init__(object(), product, {"vps_host": "203.0.113.10"}, lambda _line: None)
        self.current = empty_state()
        self.activations: list[tuple[dict, str]] = []
        self.commits: list[dict] = []
        self.ensured_states: list[dict] = []
        self.compose_calls: list[str] = []
        self.stop_called = False
        self.fail_certificate = False
        self.fail_final_activation = False
        self.fail_commit = False
        self.valid_certificate = True

    def read_state(self):
        return json.loads(json.dumps(self.current))

    def probe(self, domain: str) -> ProxyEnvironment:
        return ProxyEnvironment(
            "OK", "OK", "FREE", "FREE", ("203.0.113.10",), (), ("203.0.113.10",)
        )

    def _activate(self, state, *, candidate="") -> None:
        self.activations.append((json.loads(json.dumps(state)), candidate))
        if self.fail_final_activation and not candidate and state != self.current:
            raise RuntimeError("nginx -t failed")

    def _obtain_certificate(self, domain: str, email: str) -> None:
        if self.fail_certificate:
            raise RuntimeError("certbot failed")

    def _certificate_valid(self, domain: str) -> bool:
        return self.valid_certificate

    def _ensure_state_file(self, state) -> None:
        self.ensured_states.append(json.loads(json.dumps(state)))

    def _compose(self, arguments: str, *, timeout: float = 180):
        self.compose_calls.append(arguments)
        if arguments.startswith("stop"):
            self.stop_called = True
        return 0, ""

    def _commit_state(self, state) -> None:
        if self.fail_commit:
            raise RuntimeError("state commit failed")
        self.commits.append(json.loads(json.dumps(state)))
        self.current = json.loads(json.dumps(state))

    def _install_config(self, state, *, candidate="") -> None:
        self.activations.append((json.loads(json.dumps(state)), candidate))

    def status(self, state=None) -> ProxyReport:
        current = state or self.current
        item = current["domains"].get(self.product.key)
        if not item:
            return ProxyReport("", "not_configured", "none", ())
        return ProxyReport(item["domain"], "healthy", "ok", (("HTTPS", "通过"),))


class CertificateManager(DomainProxyManager):
    def __init__(self, *, exists: bool, valid: bool) -> None:
        self.logs: list[str] = []
        super().__init__(object(), OPENLIST_PRODUCT, {}, self.logs.append)
        self.exists = exists
        self.valid = valid
        self.compose_calls: list[str] = []
        self.compose_result = (0, "")

    def _certificate_exists(self, domain: str) -> bool:
        return self.exists

    def _certificate_valid(self, domain: str) -> bool:
        return self.valid

    def _compose(self, arguments: str, *, timeout: float = 180):
        self.compose_calls.append(arguments)
        return self.compose_result


class CertificateTests(unittest.TestCase):
    def test_certificate_probe_validates_san_and_remaining_lifetime(self) -> None:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        now = dt.datetime.now(dt.UTC)
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ol.example.com")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=1))
            .not_valid_after(now + dt.timedelta(days=30))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("ol.example.com")]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fullchain.pem"
            path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
            valid = subprocess.run(
                [sys.executable, "-c", _CERTIFICATE_CHECK_SCRIPT, str(path), "ol.example.com"],
                check=False,
                capture_output=True,
                text=True,
            )
            wrong_domain = subprocess.run(
                [sys.executable, "-c", _CERTIFICATE_CHECK_SCRIPT, str(path), "cd.example.com"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(valid.returncode, 0)
        self.assertRegex(valid.stdout.strip(), r"^\d{4}-\d{2}-\d{2}T")
        self.assertNotEqual(wrong_domain.returncode, 0)

    def test_certificate_probe_uses_pinned_certbot_python(self) -> None:
        class RecordingSession:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def run(self, command: str, **_kwargs):
                self.commands.append(command)
                return 0, ""

        session = RecordingSession()
        manager = DomainProxyManager(session, OPENLIST_PRODUCT, {}, lambda _line: None)
        self.assertTrue(manager._certificate_valid("ol.example.com"))
        probe = session.commands[-1]
        self.assertIn(f"--entrypoint python {CERTBOT_IMAGE}", probe)
        self.assertIn("--cap-drop ALL", probe)
        self.assertNotIn(NGINX_IMAGE, probe)

    def test_valid_existing_certificate_is_reused(self) -> None:
        manager = CertificateManager(exists=True, valid=True)
        manager._obtain_certificate("ol.example.com", "ops@example.com")
        self.assertEqual(manager.compose_calls, [])

    def test_invalid_existing_certificate_uses_forced_renewal(self) -> None:
        manager = CertificateManager(exists=True, valid=False)
        manager._obtain_certificate("ol.example.com", "ops@example.com")
        self.assertIn("--force-renewal", manager.compose_calls[0])
        self.assertIn("--cert-name ol.example.com", manager.compose_calls[0])
        self.assertIn("--no-eff-email", manager.compose_calls[0])

    def test_certificate_failure_logs_redacted_certbot_detail(self) -> None:
        manager = CertificateManager(exists=False, valid=False)
        email = "ops@example.com"
        manager.compose_result = (
            1,
            f"Certbot failed for {email}\nDetail: Invalid response from http://ol.example.com",
        )
        with self.assertRaisesRegex(RuntimeError, "Certbot 具体原因"):
            manager._obtain_certificate("ol.example.com", email)
        rendered = "\n".join(manager.logs)
        self.assertIn("Invalid response", rendered)
        self.assertNotIn(email, rendered)


class TransactionTests(unittest.TestCase):
    def test_existing_runtime_without_state_is_not_overwritten(self) -> None:
        class MissingStateSession:
            def run(self, command, **_kwargs):
                self.command = command
                return 3, "TG2CLOUD_PROXY_STATE_MISSING_WITH_RUNTIME=1\n"

        session = MissingStateSession()
        manager = DomainProxyManager(
            session, OPENLIST_PRODUCT, {"vps_host": "203.0.113.10"}, lambda _line: None
        )
        with self.assertRaisesRegex(RuntimeError, "缺少 domains.json"):
            manager.read_state()
        self.assertIn("docker container inspect", session.command)

    def test_certificate_failure_rolls_back_without_commit(self) -> None:
        manager = TransactionManager()
        manager.fail_certificate = True
        with self.assertRaisesRegex(RuntimeError, "certbot"):
            manager.configure("ol.example.com", "")
        self.assertFalse(manager.commits)
        self.assertEqual(manager.ensured_states, [empty_state()])
        self.assertEqual(manager.activations[-1][0], empty_state())
        self.assertTrue(manager.stop_called)

    def test_nginx_validation_failure_rolls_back(self) -> None:
        manager = TransactionManager()
        manager.fail_final_activation = True
        with self.assertRaisesRegex(RuntimeError, "nginx"):
            manager.configure("ol.example.com", "ops@example.com")
        self.assertFalse(manager.commits)
        self.assertEqual(manager.activations[-1][0], empty_state())

    def test_domain_update_failure_preserves_old_route(self) -> None:
        manager = TransactionManager()
        manager.current = state_with_route(
            empty_state(), OPENLIST_PRODUCT, "old.example.com"
        )
        manager.fail_certificate = True
        with self.assertRaises(RuntimeError):
            manager.configure("new.example.com", "")
        self.assertEqual(
            manager.activations[-1][0]["domains"]["openlist"]["domain"],
            "old.example.com",
        )

    def test_broken_existing_certificate_uses_bootstrap_before_retry(self) -> None:
        manager = TransactionManager()
        manager.current = state_with_route(
            empty_state(), OPENLIST_PRODUCT, "ol.example.com"
        )
        manager.valid_certificate = False
        manager.fail_certificate = True
        with self.assertRaisesRegex(RuntimeError, "certbot"):
            manager.configure("ol.example.com", "")
        first_state, candidate = manager.activations[0]
        self.assertEqual(first_state, empty_state())
        self.assertEqual(candidate, "ol.example.com")

    def test_success_commits_only_after_healthy_status(self) -> None:
        manager = TransactionManager()
        report = manager.configure("ol.example.com", "")
        self.assertEqual(report.state, "healthy")
        self.assertEqual(manager.commits[-1]["domains"]["openlist"]["domain"], "ol.example.com")

    def test_failed_final_status_reports_exact_checks_before_rollback(self) -> None:
        class UnhealthyManager(TransactionManager):
            def __init__(self) -> None:
                self.logs: list[str] = []
                super().__init__()
                self.log = self.logs.append

            def status(self, state=None) -> ProxyReport:
                return ProxyReport(
                    "ol.example.com",
                    "running_error",
                    "failed",
                    (("HTTPS 管理页", "失败"), ("证书域名与有效期", "通过")),
                )

        manager = UnhealthyManager()
        with self.assertRaisesRegex(RuntimeError, "HTTPS 管理页"):
            manager.configure("ol.example.com", "")
        self.assertIn("TG2CLOUD_PROXY_CHECK=HTTPS 管理页:失败", manager.logs)
        self.assertFalse(manager.commits)

    def test_remove_one_edition_does_not_stop_shared_proxy(self) -> None:
        manager = TransactionManager()
        state = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        state = state_with_route(state, CLOUDDRIVE2_PRODUCT, "cd.example.com")
        manager.current = state
        manager.remove()
        self.assertFalse(manager.stop_called)
        self.assertIn("clouddrive2", manager.commits[-1]["domains"])

    def test_remove_last_edition_stops_shared_proxy(self) -> None:
        manager = TransactionManager()
        manager.current = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        manager.remove()
        self.assertTrue(manager.stop_called)
        self.assertEqual(manager.commits[-1], empty_state())

    def test_remove_last_commit_failure_restarts_certbot_during_rollback(self) -> None:
        manager = TransactionManager()
        manager.current = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        manager.fail_commit = True
        with self.assertRaisesRegex(RuntimeError, "state commit"):
            manager.remove()
        self.assertIn("up -d certbot", manager.compose_calls)
        self.assertEqual(
            manager.activations[-1][0]["domains"]["openlist"]["domain"],
            "ol.example.com",
        )


class GeneratedArtifactTests(unittest.TestCase):
    @staticmethod
    def _bash_scripts() -> tuple[str, ...]:
        commands = (
            environment_probe_command(OPENLIST_PRODUCT, "ol.example.com"),
            status_command(OPENLIST_PRODUCT, "ol.example.com"),
            install_config_command("/tmp/tg2cloud-proxy-" + "a" * 32),
        )
        return tuple(shlex.split(command)[2] for command in commands) + (
            render_certbot_loop(),
        )

    def test_acme_webroot_is_traversable_but_certbot_state_stays_private(self) -> None:
        script = shlex.split(
            install_config_command("/tmp/tg2cloud-proxy-" + "a" * 32)
        )[2]
        self.assertIn('install -d -m 755 "$root/certbot/www"', script)
        self.assertIn('install -d -m 700 "$root"', script)
        self.assertNotIn('install -d -m 700 "$root/certbot/www"', script)

    @unittest.skipUnless(shutil.which("bash"), "bash is not installed")
    def test_generated_remote_commands_pass_bash_syntax(self) -> None:
        for script in self._bash_scripts():
            with self.subTest(script=script[:40]):
                result = subprocess.run(
                    ["bash", "-n"],
                    input=script,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("shellcheck"), "ShellCheck is not installed")
    def test_generated_remote_commands_pass_shellcheck(self) -> None:
        for script in self._bash_scripts():
            with self.subTest(script=script[:40]):
                result = subprocess.run(
                    ["shellcheck", "-s", "bash", "-"],
                    input=script,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("docker"), "Docker CLI is not installed")
    def test_generated_proxy_compose_passes_docker_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "docker-compose.yml"
            path.write_text(
                render_compose(("ol.example.com", "cd.example.com")),
                encoding="utf-8",
            )
            result = subprocess.run(
                ["docker", "compose", "-f", str(path), "config", "--quiet"],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("docker"), "Docker CLI is not installed")
    def test_generated_nginx_config_passes_pinned_image_test(self) -> None:
        docker_info = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, check=False
        )
        if docker_info.returncode != 0:
            self.skipTest("Docker daemon is not available")

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        state = state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com")
        state = state_with_route(state, CLOUDDRIVE2_PRODUCT, "cd.example.com")
        files = render_config_set(state)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ol.example.com")])
        now = dt.datetime.now(dt.UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=1))
            .not_valid_after(now + dt.timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("ol.example.com"), x509.DNSName("cd.example.com")]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conf_dir = root / "conf.d"
            cert_root = root / "letsencrypt"
            webroot = root / "www"
            conf_dir.mkdir()
            webroot.mkdir()
            (root / "nginx.conf").write_text(files.pop("nginx.conf"), encoding="utf-8")
            for relative, content in files.items():
                (root / relative).write_text(content, encoding="utf-8")
            for domain in ("ol.example.com", "cd.example.com"):
                live = cert_root / "live" / domain
                live.mkdir(parents=True)
                (live / "fullchain.pem").write_bytes(
                    certificate.public_bytes(serialization.Encoding.PEM)
                )
                (live / "privkey.pem").write_bytes(
                    key.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.TraditionalOpenSSL,
                        serialization.NoEncryption(),
                    )
                )
            result = subprocess.run(
                [
                    "docker", "run", "--rm", "--network", "none", "--read-only",
                    "--tmpfs", "/var/cache/nginx", "--tmpfs", "/var/run", "--tmpfs", "/tmp",
                    "-v", f"{root / 'nginx.conf'}:/etc/nginx/nginx.conf:ro",
                    "-v", f"{conf_dir}:/etc/nginx/conf.d:ro",
                    "-v", f"{webroot}:/var/www/certbot:ro",
                    "-v", f"{cert_root}:/etc/letsencrypt:ro",
                    NGINX_IMAGE, "nginx", "-t",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RegressionBoundaryTests(unittest.TestCase):
    def test_ssh_tunnel_implementation_remains_present(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "installer.py").read_text(encoding="utf-8")
        self.assertIn("def open_clouddrive(self, values:", source)
        self.assertIn("self._tunnel_factory(", source)

    def test_internal_webdav_bindings_remain_loopback_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertIn(
            '"127.0.0.1:19798:19798"',
            (root / "payload_clouddrive2/docker-compose.yml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            '"127.0.0.1:5244:5244"',
            (root / "payload_openlist/docker-compose.yml").read_text(encoding="utf-8"),
        )

    def test_templates_do_not_contain_credentials_or_private_keys(self) -> None:
        rendered = render_compose() + render_route_conf(
            DomainRoute("openlist", "ol.example.com", 5244)
        )
        self.assertNotIn("PRIVATE KEY", rendered)
        self.assertNotIn("password", rendered.lower())
        self.assertNotIn("ops@example.com", rendered)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 is not installed")
class QtLayoutTests(unittest.TestCase):
    def test_both_domain_dialogs_fit_at_supported_scale_factors(self) -> None:
        root = Path(__file__).resolve().parents[1]
        program = r"""
import sys
from deployer_products import CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT
from installer import DomainAccessDialog, InstallerWindow, make_app

app = make_app()
product = OPENLIST_PRODUCT if sys.argv[1] == "openlist" else CLOUDDRIVE2_PRODUCT
window = InstallerWindow(preview=True, product=product)
window.backend = object()
dialog = DomainAccessDialog(window)
dialog.show()
app.processEvents()
hint = dialog.layout().minimumSize()
assert hint.width() <= dialog.width(), (hint.width(), dialog.width())
assert hint.height() <= dialog.height(), (hint.height(), dialog.height())
assert not dialog.buttons["proxy_configure"].text().endswith("…")
assert dialog.domain_edit.isVisible()
assert dialog.email_edit.isVisible()
assert dialog.status_text.objectName() == "DomainStatus"
assert dialog.status_text.isReadOnly()
assert dialog.status_text.height() == 112
dialog.close()
window.close()
"""
        for scale in ("1", "1.25", "1.5"):
            for edition in ("clouddrive2", "openlist"):
                with self.subTest(scale=scale, edition=edition):
                    environment = dict(os.environ)
                    environment["QT_QPA_PLATFORM"] = "offscreen"
                    environment["QT_SCALE_FACTOR"] = scale
                    result = subprocess.run(
                        [sys.executable, "-c", program, edition],
                        cwd=root,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
