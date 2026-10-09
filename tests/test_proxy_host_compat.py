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
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import domain_proxy as proxy
import proxy_maintenance as backups
from deployer_products import PRODUCTS


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
        with patch.object(proxy, "dt", api):
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
            text = (root / ("payload_" + edition) / "remote_install.sh").read_text(encoding="utf-8")
            packages = text.split("install -y --no-install-recommends \\\n", 1)[1].splitlines()[0].split()
            self.assertIn("iproute2", packages)
            self.assertIn("python3", packages)


if __name__ == "__main__":
    unittest.main()
