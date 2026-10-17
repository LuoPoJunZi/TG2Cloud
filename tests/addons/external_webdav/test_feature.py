from __future__ import annotations

import base64
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.addons.external_webdav import cli, config, nginx, releases, verification
from tg2cloud.addons.external_webdav.service import Service
from tg2cloud.deployment import uninstall
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import maintenance
from tg2cloud.deployment.proxy.manager import (
    DomainProxyManager,
    render_compose,
    render_config_set,
)
from tg2cloud.deployment.proxy.state import (
    certificate_domains,
    empty_state,
    has_routes,
    normalize_state,
    state_with_route,
    state_without_route,
)

ROOT = Path(__file__).resolve().parents[3]
SECRET = "Kp9!synthetic-Qx8uLz-7mR"
XML = b'<D:multistatus xmlns:D="DAV:"><D:response><D:href>/dav/</D:href><D:propstat><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response></D:multistatus>'


def route(edition="openlist", *, enabled=True):
    return {"kind": "external_webdav", "owner": config.OWNER, "edition": edition,
            "instance_dir": PRODUCTS[edition].install_dir, "domain": edition + "-files.example.test",
            "enabled": enabled, "backend_port": PRODUCTS[edition].management_port,
            "auth_file": f"external-auth/{edition}.htpasswd"}


def shared():
    return {"version": 2, "domains": {"clouddrive2": {"domain": "admin.example.test", "backend_port": 19798}},
            "external_webdav": {"openlist": route()}}


def env(relative="Telegram", user="bot-reader"):
    return {"WEBDAV_" + key + "_B64": base64.b64encode(value.encode()).decode()
            for key, value in {"URL": PRODUCTS["openlist"].webdav_url, "USERNAME": user, "TARGET_PATH": relative}.items()}


class ConfigTests(unittest.TestCase):
    def test_logical_root_and_relative_are_distinct(self):
        self.assertEqual(config.logical_path("/网盘/视频 目录/"), "/网盘/视频 目录")
        self.assertEqual(config.logical_path("/", allow_root=True), "/")
        for value in ("/", "relative", "/a/../b", "/a//b", "/a\\b", "/a\nb"):
            with self.subTest(path=value), self.assertRaises(ValueError):
                config.logical_path(value)

    def test_bot_binding_tracks_directory_not_password(self):
        original = env()
        self.assertNotEqual(config.binding(original), config.binding(env("New")))
        self.assertNotEqual(config.binding(original), config.binding(env(user="other")))
        self.assertEqual(config.binding(original), config.binding(dict(original, WEBDAV_PASSWORD_B64="irrelevant")))

    def test_legacy_and_blank_primary_keys_follow_actual_bot_precedence(self):
        legacy = {"CD2_TARGET_PATH_B64": base64.b64encode(b"Old/Telegram").decode(), "WEBDAV_TARGET_PATH_B64": ""}
        self.assertEqual(config.decode(legacy, "TARGET_PATH"), "Old/Telegram")
        legacy["WEBDAV_TARGET_PATH_B64"] = base64.b64encode(b"New").decode()
        self.assertEqual(config.decode(legacy, "TARGET_PATH"), "New")
        self.assertEqual(config.decode({"WEBDAV_USERNAME_B64": "", "CD2_WEBDAV_USERNAME_B64": base64.b64encode(b"bot-user").decode()}, "USERNAME"), "bot-user")

    def test_accounts_never_reuse_bot_or_admin(self):
        for user in ("admin", "root", "administrator", "guest", "bot-reader", "a:b", "new\nuser", "bad user", "--flag"):
            with self.subTest(user=user), self.assertRaises(ValueError):
                config.username(user, "bot-reader")
        self.assertEqual(config.username("phone-reader", "bot-reader"), "phone-reader")

    def test_password_generation_and_rejection(self):
        self.assertEqual(config.password(SECRET), SECRET)
        for value in ("short", "PASSWORD123456789", " " + SECRET, SECRET + "\n", "重复" * 20):
            with self.subTest(value=value), self.assertRaises(ValueError):
                config.password(value)
        for _ in range(20):
            config.password(config.new_password())

    def test_real_openssl_salted_slow_hash_and_rotation(self):
        executable = shutil.which("openssl")
        if executable is None and Path("F:/Program Files/Git/usr/bin/openssl.exe").is_file():
            executable = "F:/Program Files/Git/usr/bin/openssl.exe"
        self.assertIsNotNone(executable, "OpenSSL is a prerequisite of this feature test")
        first = config.password_hash(SECRET, executable=executable)
        self.assertRegex(first, config.HASH)
        self.assertNotEqual(first, config.password_hash(SECRET, executable=executable))
        self.assertEqual(first, config.password_hash(SECRET, existing=first, executable=executable))
        with self.assertRaisesRegex(ValueError, "不一致"):
            config.password_hash(SECRET + "-changed", existing=first, executable=executable)
        self.assertNotIn(SECRET, first)

    def test_atomic_hash_replacement_is_seen_by_directory_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "auth" / "openlist.htpasswd"
            config.atomic(path, b"old-hash", mode=0o640)
            old_inode = path.stat().st_ino
            config.atomic(path, b"new-hash", mode=0o640)
            self.assertEqual(path.read_bytes(), b"new-hash")
            self.assertNotEqual(path.stat().st_ino, old_inode)

    def test_safe_log_redacts_secrets_and_headers(self):
        messages = []
        log = SafeLog(messages.append)
        log.register({"EXTERNAL_PASSWORD": SECRET})
        log("failed: " + SECRET)
        log("Authorization: Basic testfixture")
        self.assertNotIn(SECRET, "\n".join(messages))
        self.assertNotIn("testfixture", "\n".join(messages))


