"""Opt-in ephemeral Linux CI gateway test, never a NAS/VPS deployment test."""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

from deployer_products import PRODUCTS
from scripts import lan_installer as lan

ENABLED = (sys.platform.startswith("linux") and shutil.which("docker")
           and os.environ.get("TG2CLOUD_TEST_LAN_DOCKER") == "1")


@unittest.skipUnless(ENABLED, "Opt-in Docker host-network test on disposable Linux CI only")
class LanDockerTests(unittest.TestCase):
    def docker(self, *args):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=180, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def exercise(self, product):
        network = json.loads(self.docker("network", "inspect", "bridge"))[0]
        address = lan.validate_ip(network["IPAM"]["Config"][0]["Gateway"])
        # Use Docker's private bridge IP solely as an isolated listener fixture.
        # The actual wizard rejects docker0 as a user-provided LAN interface.
        observed = []

        class Backend(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"LAN test backend")

            def log_message(self, *_args):
                pass

        backend = http.server.ThreadingHTTPServer(("127.0.0.1", product.management_port), Backend)
        self.addCleanup(backend.server_close)
        serving = threading.Thread(target=backend.serve_forever, daemon=True)
        serving.start()
        self.addCleanup(lambda: serving.join(timeout=5))
        self.addCleanup(backend.shutdown)
        self.docker("pull", lan.NGINX_IMAGE)
        with tempfile.TemporaryDirectory(prefix="tg2cloud-lan-nginx-test-") as private:
            directory = Path(private)
            directory.chmod(0o755)
            config = directory / "nginx.conf"
            config.write_text(lan.render_files(product, address)["nginx.conf"])
            config.chmod(0o644)
            name = "tg2cloud-test-lan-" + uuid.uuid4().hex
            flags = ["--name", name, "--network", "host", "--user", "101:101", "--read-only", "--cap-drop", "ALL",
                     "--security-opt", "no-new-privileges:true", "--tmpfs", lan.CONTAINER_TMP + ":" + lan.TMPFS_FLAGS,
                     "--mount", f"type=bind,source={config},target=/etc/nginx/nginx.conf,readonly", "--entrypoint", "nginx"]
            self.docker("run", "--rm", *flags, lan.NGINX_IMAGE, "-t")
            try:
                self.docker("run", "-d", *flags, lan.NGINX_IMAGE, "-g", "daemon off;")
                lan.wait_for_entry(product, address)
                self.assertTrue(observed)
                self.assertTrue(all(path == "/" for path in observed), "Nginx must block DAV before the backend")
                # Backend loopback remains reachable independently, with no LAN marker.
                self.assertNotEqual(lan.request_status(product, address, "/dav")[0], 200)
            finally:
                # Only this named UUID fixture container, never product containers.
                self.docker("rm", "-f", name)

    def test_clouddrive2_lan_nginx(self):
        self.exercise(PRODUCTS["clouddrive2"])

    def test_openlist_lan_nginx(self):
        self.exercise(PRODUCTS["openlist"])


if __name__ == "__main__":
    unittest.main()
