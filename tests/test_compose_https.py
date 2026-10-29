"""Isolated host HTTPS ownership tests; no Docker, ACME or public network."""
from __future__ import annotations

import copy
import json
import os
import signal
import tempfile
import unittest
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from tg2cloud.compose import https, packaging, runtime
from tg2cloud.deployment import configuration
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy.manager import DomainProxyManager
from tg2cloud.deployment.proxy.rendering import render_compose
from tg2cloud.deployment.proxy.state import ProxyReport, empty_state, state_with_route
from tg2cloud.version import VERSION

SOURCE = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/luopojunzi/tg2cloud@sha256:" + "a" * 64


class ComposeHttpsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.proxy = self.directory / "proxy"
        self.messages = []
        self.log = SafeLog(self.messages.append)
        self.session = Mock()
        self.session.run.side_effect = self.command
        self.containers = {}
        self.locked = False
        self.commands = []
        @contextmanager
        def shared_lock(*args, **kwargs):
            self.assertFalse(self.locked)
            self.locked = True
            try:
                yield
            finally:
                self.locked = False
        self.session.hold_lock.side_effect = shared_lock
        self.addCleanup(patch.stopall)
        patch.object(https, "PROXY_ROOT", str(self.proxy)).start()
        # Windows runs these host-independent decision tests. POSIX owner/mode
        # enforcement is exercised independently below with exact stat values.
        def physical(path):
            if not path.is_absolute() or path.resolve() != path or path.is_symlink() or not path.is_dir():
                raise runtime.ComposeError("physical directory required")
        def owned(path, **_):
            if path.is_symlink() or path.resolve() != path or not path.is_file():
                raise runtime.ComposeError("regular owner file required")
            return path.read_bytes()
        self.physical = https.physical_directory
        self.owned = https.owned_file
        patch.object(https, "physical_directory", side_effect=physical).start()
        patch.object(https, "owned_file", side_effect=owned).start()
        patch.object(runtime, "private_config_file").start()
        patch.object(https.architecture, "check_docker").start()
        patch.object(https.architecture, "check_container").start()
        if os.name != "posix":
            strict_parse = https.parse_compose_registry
            def synthetic_registry(raw, **_):
                value = json.loads(raw)
                checked = copy.deepcopy(value)
                for entry in checked.get("instances", {}).values():
                    source = Path(entry["root"])
                    if not source.is_relative_to(self.directory):
                        raise ValueError("fixture outside temporary directory")
                    entry["root"] = "/temporary-fixture/" + source.relative_to(self.directory).as_posix()
                strict_parse(json.dumps(checked), physical=False)
                return value
            patch.object(https, "parse_compose_registry", side_effect=synthetic_registry).start()

    def command(self, command, **kwargs):
        self.commands.append(command)
        if command.startswith("docker ps "):
            return 0, "\n".join(item["id"] for item in self.containers.values())
        if command.startswith("docker container inspect --format "):
            return 0, "\n".join(json.dumps(item) for item in self.containers.values())
        if command.startswith("docker image inspect --format "):
            for item in self.containers.values():
                if command.endswith(item["image"]):
                    return 0, json.dumps(item["image_id"])
        if command == "id -u":
            return 0, "0\n"
        return 0, ""

    def candidate(self, edition="openlist"):
        product = PRODUCTS[edition]
        root = self.directory / edition
        root.mkdir()
        (root / "docker-compose.yml").write_text(packaging.render(SOURCE, edition, IMAGE), encoding="utf-8")
        (root / "compose-bundle.json").write_text(json.dumps({"format": 1, "mode": "compose", "edition": edition,
                                                            "version": VERSION, "image": IMAGE, "commit": "a" * 40}), encoding="utf-8")
        config = configuration.new_config(product, {"api_id": "123456", "api_hash": "a" * 32,
            "bot_token": "123456789:FAKE_COMPOSE_HTTPS_TEST_ONLY", "user_id": "123456789", "webdav_user": "tg2cloud",
            "webdav_password": "FAKE_PASSWORD_COMPOSE_TEST", "target": "", "budget": "20", "reserve": "8",
            "timezone": "Asia/Shanghai", "admin_password": "FAKE_ADMIN_COMPOSE_TEST"})
        config.update(TG2CLOUD_INSTALL_MODE="compose", TG2CLOUD_BIND_IP="127.0.0.1")
        (root / ".env").write_text("".join(key + "=" + value + "\n" for key, value in config.items()), encoding="utf-8")
        (root / runtime.MARKER).write_text(json.dumps({"format": 1, "edition": edition, "state": "ready"}), encoding="utf-8")
        for child in ("data", "downloads", "logs", "config", "openlist/data", "clouddrive/config", "clouddrive/mounts"):
            (root / child).mkdir(parents=True, exist_ok=True)
        gateway_image = next(line.split(": ", 1)[1] for line in
            (SOURCE / "packaging/compose" / ("docker-compose." + edition + ".yml")).read_text().splitlines()
            if line.startswith("    image: "))
        for index, (name, service, image) in enumerate(((product.storage_container, edition, gateway_image),
                                                      (product.bot_container, product.bot_service, IMAGE)), 1):
            gateway = service == edition
            mounts = {"/" + child: str(root / child) for child in ("data", "downloads", "logs", "config")}
            if gateway:
                mounts = ({"/opt/openlist/data": str(root / "openlist/data")} if product.is_openlist else
                          {"/Config": str(root / "clouddrive/config"), "/CloudNAS": str(root / "clouddrive/mounts")})
            port = str(product.management_port)
            self.containers[name] = {"id": str(index) * 64, "name": "/" + name, "running": gateway,
                "image": image, "image_id": "sha256:" + str(index) * 64, "network": "test_default",
                "labels": {"com.tg2cloud.install-mode": "compose", https.COMPOSE + "service": service,
                           https.COMPOSE + "project": "test", https.COMPOSE + "project.working_dir": str(root),
                           https.COMPOSE + "project.config_files": str(root / "docker-compose.yml")},
                "mounts": [{"Type": "bind", "Destination": target, "Source": source} for target, source in mounts.items()],
                "ports": {port + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]} if gateway else {},
                "bindings": {port + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]} if gateway else {}}
        instance = https.ComposeInstance(root, self.session, self.log, source=SOURCE)
        instance.validate()
        return instance, https.ComposeProxyManager(instance, Mock())

    def state(self, value, registry=None):
        (self.proxy / "state").mkdir(parents=True, exist_ok=True)
        (self.proxy / "state/domains.json").write_text(json.dumps(value), encoding="utf-8")
        (self.proxy / "docker-compose.yml").write_bytes(render_compose(
            tuple(sorted(item["domain"] for item in value["domains"].values())), external_auth=value["version"] == 2).encode())
        if registry is not None:
            (self.proxy / "state" / https.REGISTRY).write_text(json.dumps(registry), encoding="utf-8")

    def registry(self, instance, domain="panel.example.com"):
        return {"format": 1, "owner": https.OWNER, "instances": {instance.product.key: {"root": str(instance.root), "domain": domain}}}

    def test_both_editions_validate_without_any_business_mutation(self):
        for edition in PRODUCTS:
            with self.subTest(edition=edition):
                self.containers.clear()
                instance, manager = self.candidate(edition)
                self.assertEqual(manager.guard(), empty_state())
                self.assertEqual(instance.info["edition"], edition)
                self.assertFalse(self.proxy.exists())
        self.assertFalse(any(token in command for command in self.commands for token in (" up ", "restart", " stop ", "docker pull")))
        self.assertNotIn("Config.Env", https.INSPECT)

    def test_status_unconfigured_creates_no_shared_state_or_lock(self):
        _, manager = self.candidate()
        self.assertEqual(manager.inspect_status().state, "not_configured")
        self.assertFalse(self.proxy.exists())
        self.session.hold_lock.assert_not_called()

    def test_missing_marker_and_unready_marker_reject(self):
        instance, _ = self.candidate()
        marker = instance.root / runtime.MARKER
        marker.write_text('{"format":1,"edition":"openlist","state":"pending"}')
        with self.assertRaises(ValueError):
            instance.validate()
        marker.unlink()
        with self.assertRaises(ValueError):
            instance.validate()

    def test_foreign_compose_overrides_and_env_controls_reject(self):
        instance, _ = self.candidate()
        base = (instance.root / "docker-compose.yml").read_bytes()
        (instance.root / "docker-compose.yml").write_bytes(base + b"\n# foreign edit\n")
        with self.assertRaises(ValueError):
            instance.validate()
        (instance.root / "docker-compose.yml").write_bytes(base)
        override = instance.root / "compose.override.yaml"
        override.write_text("services: {}")
        with self.assertRaises(ValueError):
            instance.validate()
        override.unlink()
        with (instance.root / ".env").open("a") as handle:
            handle.write("COMPOSE_PROJECT_NAME=foreign\n")
        with self.assertRaises(ValueError):
            instance.validate()

    def test_foreign_container_metadata_rejected(self):
        instance, _ = self.candidate()
        gateway = self.containers[instance.product.storage_container]
        original = copy.deepcopy(gateway)
        for change in ({"image": "gateway:latest"}, {"network": "host"}, {"running": False},
                       {"mounts": []}, {"bindings": {}}, {"ports": {"5244/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5244"}]}}):
            gateway.clear()
            gateway.update(original | change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                instance.validate()
        gateway.clear()
        gateway.update(original)
        for label in ("com.tg2cloud.install-mode", https.COMPOSE + "project.config_files", https.COMPOSE + "project.working_dir", https.COMPOSE + "project"):
            gateway["labels"][label] = "foreign"
            with self.subTest(label=label), self.assertRaises(ValueError):
                instance.validate()
            gateway["labels"][label] = original["labels"][label]

    def test_actual_image_id_and_remote_context_errors_propagate(self):
        instance, _ = self.candidate()
        with patch.object(https.architecture, "check_docker", side_effect=ValueError("remote daemon")), self.assertRaises(ValueError):
            instance.validate()
        original = self.session.run.side_effect
        self.session.run.side_effect = lambda command, **kwargs: (0, json.dumps("sha256:" + "f" * 64)) if command.startswith("docker image inspect") else original(command, **kwargs)
        with self.assertRaises(ValueError):
            instance.validate()

    def test_unsafe_real_stat_owner_mode_and_hardlinks_reject(self):
        path = Mock()
        path.resolve.return_value = path
        path.is_symlink.return_value = False
        path.is_file.return_value = True
        path.is_dir.return_value = True
        path.is_absolute.return_value = True
        path.read_bytes.return_value = b"synthetic"
        for uid, mode, links in ((1000, 0o600, 1), (0, 0o644, 1), (0, 0o600, 2), (0, 0o400, 1)):
            path.stat.return_value = NS(st_uid=uid, st_mode=mode, st_nlink=links, st_size=9)
            with self.subTest(uid=uid, mode=mode, links=links), self.assertRaises(ValueError):
                self.owned(path, private=True)
        for uid, mode in ((1000, 0o700), (0, 0o777)):
            path.stat.return_value = NS(st_uid=uid, st_mode=mode)
            with self.assertRaises(ValueError):
                self.physical(path)

    def test_existing_unregistered_or_other_root_route_cannot_be_taken_over(self):
        instance, manager = self.candidate()
        value = state_with_route(empty_state(), instance.product, "panel.example.com")
        self.state(value)
        with self.assertRaisesRegex(ValueError, "未登记"):
            manager.guard()
        registry = self.registry(instance)
        registry["instances"][instance.product.key]["root"] = str(self.directory / "other")
        self.state(value, registry)
        with self.assertRaisesRegex(ValueError, "另一"):
            manager.guard()
        self.state(value, self.registry(instance))
        self.assertEqual(manager.guard(), value)

    def test_other_script_edition_preserved_and_domain_conflict_rejected(self):
        _, manager = self.candidate()
        value = state_with_route(empty_state(), PRODUCTS["clouddrive2"], "other.example.com")
        self.state(value)
        self.assertEqual(manager.guard(), value)
        before = (self.proxy / "state/domains.json").read_bytes()
        with self.assertRaises(ValueError):
            manager.configure("other.example.com", "")
        self.assertEqual((self.proxy / "state/domains.json").read_bytes(), before)

    def test_missing_state_external_mode_extra_proxy_env_and_journal_fail_closed(self):
        _, manager = self.candidate()
        self.proxy.mkdir()
        (self.proxy / "nginx").mkdir()
        with self.assertRaisesRegex(ValueError, "缺少"):
            manager.guard()
        (self.proxy / "nginx").rmdir()
        self.state(empty_state())
        extra = self.proxy / ".env"
        extra.write_text("COMPOSE_PROJECT_NAME=foreign")
        with self.assertRaises(ValueError):
            manager.guard()
        extra.unlink()
        journal = self.proxy / "state" / https.JOURNAL
        journal.write_text("{}")
        with self.assertRaisesRegex(ValueError, "未确认"):
            manager.guard()
        journal.unlink()
        state = {"version": 3, "domains": {}, "external_webdav": {}, "entry": {}}
        with patch.object(https, "normalize_state", return_value=state), self.assertRaisesRegex(ValueError, "外部入口"):
            manager.read_state()

    def test_unknown_shared_container_cannot_pass_the_manager_guard(self):
        _, manager = self.candidate()
        self.state(empty_state())
        self.containers[https.PROXY_NGINX_CONTAINER] = {"id": "3" * 64, "name": "/" + https.PROXY_NGINX_CONTAINER,
            "labels": {https.COMPOSE + "project": "foreign"}}
        with self.assertRaises(ValueError):
            manager.guard()

    def test_mutation_revalidates_inside_shared_lock(self):
        _, manager = self.candidate()
        seen = []
        original = manager.guard
        def guard():
            seen.append(self.locked)
            return original()
        with patch.object(manager, "guard", side_effect=guard), patch.object(DomainProxyManager, "_configure_locked", return_value="done"):
            self.assertEqual(manager.configure("panel.example.com", ""), "done")
        self.assertEqual(seen, [False, True])

    def test_pair_commit_keeps_other_edition_registry_and_fences_failure(self):
        instance, manager = self.candidate()
        other_root = self.directory / "other"
        registry = {"format": 1, "owner": https.OWNER, "instances": {"clouddrive2": {"root": str(other_root), "domain": "other.example.com"}}}
        previous = state_with_route(empty_state(), PRODUCTS["clouddrive2"], "other.example.com")
        self.state(previous, registry)
        manager.guard()
        target = state_with_route(previous, instance.product, "panel.example.com")
        original_config = (instance.root / ".env").read_bytes()
        def commit(_, value):
            (self.proxy / "state/domains.json").write_text(json.dumps(value), encoding="utf-8")
        def atomic(path, value):
            path.write_text(json.dumps(value), encoding="utf-8")
        with patch.object(DomainProxyManager, "_commit_state", autospec=True, side_effect=commit), patch.object(https, "atomic_private", side_effect=atomic):
            manager._commit_state(target)
        saved = json.loads((self.proxy / "state" / https.REGISTRY).read_text())
        self.assertEqual(saved["instances"]["clouddrive2"], registry["instances"]["clouddrive2"])
        self.assertEqual(saved["instances"]["openlist"]["root"], str(instance.root))
        self.assertFalse((self.proxy / "state" / https.JOURNAL).exists())
        with patch.object(DomainProxyManager, "_commit_state", side_effect=OSError("synthetic failure")), patch.object(https, "atomic_private", side_effect=atomic), self.assertRaisesRegex(ValueError, "不确定"):
            manager._commit_state(previous)
        self.assertTrue((self.proxy / "state" / https.JOURNAL).exists())
        with self.assertRaisesRegex(ValueError, "未确认"):
            manager.guard()
        self.assertEqual((instance.root / ".env").read_bytes(), original_config)

    def test_remove_only_releases_own_registry_and_keeps_certificates(self):
        instance, manager = self.candidate()
        current = state_with_route(empty_state(), instance.product, "panel.example.com")
        self.state(current, self.registry(instance))
        manager.guard()
        certificate = self.proxy / "certificate-retained"
        certificate.write_text("synthetic")
        def commit(_, value):
            (self.proxy / "state/domains.json").write_text(json.dumps(value), encoding="utf-8")
        with patch.object(DomainProxyManager, "_commit_state", autospec=True, side_effect=commit), patch.object(https, "atomic_private", side_effect=lambda path, value: path.write_text(json.dumps(value))):
            manager._commit_state(empty_state())
        self.assertEqual(json.loads((self.proxy / "state" / https.REGISTRY).read_text())["instances"], {})
        self.assertTrue(certificate.exists())

    def test_export_has_real_cert_paths_dav_denials_and_explicit_network_limit(self):
        instance, _ = self.candidate()
        ui = Mock()
        ui.ask.side_effect = ["panel.example.com", "/srv/certs/fullchain.pem", "/srv/certs/privkey.pem"]
        ui.confirm.return_value = True
        before = (instance.root / ".env").read_bytes()
        target = https.export_existing(instance, ui)
        text = target.read_text()
        self.assertIn("ssl_certificate /srv/certs/fullchain.pem;", text)
        self.assertIn("ssl_certificate_key /srv/certs/privkey.pem;", text)
        self.assertIn("proxy_pass http://127.0.0.1:5244;", text)
        self.assertIn("location ^~ /dav/ { return 403; }", text)
        self.assertIn("bridge", "\n".join(self.messages))
        self.assertEqual(before, (instance.root / ".env").read_bytes())
        self.assertFalse(self.proxy.exists())
        for path in ("relative.pem", "/tmp/a;include.conf", "/tmp/../root/key", "/tmp/space key"):
            with self.assertRaises(ValueError):
                https.certificate_path(path)

    def test_main_export_reaches_candidate_only_flow_with_external_proxy_state(self):
        instance, manager = self.candidate()
        self.proxy.mkdir()
        (self.proxy / "state").mkdir()
        state_file = self.proxy / "state/domains.json"
        state_file.write_bytes(b'{"version":3,"domains":{},"external_webdav":{},"entry":{}}')
        shared_before = state_file.read_bytes()
        with patch.object(https, "normalize_state", return_value={"version": 3}), self.assertRaisesRegex(ValueError, "外部入口"):
            manager.guard()
        ui = Mock()
        ui.ask.side_effect = ["panel.example.com", "/srv/certs/fullchain.pem", "/srv/certs/privkey.pem"]
        ui.confirm.return_value = True
        with patch.object(https, "os", NS(name="posix", geteuid=lambda: 0)), \
                patch.object(https.architecture, "check_environment"), \
                patch.object(runtime, "operation_lock", return_value=nullcontext()):
            result = https.main(["export-existing", "--root", str(instance.root)], session=self.session, ui=ui, log=self.log)
        self.assertEqual(result, 0)
        self.assertEqual(state_file.read_bytes(), shared_before)
        self.assertEqual(len(list(instance.root.glob("nginx-openlist-*.conf"))), 1)
        self.session.hold_lock.assert_not_called()
        self.assertFalse(any(token in command for command in self.commands for token in ("restart", " up ", " stop ", "nginx -s reload")))

    def test_export_still_refuses_unready_or_foreign_business_upstream(self):
        instance, manager = self.candidate()
        self.containers[instance.product.storage_container]["running"] = False
        ui = Mock()
        with self.assertRaisesRegex(ValueError, "网关必须运行"):
            https.run_action("export-existing", instance, manager, ui)
        ui.ask.assert_not_called()
        self.assertFalse(list(instance.root.glob("nginx-*.conf")))

    def test_stopped_or_removed_business_can_remove_owned_https_under_lock(self):
        instance, manager = self.candidate()
        current = state_with_route(empty_state(), instance.product, "panel.example.com")
        self.state(current, self.registry(instance))
        gateway = self.containers[instance.product.storage_container]
        gateway.update(running=False, ports={})
        with self.assertRaisesRegex(ValueError, "网关必须运行"):
            manager.guard()
        self.assertEqual(manager.guard(require_running=False, allow_missing=True), current)
        seen = []
        def removed(_):
            seen.append(self.locked)
            return "removed"
        with patch.object(DomainProxyManager, "_remove_locked", autospec=True, side_effect=removed):
            self.assertEqual(manager.remove(), "removed")
            self.containers.clear()  # docker compose down removes both containers.
            self.assertEqual(manager.remove(), "removed")
        self.assertEqual(seen, [True, True])
        self.assertFalse(any(token in command for command in self.commands for token in ("restart", " stop ", " up ")))

    def test_missing_unregistered_or_foreign_containers_cannot_remove_routes(self):
        instance, manager = self.candidate()
        original = copy.deepcopy(self.containers)
        self.containers.clear()
        with self.assertRaisesRegex(ValueError, "没有.*HTTPS 登记"):
            manager.remove()
        self.state(state_with_route(empty_state(), instance.product, "panel.example.com"), self.registry(instance))
        self.containers.update(original)
        self.containers[instance.product.bot_container]["labels"][https.COMPOSE + "project.working_dir"] = "/foreign"
        with patch.object(DomainProxyManager, "_remove_locked") as remove, self.assertRaises(ValueError):
            manager.remove()
        remove.assert_not_called()

    def test_configure_can_change_local_plan_and_cancel_preserves_plan_and_env(self):
        from tg2cloud.compose import access
        from tg2cloud.compose.access import ACCESS_FILE, OWNER
        instance, _ = self.candidate()
        old = {"format": 1, "owner": OWNER, "edition": instance.product.key,
               "mode": "local", "domain": "", "email": ""}
        path = instance.root / ACCESS_FILE
        path.write_bytes(json.dumps(old).encode())
        path.chmod(0o600)
        # The fixture is owned by a non-root CI user. Keep the real permission
        # check and restrict only the ownership stand-in to this temporary file.
        original_read = access.read_access
        def fixture_private(candidate):
            self.assertEqual(candidate, path)
            if os.name == "posix" and candidate.stat().st_mode & 0o077:
                raise ValueError("fixture permissions are too broad")
        reader = patch.object(access, "read_access", side_effect=lambda root, edition: original_read(root, edition, private_check=fixture_private))
        reader.start()
        self.addCleanup(reader.stop)
        before_plan = path.read_bytes()
        before_env = (instance.root / ".env").read_bytes()
        ui = Mock()
        ui.ask.side_effect = ["2", "panel.example.com", ""]
        ui.confirm.return_value = False
        manager = Mock()
        manager.configure.return_value = NS(message="configured")
        https.configure(instance, manager, ui)
        manager.configure.assert_not_called()
        self.assertEqual(path.read_bytes(), before_plan)
        self.assertEqual((instance.root / ".env").read_bytes(), before_env)
        ui.ask.side_effect = ["2", "panel.example.com", ""]
        ui.confirm.return_value = True
        with patch.object(https, "atomic_private", side_effect=lambda target, value: target.write_bytes(json.dumps(value).encode())):
            https.configure(instance, manager, ui)
        manager.configure.assert_called_once_with("panel.example.com", "")
        self.assertEqual(json.loads(path.read_bytes())["mode"], "managed")
        self.assertEqual((instance.root / ".env").read_bytes(), before_env)

    def test_invalid_registry_keys_domain_and_journal_reject_before_mutation(self):
        instance, manager = self.candidate()
        current = state_with_route(empty_state(), instance.product, "panel.example.com")
        for alter in (lambda value: value.update(format=True), lambda value: value.update(unknown="extra"),
                      lambda value: value["instances"][instance.product.key].update(domain="UPPER.example.com")):
            registry = self.registry(instance)
            alter(registry)
            self.state(current, registry)
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                manager.remove()
        self.session.hold_lock.assert_not_called()

    def test_real_base_configure_runs_shared_pipeline_after_owner_guard(self):
        instance, manager = self.candidate()
        expected = state_with_route(empty_state(), instance.product, "panel.example.com")
        report = ProxyReport("panel.example.com", "healthy", "verified test report", ())
        with patch.object(manager, "probe"), patch.object(manager, "_validate_environment"), \
                patch.object(manager, "_ensure_state_file"), patch.object(manager, "_activate") as activate, \
                patch.object(manager, "_obtain_certificate") as obtain, \
                patch.object(manager, "_compose", return_value=(0, "")), \
                patch.object(manager, "status", return_value=report), patch.object(manager, "_commit_state") as commit:
            self.assertEqual(manager.configure("panel.example.com", ""), report)
        self.assertEqual(activate.call_count, 2)
        obtain.assert_called_once_with("panel.example.com", "")
        commit.assert_called_once_with(expected)
        self.assertFalse(self.locked)

    def test_remove_defers_sigint_until_shared_commit_is_complete(self):
        instance, manager = self.candidate()
        self.state(state_with_route(empty_state(), instance.product, "panel.example.com"), self.registry(instance))
        def interrupt(_):
            signal.raise_signal(signal.SIGINT)
        with patch.object(manager, "_install_config", side_effect=interrupt), \
                patch.object(manager, "_compose", return_value=(0, "")), \
                patch.object(manager, "_commit_state") as commit, self.assertRaises(KeyboardInterrupt):
            manager.remove()
        commit.assert_called_once_with(empty_state())
        self.assertFalse(self.locked)

    def test_proxy_backup_uses_existing_manager_and_rechecks_inside_shared_lock(self):
        instance, manager = self.candidate()
        self.state(state_with_route(empty_state(), instance.product, "panel.example.com"), self.registry(instance))
        self.containers.clear()
        checks = []
        original = manager.validate_shared
        def validate(*args):
            checks.append(self.locked)
            return original(*args)
        def maintenance(_, action):
            self.assertEqual(action, "backup")
            with self.session.hold_lock("synthetic-shared-lock"):
                manager.read_state()
            return "backup-ready"
        with patch.object(manager, "validate_shared", side_effect=validate), patch.object(DomainProxyManager, "maintenance", autospec=True, side_effect=maintenance):
            self.assertEqual(manager.proxy_backup(), "backup-ready")
        self.assertEqual(checks, [False, True])

    def test_help_does_not_require_linux_root_or_create_files(self):
        with self.assertRaises(SystemExit) as result:
            https.main(["--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertFalse(self.proxy.exists())

    def test_main_rejects_non_root_without_constructing_terminal(self):
        with patch.object(https.os, "geteuid", return_value=1000, create=True):
            self.assertEqual(https.main(["status", "--root", str(self.directory)], log=self.log), 1)
        self.assertTrue(any("root" in message for message in self.messages))


if __name__ == "__main__":
    unittest.main()