class SharedStateTests(unittest.TestCase):
    def test_v1_unchanged_and_v2_no_downgrade(self):
        self.assertEqual(normalize_state(json.dumps(empty_state())), empty_state())
        self.assertEqual(normalize_state(json.dumps(shared())), shared())
        for data in ({"version": 99, "domains": {}}, {"version": True, "domains": {}}, dict(shared(), future={}), dict(shared(), version=1)):
            with self.assertRaises(ValueError):
                normalize_state(json.dumps(data))

    def test_unknown_owner_auth_scope_or_type_is_rejected(self):
        for field, value in (("owner", "unknown"), ("kind", "management"), ("enabled", "yes"),
                             ("auth_file", "../../passwd"), ("instance_dir", "/opt/../private"), ("backend_port", 80)):
            state = shared()
            state["external_webdav"]["openlist"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                normalize_state(json.dumps(state))

    def test_management_reconfigure_and_remove_preserve_addon_and_cert(self):
        state = shared()
        updated = state_with_route(state, PRODUCTS["clouddrive2"], "new-admin.example.test")
        removed = state_without_route(updated, "clouddrive2")
        self.assertEqual(removed["external_webdav"], state["external_webdav"])
        self.assertTrue(has_routes(removed))
        self.assertEqual(certificate_domains(removed), ("openlist-files.example.test",))
        removed["external_webdav"]["openlist"]["enabled"] = False
        self.assertEqual(certificate_domains(removed), ("openlist-files.example.test",))

    def test_management_domain_collision(self):
        with self.assertRaisesRegex(ValueError, "WebDAV"):
            state_with_route(shared(), PRODUCTS["clouddrive2"], route()["domain"])

    def test_generated_config_has_independent_gate_and_preserves_management_block(self):
        files = render_config_set(shared())
        management = files["conf.d/20-clouddrive2.conf"]
        public = files["conf.d/30-external-webdav-openlist.conf"]
        self.assertIn("location = /dav", management)
        self.assertIn("return 403", management)
        for expected in ("auth_basic_user_file /etc/nginx/external-auth/openlist.htpasswd", "proxy_set_header Authorization $http_authorization",
                         "GET|HEAD|OPTIONS|PROPFIND", "return 405", "proxy_buffering off", "proxy_set_header Range $http_range",
                         "location = /dav", "location ^~ /dav/", "location / { return 404", "proxy_hide_header Location",
                         "limit_conn", "rate=2r/s", "client_max_body_size 16k", "access_log off", "proxy_max_temp_file_size 0"):
            self.assertIn(expected, public)
        self.assertNotIn(SECRET, public)
        self.assertIn("./external-auth:/etc/nginx/external-auth:ro", render_compose(certificate_domains(shared()), external_auth=True))
        self.assertNotIn("external-auth", render_compose())

    def test_disabled_route_stays_tls_but_has_no_proxy(self):
        text = nginx.render_route(route(enabled=False))
        self.assertNotIn("proxy_pass", text)
        self.assertIn("return 403", text)
        self.assertIn("listen 443 ssl", text)

    def test_last_management_removal_keeps_proxy_alive(self):
        manager = DomainProxyManager(Mock(), PRODUCTS["clouddrive2"], {}, Mock())
        manager.read_state = Mock(return_value=shared())
        manager._activate = Mock()
        manager._compose = Mock(return_value=(0, ""))
        manager._verify_remaining_routes = Mock()
        manager._commit_state = Mock()
        manager._remove_locked()
        self.assertEqual(manager._activate.call_args.args[0]["domains"], {})
        self.assertTrue(manager._activate.call_args.args[0]["external_webdav"])
        self.assertFalse(any("stop" in call.args[0] for call in manager._compose.call_args_list))

    def test_activation_failure_preserves_other_edition_and_disables_selected(self):
        state = shared()
        state["external_webdav"]["clouddrive2"] = route("clouddrive2")
        manager = DomainProxyManager(Mock(), PRODUCTS["openlist"], {}, Mock())
        manager.read_state = Mock(return_value=state)
        manager._ensure_state_file = Mock()
        manager._activate = Mock(side_effect=[RuntimeError("candidate fails"), None])
        manager._compose = Mock(return_value=(0, ""))
        manager._commit_state = Mock()
        with self.assertRaises(RuntimeError):
            manager.apply_shared_state_locked(state)
        fallback = manager._commit_state.call_args.args[0]
        self.assertFalse(fallback["external_webdav"]["openlist"]["enabled"])
        self.assertTrue(fallback["external_webdav"]["clouddrive2"]["enabled"])

    def test_core_uninstall_refuses_dependent_gateway(self):
        with patch.object(uninstall, "docker_snapshot", return_value=({}, {})), patch.object(uninstall, "read_state", return_value=shared()), self.assertRaisesRegex(uninstall.UninstallError, "WebDAV"):
            uninstall.build_plan(("openlist",), Mock())

    def test_schema2_backup_requires_authentication_resources(self):
        with self.assertRaisesRegex(ValueError, "authentication"):
            maintenance.validate_auth_records(shared(), {})
        maintenance.validate_auth_records(shared(), {"proxy/external-auth/openlist.htpasswd": {"kind": "file"}})


class VerificationTests(unittest.TestCase):
    def test_xml_encoding_and_untrusted_href(self):
        self.assertEqual(verification.propfind(XML, route()["domain"]), ("/dav/",))
        for href in ("/dav/%E4%B8%AD%E6%96%87%20file.mp4", "https://openlist-files.example.test/dav/a.mp4"):
            self.assertTrue(verification.propfind(XML.replace(b"/dav/", href.encode()), route()["domain"]))
        for href in ("/davevil/", "/dav/../admin", "/dav/%252e%252e/foo", "http://127.0.0.1/dav/", "https://evil.test/dav/", "/dav/a?token=secret", "/dav/\\foo"):
            with self.subTest(href=href), self.assertRaises(ValueError):
                verification.propfind(XML.replace(b"/dav/", href.encode()), route()["domain"])
        with self.assertRaises(ValueError):
            verification.propfind(b'<!DOCTYPE x [<!ENTITY e "test">]>' + XML, route()["domain"])

    def test_authentication_directory_and_anonymous_denial(self):
        target = dict(route(), username="phone-reader")
        with patch.object(verification, "request", side_effect=[(207, XML, {}), (401, b"", {})]) as request:
            verification.check_backend(target, SECRET)
            self.assertEqual(request.call_args_list[0].kwargs["credentials"], ("phone-reader", SECRET))
        for status in (401, 403, 429, 500, 502):
            with patch.object(verification, "request", return_value=(status, b"", {})), self.assertRaisesRegex(ValueError, str(status)):
                verification.check_backend(target, SECRET)

    def test_real_probe_never_uses_destructive_methods(self):
        for method in ("DELETE", "PUT", "MOVE", "COPY", "LOCK", "PROPPATCH"):
            with self.assertRaises(ValueError):
                verification.request("example.test", 1, method, "/dav/")

    def test_range_sample_is_bounded_and_read_only(self):
        responses = [(200, b"", {"Content-Length": "42"}), (204, b"", {}), (206, b"x", {"Content-Range": "bytes 0-0/42"})]
        with patch.object(verification, "request", side_effect=responses) as request:
            verification.check_media(dict(route(), username="phone-reader"), SECRET, "中文 视频.mp4")
            self.assertEqual([call.args[2] for call in request.call_args_list], ["HEAD", "OPTIONS", "GET"])
            self.assertEqual(request.call_args.kwargs["headers"], {"Range": "bytes=0-0"})
            self.assertIn("%20", request.call_args.args[3])
        for path in ("/absolute", "../file", "a//b", "file?token=x", "file%2fsecret"):
            with self.assertRaises(ValueError):
                verification.check_media({}, SECRET, path)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ui, self.session = Mock(), Mock()
        self.messages = []
        self.service = Service(PRODUCTS["openlist"], self.session, SafeLog(self.messages.append), self.ui,
                               root=Path(self.temp.name).resolve())
        self.service.launcher = Path(self.temp.name).resolve() / "bin/tg2cloud-webdav"
        self.item = {"schema": 1, "owner": config.OWNER, "edition": "openlist", "instance_dir": "/opt/tg2cloud-openlist",
                     "domain": route()["domain"], "username": "phone-reader", "bot_root": "/网盘", "target_dir": "/网盘/Telegram",
                     "binding": config.binding(env()), "phase": "enabled", "scope_verification": "manual-native-readonly",
                     "backend_image": "pinned-test-image", "revision": "a" * 32}
        self.service.record = Mock(return_value=copy.deepcopy(self.item))
        self.service.locked = lambda: nullcontext()
        self.service.preflight = Mock(return_value=(SimpleNamespace(directory=PurePosixPath(self.item["instance_dir"]), config=env(), gateway_image="pinned-test-image"), shared()))
        self.service.manager = Mock()
        self.service.backup = Mock()
        self.service.revoke = Mock()
        self.service.save = Mock()
        self.ui.confirm.return_value = True
        self.ui.ask.return_value = SECRET

    def test_status_does_not_download_probe_or_ask(self):
        self.service.maintain("status")
        self.service.preflight.assert_not_called()
        self.ui.ask.assert_not_called()
        self.assertNotIn(SECRET, "\n".join(self.messages))

    def test_install_is_idempotent(self):
        self.service.configure(install_dir=None, install=True)
        self.service.preflight.assert_not_called()
        self.service.manager.apply_shared_state_locked.assert_not_called()

    def test_disable_revokes_before_shared_activation_and_preserves_other_routes(self):
        events = []
        self.service.revoke.side_effect = lambda: events.append("revoke")
        self.service.manager.apply_shared_state_locked.side_effect = lambda state, **kwargs: events.append("apply")
        self.service.maintain("disable")
        self.assertEqual(events, ["revoke", "apply"])
        state = self.service.manager.apply_shared_state_locked.call_args.args[0]
        self.assertEqual(state["domains"], shared()["domains"])
        self.assertFalse(state["external_webdav"]["openlist"]["enabled"])
        self.session.run.assert_not_called()

    def test_concurrent_revision_change_prevents_mutation(self):
        self.service.record.return_value["revision"] = "b" * 32
        with self.assertRaisesRegex(ValueError, "另一操作"):
            self.service.assert_record(self.item)
        self.service.revoke.assert_not_called()

    def test_directory_drift_cannot_enable_or_expand_scope(self):
        self.service.preflight.return_value[0].config = env("Expanded")
        with self.assertRaisesRegex(ValueError, "范围不自动扩大"):
            self.service.maintain("enable")
        self.service.manager.apply_shared_state_locked.assert_not_called()

    def test_failed_enable_revokes_and_records_repair_not_old_credentials(self):
        self.service.manager.apply_shared_state_locked.side_effect = RuntimeError("activation failed")
        self.service.auth_write = Mock()
        with patch.object(verification, "check_backend"), patch.object(config, "password_hash", return_value="test-hash"), self.assertRaises(RuntimeError):
            self.service.maintain("enable")
        self.assertEqual(self.service.revoke.call_count, 2)
        self.assertEqual(self.service.save.call_args.args[0]["phase"], "needs_repair")

    def configure_fixture(self):
        current = {"value": None}
        self.service.record.side_effect = lambda: copy.deepcopy(current["value"])
        self.service.save.side_effect = lambda item: current.update(value=copy.deepcopy(item))
        self.service.preflight.return_value = (self.service.preflight.return_value[0], empty_state())
        self.ui.ask.side_effect = [route()["domain"], "", "/网盘", "phone-reader", SECRET, "/网盘/Telegram"]
        self.service.auth_write = Mock()
        self.service.verify_mounted_hash = Mock()
        return current

    def test_confirmed_manual_native_account_install_does_not_touch_bot(self):
        current = self.configure_fixture()
        with patch.object(verification, "check_backend") as verify, patch.object(config, "password_hash", return_value="synthetic-hash"):
            self.service.configure(install_dir=None, install=True)
        self.assertEqual(current["value"]["phase"], "enabled")
        self.assertEqual(current["value"]["target_dir"], "/网盘/Telegram")
        self.assertEqual(current["value"]["scope_verification"], "manual-native-readonly")
        self.assertNotIn(SECRET, json.dumps(current["value"]))
        verify.assert_called_once()
        self.assertEqual(self.service.auth_write.call_args.args[0], b"phone-reader:synthetic-hash\n")
        self.session.run.assert_not_called()

    def test_declining_plan_performs_no_write(self):
        self.configure_fixture()
        self.ui.confirm.return_value = False
        self.service.configure(install_dir=None, install=True)
        self.service.save.assert_not_called()
        self.service.revoke.assert_not_called()
        self.service.manager.apply_shared_state_locked.assert_not_called()

    def test_interrupted_manual_account_setup_remains_closed_and_repairable(self):
        current = self.configure_fixture()
        self.ui.reveal.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.service.configure(install_dir=None, install=True)
        self.assertEqual(current["value"]["phase"], "needs_repair")
        self.service.auth_write.assert_not_called()
        self.service.manager.apply_shared_state_locked.assert_not_called()

    def test_manual_scope_mismatch_never_publishes(self):
        current = self.configure_fixture()
        self.ui.ask.side_effect = [route()["domain"], "", "/网盘", "phone-reader", SECRET, "/网盘/Other"]
        with self.assertRaisesRegex(ValueError, "未完成"):
            self.service.configure(install_dir=None, install=True)
        self.assertEqual(current["value"]["phase"], "needs_repair")
        self.service.auth_write.assert_not_called()

    def test_independent_uninstall_removes_only_owned_route(self):
        self.service.auth = Path(self.temp.name) / "owned.htpasswd"
        self.service.auth.write_bytes(b"synthetic-hash")
        self.service.directory.mkdir()
        self.service.record_path.write_text("synthetic-record")
        self.service.maintain("uninstall")
        updated = self.service.manager.apply_shared_state_locked.call_args.args[0]
        self.assertEqual(updated["domains"], shared()["domains"])
        self.assertEqual(updated["external_webdav"], {})
        self.assertFalse(self.service.auth.exists())
        self.assertFalse(self.service.record_path.exists())
        self.session.run.assert_not_called()


class EntryAndReleaseTests(unittest.TestCase):
    def test_idempotent_or_declined_install_never_replaces_offline_code(self):
        service = Mock()
        service.configure.return_value = False
        service.record.return_value = {"phase": "enabled"}
        with (patch("tg2cloud.addons.external_webdav.discovery.host"),
              patch("tg2cloud.addons.external_webdav.service.Service", return_value=service),
              patch("tg2cloud.cli.terminal.Terminal"), patch.object(cli.signal, "signal"),
              patch.object(cli, "source_identity", return_value={"source": "local-reviewed-source"}),
              patch("builtins.print")):
            self.assertEqual(cli.main(["install", "--edition", "openlist"]), 0)
        service.install_runtime.assert_not_called()

    def test_help_without_site_packages_or_checkout_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(ROOT / "scripts/run_source.py"), "webdav", "--help"],
                                    cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--edition", result.stdout)
        self.assertIn("print-config", result.stdout)

    def test_main_installers_and_bot_do_not_opt_in(self):
        for name in ("install.sh", "install-lan.sh", "src/tg2cloud/cli/vps.py", "src/tg2cloud/app.py"):
            self.assertNotIn("external_webdav", (ROOT / name).read_text(encoding="utf-8"))

    def test_stable_contract_and_host_bundle_are_complete(self):
        releases.supported(ROOT)
        files = releases.host_files(ROOT)
        self.assertIn("src/tg2cloud/addons/external_webdav/cli.py", files)
        self.assertIn("src/tg2cloud/deployment/proxy/manager.py", files)
        self.assertNotIn("src/tg2cloud/app.py", files)
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "尚不包含"):
            releases.supported(Path(directory))

    def test_offline_host_bundle_is_self_contained_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            service = Service(PRODUCTS["openlist"], Mock(), Mock(), Mock(), root=root)
            launcher = root / "bin/tg2cloud-webdav"
            service.install_runtime(ROOT, {"source": "local-reviewed-source"}, launcher=launcher)
            runtime = next((root / "runtime").iterdir())
            self.assertNotIn("app.py", {path.name for path in (runtime / "src/tg2cloud").iterdir()})
            code = ("import sys; sys.path.insert(0," + repr(str(runtime / "src")) + "); "
                    "import tg2cloud.addons.external_webdav.service, tg2cloud.addons.external_webdav.cli; "
                    "assert not any(n.split('.')[0] in {'telethon','cryptg','psutil','PySide6'} for n in sys.modules)")
            result = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=root,
                                    capture_output=True, text=True, timeout=20, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = launcher.read_bytes()
            service.install_runtime(ROOT, {"source": "local-reviewed-source"}, launcher=launcher)
            self.assertEqual(launcher.read_bytes(), before)
            nested = runtime / "src/tg2cloud/addons/external_webdav/nginx.py"
            nested.write_bytes(nested.read_bytes() + b"\n# synthetic tamper\n")
            with self.assertRaisesRegex(ValueError, "摘要不匹配"):
                service.install_runtime(ROOT, {"source": "local-reviewed-source"}, launcher=launcher)
            self.assertEqual(launcher.read_bytes(), before)

    def test_release_asset_host_allowlist(self):
        for url in ("http://github.com/a", "https://evil.test/a", "https://user:secret@github.com/a", "https://github.com:444/a"):
            with self.assertRaises(ValueError):
                releases.valid_url(url)
        releases.valid_url("https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v9.0.0/SHA256SUMS.txt")

    def test_hash_not_secret_is_passed_to_openssl_argv(self):
        fake = "$6$rounds=200000$" + "a" * 16 + "$" + "b" * 86
        with patch.object(config.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=fake.encode())) as runner:
            config.password_hash(SECRET)
        self.assertNotIn(SECRET, repr(runner.call_args.args))
        self.assertEqual(runner.call_args.kwargs["input"], SECRET.encode() + b"\n")
