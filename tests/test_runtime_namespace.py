"""Opt-in real Docker preflight; no VPS, Telegram or cloud-storage connection."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from deployer_products import PRODUCTS
from scripts import vps_installer as cli

ROOT = Path(__file__).resolve().parents[1]
CONTAINER_CHECK = """
import os
import pwd
import sys
from pathlib import Path
from app.main import TransferService
from app.deployment_check import code_fingerprint, main

assert os.getuid() == 10001 and os.getgid() == 10001
assert pwd.getpwuid(os.getuid()).pw_name == 'tg2cloud'
assert pwd.getpwuid(os.getuid()).pw_dir == '/nonexistent'
assert Path.cwd() == Path('/opt/tg2cloud')
assert os.environ['PYTHONPATH'] == '/opt/tg2cloud'
for path in Path('app').rglob('*'):
    assert path.stat().st_uid == 0, str(path)
    assert os.access(path, os.R_OK), str(path)
    assert not os.access(path, os.W_OK), str(path)
    if path.is_dir():
        assert os.access(path, os.X_OK), str(path)
assert not Path('config.env').exists()
assert not Path('.env').exists()
assert len(code_fingerprint()) == 64
assert TransferService is not None
sys.argv = ['deployment_check', '--validate-only']
assert main() == 0
print('TG2CLOUD_CONTAINER_RUNTIME=OK')
"""


@unittest.skipUnless(os.getenv("TG2CLOUD_TEST_DOCKER") == "1", "real Docker test requires explicit opt-in")
class RuntimeImageTests(unittest.TestCase):
    def run_docker(self, *arguments: str, timeout: int = 180) -> str:
        result = subprocess.run(
            ["docker", *arguments], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_both_editions_private_source_non_root_preflight(self) -> None:
        self.assertEqual(os.name, "posix", "This opt-in job must use a Linux Docker runner")
        self.assertIsNotNone(shutil.which("docker"), "Enabled Docker checks cannot silently skip a missing Docker daemon")
        self.run_docker("info", timeout=30)
        values = {
            "api_id": "123456", "user_id": "123456789", "api_hash": "a" * 32,
            "bot_token": "123456789:FAKE_DOCKER_TEST_NOT_A_REAL_TOKEN",
            "webdav_user": "tg2cloud", "webdav_password": "FAKE_DOCKER_TEST_PASSWORD",
            "target": "", "budget": "20", "reserve": "8", "timezone": "Asia/Shanghai",
            "admin_password": "FAKE_DOCKER_TEST_ADMIN_PASSWORD",
        }
        for product in PRODUCTS.values():
            for private_app in (False, True):
                with self.subTest(edition=product.key, private_app=private_app), tempfile.TemporaryDirectory() as private:
                    context = Path(private) / "payload"
                    cli.build_payload(ROOT, product, context)
                    if private_app:
                        # Also exercise Dockerfile hardening for callers that
                        # supply restrictive source modes, independent of CLI.
                        for path in (context / "app").rglob("*"):
                            path.chmod(0o700 if path.is_dir() else 0o600)
                        (context / "app").chmod(0o700)
                    candidate = Path(private) / "config.env"
                    config = cli.new_config(product, values)
                    candidate.write_text("".join(f"{key}={value}\n" for key, value in config.items()), encoding="utf-8")
                    candidate.chmod(0o600)
                    identifier = uuid.uuid4().hex
                    image = "tg2cloud-runtime-check:" + identifier
                    container = "tg2cloud-runtime-check-" + identifier
                    try:
                        self.run_docker("build", "--quiet", "--tag", image, str(context), timeout=900)
                        # This is the candidate's restricted validation boundary,
                        # not a running Bot. Do not mount production data.
                        output = self.run_docker(
                            "run", "--rm", "--name", container, "--read-only", "--tmpfs", "/tmp",
                            "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                            "--env-file", str(candidate), image, "python", "-c", CONTAINER_CHECK,
                        )
                        self.assertIn("TG2CLOUD_CONFIG=OK", output)
                        self.assertIn("TG2CLOUD_VERSION=" + product.app_version, output)
                        self.assertIn("TG2CLOUD_CONTAINER_RUNTIME=OK", output)
                        self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
                        self.assertEqual(context.stat().st_mode & 0o777, 0o700)
                    finally:
                        # Only remove this test's randomly named resources;
                        # never prune Docker or touch an Edition container.
                        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30, check=False)
                        subprocess.run(["docker", "image", "rm", image], capture_output=True, timeout=30, check=False)


if __name__ == "__main__":
    unittest.main()
