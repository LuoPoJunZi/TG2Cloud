"""Synthetic local family-account transactions; no real gateway or cloud data."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.addons.external_webdav import config, users, verification
from tg2cloud.addons.external_webdav.service import Service
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.resources import validate_install_dir

from .test_feature import SECRET, env, route, shared

HASH = "$6$rounds=200000$" + "a" * 16 + "$" + "b" * 86
NEW_HASH = "$6$rounds=200000$" + "c" * 16 + "$" + "d" * 86


class FamilyWebDAVTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        # Gateway instance is a simulated Linux path (never a real install).
        # Real private record/hash files still use canonical temporary paths.
        self.paths = patch("tg2cloud.deployment.configuration.checked_directory",
                           side_effect=lambda value: (validate_install_dir(value), PurePosixPath(value))[1])
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.ui, self.session = Mock(), Mock()
        self.session.run.return_value = (0, "")
        self.messages = []
        self.service = Service(PRODUCTS["openlist"], self.session, SafeLog(self.messages.append), self.ui, root=self.root)
        self.service.auth = self.root / "auth/openlist.htpasswd"
        self.service.locked = lambda: nullcontext()
        self.item = {"schema": 1, "owner": config.OWNER, "edition": "openlist", "instance_dir": PRODUCTS["openlist"].install_dir,
                     "domain": route()["domain"], "username": "phone-reader", "bot_root": "/媒体", "target_dir": "/媒体/Telegram",
                     "binding": config.binding(env()), "phase": "enabled", "scope_verification": "manual-native-readonly",
                     "backend_image": "pinned-test-image", "revision": "a" * 32}
        self.instance = SimpleNamespace(directory=PurePosixPath(self.item["instance_dir"]), config=env(), gateway_image="pinned-test-image")
        self.state = shared()
        self.service.preflight = Mock(side_effect=lambda *a, **k: (self.instance, copy.deepcopy(self.state)))
        self.service.backup = Mock()
        self.service.manager = Mock()
        self.service.verify_mounted_hash = Mock()
        self.service.auth_write = lambda content: config.atomic(self.service.auth, content, mode=0o640)
        self.service.save(copy.deepcopy(self.item))
        # Test runner need not be Linux root. Exercise the full metadata schema
        # against actual temporary JSON without impersonating a root-owned file.
        self.service.record = lambda: config.validate_record(json.loads(self.service.record_path.read_text()))
        self.service.revoke = lambda: self.service.auth_write(config.auth_content({}))
        self.service.auth_write(config.auth_content({"phone-reader": HASH}))
        # Only ownership is privileged: retain real temporary writes, fsync,
        # chmod and atomic replacement without requiring a root test runner.
        def check_owner(path, uid, gid):
            self.assertEqual(Path(path).parent, self.service.auth.parent)
            self.assertTrue(Path(path).name.startswith("." + self.service.auth.name + "-"))
            self.assertEqual(uid, 0)
            self.assertEqual(gid, self.service.auth.stat().st_gid)

        self.ownership = patch.object(config.os, "chown", side_effect=check_owner, create=True)
        self.chown = self.ownership.start()
        self.addCleanup(self.ownership.stop)
        self.ui.confirm.return_value = True
        self.ui.ask.side_effect = [SECRET, self.item["target_dir"]]
        self.backend = patch.object(verification, "check_backend")
        self.public = patch.object(verification, "check_public")
        self.check_backend = self.backend.start()
        self.check_public = self.public.start()
        self.addCleanup(self.backend.stop)
        self.addCleanup(self.public.stop)
        self.hashing = patch.object(config, "password_hash", return_value=NEW_HASH)
        self.hashing.start()
        self.addCleanup(self.hashing.stop)

    def run_account(self, action="add", user="family-reader"):
        users.account(self.service, action, user)

    def test_failed_chown_preserves_previous_auth_and_removes_candidate(self):
        before = self.service.auth.read_bytes()
        inode = self.service.auth.stat().st_ino
        self.chown.side_effect = PermissionError("synthetic ownership failure")
        with self.assertRaises(PermissionError):
            config.atomic(self.service.auth, config.auth_content({"family-reader": NEW_HASH}),
                          mode=0o640, gid=self.service.auth.stat().st_gid)
        self.chown.assert_called_once()
        self.assertEqual(self.service.auth.read_bytes(), before)
        self.assertEqual(self.service.auth.stat().st_ino, inode)
        self.assertEqual(list(self.service.auth.parent.glob("." + self.service.auth.name + "-*")), [])

    def test_add_migrates_v1_without_changing_directory_route_or_primary(self):
        self.assertEqual(self.service.record()["schema"], 1)
        self.run_account()
        item = self.service.record()
        self.assertEqual(item["schema"], 2)
        self.assertEqual(item["members"], [{"username": "family-reader", "phase": "enabled"}])
        for field in ("target_dir", "bot_root", "username", "binding", "domain"):
            self.assertEqual(item[field], self.item[field])
        self.assertEqual(users.entries(self.service, item), {"phone-reader": HASH, "family-reader": NEW_HASH})
        self.service.manager.apply_shared_state_locked.assert_not_called()
        self.assertEqual({call.args[0] for call in self.session.run.call_args_list}, {
            "docker exec tg2cloud-proxy-nginx nginx -t", "docker exec tg2cloud-proxy-nginx nginx -s reload"})
        self.assertNotIn(SECRET, self.service.record_path.read_text())
        self.assertNotIn(SECRET, "\n".join(self.messages))
        # The old v1 reader required exactly its fields + schema=1: it rejects,
        # rather than silently overwriting the extended account record.
        self.assertNotEqual(set(item), set(self.item))

    def test_both_editions_use_actual_same_root_never_an_arbitrary_per_user_path(self):
        for edition in PRODUCTS:
            with self.subTest(edition=edition):
                self.service.product = PRODUCTS[edition]
                item = copy.deepcopy(self.item)
                item.update(edition=edition, instance_dir=PRODUCTS[edition].install_dir, target_dir="/家庭/电影")
                self.instance.directory = PurePosixPath(item["instance_dir"])
                self.state["external_webdav"] = {edition: self.service.route(item, True)}
                self.service.save(item)
                self.service.auth_write(config.auth_content({item["username"]: HASH}))
                self.ui.ask.side_effect = [SECRET, "/家庭/电影"]
                self.run_account()
                self.assertEqual(self.service.record()["target_dir"], "/家庭/电影")
                self.assertEqual(self.check_backend.call_args.args[0]["username"], "family-reader")

    def test_failed_or_interrupted_rotation_revokes_only_selected_account(self):
        self.run_account()
        for error in (RuntimeError("synthetic verification failure"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.ui.ask.side_effect = [SECRET, self.item["target_dir"]]
                self.check_backend.side_effect = error
                with self.assertRaises(type(error)):
                    self.run_account("rotate")
                item = self.service.record()
                self.assertEqual(item["members"][0]["phase"], "needs_repair")
                self.assertEqual(users.entries(self.service, item), {"phone-reader": HASH})
        self.service.manager.apply_shared_state_locked.assert_not_called()

    def test_disable_remove_reenable_no_backend_deletion_and_no_other_user_changes(self):
        self.run_account()
        self.run_account("disable")
        self.assertEqual(users.entries(self.service, self.service.record()), {"phone-reader": HASH})
        self.ui.ask.side_effect = [SECRET, self.item["target_dir"]]
        self.run_account("enable")
        self.assertIn("family-reader", users.entries(self.service, self.service.record()))
        self.run_account("remove")
        self.assertEqual(self.service.record()["members"], [])
        self.assertEqual(users.entries(self.service, self.service.record()), {"phone-reader": HASH})
        self.assertTrue(all("DELETE" not in str(call) and "remove" not in str(call) for call in self.session.run.call_args_list))

    def test_wrong_root_confirmation_or_backend_failure_never_opens_member(self):
        self.ui.ask.side_effect = [SECRET, "/other-directory"]
        with self.assertRaises(ValueError):
            self.run_account()
        item = self.service.record()
        self.assertEqual(item["members"][0]["phase"], "needs_repair")
        self.assertEqual(users.entries(self.service, item), {"phone-reader": HASH})
        self.check_backend.assert_not_called()
        self.check_public.assert_not_called()

    def test_declined_plan_no_schema_migration_hash_write_or_reload(self):
        before = self.service.auth.read_bytes()
        self.ui.confirm.return_value = False
        self.run_account()
        self.assertEqual(self.service.record(), self.item)
        self.assertEqual(self.service.auth.read_bytes(), before)
        self.session.run.assert_not_called()

    def test_unknown_primary_bot_admin_duplicates_and_version_fail_closed(self):
        for user in ("phone-reader", "PHONE-reader", "bot-reader", "admin", "../x"):
            with self.subTest(user=user), self.assertRaises(ValueError):
                self.run_account(user=user)
        self.run_account()
        with self.assertRaises(ValueError):
            self.run_account(user="FAMILY-reader")
        item = self.service.record()
        item["schema"] = 99
        config.write_record(self.service.record_path, item)
        with self.assertRaises(ValueError):
            self.service.record()

    def test_cas_and_binding_drift_prevent_activation(self):
        previous = self.service.record()
        newer = dict(previous, revision="b" * 32)
        self.ui.confirm.side_effect = lambda prompt: (self.service.save(newer) or True)
        with self.assertRaisesRegex(ValueError, "另一操作"):
            self.run_account()
        self.session.run.assert_not_called()
        self.ui.confirm.side_effect = None
        self.instance.config = env("other-directory")
        with self.assertRaisesRegex(ValueError, "范围不自动扩大"):
            self.run_account()

    def test_whole_disable_disables_members_and_configure_cannot_discard_them(self):
        self.run_account()
        with self.assertRaisesRegex(ValueError, "不会静默丢弃"):
            self.service.configure(install_dir=None)
        self.service.maintain("disable")
        item = self.service.record()
        self.assertEqual(item["phase"], "disabled")
        self.assertEqual(item["members"][0]["phase"], "disabled")
        self.assertEqual(users.entries(self.service, item), {})
        self.ui.ask.side_effect = [SECRET]
        self.service.maintain("enable")
        self.assertEqual(self.service.record()["members"][0]["phase"], "disabled")
        self.assertEqual(users.entries(self.service, self.service.record()), {"phone-reader": NEW_HASH})

    def test_hash_parser_rejects_unknown_names_duplicates_weak_or_unbounded_content(self):
        for content in ("", "admin:" + HASH + "\n", "reader:plaintext\n", "reader:" + HASH,
                        "reader:" + HASH + "\nREADER:" + HASH + "\n", "x" * 20000):
            with self.subTest(content=content[:20]), self.assertRaises(ValueError):
                config.auth_entries(content)
        self.assertEqual(config.auth_entries("disabled:!\n"), {})
        item = self.service.record()
        self.service.auth_write(config.auth_content({"unknown-reader": HASH}))
        with self.assertRaisesRegex(ValueError, "未登记"):
            users.entries(self.service, item)
        self.assertNotIn("password", json.dumps(item))

    def test_disabled_portal_and_drift_still_allow_removing_a_family_grant(self):
        self.run_account()
        self.service.maintain("disable")
        self.state["external_webdav"]["openlist"]["enabled"] = False
        self.instance.config = env("changed-shared-directory")
        self.run_account("remove")
        self.assertEqual(self.service.record()["members"], [])
        self.assertEqual(self.service.record()["phase"], "disabled")
        self.assertTrue(all(call.kwargs.get("require_running") is False
                            for call in self.service.preflight.call_args_list[-2:]))

    def test_public_failure_removes_only_new_hash_before_releasing_activation(self):
        self.check_public.side_effect = RuntimeError("synthetic public failure")
        with self.assertRaises(RuntimeError):
            self.run_account()
        item = self.service.record()
        self.assertEqual(users.entries(self.service, item), {"phone-reader": HASH})
        self.assertEqual(item["members"][0]["phase"], "needs_repair")
