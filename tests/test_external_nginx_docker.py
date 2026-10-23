"""Opt-in real Nginx single-hop smoke; isolated network, no host port binds.

TG2CLOUD_TEST_EXTERNAL_NGINX_DOCKER=1 enables this on a Linux test daemon.
It exercises rendered configs/reload, not production ACME or migration.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from tg2cloud.deployment.proxy.external_config import render_route
from tg2cloud.deployment.proxy.manager import NGINX_IMAGE
from tg2cloud.deployment.proxy.state import DomainRoute


@unittest.skipUnless(os.environ.get("TG2CLOUD_TEST_EXTERNAL_NGINX_DOCKER") == "1", "opt-in isolated external Nginx Docker test")
class ExternalNginxDockerTests(unittest.TestCase):
    def run_docker(self, *arguments):
        result = subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, "isolated Docker command failed: " + " ".join(arguments[:2]) + "\n" + result.stderr[-2000:])
        return result.stdout

    def setUp(self):
        if os.name != "posix" or not shutil.which("docker"):
            self.fail("explicit Docker integration requires Linux and a dedicated local test daemon")
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
        self.temp = tempfile.TemporaryDirectory(prefix="tg2cloud-external-nginx-")
        self.addCleanup(self.temp.cleanup)
        root = self.root = Path(self.temp.name).resolve()
        root.chmod(0o755)
        sites = self.sites = root / "sites"
        sites.mkdir(mode=0o755)
        self.key = "tg2cloud-it-" + uuid.uuid4().hex[:16]
        self.run_docker("network", "create", "--label", "com.tg2cloud.test=true", self.key)
        self.addCleanup(lambda: self.run_docker("network", "rm", self.key))
        self.backend = self.key + "-backend"
        self.frontend = self.key + "-edge"
        config = root / "nginx.conf"
        config.write_text("events {}\nhttp { include /etc/nginx/conf.d/*.conf; }\n")
        original = sites / "original.conf"
        original.write_text('server {listen 80; server_name original.example.test; location / {return 200 "original site";}}\n')
        self.original = original.read_bytes()
        backend = root / "backend.conf"
        backend.write_text('events {}\nhttp {server {listen 19798; location / {return 200 "CloudDrive test backend";}}}\n')
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cloud.example.test")])
        now = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(private.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=1))
                .not_valid_after(now + dt.timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(private.public_key()), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private.public_key()), critical=False)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                    data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                    encipher_only=None, decipher_only=None), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName("cloud.example.test"), x509.DNSName("dav.example.test")]), critical=False)
                .sign(private, hashes.SHA256()))
        self.test_certificate, self.test_private = cert, private
        (root / "test.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        secret = root / "test-key.pem"
        secret.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        secret.chmod(0o600)
        self.run_docker("run", "-d", "--name", self.backend, "--network", self.key,
                        "--network-alias", "tg2cloud-clouddrive2", "--mount", f"type=bind,src={backend},dst=/etc/nginx/nginx.conf,readonly", NGINX_IMAGE)
        self.addCleanup(lambda: self.run_docker("rm", "-f", self.backend))
        self.run_docker("run", "-d", "--name", self.frontend, "--network", self.key,
                        "--mount", f"type=bind,src={config},dst=/etc/nginx/nginx.conf,readonly",
                        "--mount", f"type=bind,src={sites},dst=/etc/nginx/conf.d,readonly",
                        "--mount", f"type=bind,src={root},dst=/test,readonly", NGINX_IMAGE)
        self.addCleanup(lambda: self.run_docker("rm", "-f", self.frontend))
        self.before = self.run_docker("inspect", "--format", "{{.Id}}", self.frontend).strip()
        self.assertEqual(self.request("http://original.example.test/"), "original site")

    def request(self, url, *, code=False, credentials=None, peer=False):
        # Use the existing image as a short-lived network client. No host port,
        # Docker Socket, credentials or certificate-verification bypass.
        hostname = url.split("/")[2]
        # Standard nginx Debian/alpine images need not ship curl; client uses
        # the separately pinned Certbot Python image's standard TLS libraries.
        from tg2cloud.deployment.proxy.manager import CERTBOT_IMAGE
        authorization = "Basic " + base64.b64encode((credentials[0] + ":" + credentials[1]).encode()).decode() if credentials else ""
        python = ("import http.client,ssl,sys,hashlib; "
                  "host,secure,path=sys.argv[1],sys.argv[2]=='1',sys.argv[3]; "
                  "context=ssl.create_default_context(cafile='/test/test.pem'); "
                  "C=http.client.HTTPSConnection if secure else http.client.HTTPConnection; "
                  "c=C(host,443 if secure else 80,timeout=8,**({'context':context} if secure else {})); "
                  "c.connect();fingerprint=hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest() if secure else ''; "
                  "c.request('GET',path,headers=({'Authorization':sys.argv[5]} if sys.argv[5] else {}));r=c.getresponse(); "
                  "print(fingerprint if sys.argv[4]=='peer' else str(r.status) if sys.argv[4]=='code' else r.read().decode(),end='')")
        # A per-client host alias uses the current frontend IP; the production
        # upstream still uses variable Docker DNS and its stable gateway alias.
        ip = self.run_docker("inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", self.frontend).strip()
        return self.run_docker("run", "--rm", "--network", self.key, "--add-host", hostname + ":" + ip,
            "--mount", f"type=bind,src={self.root},dst=/test,readonly", "--entrypoint", "python", CERTBOT_IMAGE,
            "-c", python, hostname, "1" if url.startswith("https:") else "0", "/" + url.split("/", 3)[3],
            "peer" if peer else "code" if code else "body", authorization)

    def reload(self):
        self.run_docker("exec", self.frontend, "nginx", "-t")
        self.run_docker("exec", self.frontend, "nginx", "-s", "reload")
        time.sleep(0.3)

    def test_dav_rotation_disable_and_management_removal_preserve_original(self):
        from tg2cloud.addons.external_webdav.config import password_hash
        value = {"mount": {"conf_dir": "/etc/nginx/conf.d"}, "network": {"mode": "bridge"},
                 "certificates": {domain: {"chain": "/test/test.pem", "key": "/test/test-key.pem"}
                                  for domain in ("cloud.example.test", "dav.example.test")}}
        route = {"edition": "clouddrive2", "domain": "dav.example.test", "backend_port": 19798,
                 "auth_file": "external-auth/clouddrive2.htpasswd", "enabled": True}
        directory = self.sites / "tg2cloud-assets/auth"
        directory.mkdir(parents=True)
        directory.parent.chmod(0o755)
        directory.chmod(0o755)
        auth = directory / "clouddrive2.htpasswd"
        first, second = "FixtureOnly-Rotate-First-93", "FixtureOnly-Rotate-Second-47"
        auth.write_text("reader:" + password_hash(first) + "\n")
        auth.chmod(0o644)  # Synthetic hashes only, fixture worker must read them.
        management = self.sites / "tg2cloud-clouddrive2.conf"
        dav = self.sites / "tg2cloud-webdav-clouddrive2.conf"
        management.write_text(render_route(DomainRoute("clouddrive2", "cloud.example.test", 19798), value))
        dav.write_text(render_route(route, value))
        self.reload()
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True), "401")
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", first)), "200")
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("bot-user", first)), "401")
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("admin", first)), "401")
        replacement = auth.with_suffix(".candidate")
        replacement.write_text("reader:" + password_hash(second) + "\n")
        replacement.chmod(0o644)
        replacement.replace(auth)  # Directory mount must observe the new inode WITHOUT reload.
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", first)), "401")
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", second)), "200")
        dav.write_text(render_route({**route, "enabled": False}, value))
        self.reload()
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", second)), "403")
        dav.write_text(render_route(route, value))
        management.unlink()
        self.reload()
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", second)), "200")
        self.run_docker("restart", self.frontend)  # Only this isolated test container.
        self.assertEqual(self.request("https://dav.example.test/dav/", code=True, credentials=("reader", second)), "200")
        dav.unlink()
        self.reload()
        self.assertEqual(self.request("http://original.example.test/"), "original site")
        self.assertEqual((self.sites / "original.conf").read_bytes(), self.original)

    def test_certificate_reload_serves_new_fingerprint_without_touching_original(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        value = {"mount": {"conf_dir": "/etc/nginx/conf.d"}, "network": {"mode": "bridge"},
                 "certificates": {"cloud.example.test": {"chain": "/test/test.pem", "key": "/test/test-key.pem"}}}
        path = self.sites / "tg2cloud-clouddrive2.conf"
        path.write_text(render_route(DomainRoute("clouddrive2", "cloud.example.test", 19798), value))
        self.reload()
        before = self.request("https://cloud.example.test/", peer=True)
        old = self.test_certificate
        builder = (x509.CertificateBuilder().subject_name(old.subject).issuer_name(old.issuer)
                   .public_key(self.test_private.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(old.not_valid_before_utc).not_valid_after(old.not_valid_after_utc))
        for extension in old.extensions:
            builder = builder.add_extension(extension.value, critical=extension.critical)
        renewed = builder.sign(self.test_private, hashes.SHA256())
        replacement = self.root / "test.pem.candidate"
        replacement.write_bytes(renewed.public_bytes(serialization.Encoding.PEM))
        replacement.replace(self.root / "test.pem")
        self.reload()
        after = self.request("https://cloud.example.test/", peer=True)
        self.assertNotEqual(before, after)
        self.assertEqual(after, hashlib.sha256(renewed.public_bytes(serialization.Encoding.DER)).hexdigest())
        self.assertEqual(self.request("http://original.example.test/"), "original site")
        self.assertEqual(self.run_docker("inspect", "--format", "{{.Id}}", self.frontend).strip(), self.before)

    def test_gateway_recreation_changes_ip_but_keeps_stable_alias_and_original_site(self):
        value = {"mount": {"conf_dir": "/etc/nginx/conf.d"}, "network": {"mode": "bridge"},
                 "certificates": {"cloud.example.test": {"chain": "/test/test.pem", "key": "/test/test-key.pem"}}}
        (self.sites / "tg2cloud-clouddrive2.conf").write_text(
            render_route(DomainRoute("clouddrive2", "cloud.example.test", 19798), value))
        self.reload()
        self.assertEqual(self.request("https://cloud.example.test/"), "CloudDrive test backend")
        old_ip = self.run_docker("inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", self.backend).strip()
        self.run_docker("rm", "-f", self.backend)
        blocker = self.key + "-occupy-old-ip"
        self.run_docker("run", "-d", "--name", blocker, "--network", self.key, "--ip", old_ip, NGINX_IMAGE)
        self.addCleanup(lambda: self.run_docker("rm", "-f", blocker))
        config = self.root / "backend.conf"
        config.write_text('events {}\nhttp {server {listen 19798; location / {return 200 "CloudDrive recreated backend";}}}\n')
        self.run_docker("run", "-d", "--name", self.backend, "--network", self.key,
                        "--network-alias", "tg2cloud-clouddrive2", "--mount", f"type=bind,src={config},dst=/etc/nginx/nginx.conf,readonly", NGINX_IMAGE)
        new_ip = self.run_docker("inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", self.backend).strip()
        self.assertNotEqual(old_ip, new_ip)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.request("https://cloud.example.test/", code=True) == "200":
                break
            time.sleep(0.5)
        self.assertEqual(self.request("https://cloud.example.test/"), "CloudDrive recreated backend")
        self.assertEqual(self.request("http://original.example.test/"), "original site")
        self.assertEqual(self.run_docker("inspect", "--format", "{{.Id}}", self.frontend).strip(), self.before)

    def test_single_proxy_reload_failure_and_removal_preserve_original(self):
        value = {"mount": {"conf_dir": "/etc/nginx/conf.d"}, "network": {"mode": "bridge"},
                 "certificates": {"cloud.example.test": {"chain": "/test/test.pem", "key": "/test/test-key.pem"}}}
        path = self.sites / "tg2cloud-clouddrive2.conf"
        candidate = render_route(DomainRoute("clouddrive2", "cloud.example.test", 19798), value)
        path.write_text(candidate)
        self.run_docker("exec", self.frontend, "nginx", "-t")
        self.run_docker("exec", self.frontend, "nginx", "-s", "reload")
        time.sleep(0.5)
        self.assertEqual(self.request("https://cloud.example.test/"), "CloudDrive test backend")
        self.assertEqual(self.request("https://cloud.example.test/dav/", code=True), "403")
        self.assertEqual(self.request("http://original.example.test/"), "original site")
        path.write_text("invalid nginx directive;\n")
        failure = subprocess.run(["docker", "exec", self.frontend, "nginx", "-t"], capture_output=True, timeout=30, check=False)
        self.assertNotEqual(failure.returncode, 0)
        self.assertEqual(self.request("http://original.example.test/"), "original site")
        path.unlink()
        self.run_docker("exec", self.frontend, "nginx", "-t")
        self.run_docker("exec", self.frontend, "nginx", "-s", "reload")
        self.assertEqual((self.sites / "original.conf").read_bytes(), self.original)
        self.assertEqual(self.run_docker("inspect", "--format", "{{.Id}}", self.frontend).strip(), self.before)
        self.assertEqual(self.request("http://original.example.test/"), "original site")


if __name__ == "__main__":
    unittest.main()
