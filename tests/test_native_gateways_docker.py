"""Opt-in disposable native gateway smoke; no Telegram, cloud login or real data."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

from tg2cloud.deployment import architecture, payload, uninstall
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import manager as proxy
from tg2cloud.deployment.proxy.manager import CERTBOT_IMAGE, NGINX_IMAGE, render_compose

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("TG2CLOUD_TEST_NATIVE_DOCKER") == "1", "native Docker gateway test requires explicit opt-in")
class NativeGatewayTests(unittest.TestCase):
    def docker(self, *args, timeout=120):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_real_certbot_startup_repairs_only_missing_status_and_reads_back_mounts(self):
        # No Nginx service is started: no host 80/443, ACME or real certificates.
        project = "tg2cloud-certbot-test-" + uuid.uuid4().hex
        name = project + "-certbot"
        with tempfile.TemporaryDirectory(prefix="tg2cloud-certbot-test-") as temporary:
            root = Path(temporary).resolve() / project
            for child in ("www", "letsencrypt", "lib", "log", "status"):
                (root / "certbot" / child).mkdir(parents=True)
            compose = root / "docker-compose.yml"
            content = render_compose().replace("container_name: tg2cloud-proxy-certbot", "container_name: " + name)
            compose.write_text(content, encoding="utf-8")
            arguments = ("compose", "--project-name", project, "-f", str(compose))
            template = ('{"labels":{{json .Config.Labels}},"network":{{json .HostConfig.NetworkMode}},'
                        '"mounts":{{json .Mounts}}}')
            try:
                self.docker(*arguments, "up", "-d", "certbot")
                with (patch.object(uninstall, "PROXY_ROOT", str(root)),
                      patch.object(uninstall, "PROXY_PROJECT", project),
                      patch.object(uninstall, "PROXY_NETWORK", project + "_default"),
                      patch.object(uninstall, "PROXY_CERTBOT_CONTAINER", name)):
                    item = json.loads(self.docker("inspect", "--format", template, name))
                    uninstall.proxy_identity(name, item)
                    self.assertEqual(len(uninstall.bind_map(item)), 5)
                    compose.write_text(content.replace("      - ./certbot/status:/status\n", ""), encoding="utf-8")
                    self.docker(*arguments, "up", "-d", "certbot")
                    item = json.loads(self.docker("inspect", "--format", template, name))
                    with self.assertRaisesRegex(uninstall.UninstallError, "缺少续期状态挂载 /status"):
                        uninstall.proxy_identity(name, item)
                    # Exercise startup against the real incomplete container.
                    # Simulate Compose reusing it on the initial up; the guarded
                    # one-shot recreation and final readback use actual Docker.
                    compose.write_text(content, encoding="utf-8")
                    manager = proxy.DomainProxyManager(LocalSession(SafeLog()), PRODUCTS["clouddrive2"], {}, lambda _: None)
                    manager._expected_compose_sha256 = hashlib.sha256(content.encode()).hexdigest()
                    original_run = manager._run
                    def reused_first_up(command, **kwargs):
                        if command == f"docker compose -f {root}/docker-compose.yml up -d certbot":
                            return 0, ""
                        return original_run(command, **kwargs)
                    manager._run = reused_first_up
                    with (patch.object(proxy, "PROXY_ROOT", str(root)),
                          patch.object(proxy, "PROXY_CERTBOT_CONTAINER", name)):
                        self.assertEqual(manager._compose("up -d certbot")[0], 0)
                    item = json.loads(self.docker("inspect", "--format", template, name))
                    uninstall.proxy_identity(name, item)
                    self.assertEqual(len(uninstall.bind_map(item)), 5)
            finally:
                self.docker(*arguments, "down", "--remove-orphans")

    def test_native_gateway_http_and_proxy_executables(self):
        self.assertIsNotNone(shutil.which("docker"), "Opted-in native tests require Docker")
        self.assertTrue(Path("/dev/fuse").is_char_device(), "CloudDrive2 smoke requires native kernel /dev/fuse, not QEMU")
        session = LocalSession(SafeLog())
        architecture.check_docker(session)
        for image, command in ((NGINX_IMAGE, ["nginx", "-t"]), (CERTBOT_IMAGE, ["--version"])):
            architecture.ensure_image(session, image)
            self.docker("run", "--rm", "--network", "none", image, *command)
        for edition, port in (("clouddrive2", 19798), ("openlist", 5244)):
            with self.subTest(edition=edition):
                product = PRODUCTS[edition]
                image = payload.gateway_image(ROOT, product)
                architecture.ensure_image(session, image)
                name = "tg2cloud-native-test-" + uuid.uuid4().hex
                volumes = [name + "-data", name + "-mounts"] if edition == "clouddrive2" else [name + "-data"]
                try:
                    for volume in volumes:
                        self.docker("volume", "create", volume)
                    options = ["--name", name, "--publish", f"127.0.0.1::{port}"]
                    if edition == "clouddrive2":
                        options += ["--privileged", "--pid", "host", "--device", "/dev/fuse:/dev/fuse",
                                    "--env", "CLOUDDRIVE_HOME=/Config", "--volume", volumes[0] + ":/Config",
                                    "--volume", volumes[1] + ":/CloudNAS"]
                    else:
                        # Prepare only the newly-created disposable volume for
                        # the same non-root gateway identity as production.
                        self.docker("run", "--rm", "--network", "none", "--user", "0:0",
                                    "--volume", volumes[0] + ":/opt/openlist/data", "--entrypoint", "chown",
                                    image, "1001:1001", "/opt/openlist/data")
                        options += ["--user", "1001:1001", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                                    "--env", "OPENLIST_ADMIN_PASSWORD=isolated-native-ci-only",
                                    # Empty named volumes otherwise copy the
                                    # image's root-owned directory metadata a
                                    # second time, undoing the prepared owner.
                                    # Production uses an already-owned bind.
                                    "--mount", "type=volume,source=" + volumes[0] + ",target=/opt/openlist/data,volume-nocopy"]
                    self.docker("run", "--detach", *options, image)
                    try:
                        binding = self.docker("port", name, str(port) + "/tcp")
                    except AssertionError:
                        # Report only this disposable fixture's bounded output,
                        # never inspect its full environment or real instances.
                        state = self.docker("inspect", "--format", "{{json .State}}", name)
                        logs = self.docker("logs", "--tail", "40", name)
                        log = SafeLog()
                        log.register({"OPENLIST_ADMIN_PASSWORD": "isolated-native-ci-only"})
                        self.fail(log.clean("Gateway fixture stopped before port publication: " + state + "\n" + logs))
                    self.assertTrue(binding.startswith("127.0.0.1:"), binding)
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    deadline, ready = time.monotonic() + 120, False
                    while time.monotonic() < deadline:
                        try:
                            with opener.open("http://" + binding + "/", timeout=5) as response:
                                ready = response.status == 200 and bool(response.read(4096))
                        except (OSError, urllib.error.URLError):
                            pass
                        if ready:
                            break
                        time.sleep(2)
                    self.assertTrue(ready, "Fresh isolated gateway did not serve its management page")
                    architecture.check_container(session, name, require_running=True)
                    state = json.loads(self.docker("inspect", "--format", "{{json .State}}", name))
                    self.assertTrue(state["Running"])
                    self.assertFalse(state.get("OOMKilled"))
                finally:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)
                    for volume in volumes:
                        subprocess.run(["docker", "volume", "rm", volume], capture_output=True, timeout=30, check=False)
