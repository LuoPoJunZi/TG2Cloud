"""Actual loopback HTTP transport with synthetic, non-persistent fixtures."""
from __future__ import annotations

import base64
import http.server
import threading
import unittest

from tg2cloud.addons.external_webdav import verification

from .test_feature import SECRET, XML


class TransportTests(unittest.TestCase):
    def test_auth_propfind_xml_range_and_headers_over_real_loopback(self):
        observed = []

        class Fixture(http.server.BaseHTTPRequestHandler):
            def respond(self):
                expected = "Basic " + base64.b64encode(("phone-reader:" + SECRET).encode()).decode()
                observed.append((self.command, self.path, self.headers.get("Depth"), self.headers.get("Range")))
                if self.headers.get("Authorization") != expected:
                    self.send_response(401)
                    payload = b""
                elif self.command == "PROPFIND":
                    self.send_response(207)
                    payload = XML
                else:
                    self.send_response(206)
                    self.send_header("Content-Range", "bytes 0-0/256")
                    payload = b"x"
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)

            do_GET = do_HEAD = do_OPTIONS = do_PROPFIND = respond

            def log_message(self, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            target = {"domain": "external.example.test", "backend_port": port, "username": "phone-reader"}
            verification.check_backend(target, SECRET)
            status, body, headers = verification.request(target["domain"], port, "GET", "/dav/%E4%B8%AD%E6%96%87%20video.mp4",
                                                        credentials=("phone-reader", SECRET), headers={"Range": "bytes=0-0"})
            self.assertEqual((status, body), (206, b"x"))
            self.assertEqual(headers["Content-Range"], "bytes 0-0/256")
            self.assertEqual([item[0] for item in observed], ["PROPFIND", "PROPFIND", "GET"])
            self.assertEqual(observed[-1][-1], "bytes=0-0")
            self.assertTrue(all(item[2] == "0" for item in observed))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
