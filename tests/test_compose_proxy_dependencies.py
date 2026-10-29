"""Offline Compose HTTPS ownership, shared backup and removal boundaries."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.deployment import uninstall
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.proxy import maintenance
from tg2cloud.deployment.proxy.manager import DomainProxyManager, empty_state


def registry(edition="clouddrive2"):
    return {"format": 1, "owner": "tg2cloud.compose.https", "instances": {
        edition: {"root": "/srv/tg2cloud-" + edition, "domain": edition + ".example.test"}}}


def proxy_state(edition="clouddrive2"):
    value = empty_state()
    value["domains"][edition] = {"domain": edition + ".example.test", "backend_port": PRODUCTS[edition].management_port}
    return value


class RegistryTests(unittest.TestCase):
    def test_optional_empty_and_valid_two_editions(self):
        value = registry()
        value["instances"].update(registry("openlist")["instances"])
        self.assertEqual(maintenance.parse_compose_registry(json.dumps(value)), value)
        value["instances"] = {}
        self.assertEqual(maintenance.validate_compose_registry(value), value)

    def test_strict_schema_paths_domains_and_overlaps(self):
        invalid = []
        for key, replacement in (("format", True), ("format", 2), ("owner", "foreign"), ("instances", [])):
            value = registry()
            value[key] = replacement
            invalid.append(value)
        value = registry()
        value["extra"] = True
        invalid.append(value)
        for path in ("/", "relative", "//srv/one", "/srv/../etc", "/srv//one", "/srv/one/", "/srv/a\\b", "/srv/a\n"):
            value = registry()
            value["instances"]["clouddrive2"]["root"] = path
            invalid.append(value)
        for domain in ("127.0.0.1", "example", "HTTPS://example.test", "Example.test", "bad_.test", "例子.test"):
            value = registry()
            value["instances"]["clouddrive2"]["domain"] = domain
            invalid.append(value)
        for suffix in ("", "/nested"):
            value = registry()
            value["instances"].update(registry("openlist")["instances"])
            value["instances"]["openlist"]["root"] = value["instances"]["clouddrive2"]["root"] + suffix
            invalid.append(value)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                maintenance.validate_compose_registry(value)

    def test_duplicate_json_fields_and_bounded_input(self):
        for raw in ('{"format":1,"format":1}', "{" + " " * maintenance.COMPOSE_REGISTRY_LIMIT, "null", "[]"):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                maintenance.parse_compose_registry(raw)

    def test_consistency_requires_owned_route_to_exist_and_match(self):
        maintenance.validate_compose_routes(registry(), proxy_state())
        for state in (empty_state(), proxy_state("openlist")):
            with self.assertRaisesRegex(ValueError, "disagrees"):
                maintenance.validate_compose_routes(registry(), state)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "proxy"
        self.backups = Path(self.temporary.name) / "backups"
        for relative in ("state", "nginx/conf.d", "certbot/letsencrypt"):
            (self.root / relative).mkdir(parents=True)
        (self.root / "state/domains.json").write_text(json.dumps(proxy_state()), encoding="utf-8")
        (self.root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "nginx/nginx.conf").write_text("events {}\n", encoding="utf-8")
        self.path = self.root / maintenance.COMPOSE_REGISTRY

    def write_registry(self):
        self.path.write_text(json.dumps(registry()), encoding="utf-8")
        self.path.chmod(0o600)

    def test_old_backup_without_registry_remains_valid(self):
        archive = maintenance.create_backup(self.root, self.backups)
        records = maintenance.verify_backup(archive)
        self.assertNotIn("proxy/" + maintenance.COMPOSE_REGISTRY, records)
        self.assertEqual(maintenance.recovery_drill(archive, self.backups), len(records))

    def test_registry_in_backup_and_isolated_drill_preserves_live_state(self):
        self.write_registry()
        before = self.path.read_bytes()
        archive = maintenance.create_backup(self.root, self.backups)
        records = maintenance.verify_backup(archive)
        self.assertEqual(records["proxy/" + maintenance.COMPOSE_REGISTRY]["kind"], "file")
        self.assertEqual(maintenance.recovery_drill(archive, self.backups), len(records))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.backups.glob("recovery-drill-*")), [])

    def test_journal_incomplete_or_malformed_registry_blocks_backup(self):
        journal = self.root / maintenance.COMPOSE_TRANSACTION
        journal.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unfinished"):
            maintenance.snapshot(self.root)
        journal.unlink()
        self.path.write_text("{}", encoding="utf-8")
        self.path.chmod(0o600)
        with self.assertRaises(ValueError):
            maintenance.snapshot(self.root)

    def test_registry_path_must_not_be_linked_even_if_target_is_private(self):
        self.write_registry()
        # A deterministic link metadata probe also works without Windows symlink privileges.
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == self.path or original(path)), self.assertRaisesRegex(ValueError, "unsafe"):
            maintenance.validate_live_compose_registry(self.root)

    def test_registry_hardlinks_are_rejected(self):
        self.write_registry()
        alias = self.path.with_name("other.json")
        os.link(self.path, alias)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            maintenance.validate_live_compose_registry(self.root)

    def test_registry_owner_and_permissions_are_checked(self):
        self.write_registry()
        real = self.path.lstat()
        for uid, mode in ((12345, stat.S_IFREG | 0o600), (0, stat.S_IFREG | 0o644)):
            info = SimpleNamespace(st_mode=mode, st_uid=uid, st_size=real.st_size, st_nlink=1)
            with self.subTest(uid=uid, mode=mode), patch.object(maintenance, "os", SimpleNamespace(name="posix", geteuid=lambda: 0)), patch.object(Path, "lstat", return_value=info), self.assertRaisesRegex(ValueError, "unsafe"):
                maintenance.validate_live_compose_registry(self.root)

    def test_live_registry_route_mismatch_is_not_reported_valid(self):
        self.write_registry()
        (self.root / "state/domains.json").write_text(json.dumps(empty_state()), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "disagrees"):
            maintenance.snapshot(self.root)

    def test_rechecks_semantics_even_for_self_consistent_archive_hashes(self):
        self.write_registry()
        archive = maintenance.create_backup(self.root, self.backups)
        entries = []
        with tarfile.open(archive, "r:gz") as source:
            for member in source:
                handle = source.extractfile(member) if member.isfile() else None
                entries.append((copy.copy(member), handle.read() if handle else None))
        replacement = json.dumps(registry("openlist")).encode()
        for member, content in entries:
            if member.name == "proxy/manifest.json":
                manifest = json.loads(content)
                record = manifest["files"]["proxy/" + maintenance.COMPOSE_REGISTRY]
                record.update(size=len(replacement), sha256=hashlib.sha256(replacement).hexdigest())
                new_manifest = json.dumps(manifest).encode()
        with tarfile.open(archive, "w:gz") as output:
            for member, content in entries:
                if member.name == "proxy/" + maintenance.COMPOSE_REGISTRY:
                    content = replacement
                elif member.name == "proxy/manifest.json":
                    content = new_manifest
                if content is not None:
                    member.size = len(content)
                output.addfile(member, io.BytesIO(content) if content is not None else None)
        archive.with_name(archive.name + ".sha256").write_text(maintenance.digest(archive), encoding="ascii")
        with self.assertRaisesRegex(ValueError, "disagrees"):
            maintenance.verify_backup(archive)


class UninstallDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "proxy"
        (self.root / "state").mkdir(parents=True)
        self.path = self.root / maintenance.COMPOSE_REGISTRY
        self.patch = patch.object(uninstall, "PROXY_ROOT", str(self.root))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_registry(self, edition="clouddrive2"):
        self.path.write_text(json.dumps(registry(edition)), encoding="utf-8")
        self.path.chmod(0o600)

    def fixture_private(self, path):
        # Only this private temporary fixture substitutes its uid for root; links,
        # regularity and Linux private mode remain checked by real file metadata.
        self.assertEqual(path, self.path)
        self.assertEqual(path.resolve(), path)
        self.assertFalse(path.is_symlink())
        self.assertTrue(path.is_file())
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        return path.read_bytes()

    def test_registry_absent_and_valid_reader(self):
        self.assertEqual(uninstall.read_compose_instances(), {})
        self.write_registry()
        with patch.object(uninstall.configuration, "regular_private", side_effect=self.fixture_private):
            self.assertEqual(uninstall.read_compose_instances(), registry()["instances"])

    def test_reader_refuses_bad_private_link_or_unknown_schema(self):
        self.write_registry()
        for error in (ValueError("fixture unsafe owner"), OSError("fixture unavailable")):
            with patch.object(uninstall.configuration, "regular_private", side_effect=error), self.assertRaises(uninstall.UninstallError):
                uninstall.read_compose_instances()
        self.path.write_text('{"format":99}', encoding="utf-8")
        with patch.object(uninstall.configuration, "regular_private", side_effect=self.fixture_private), self.assertRaises(uninstall.UninstallError):
            uninstall.read_compose_instances()
        os.link(self.path, self.path.with_name("alias"))
        with self.assertRaises(uninstall.UninstallError):
            uninstall.read_compose_instances()

    def test_registered_selected_edition_refuses_even_without_containers(self):
        self.write_registry()
        session = Mock()
        with patch.object(uninstall.configuration, "regular_private", side_effect=self.fixture_private), patch.object(uninstall, "docker_snapshot") as snapshot:
            for editions in (("clouddrive2",), tuple(PRODUCTS)):
                with self.subTest(editions=editions), self.assertRaises(uninstall.UninstallError):
                    uninstall.build_plan(editions, session)
            snapshot.assert_not_called()
        session.run.assert_not_called()

    def test_other_edition_registry_keeps_proxy_and_manager(self):
        self.write_registry("openlist")
        with patch.object(uninstall.configuration, "regular_private", side_effect=self.fixture_private), patch.object(uninstall, "docker_snapshot", return_value=({}, {})), patch.object(uninstall, "read_state", return_value=empty_state()), patch.object(uninstall, "checked_path"):
            plan = uninstall.build_plan(("clouddrive2",), Mock())
            self.assertFalse(plan.remove_proxy)
            self.assertTrue(uninstall.other_edition_present(("clouddrive2",), {}))
            self.assertTrue(uninstall.manager_in_use(Mock()))
            self.assertNotIn(uninstall.PROXY_BACKUP_ROOT, uninstall.backup_targets(("clouddrive2",), {}, True))

    def test_purge_refuses_own_or_global_proxy_deletion_with_any_owner(self):
        self.write_registry()
        with patch.object(uninstall.configuration, "regular_private", side_effect=self.fixture_private), patch.object(uninstall, "mountpoints") as points:
            for editions, remove_proxy in ((("clouddrive2",), False), (("openlist",), True)):
                with self.subTest(editions=editions, remove_proxy=remove_proxy), self.assertRaises(uninstall.UninstallError):
                    uninstall.purge_preflight(editions, {}, {}, remove_proxy)
            points.assert_not_called()

    def test_unfinished_transaction_blocks_plan_purge_and_manager_cleanup(self):
        (self.root / maintenance.COMPOSE_TRANSACTION).write_text("{}", encoding="utf-8")
        for operation in (lambda: uninstall.build_plan(("clouddrive2",), Mock()),
                          lambda: uninstall.purge_preflight(("clouddrive2",), {}, {}, False),
                          lambda: uninstall.manager_in_use(Mock())):
            with self.assertRaisesRegex(uninstall.UninstallError, "事务"):
                operation()


class GenericWriterTests(unittest.TestCase):
    def manager(self, edition="clouddrive2", output="", code=0):
        session = SimpleNamespace(run=Mock(return_value=(code, output)))
        return DomainProxyManager(session, PRODUCTS[edition], {}, lambda _: None)

    def test_global_migration_refuses_even_another_editions_compose_route(self):
        from tg2cloud.cli import proxy
        manager = self.manager("openlist", json.dumps(registry()))
        manager.read_state = Mock(return_value=proxy_state())
        manager.session.hold_lock = Mock()
        with patch.object(proxy, "DockerNginx") as docker, self.assertRaisesRegex(RuntimeError, "Compose"):
            proxy.migrate(manager, "existing-edge", "", Mock())
        docker.assert_not_called()
        manager.session.hold_lock.assert_not_called()

    def test_missing_registry_preserves_generic_writer(self):
        self.manager()._check_compose_owner(empty_state())

    def test_selected_owner_blocked_other_edition_preserved(self):
        for edition in PRODUCTS:
            manager = self.manager(edition, json.dumps(registry()))
            if edition == "clouddrive2":
                with self.assertRaisesRegex(RuntimeError, "Compose"):
                    manager._check_compose_owner(proxy_state())
            else:
                manager._check_compose_owner(proxy_state())

    def test_bad_registry_transaction_or_read_failure_never_falls_back(self):
        for code, output in ((0, "{}"), (0, '{"format":99}'), (0, json.dumps(registry())), (3, ""), (5, "")):
            with self.subTest(code=code, output=output), self.assertRaises(RuntimeError):
                self.manager(output=output, code=code)._check_compose_owner(empty_state())

    def test_configure_and_remove_check_before_any_mutation(self):
        manager = self.manager()
        manager.read_state = Mock(return_value=empty_state())
        manager._check_compose_owner = Mock(side_effect=RuntimeError("owned by Compose"))
        manager._activate = Mock()
        manager._install_config = Mock()
        manager._commit_state = Mock()
        for operation in (lambda: manager._configure_locked("panel.example.test", ""), manager._remove_locked):
            with self.assertRaises(RuntimeError):
                operation()
        manager._activate.assert_not_called()
        manager._install_config.assert_not_called()
        manager._commit_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
