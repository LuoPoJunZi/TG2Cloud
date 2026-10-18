"""Opt-in real Nginx + synthetic read-only HTTP fixture, never user gateways."""
from __future__ import annotations

import base64
import http.server
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tg2cloud.addons.external_webdav import config, verification
from tg2cloud.deployment.proxy.manager import NGINX_IMAGE, render_config_set

from .test_feature import SECRET, XML, route

ENABLED = (os.name == "posix" and shutil.which("docker") and os.environ.get("TG2CLOUD_TEST_EXTERNAL_WEBDAV_DOCKER") == "1")


@unittest.skipUnless(ENABLED, "Requires explicit disposable Linux Docker integration environment")
class ExternalNginxTests(unittest.TestCase):
    def docker(self, *args):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=180, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def exercise(self, edition):
        target = route(edition)
        domain = target["domain"]
        user = "phone-reader"
        family = "family-reader"
        observed = []
        current = {"password": SECRET}

        class Backend(http.server.BaseHTTPRequestHandler):
            # This is only an HTTP fixture. No real storage or WebDAV server is installed.
            def handle_read(self):
                expected = "Basic " + base64.b64encode((user + ":" + current["password"]).encode()).decode()
                bot = "Basic " + base64.b64encode(("bot-user:" + SECRET).encode()).decode()
                admin = "Basic " + base64.b64encode(("admin:" + SECRET).encode()).decode()
                family_auth = "Basic " + base64.b64encode((family + ":" + SECRET).encode()).decode()
                if self.headers.get("Authorization") not in {expected, family_auth, bot, admin}:
                    self.send_response(401)
                    self.end_headers()
                    return
                observed.append((self.command, self.path, self.headers.get("Range")))
                if self.command == "PROPFIND":
                    self.send_response(207)
                    body = XML
                elif self.command == "OPTIONS":
                    self.send_response(204)
                    body = b""
                elif self.path.endswith("redirect.mp4"):
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1/internal-token")
                    body = b""
                elif self.headers.get("Range"):
                    self.send_response(206)
                    self.send_header("Content-Range", "bytes 0-0/10")
                    body = b"x"
                else:
                    self.send_response(200)
                    body = b"0123456789"
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            do_PROPFIND = do_GET = do_HEAD = do_OPTIONS = handle_read

            def write_forbidden(self):
                observed.append((self.command, "FORBIDDEN_WRITE", None))
                self.send_response(403)
                self.end_headers()

            do_DELETE = do_PUT = do_MOVE = do_COPY = do_MKCOL = do_PROPPATCH = do_LOCK = do_UNLOCK = write_forbidden

            def log_message(self, *_args):
                pass

        backend = http.server.ThreadingHTTPServer(("127.0.0.1", target["backend_port"]), Backend)
        serving = threading.Thread(target=backend.serve_forever, daemon=True)
        serving.start()
        try:
            self.docker("pull", NGINX_IMAGE)
            gid = self.docker("run", "--rm", "--entrypoint", "id", NGINX_IMAGE, "-g", "nginx")
            self.assertTrue(gid.isdigit())
            with tempfile.TemporaryDirectory(prefix="tg2cloud-external-nginx-test-") as private:
                directory = Path(private)
                directory.chmod(0o755)
                auth = directory / "auth"
                auth.mkdir(mode=0o755)
                certs = directory / "certs" / "live" / domain
                certs.mkdir(parents=True)
                result = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                                         "-subj", "/CN=" + domain, "-addext", "subjectAltName=DNS:" + domain,
                                         "-keyout", str(certs / "privkey.pem"), "-out", str(certs / "fullchain.pem")],
                                        capture_output=True, timeout=30, check=False)
                self.assertEqual(result.returncode, 0)
                files = render_config_set({"version": 2, "domains": {}, "external_webdav": {edition: target}})
                for name, content in files.items():
                    destination = directory / "nginx" / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(content)

                def rotate(password, *, include_family=True):
                    hashes = {user: config.password_hash(password)}
                    if include_family:
                        hashes[family] = config.password_hash(SECRET)
                    config.atomic(auth / (edition + ".htpasswd"), config.auth_content(hashes), mode=0o640)
                    # Assign actual image worker GID; retain test-runner UID for
                    # safe temp cleanup. No host-wide chown or product paths.
                    self.docker("run", "--rm", "-v", str(auth) + ":/auth", "--entrypoint", "sh", NGINX_IMAGE,
                                "-c", f"chown {os.geteuid()}:{gid} /auth /auth/{edition}.htpasswd && chmod 750 /auth && chmod 640 /auth/{edition}.htpasswd")

                rotate(SECRET)
                name = "tg2cloud-test-external-" + uuid.uuid4().hex
                flags = ["--name", name, "--network", "host", "--read-only", "--tmpfs", "/var/run", "--tmpfs", "/var/cache/nginx", "--tmpfs", "/tmp",
                         "-v", str(directory / "nginx/nginx.conf") + ":/etc/nginx/nginx.conf:ro",
                         "-v", str(directory / "nginx/conf.d") + ":/etc/nginx/conf.d:ro",
                         "-v", str(directory / "certs") + ":/etc/letsencrypt:ro",
                         "-v", str(auth) + ":/etc/nginx/external-auth:ro"]
                self.docker("run", "--rm", *flags, NGINX_IMAGE, "nginx", "-t")
                context = ssl.create_default_context(cafile=str(certs / "fullchain.pem"))

                def request(method, path, username=user, password=SECRET, headers=None):
                    client = verification.LoopbackTLS(domain, 443, context=context, timeout=10)
                    try:
                        fields = {"Authorization": "Basic " + base64.b64encode((username + ":" + password).encode()).decode()}
                        fields.update(headers or {})
                        client.request(method, path, headers=fields)
                        response = client.getresponse()
                        return response.status, response.read(), dict(response.getheaders())
                    finally:
                        client.close()

                try:
                    self.docker("run", "-d", *flags, NGINX_IMAGE, "nginx", "-g", "daemon off;")
                    for attempt in range(30):
                        try:
                            if request("GET", "/")[0] == 404:
                                break
                        except OSError:
                            if attempt == 29:
                                raise
                        time.sleep(0.1)
                    for bad_user, bad_secret in ((user, SECRET + "-bad"), ("bot-user", SECRET), ("admin", SECRET)):
                        self.assertEqual(request("PROPFIND", "/dav/", bad_user, bad_secret)[0], 401)
                    before = len(observed)
                    for method in ("PUT", "DELETE", "MOVE", "COPY", "MKCOL", "PROPPATCH", "LOCK", "UNLOCK", "POST", "PATCH"):
                        for path in ("/dav", "/dav/", "/dav/test-only"):
                            with self.subTest(method=method, path=path):
                                self.assertEqual(request(method, path)[0], 405)
                    self.assertEqual(len(observed), before, "write rejection must happen before the synthetic backend")
                    for path in ("/dav", "/dav/"):
                        status, body, _ = request("PROPFIND", path)
                        self.assertEqual(status, 207)
                        verification.propfind(body, domain)
                    self.assertEqual(request("PROPFIND", "/dav/", username=family)[0], 207)
                    self.assertEqual(request("GET", "/dav/video.mp4", username=family, headers={"Range": "bytes=0-0"})[:2], (206, b"x"))
                    for path in ("/dav/%E4%B8%AD%E6%96%87%20video.mp4", "/dav/file%25name.mp4"):
                        self.assertEqual(request("GET", path, headers={"Range": "bytes=0-0"})[:2], (206, b"x"))
                    self.assertEqual(request("HEAD", "/dav/video.mp4")[0], 200)
                    self.assertEqual(request("OPTIONS", "/dav/video.mp4")[0], 204)
                    for path in ("/davevil/", "/admin"):
                        self.assertEqual(request("GET", path)[0], 404)
                    for path in ("/dav/../admin", "/dav/%2e%2e/admin", "/dav/%252e%252e/admin", "/dav/a%2fb",
                                 "/dav/a%252fb", "/dav/a%5cb", "/dav/a%255cb", "/dav/a%25255cb", r"/dav/a\b", "/dav//a"):
                        with self.subTest(path=path):
                            self.assertEqual(request("GET", path)[0], 400)
                    self.assertEqual(request("GET", "/dav/redirect.mp4")[0], 502)
                    changed = SECRET + "-rotated"
                    current["password"] = changed
                    rotate(changed)
                    self.assertEqual(request("GET", "/dav/video.mp4")[0], 401)
                    self.assertEqual(request("GET", "/dav/video.mp4", password=changed)[0], 200)
                    self.assertEqual(request("GET", "/dav/video.mp4", username=family)[0], 200)
                    rotate(changed, include_family=False)
                    self.assertEqual(request("PROPFIND", "/dav/", username=family)[0], 401)
                    self.assertEqual(request("GET", "/dav/video.mp4", password=changed)[0], 200)
                    with patch.object(verification.ssl, "create_default_context", return_value=context):
                        verification.check_media(dict(target, username=user), changed, "视频 空格.mp4")
                finally:
                    self.docker("rm", "-f", name)
        finally:
            backend.shutdown()
            serving.join(timeout=5)
            backend.server_close()

    def test_both_editions_readonly_gate_range_encoding_and_rotation(self):
        for edition in ("clouddrive2", "openlist"):
            with self.subTest(edition=edition):
                self.exercise(edition)
