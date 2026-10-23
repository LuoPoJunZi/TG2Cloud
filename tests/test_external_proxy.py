"""Offline contract/fault-injection tests. Never touch a Docker daemon or ACME."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.cli.proxy import main, parser, select_entry
from tg2cloud.deployment.profiles import CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT
from tg2cloud.deployment.proxy.docker_nginx import DockerNginx
from tg2cloud.deployment.proxy.external_config import (
    OWNER,
    checksum,
    compose_network,
    configuration_files,
    conflicting_names,
    directives,
    global_digest,
    http_includes,
    render_route,
    validate_entry,
)
from tg2cloud.deployment.proxy.external_entry import (
    CRON_CONTENT,
    ExternalEntry,
    retained_network,
)
from tg2cloud.deployment.proxy.external_transaction import SiteTransaction, atomic, read
from tg2cloud.deployment.proxy.state import (
    DomainRoute,
    ProxyEnvironment,
    certificate_domains,
    normalize_state,
    state_with_route,
    state_without_route,
)


def entry():
    return {"mode": "external_docker", "owner": OWNER,
            "identity": {"name": "edge", "container_id": "a" * 64, "image": "nginx:stable-alpine", "image_id": "sha256:" + "f" * 64,
                         "project": "edge", "service": "nginx", "working_dir": "/srv/edge",
                         "config_files": ["/srv/edge/compose.yml"], "config_digest": "b" * 64},
            "mount": {"source": "/srv/edge/conf", "destination": "/etc/nginx/conf.d", "type": "bind", "name": "",
                      "conf_dir": "/etc/nginx/conf.d", "host_dir": "/srv/edge/conf", "worker_gid": 101},
            "network": {"mode": "host", "name": "", "id": "", "listen_address": "127.0.0.1"},
            "files": {}, "certificates": {}, "revision": "0" * 32}


def state():
    return {"version": 3, "domains": {}, "external_webdav": {}, "entry": entry()}


def content(text):
    return ("# " + OWNER + "\n" + text + "\n").encode()


class ConfigurationTests(unittest.TestCase):
    def test_schema_round_trip_and_old_states(self):
        for value in ({"version": 1, "domains": {}}, {"version": 2, "domains": {}, "external_webdav": {}}, state()):
            self.assertEqual(normalize_state(json.dumps(value)), value)

    def test_unknown_schema_and_fields_rejected(self):
        for value in (dict(state(), version=99), dict(state(), unknown=True), dict(state(), entry=dict(entry(), unsafe=True))):
            with self.assertRaises(ValueError):
                normalize_state(json.dumps(value))

    def test_two_editions_share_entry_without_downgrade(self):
        value = state_with_route(state(), CLOUDDRIVE2_PRODUCT, "cd.example.com")
        value = state_with_route(value, OPENLIST_PRODUCT, "ol.example.com")
        self.assertEqual(certificate_domains(value), ("cd.example.com", "ol.example.com"))
        remaining = state_without_route(value, "clouddrive2")
        self.assertEqual(remaining["entry"], value["entry"])
        self.assertEqual(set(remaining["domains"]), {"openlist"})

    def test_unsafe_identity_and_paths_rejected(self):
        for field, replacement in (("name", "nginx;id"), ("container_id", "unknown"), ("image", "x$(id)")):
            value = entry()
            value["identity"][field] = replacement
            with self.assertRaises(ValueError):
                validate_entry(value)
        value = entry()
        value["mount"]["host_dir"] = "/srv/edge/../bad"
        with self.assertRaises(ValueError):
            validate_entry(value)

    def test_compact_nginx_include_context(self):
        files = {"/etc/nginx/nginx.conf": "events{} http{include /etc/nginx/conf.d/*.conf;}",
                 "/etc/nginx/conf.d/default.conf": "server{listen 80;server_name original.example.com;}"}
        self.assertEqual(http_includes(files), ("/etc/nginx/conf.d",))
        self.assertIn((("server",), ("listen", "80")), list(directives(files["/etc/nginx/conf.d/default.conf"])))

    def test_nested_include_and_wrong_context(self):
        files = {"/etc/nginx/nginx.conf": "http {include /etc/nginx/http.inc;}",
                 "/etc/nginx/http.inc": "include /etc/nginx/sites/*.conf; server {include /etc/nginx/wrong/*.conf;}"}
        self.assertEqual(http_includes(files), ("/etc/nginx/sites",))
        with self.assertRaises(ValueError):
            http_includes({"/etc/nginx/nginx.conf": "http {include conf.d/*.conf;}"})

    def test_nginx_dump_not_arbitrary_text(self):
        dump = "nginx: configuration valid\n# configuration file /etc/nginx/nginx.conf:\nhttp{}\n"
        self.assertEqual(list(configuration_files(dump)), ["/etc/nginx/nginx.conf"])
        with self.assertRaises(ValueError):
            configuration_files("not an nginx dump")

    def test_exact_wildcard_regex_domain_conflicts(self):
        for name in ("new.example.com", "*.example.com", ".example.com", "~^new"):
            files = {"/etc/nginx/conf.d/site.conf": "server {server_name " + name + ";}"}
            self.assertTrue(conflicting_names(files, "new.example.com", set()))
            self.assertFalse(conflicting_names(files, "new.example.com", set(files)))

    def test_same_basename_elsewhere_not_trusted(self):
        files = {"/a/tg2cloud-openlist.conf": "own", "/b/tg2cloud-openlist.conf": "foreign"}
        digest = global_digest(files, {"/a/tg2cloud-openlist.conf"})
        files["/b/tg2cloud-openlist.conf"] = "changed"
        self.assertNotEqual(digest, global_digest(files, {"/a/tg2cloud-openlist.conf"}))

    def test_both_gateway_networks_persist_bot_unchanged(self):
        for edition in ("clouddrive2", "openlist"):
            source = Path("packaging/compose/docker-compose." + edition + ".yml").read_text()
            result = compose_network(source, edition, "edge_net")
            self.assertEqual(result.count("      - tg2cloud-external-entry\n"), 1)
            self.assertIn("    external: true\n    name: edge_net", result)
            self.assertIn("127.0.0.1:", result)
            with self.assertRaises(ValueError):
                compose_network(result, edition, "different")

    def test_host_renderer_preserves_security_and_websocket(self):
        value = entry()
        value["certificates"]["cd.example.com"] = ExternalEntry.new_certificate("cd.example.com", "external", "/cert/fullchain.pem", "/cert/privkey.pem")
        rendered = render_route(DomainRoute("clouddrive2", "cd.example.com", 19798), value)
        self.assertIn("proxy_pass http://127.0.0.1:19798", rendered)
        self.assertIn("proxy_set_header Upgrade $http_upgrade", rendered)
        self.assertNotIn("$connection_upgrade", rendered)
        self.assertIn("location = /dav", rendered)
        self.assertIn("return 403", rendered)
        self.assertIn("ssl_certificate /cert/fullchain.pem", rendered)
        self.assertNotIn("proxy_add_x_forwarded_for", rendered)

    def test_bridge_dynamic_dns_and_dav_policy(self):
        value = entry()
        value["network"].update(mode="bridge", name="edge_net", id="c" * 64)
        value["certificates"]["dav.example.com"] = ExternalEntry.new_certificate("dav.example.com", "tg2cloud", "/cert/fullchain.pem", "/cert/key.pem")
        route = {"edition": "openlist", "domain": "dav.example.com", "backend_port": 5244,
                 "auth_file": "external-auth/openlist.htpasswd", "enabled": True}
        rendered = render_route(route, value)
        self.assertIn("resolver 127.0.0.11 valid=10s", rendered)
        self.assertIn("set $tg2cloud_openlist_backend tg2cloud-openlist:5244", rendered)
        self.assertNotIn("127.0.0.1:5244", rendered)
        self.assertIn("$tg2cloud_openlist_backend$request_uri", rendered)
        self.assertIn("auth_basic_user_file /etc/nginx/conf.d/tg2cloud-assets/auth/openlist.htpasswd", rendered)
        self.assertIn("GET|HEAD|OPTIONS|PROPFIND", rendered)
        self.assertIn("proxy_set_header Range $http_range", rendered)
        self.assertIn("location / { return 404; }", rendered)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / "sites"
        self.directory.mkdir()
        self.journal = self.root / "private/transaction.json"
        self.name = "tg2cloud-clouddrive2.conf"
        self.path = self.directory / self.name

    def test_success_and_rollback_leave_other_sites(self):
        foreign = self.directory / "default.conf"
        atomic(foreign, b"other site")
        old, new = content("old"), content("new")
        atomic(self.path, old, mode=0o644)
        transaction = SiteTransaction(self.directory, self.journal, {self.name: checksum(old)}, {self.name: new})
        transaction.publish()
        self.assertEqual(read(self.path), new)
        transaction.rollback()
        transaction.finish()
        self.assertEqual(read(self.path), old)
        self.assertEqual(read(foreign), b"other site")

    def test_unknown_same_name_never_overwritten(self):
        atomic(self.path, b"foreign")
        with self.assertRaises(ValueError):
            SiteTransaction(self.directory, self.journal, {}, {self.name: content("candidate")})
        self.assertEqual(read(self.path), b"foreign")

    def test_foreign_concurrent_change_blocks_rollback(self):
        transaction = SiteTransaction(self.directory, self.journal, {}, {self.name: content("new")})
        transaction.publish()
        atomic(self.path, b"concurrent operator edit")
        with self.assertRaisesRegex(ValueError, "并发"):
            transaction.rollback()
        self.assertTrue(self.journal.exists())
        self.assertEqual(read(self.path), b"concurrent operator edit")

    def test_interrupted_publication_can_be_recovered(self):
        transaction = SiteTransaction(self.directory, self.journal, {}, {self.name: content("new")})
        transaction.publish()
        restored = SiteTransaction.recover(self.directory, self.journal)
        restored.rollback()
        restored.finish()
        self.assertFalse(self.path.exists())

    def test_second_transaction_blocked_until_recovery(self):
        SiteTransaction(self.directory, self.journal, {}, {self.name: content("new")})
        with self.assertRaisesRegex(ValueError, "未完成"):
            SiteTransaction(self.directory, self.journal, {}, {})

    def test_drift_before_publication_is_preserved(self):
        transaction = SiteTransaction(self.directory, self.journal, {}, {self.name: content("new")})
        atomic(self.path, b"external")
        with self.assertRaises(ValueError):
            transaction.publish()
        self.assertEqual(read(self.path), b"external")

    def test_forged_recovery_path_rejected(self):
        SiteTransaction(self.directory, self.journal, {}, {self.name: content("new")})
        value = json.loads(read(self.journal))
        value["items"]["../../default.conf"] = value["items"].pop(self.name)
        atomic(self.journal, json.dumps(value).encode())
        with self.assertRaises(ValueError):
            SiteTransaction.recover(self.directory, self.journal)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.current = state()
        self.messages = []
        self.manager = SimpleNamespace(product=CLOUDDRIVE2_PRODUCT, session=SimpleNamespace(hold_lock=lambda *_: nullcontext()),
            log=self.messages.append, read_state=lambda: copy.deepcopy(self.current), _commit_state=self.commit)
        self.adapter = ExternalEntry(self.manager, entry())
        self.adapter.root = self.root / "private"
        self.adapter.directory = self.root / "sites"
        self.adapter.directory.mkdir()
        self.adapter.assets = self.adapter.directory / "tg2cloud-assets"
        self.adapter.journal = self.adapter.root / "state/transaction.json"
        for name in ("preflight", "setup_assets", "backup", "verify", "install_schedule", "verify_webroot"):
            setattr(self.adapter, name, Mock())
        self.adapter.context = Mock(return_value={"id": "a" * 64})
        self.adapter.canaries = Mock(return_value={})
        self.adapter.docker = Mock()
        self.adapter.certificate_record = Mock(side_effect=lambda domain: ExternalEntry.new_certificate(domain, "tg2cloud", "/cert/chain.pem", "/cert/key.pem"))
        self.adapter.certificate_valid = Mock(return_value=True)
        self.adapter.obtain = Mock()

    def commit(self, value):
        self.current = copy.deepcopy(value)

    def target(self):
        return state_with_route(self.current, CLOUDDRIVE2_PRODUCT, "cd.example.com")

    def test_install_and_repeat_no_external_start_stop_or_recreate(self):
        self.adapter.transaction(self.target(), domain="cd.example.com")
        self.assertEqual(self.current["version"], 3)
        first = read(self.adapter.directory / "tg2cloud-clouddrive2.conf")
        self.adapter.transaction(self.target(), domain="cd.example.com")
        self.assertEqual(first, read(self.adapter.directory / "tg2cloud-clouddrive2.conf"))
        self.assertFalse(self.adapter.journal.exists())
        self.assertFalse(self.adapter.docker.command.called)
        self.assertTrue(self.adapter.docker.reload.called)

    def test_issuance_failure_rolls_back_own_files(self):
        self.adapter.certificate_valid.return_value = False
        self.adapter.obtain.side_effect = ValueError("ACME failed")
        before = copy.deepcopy(self.current)
        with self.assertRaisesRegex(ValueError, "ACME"):
            self.adapter.transaction(self.target(), domain="cd.example.com")
        self.assertEqual(self.current, before)
        self.assertFalse((self.adapter.directory / "tg2cloud-clouddrive2.conf").exists())

    def test_ordinary_interrupt_rollback(self):
        self.adapter.verify.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.adapter.transaction(self.target(), domain="cd.example.com")
        self.assertFalse(self.adapter.journal.exists())
        self.assertFalse(self.current["domains"])

    def test_reload_failure_preserves_recovery_journal(self):
        self.adapter.docker.reload.side_effect = ValueError("reload failed")
        with self.assertRaises(ValueError):
            self.adapter.transaction(self.target(), domain="cd.example.com")
        self.assertTrue(self.adapter.journal.exists())
        self.assertTrue(any("回滚未完成" in message for message in self.messages))

    def test_last_route_removal_does_not_stop_external_container(self):
        self.adapter.transaction(self.target(), domain="cd.example.com")
        self.adapter.remove_locked()
        self.assertFalse(self.current["domains"])
        self.assertEqual(self.current["version"], 3)
        self.assertFalse((self.adapter.directory / "tg2cloud-clouddrive2.conf").exists())
        self.assertFalse(self.adapter.docker.command.called)

    def test_certificate_reuse_does_not_call_certbot(self):
        self.adapter.entry["certificates"]["cd.example.com"] = ExternalEntry.new_certificate("cd.example.com", "external", "/cert/chain.pem", "/cert/key.pem")
        self.adapter.certbot = Mock()
        ExternalEntry.obtain(self.adapter, "cd.example.com", "")
        self.adapter.certbot.assert_not_called()

    def test_dav_bootstrap_never_replaces_same_edition_management(self):
        value = self.target()
        value["external_webdav"]["clouddrive2"] = {"kind": "external_webdav", "owner": "tg2cloud.external_webdav",
            "edition": "clouddrive2", "instance_dir": "/opt/tg2cloud-clouddrive2", "domain": "dav.example.com", "enabled": True,
            "backend_port": 19798, "auth_file": "external-auth/clouddrive2.htpasswd"}
        for domain in ("cd.example.com", "dav.example.com"):
            self.adapter.entry["certificates"][domain] = self.adapter.certificate_record(domain)
        final = self.adapter.files(value)
        bootstrap = self.adapter.files(value, bootstrap="dav.example.com")
        self.assertEqual(set(final), set(bootstrap))
        self.assertEqual(final["tg2cloud-clouddrive2.conf"], bootstrap["tg2cloud-clouddrive2.conf"])
        self.assertNotIn(b"listen 443", bootstrap["tg2cloud-webdav-clouddrive2.conf"])

    def test_removing_management_preserves_dav_route_files_and_certificate_domain(self):
        # This test isolates route/renewal ownership; actual hash replacement
        # has its own file and opt-in Docker regressions.
        self.adapter.copy_auth = Mock()
        value = self.target()
        value["external_webdav"]["clouddrive2"] = {"kind": "external_webdav", "owner": "tg2cloud.external_webdav",
            "edition": "clouddrive2", "instance_dir": "/opt/tg2cloud-clouddrive2", "domain": "dav.example.com", "enabled": True,
            "backend_port": 19798, "auth_file": "external-auth/clouddrive2.htpasswd"}
        for domain in ("cd.example.com", "dav.example.com"):
            self.adapter.entry["certificates"][domain] = self.adapter.certificate_record(domain)
        self.adapter.transaction(value)
        previous = read(self.adapter.directory / "tg2cloud-webdav-clouddrive2.conf")
        self.adapter.remove_locked()
        self.assertFalse(self.current["domains"])
        self.assertEqual(read(self.adapter.directory / "tg2cloud-webdav-clouddrive2.conf"), previous)
        self.assertIn("dav.example.com", certificate_domains(self.current))
        self.assertNotIn("cd.example.com", certificate_domains(self.current))
        self.assertFalse(self.adapter.docker.command.called)

    def test_private_backup_roundtrip_and_isolated_drill(self):
        self.adapter.backup = ExternalEntry.backup.__get__(self.adapter)
        archive = self.adapter.backup(self.current)
        self.assertTrue(archive.exists())
        self.assertIn("不含私钥", self.adapter.check_backup(archive=str(archive), drill=True))

    def test_actual_auth_copy_replaced_before_identity_failure(self):
        self.adapter.assets.mkdir()
        marker = {"owner": OWNER, "mount_source": self.adapter.entry["mount"]["source"],
                  "container_dir": self.adapter.entry["mount"]["conf_dir"]}
        atomic(self.adapter.assets / "owner.json", json.dumps(marker).encode())
        target = self.adapter.assets / "auth/clouddrive2.htpasswd"
        atomic(target, b"old:hash\n")
        self.adapter.context.side_effect = ValueError("external drift")
        with patch("tg2cloud.deployment.proxy.external_transaction.os.chown", create=True), self.assertRaisesRegex(ValueError, "drift"):
            self.adapter.revoke_auth("clouddrive2")
        self.assertEqual(read(target), b"disabled:!\n")

    def test_renewed_but_reload_failed_stays_pending(self):
        domain = "cd.example.com"
        self.current = self.target()
        self.adapter.entry["certificates"][domain] = ExternalEntry.new_certificate(domain, "tg2cloud", "/cert/chain.pem", "/cert/key.pem")
        self.adapter.entry["certificates"][domain]["loaded"] = "d" * 64
        self.adapter.disk_fingerprint = Mock(side_effect=["d" * 64, "e" * 64])
        self.adapter.certbot = Mock()
        self.adapter.docker.reload.side_effect = ValueError("reload failed")
        with self.assertRaisesRegex(ValueError, "reload"):
            self.adapter.maintain()
        record = self.current["entry"]["certificates"][domain]
        self.assertTrue(record["pending_load"])
        self.assertGreater(record["last_change"], 0)

    def test_dry_run_does_not_claim_certificate_changed(self):
        domain = "cd.example.com"
        self.current = self.target()
        self.adapter.entry["certificates"][domain] = ExternalEntry.new_certificate(domain, "tg2cloud", "/cert/chain.pem", "/cert/key.pem")
        self.adapter.entry["certificates"][domain]["loaded"] = "d" * 64
        self.adapter.disk_fingerprint = Mock(return_value="d" * 64)
        self.adapter.certbot = Mock()
        self.adapter.maintain(dry_run=True)
        self.assertIn("--dry-run", self.adapter.certbot.call_args.args[0])
        self.assertEqual(self.current["entry"]["certificates"][domain]["last_change"], 0)
        self.adapter.docker.reload.assert_not_called()

    def test_pending_bridge_plan_strict_ownership(self):
        product = CLOUDDRIVE2_PRODUCT
        value = entry()
        value["network"].update(mode="bridge", name="edge_net", id="c" * 64)
        record = {"schema": 1, "edition": product.key, "instance_dir": str(Path(product.install_dir)), "entry": value}
        pending = self.root / "state/external-pending-clouddrive2.json"
        atomic(pending, json.dumps(record).encode())
        # Exercise plan identity with an ordinary Runner-owned fixture; root-only
        # production file checks are covered independently below, never disabled.
        with patch("tg2cloud.deployment.configuration.regular_private", side_effect=lambda path: path.read_bytes()) as read:
            self.assertEqual(retained_network(product, Path(product.install_dir), {}, self.root), "edge_net")
            with self.assertRaisesRegex(ValueError, "归属"):
                retained_network(product, Path("/opt/not-the-instance"), {}, self.root)
            self.assertEqual([call.args[0] for call in read.call_args_list], [pending, pending])

    def test_pending_plan_reader_rejects_nonroot_and_readable_files_before_read(self):
        from tg2cloud.deployment.configuration import regular_private
        for uid, mode in ((1000, 0o100600), (0, 0o100640), (0, 0o100604)):
            with self.subTest(uid=uid, mode=mode):
                path = Mock(spec=Path)
                path.name = "external-pending-clouddrive2.json"
                path.is_symlink.return_value = False
                path.resolve.return_value = path
                path.is_file.return_value = True
                path.stat.return_value = SimpleNamespace(st_size=100, st_uid=uid, st_mode=mode)
                # Replace only this module's OS facade, not global os.name or
                # pathlib's platform selection, so the same contract runs on NT.
                with patch("tg2cloud.deployment.configuration.os", SimpleNamespace(name="posix")), self.assertRaisesRegex(ValueError, "root"):
                    regular_private(path)
                path.read_bytes.assert_not_called()


class DetectionAndAuthorizationTests(unittest.TestCase):
    def docker(self):
        docker = DockerNginx(Mock())
        docker.check_supported = Mock()
        docker.command = Mock(return_value="")
        return docker

    def test_expose_is_not_a_published_port(self):
        docker = self.docker()
        with self.assertRaisesRegex(ValueError, "EXPOSE"):
            docker.check_ports({"id": "a" * 64, "network_mode": "bridge", "ports": {"80/tcp": None, "443/tcp": None}})

    def test_bridge_actual_published_ipv4_ipv6(self):
        docker = self.docker()
        docker.command.side_effect = ["", "a" * 64, "a" * 64]
        item = {"id": "a" * 64, "network_mode": "edge_default", "ports": {
            str(port) + "/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}, {"HostIp": "::", "HostPort": str(port)}]
            for port in (80, 443)}}
        self.assertEqual(docker.check_ports(item), "127.0.0.1")

    def test_foreign_ss_listener_is_rejected(self):
        docker = self.docker()
        docker.command.return_value = 'LISTEN 0 128 0.0.0.0:80 0.0.0.0:* users:(("apache2",pid=123,fd=4))'
        item = {"id": "a" * 64, "network_mode": "edge_default", "ports": {
            str(port) + "/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}] for port in (80, 443)}}
        with self.assertRaisesRegex(ValueError, "归属"):
            docker.check_ports(item)

    def test_unrelated_container_port_80_published_as_8080_is_not_owner(self):
        docker = self.docker()
        docker.command.side_effect = ["", "a" * 64 + "\n" + "b" * 64]
        item = {"id": "a" * 64, "network_mode": "edge_default", "ports": {
            str(port) + "/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}] for port in (80, 443)}}
        docker.inspect = Mock(return_value={"ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}})
        self.assertEqual(docker.check_ports(item), "127.0.0.1")

    def test_host_checks_actual_pid_not_process_name_only(self):
        docker = self.docker()
        lines = '\n'.join('LISTEN 0 128 *:' + str(port) + ' *:* users:(("nginx",pid=123,fd=4))' for port in (80, 443))
        docker.command.side_effect = [lines, 'PID COMMAND\n123 nginx: master process nginx']
        self.assertEqual(docker.check_ports({"id": "a" * 64, "network_mode": "host"}), "127.0.0.1")
        docker.command.side_effect = [lines, 'PID COMMAND\n999 nginx: master process nginx']
        with self.assertRaisesRegex(ValueError, "不完全属于"):
            docker.check_ports({"id": "a" * 64, "network_mode": "host"})

    def test_bridge_without_compose_is_not_persistent(self):
        with self.assertRaisesRegex(ValueError, "持久化"):
            self.docker().network({"network_mode": "bridge", "labels": {}})

    def test_missing_mount_stops_without_recreation(self):
        with self.assertRaisesRegex(ValueError, "不会重建"):
            self.docker().choose_mount({"mounts": []}, {"/etc/nginx/nginx.conf": "http {include /etc/nginx/conf.d/*.conf;}"})

    def test_local_named_volume_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            docker = self.docker()
            docker.exec = Mock(return_value="101")
            docker.command.return_value = json.dumps([{"Driver": "local", "Options": None, "Mountpoint": str(directory)}])
            item = {"mounts": [{"Source": directory.as_posix(), "Destination": "/etc/nginx/conf.d", "Type": "volume", "Name": "edge_conf"}]}
            # Path policy is Linux-only; the fixture supplies an explicit safe
            # mapping so this parser contract also runs on a Windows dev host.
            with patch("tg2cloud.deployment.proxy.docker_nginx.absolute_path", side_effect=lambda value: value), patch("tg2cloud.deployment.proxy.docker_nginx.safe_host_path"):
                volume = docker.choose_mount(item, {"/etc/nginx/nginx.conf": "user nginx; http{include /etc/nginx/conf.d/*.conf;}"})
            self.assertEqual(volume["type"], "volume")
            self.assertEqual(volume["host_dir"], str(directory))
            self.assertEqual(volume["worker_gid"], 101)

    def test_compose_recreation_revalidates_full_identity(self):
        docker = self.docker()
        saved, fresh = entry(), entry()
        fresh["identity"]["container_id"] = "c" * 64
        docker.plan = Mock(return_value=fresh)
        docker.inspect = Mock(return_value={"id": "c" * 64})
        item, _ = docker.revalidate(saved)
        self.assertEqual(item["id"], "c" * 64)
        fresh["identity"]["project"] = "other"
        with self.assertRaisesRegex(ValueError, "身份"):
            docker.revalidate(saved)

    def test_noncompose_recreated_container_is_not_trusted(self):
        docker = self.docker()
        saved, fresh = entry(), entry()
        for value in (saved, fresh):
            value["identity"]["project"] = ""
        fresh["identity"]["container_id"] = "c" * 64
        docker.plan = Mock(return_value=fresh)
        with self.assertRaisesRegex(ValueError, "仅凭名字"):
            docker.revalidate(saved)

    def test_panel_managed_nginx_is_not_taken_over(self):
        docker = DockerNginx(Mock())
        with self.assertRaisesRegex(ValueError, "面板"):
            docker.check_supported({"running": True, "user": "", "userns": "", "image": "jc21/nginx-proxy-manager", "name": "edge", "labels": {}})

    def test_runtime_only_mount_is_not_compose_persistence(self):
        docker = self.docker()
        item = {"image": "nginx:stable", "network_mode": "edge_default", "labels": {"com.docker.compose.project": "edge"}}
        config = {"services": {"nginx": {"image": "nginx:stable", "volumes": [],
                  "ports": [{"target": port, "published": str(port)} for port in (80, 443)]}}}
        docker.compose_config = Mock(return_value=("edge", "nginx", config))
        mount = entry()["mount"]
        with self.assertRaisesRegex(ValueError, "挂载未"):
            docker.persistent_mount(item, mount)
        config["services"]["nginx"]["volumes"] = [{"type": "bind", "source": mount["source"], "target": mount["destination"]}]
        docker.persistent_mount(item, mount)
        config["services"]["nginx"]["ports"].pop()
        with self.assertRaisesRegex(ValueError, "端口未"):
            docker.persistent_mount(item, mount)

    def test_multiple_containers_never_silently_selected(self):
        manager = SimpleNamespace(read_state=lambda: {"version": 1, "domains": {}}, session=Mock(), log=Mock(),
                                  probe=lambda _: ProxyEnvironment("OK", "OK", "FOREIGN", "FOREIGN"))
        candidates = [{"name": name, "kind": "external_docker", "reason": ""} for name in ("edge_a", "edge_b")]
        ui = SimpleNamespace(ask=Mock(side_effect=["1", ""]), confirm=Mock())
        with patch.object(DockerNginx, "candidates", return_value=candidates), self.assertRaisesRegex(ValueError, "不随机"):
            select_entry(manager, ui, "cd.example.com")
        ui.confirm.assert_not_called()

    def test_no_external_write_without_explicit_authorization(self):
        manager = SimpleNamespace(read_state=lambda: {"version": 1, "domains": {}}, session=Mock(), log=Mock(),
                                  probe=lambda _: ProxyEnvironment("OK", "OK", "FOREIGN", "FOREIGN"))
        with (patch.object(DockerNginx, "candidates", return_value=[{"name": "edge", "kind": "external_docker", "reason": ""}]),
              self.assertRaisesRegex(ValueError, "--authorize-proxy")):
            select_entry(manager, None, "cd.example.com", {"proxy_mode": "external_docker", "nginx_container": "edge"})
        manager.session.run.assert_not_called()

    def test_existing_managed_mode_cannot_implicitly_migrate(self):
        manager = SimpleNamespace(read_state=lambda: {"version": 1, "domains": {"clouddrive2": {"domain": "cd.example.com", "backend_port": 19798}}})
        with self.assertRaisesRegex(ValueError, "不会自动切换"):
            select_entry(manager, None, "cd.example.com", {"proxy_mode": "external_docker"})

    def test_managed_rejects_occupied_ports(self):
        manager = SimpleNamespace(read_state=lambda: {"version": 1, "domains": {}},
                                  probe=lambda _: ProxyEnvironment("OK", "OK", "FOREIGN", "FOREIGN"))
        with self.assertRaises(ValueError):
            select_entry(manager, None, "cd.example.com", {"proxy_mode": "managed"})

    def test_new_vps_keeps_managed_mode(self):
        manager = SimpleNamespace(read_state=lambda: {"version": 1, "domains": {}},
                                  probe=lambda _: ProxyEnvironment("OK", "OK", "FREE", "FREE"))
        with patch.object(DockerNginx, "candidates") as scan:
            select_entry(manager, None, "cd.example.com")
        scan.assert_not_called()

    def test_help_does_not_touch_docker(self):
        with (patch("tg2cloud.cli.proxy.preflight.validate_host") as host, patch("sys.stdout"),
              self.assertRaises(SystemExit) as exc):
            main(["--help"])
        self.assertEqual(exc.exception.code, 0)
        host.assert_not_called()
        with (patch("tg2cloud.cli.proxy.preflight.validate_host") as host, patch("sys.stderr"),
              self.assertRaises(SystemExit) as invalid):
            main(["configure", "--dry-run", "--yes", "--authorize-proxy"])
        self.assertEqual(invalid.exception.code, 2)
        host.assert_not_called()

    def test_renewal_command_is_explicitly_authorized(self):
        self.assertIn("proxy maintain --yes --authorize-proxy", CRON_CONTENT)
        args = parser().parse_args(["maintain", "--yes", "--authorize-proxy"])
        self.assertTrue(args.yes and args.authorize_proxy)

    def test_nginx_exec_is_id_scoped_not_name_and_no_restart(self):
        session = Mock()
        session.run.return_value = (0, "")
        docker = DockerNginx(session)
        docker.reload({"running": True, "id": "a" * 64, "cmd": []})
        commands = [call.args[0] for call in session.run.call_args_list]
        self.assertTrue(all("docker exec " + "a" * 64 in command for command in commands))
        self.assertTrue(commands[0].endswith("nginx -t"))
        self.assertTrue(commands[1].endswith("nginx -s reload"))
        self.assertFalse(any(word in " ".join(commands) for word in (" stop ", " restart ", " down ", " network connect ")))

    def test_two_edition_uninstall_never_takes_managed_stop_branch(self):
        from tg2cloud.deployment import uninstall
        from tg2cloud.deployment.proxy.state import ProxyReport
        value = state_with_route(state(), CLOUDDRIVE2_PRODUCT, "cd.example.com")
        value = state_with_route(value, OPENLIST_PRODUCT, "ol.example.com")
        plan = SimpleNamespace(editions=("clouddrive2", "openlist"), state=value, containers={}, networks={},
                               purge_data=False, purge_backups=False, remove_proxy=False)
        session, manager = Mock(), Mock()
        session.hold_lock.return_value = nullcontext()
        manager._remove_locked.return_value = ProxyReport("", "not_configured", "removed", ())
        with (patch.object(uninstall, "build_plan", return_value=plan),
              patch.object(uninstall, "edition_lock", side_effect=lambda *_: nullcontext()),
              patch.object(uninstall, "DomainProxyManager", return_value=manager),
              patch.object(uninstall, "docker_snapshot", return_value=({}, {})),
              patch.object(uninstall, "read_state", return_value=state())):
            uninstall.execute(plan, session, Mock())
        self.assertEqual(manager._remove_locked.call_count, 2)
        manager._install_config.assert_not_called()
        manager._compose.assert_not_called()
        session.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
