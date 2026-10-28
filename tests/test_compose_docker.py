"""Opt-in direct Compose tests on disposable native Linux runners only."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from tg2cloud.compose.packaging import bundle_files
from tg2cloud.deployment.profiles import PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "tg2cloud-bot:test"
SETUP = r"""
from pathlib import Path
from tg2cloud.compose.runtime import setup
class UI:
    def ask(self, prompt, default='', secret=False, validate=lambda v:v):
        values={'Telegram API ID':'123456', 'Telegram API Hash（隐藏输入）':'a'*32,
                'Bot Token（隐藏输入）':'123456789:FAKE_COMPOSE_CI_TOKEN_NOT_REAL',
                '管理员 Telegram 用户 ID（仅一个）':'123456789','任务暂存预算 GB':'1'}
        return validate(values.get(prompt,default))
    def confirm(self, _): return True
    def private(self, *_): pass
assert setup(Path('/workspace'),UI()) is True
assert setup(Path('/workspace'),UI()) is False
"""
CHECK = """import os;from pathlib import Path;from tg2cloud.config import Settings
assert os.geteuid()==10001
s=Settings.from_env()
p=s.data_dir/'synthetic-write-test';p.write_text('test');p.unlink()
assert s.rclone_config_path.parent.is_dir()
print('COMPOSE_NONROOT=OK')
"""


@unittest.skipUnless(os.getenv("TG2CLOUD_TEST_COMPOSE_DOCKER") == "1", "direct Compose native Docker test requires explicit opt-in")
class ComposeDockerTests(unittest.TestCase):
    def run_command(self, args, **kwargs):
        # Setup deliberately creates a root-owned 0600 .env. Compose must read
        # it as root too; do not weaken production permissions for hosted CI.
        if os.geteuid() != 0:
            args = ["sudo", "-n", *args]
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=180, **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_both_bundles_setup_offline_and_bot_nonroot(self):
        self.assertEqual(os.name, "posix")
        self.run_command(["docker", "info"])
        for edition, product in PRODUCTS.items():
            with self.subTest(edition=edition), tempfile.TemporaryDirectory(prefix="tg2cloud-compose-ci-") as temp:
                root = Path(temp)
                for name, data in bundle_files(ROOT, edition, "ghcr.io/luopojunzi/tg2cloud:ci").items():
                    (root / name).write_bytes(data)
                identifier = "tg2cloud-compose-test-" + uuid.uuid4().hex
                override = {"services": {"setup": {"image": IMAGE}, product.bot_service: {"image": IMAGE, "container_name": identifier}},
                            "networks": {product.docker_network: {"name": identifier}}}
                (root / "override.json").write_text(json.dumps(override))
                compose = ["docker", "compose", "-p", identifier, "-f", str(root / "docker-compose.yml"), "-f", str(root / "override.json")]
                try:
                    self.run_command([*compose, "config", "--quiet"])
                    self.run_command([*compose, "run", "--rm", "-T", "--pull", "never", "setup", "python", "-c", SETUP])
                    self.run_command([*compose, "run", "--rm", "-T", "--pull", "never", "setup", "python", "-m", "tg2cloud.compose", "check"])
                    output = self.run_command([*compose, "run", "--rm", "-T", "--no-deps", "--pull", "never", product.bot_service, "python", "-c", CHECK])
                    self.assertIn("COMPOSE_NONROOT=OK", output)
                    self.assertEqual((root / ".env").stat().st_mode & 0o777, 0o600)
                finally:
                    # Only return ownership of this test's private temporary tree;
                    # no project teardown, daemon prune or production path is used.
                    cleanup = """import os
from pathlib import Path
for root,dirs,files in os.walk('/workspace',followlinks=False):
    for name in dirs+files:
        path=Path(root)/name
        if not path.is_symlink():
            os.chown(path,UID,GID)
            path.chmod(0o700 if path.is_dir() else 0o600)
""".replace("UID", str(os.getuid())).replace("GID", str(os.getgid()))
                    self.run_command(["docker", "run", "--rm", "--network", "none", "--user", "0:0", "--volume", str(root) + ":/workspace", IMAGE, "python", "-c", cleanup])
                    subprocess.run(["docker", "network", "rm", identifier], capture_output=True, check=False, timeout=30)
