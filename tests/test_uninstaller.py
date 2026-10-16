"""Offline removal tests; never uninstall a real VPS, NAS or Docker resource."""

from __future__ import annotations

import copy
import io
import json
import os
import re
import shlex
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import uninstaller as uninstall
from scripts.lib.deployer_products import PRODUCTS
from scripts.lib.domain_proxy import render_compose
from scripts.vps_runtime import SafeLog

ROOT = Path(__file__).resolve().parents[1]


def identifier(number):
    return f"{number:064x}"


def container(product, *, bot=False, number=1):
    name = product.bot_container if bot else product.storage_container
    directory = Path(product.install_dir)
    expected = {"/" + key: str(directory / key) for key in ("data", "downloads", "logs", "config")}
    if not bot:
        expected = ({"/opt/openlist/data": str(directory / "openlist/data")} if product.is_openlist else
                    {"/Config": str(directory / "clouddrive/config"), "/CloudNAS": str(directory / "clouddrive/mounts")})
    return {"id": identifier(number), "name": "/" + name, "running": True, "network": product.docker_network,
            "labels": {uninstall.COMPOSE + "project": directory.name,
                       uninstall.COMPOSE + "service": product.bot_service if bot else product.key,
                       uninstall.COMPOSE + "project.working_dir": str(directory),
                       uninstall.COMPOSE + "project.config_files": str(directory / "docker-compose.yml")},
            "mounts": [{"Type": "bind", "Source": source, "Destination": destination} for destination, source in expected.items()]}


def lan_container(product, number=5):
    directory = uninstall.LAN_ROOT / product.key
    return {"id": identifier(number), "name": "/" + uninstall.lan_name(product), "running": True, "network": "host",
            "labels": {uninstall.MANAGED: "true", uninstall.ROLE: "lan-management", "com.tg2cloud.edition": product.key,
                       uninstall.COMPOSE + "project": uninstall.lan_name(product), uninstall.COMPOSE + "service": "lan",
                       uninstall.COMPOSE + "project.working_dir": str(directory),
                       uninstall.COMPOSE + "project.config_files": str(directory / "compose.json")},
            "mounts": [{"Type": "bind", "Source": str(directory / "nginx.conf"), "Destination": "/etc/nginx/nginx.conf"}]}


def proxy_container(*, nginx=True, number=7):
    name = uninstall.PROXY_NGINX_CONTAINER if nginx else uninstall.PROXY_CERTBOT_CONTAINER
    paths = {"/var/www/certbot": "/certbot/www", "/etc/letsencrypt": "/certbot/letsencrypt"}
    if nginx:
        paths.update({"/etc/nginx/nginx.conf": "/nginx/nginx.conf", "/etc/nginx/conf.d": "/nginx/conf.d"})
    else:
        paths.update({"/var/lib/letsencrypt": "/certbot/lib", "/var/log/letsencrypt": "/certbot/log", "/status": "/certbot/status"})
    return {"id": identifier(number), "name": "/" + name, "running": True,
            "network": "host" if nginx else uninstall.PROXY_NETWORK,
            "labels": {uninstall.MANAGED: "true", uninstall.ROLE: "reverse-proxy" if nginx else "certificate-manager",
                       uninstall.COMPOSE + "project": uninstall.PROXY_PROJECT,
                       uninstall.COMPOSE + "service": "nginx" if nginx else "certbot",
                       uninstall.COMPOSE + "project.working_dir": uninstall.PROXY_ROOT,
                       uninstall.COMPOSE + "project.config_files": uninstall.PROXY_ROOT + "/docker-compose.yml"},
            "mounts": [{"Type": "bind", "Source": uninstall.PROXY_ROOT + suffix, "Destination": target} for target, suffix in paths.items()]}


class FakeDocker:
    def __init__(self, *, both=True, proxy=False, lan=False):
        self.containers = {}
        self.networks = {}
        self.commands = []
        self.state = uninstall.empty_state()
        self.fail_stop = False
        self.fail_network = False
        self.attach_foreign = False
        for index, product in enumerate(PRODUCTS.values()):
            if not both and index:
                continue
            self.containers[product.bot_container] = container(product, bot=True, number=1 + index * 2)
            self.containers[product.storage_container] = container(product, number=2 + index * 2)
            self.networks[product.docker_network] = {
                "id": identifier(11 + index), "name": product.docker_network, "driver": "bridge",
                "labels": {uninstall.COMPOSE + "project": Path(product.install_dir).name,
                           uninstall.COMPOSE + "network": product.docker_network},
                "containers": {identifier(1 + index * 2): {}, identifier(2 + index * 2): {}},
            }
            if lan:
                self.containers[uninstall.lan_name(product)] = lan_container(product, 5 + index)
            if proxy:
                self.state["domains"][product.key] = {"domain": product.key + ".example.test", "backend_port": product.management_port}
        if proxy:
            self.containers[uninstall.PROXY_NGINX_CONTAINER] = proxy_container()
            self.containers[uninstall.PROXY_CERTBOT_CONTAINER] = proxy_container(nginx=False, number=8)
            self.networks[uninstall.PROXY_NETWORK] = {
                "id": identifier(13), "name": uninstall.PROXY_NETWORK, "driver": "bridge",
                "labels": {uninstall.COMPOSE + "project": uninstall.PROXY_PROJECT, uninstall.COMPOSE + "network": "default"},
                "containers": {identifier(8): {}},
            }
        self.containers["unrelated-nginx"] = {"id": identifier(20), "name": "/unrelated-nginx", "running": True,
                                               "labels": {}, "mounts": [], "network": "host"}

    def snapshot(self, _session):
        return copy.deepcopy(self.containers), copy.deepcopy(self.networks)

    def hold_lock(self, _command):
        return nullcontext()

    def run(self, command, **_kwargs):
        self.commands.append(command)
        tokens = shlex.split(command)
        if tokens[:3] == ["docker", "container", "stop"]:
            if self.fail_stop:
                return 1, "FAKE_OFFLINE_SECRET"
            return 0, ""
        if tokens[:3] == ["docker", "container", "rm"]:
            match = next(name for name, value in self.containers.items() if value["id"] == tokens[-1])
            del self.containers[match]
            for network in self.networks.values():
                network["containers"].pop(tokens[-1], None)
            return 0, ""
        if tokens[:3] == ["docker", "network", "inspect"]:
            item = next(value for value in self.networks.values() if value["id"] == tokens[-1])
            current = copy.deepcopy(item)
            if self.attach_foreign:
                current["containers"][identifier(90)] = {}
            return 0, json.dumps(current)
        if tokens[:3] == ["docker", "network", "rm"]:
            if self.fail_network:
                return 1, "FAKE_OFFLINE_SECRET"
            match = next(name for name, value in self.networks.items() if value["id"] == tokens[-1])
            del self.networks[match]
            return 0, ""
        return 0, ""

    def manager(self, _session, product, _values, _log):
        result = Mock()

        def remove_route():
            self.state["domains"].pop(product.key)
            report = Mock()
            report.message = "已移除所选路由"
            return report

        result._remove_locked.side_effect = remove_route
        return result


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.docker = FakeDocker()
        self.stack.enter_context(patch.object(uninstall, "checked_path"))
        self.stack.enter_context(patch.object(uninstall, "read_state", side_effect=lambda: copy.deepcopy(self.docker.state)))
        self.stack.enter_context(patch.object(uninstall, "docker_snapshot", side_effect=self.docker.snapshot))
        self.stack.enter_context(patch.object(Path, "exists", return_value=False))

    def test_each_edition_and_all_remove_only_matching_runtime_resources(self):
        for keys in (("clouddrive2",), ("openlist",), tuple(PRODUCTS)):
            with self.subTest(editions=keys):
                plan = uninstall.build_plan(keys, self.docker)
                self.assertEqual(set(plan.containers), {name for key in keys for name in (PRODUCTS[key].bot_container, PRODUCTS[key].storage_container)})
                self.assertEqual(set(plan.networks), {PRODUCTS[key].docker_network for key in keys})
                self.assertFalse(plan.purge_data)

    def test_same_name_foreign_container_rejected_before_mutation(self):
        for field, value in (("project.working_dir", "/opt/foreign"), ("service", "unrelated"), ("project.config_files", "/etc/compose.yml"), ("project", "$(id)")):
            with self.subTest(label=field):
                original = copy.deepcopy(self.docker.containers)
                self.docker.containers[PRODUCTS["clouddrive2"].bot_container]["labels"][uninstall.COMPOSE + field] = value
                with self.assertRaises(uninstall.UninstallError):
                    uninstall.build_plan(("clouddrive2",), self.docker)
                self.docker.containers = original
        self.assertEqual(self.docker.commands, [])

    def test_external_mount_or_named_volume_never_deleted(self):
        for kind, source in (("bind", "/srv/foreign"), ("volume", "foreign-volume")):
            with self.subTest(kind=kind):
                self.docker.containers[PRODUCTS["clouddrive2"].bot_container]["mounts"][0].update(Type=kind, Source=source)
                with self.assertRaises(uninstall.UninstallError):
                    uninstall.build_plan(("clouddrive2",), self.docker)

    def test_partial_and_stopped_container_installation_supported(self):
        del self.docker.containers[PRODUCTS["clouddrive2"].storage_container]
        self.docker.networks[PRODUCTS["clouddrive2"].docker_network]["containers"].pop(identifier(2))
        self.docker.containers[PRODUCTS["clouddrive2"].bot_container]["running"] = False
        plan = uninstall.build_plan(("clouddrive2",), self.docker)
        self.assertEqual(set(plan.containers), {PRODUCTS["clouddrive2"].bot_container})

    def test_unknown_orphan_in_project_rejected(self):
        item = copy.deepcopy(self.docker.containers[PRODUCTS["clouddrive2"].bot_container])
        item["id"] = identifier(30)
        self.docker.containers["custom-added-service"] = item
        with self.assertRaisesRegex(uninstall.UninstallError, "其他容器"):
            uninstall.build_plan(("clouddrive2",), self.docker)

    def test_network_without_identity_or_with_external_endpoint_rejected(self):
        network = self.docker.networks[PRODUCTS["clouddrive2"].docker_network]
        for field, value in (("labels", {}), ("driver", "overlay"), ("containers", {identifier(99): {}})):
            with self.subTest(field=field):
                previous = copy.deepcopy(network)
                network[field] = value
                with self.assertRaises(uninstall.UninstallError):
                    uninstall.build_plan(("clouddrive2",), self.docker)
                network.update(previous)

    def test_recognized_empty_residual_network_and_missing_runtime_supported(self):
        self.docker.containers = {"unrelated-nginx": self.docker.containers["unrelated-nginx"]}
        for network in self.docker.networks.values():
            network["containers"] = {}
        plan = uninstall.build_plan(("clouddrive2",), self.docker)
        self.assertEqual(plan.containers, {})
        self.assertEqual(len(plan.networks), 1)

    def test_lan_entry_both_editions_and_foreign_identity(self):
        for product in PRODUCTS.values():
            with self.subTest(edition=product.key):
                name = uninstall.lan_name(product)
                self.docker.containers[name] = lan_container(product)
                plan = uninstall.build_plan((product.key,), self.docker)
                self.assertIn(name, plan.containers)
                self.docker.containers[name]["labels"][uninstall.MANAGED] = "false"
                with self.assertRaises(uninstall.UninstallError):
                    uninstall.build_plan((product.key,), self.docker)
                del self.docker.containers[name]

    def test_shared_proxy_kept_until_no_other_edition_route(self):
        self.docker = FakeDocker(proxy=True)
        self.stack.enter_context(patch.object(uninstall, "docker_snapshot", side_effect=self.docker.snapshot))
        self.stack.enter_context(patch.object(Path, "exists", lambda path: path == Path(uninstall.PROXY_ROOT, "state/domains.json")))
        for keys in (("clouddrive2",), ("openlist",)):
            plan = uninstall.build_plan(keys, self.docker)
            self.assertFalse(plan.remove_proxy)
            self.assertNotIn(uninstall.PROXY_NGINX_CONTAINER, plan.containers)
        plan = uninstall.build_plan(tuple(PRODUCTS), self.docker)
        self.assertTrue(plan.remove_proxy)
        self.assertIn(uninstall.PROXY_NGINX_CONTAINER, plan.containers)
        self.assertIn(uninstall.PROXY_NETWORK, plan.networks)

    def test_proxy_network_fixture_matches_actual_compose_not_assumed_host_mode(self):
        rendered = render_compose()
        nginx, certbot = rendered.split("  certbot:\n", 1)
        self.assertIn("network_mode: host", nginx)
        self.assertNotIn("network_mode:", certbot)
        uninstall.proxy_identity(uninstall.PROXY_CERTBOT_CONTAINER, proxy_container(nginx=False))

    def test_proxy_network_with_foreign_endpoint_refused_before_route_removal(self):
        self.docker = FakeDocker(proxy=True)
        self.stack.enter_context(patch.object(uninstall, "docker_snapshot", side_effect=self.docker.snapshot))
        self.docker.networks[uninstall.PROXY_NETWORK]["containers"][identifier(90)] = {}
        with self.assertRaisesRegex(uninstall.UninstallError, "共享代理网络"):
            uninstall.build_plan(tuple(PRODUCTS), self.docker)

    def test_proxy_same_name_unknown_ownership_and_running_oneoff_refused(self):
        for managed in (None, "false"):
            item = proxy_container()
            item["labels"][uninstall.MANAGED] = managed
            with self.subTest(managed=managed), self.assertRaises(uninstall.UninstallError):
                uninstall.proxy_identity(uninstall.PROXY_NGINX_CONTAINER, item)
        item = proxy_container(nginx=False)
        item["labels"][uninstall.COMPOSE + "oneoff"] = "True"
        with self.assertRaises(uninstall.UninstallError):
            uninstall.proxy_identity("tg2cloud-proxy-certbot-run-abcd", item)
        item["running"] = False
        uninstall.proxy_identity("tg2cloud-proxy-certbot-run-abcd", item)

    def test_maintenance_helpers_not_force_removed(self):
        self.docker.containers["tg2cloud-proxy-dry-run-example"] = {
            "id": identifier(31), "labels": {uninstall.ROLE: "maintenance-dry-run"}, "mounts": [],
        }
        with self.assertRaisesRegex(uninstall.UninstallError, "维护"):
            uninstall.build_plan(tuple(PRODUCTS), self.docker)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.docker = FakeDocker()
        self.logs = []
        self.log = SafeLog(self.logs.append)
        self.stack.enter_context(patch.object(uninstall, "checked_path"))
        self.stack.enter_context(patch.object(uninstall, "docker_snapshot", side_effect=self.docker.snapshot))
        self.stack.enter_context(patch.object(uninstall, "read_state", side_effect=lambda: copy.deepcopy(self.docker.state)))
        self.stack.enter_context(patch.object(uninstall, "edition_lock", return_value=nullcontext()))
        self.stack.enter_context(patch.object(Path, "exists", return_value=False))
        self.deleted = self.stack.enter_context(patch.object(uninstall, "delete_tree"))

    def test_single_then_all_removal_preserve_foreign_and_are_repeatable(self):
        uninstall.execute(uninstall.build_plan(("clouddrive2",), self.docker), self.docker, self.log)
        self.assertIn(PRODUCTS["openlist"].bot_container, self.docker.containers)
        uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        self.assertEqual(set(self.docker.containers), {"unrelated-nginx"})
        self.assertEqual(self.docker.networks, {})
        self.deleted.assert_not_called()
        for command in self.docker.commands:
            self.assertNotRegex(command, r"prune|--force|rm -f|--volumes|--rmi|apt|systemctl|nginx -s")

    def test_changed_plan_stops_before_any_runtime_mutation(self):
        plan = uninstall.build_plan(("clouddrive2",), self.docker)
        self.docker.containers[PRODUCTS["clouddrive2"].bot_container]["id"] = identifier(80)
        self.docker.networks[PRODUCTS["clouddrive2"].docker_network]["containers"] = {identifier(80): {}, identifier(2): {}}
        with self.assertRaisesRegex(uninstall.UninstallError, "变化"):
            uninstall.execute(plan, self.docker, self.log)
        self.assertEqual(self.docker.commands, [])

    def test_stop_failure_never_removes_container_network_or_data(self):
        plan = uninstall.build_plan(("clouddrive2",), self.docker)
        self.docker.fail_stop = True
        with self.assertRaises(uninstall.UninstallError):
            uninstall.execute(plan, self.docker, self.log)
        self.assertEqual(len(self.docker.commands), 1)
        self.deleted.assert_not_called()
        self.assertNotIn("FAKE_OFFLINE_SECRET", "\n".join(self.logs))

    def test_external_connection_after_confirmation_never_forced_disconnected(self):
        plan = uninstall.build_plan(("clouddrive2",), self.docker)
        self.docker.attach_foreign = True
        with self.assertRaisesRegex(uninstall.UninstallError, "连接已变化"):
            uninstall.execute(plan, self.docker, self.log)
        self.assertFalse(any(command.startswith("docker network rm") for command in self.docker.commands))
        self.deleted.assert_not_called()

    def test_https_removal_failure_leaves_core_containers_and_networks_untouched(self):
        self.docker.state["domains"]["clouddrive2"] = {"domain": "cd2.example.test", "backend_port": 19798}
        manager = Mock()
        manager._remove_locked.side_effect = RuntimeError("FAKE_OFFLINE_SECRET")
        with patch.object(uninstall, "DomainProxyManager", return_value=manager), self.assertRaises(uninstall.UninstallError):
            uninstall.execute(uninstall.build_plan(("clouddrive2",), self.docker), self.docker, self.log)
        self.assertEqual(self.docker.commands, [])

    def test_single_route_removal_never_deletes_other_route(self):
        for key in PRODUCTS:
            self.docker.state["domains"][key] = {"domain": key + ".example.test", "backend_port": PRODUCTS[key].management_port}
        with patch.object(uninstall, "DomainProxyManager", side_effect=self.docker.manager):
            uninstall.execute(uninstall.build_plan(("clouddrive2",), self.docker), self.docker, self.log)
        self.assertEqual(set(self.docker.state["domains"]), {"openlist"})
        self.assertIn(PRODUCTS["openlist"].bot_container, self.docker.containers)

    def test_all_routes_removed_as_one_transaction_before_runtime_removal(self):
        for key in PRODUCTS:
            self.docker.state["domains"][key] = {"domain": key + ".example.test", "backend_port": PRODUCTS[key].management_port}
        manager = Mock()
        manager._compose.return_value = (0, "")
        manager._commit_state.side_effect = lambda state: setattr(self.docker, "state", copy.deepcopy(state))
        with patch.object(uninstall, "DomainProxyManager", return_value=manager):
            uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        manager._install_config.assert_called_once_with(uninstall.empty_state())
        manager._commit_state.assert_called_once_with(uninstall.empty_state())
        manager._remove_locked.assert_not_called()
        self.assertEqual(self.docker.state, uninstall.empty_state())

    def test_all_routes_failure_attempts_restore_and_leaves_core_untouched(self):
        for key in PRODUCTS:
            self.docker.state["domains"][key] = {"domain": key + ".example.test", "backend_port": PRODUCTS[key].management_port}
        previous = copy.deepcopy(self.docker.state)
        manager = Mock()
        manager._compose.side_effect = [(1, "FAKE_OFFLINE_SECRET"), (0, "")]
        with patch.object(uninstall, "DomainProxyManager", return_value=manager), self.assertRaises(uninstall.UninstallError):
            uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        manager._activate.assert_called_once_with(previous)
        manager._commit_state.assert_not_called()
        self.assertEqual(self.docker.commands, [])

    def test_proxy_containers_and_default_network_removed_only_after_last_routes(self):
        self.docker = FakeDocker(proxy=True)
        self.stack.enter_context(patch.object(uninstall, "docker_snapshot", side_effect=self.docker.snapshot))
        self.stack.enter_context(patch.object(Path, "exists", lambda path: path == Path(uninstall.PROXY_ROOT, "state/domains.json")))
        manager = Mock()
        manager._compose.return_value = (0, "")
        manager._commit_state.side_effect = lambda state: setattr(self.docker, "state", copy.deepcopy(state))
        with patch.object(uninstall, "DomainProxyManager", return_value=manager):
            uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        self.assertEqual(set(self.docker.containers), {"unrelated-nginx"})
        self.assertEqual(self.docker.networks, {})

    def test_proxy_restore_failure_reports_warning_without_exposing_original_output(self):
        for key in PRODUCTS:
            self.docker.state["domains"][key] = {"domain": key + ".example.test", "backend_port": PRODUCTS[key].management_port}
        manager = Mock()
        manager._compose.return_value = (1, "FAKE_OFFLINE_SECRET")
        manager._activate.side_effect = RuntimeError("FAKE_OFFLINE_SECRET")
        with patch.object(uninstall, "DomainProxyManager", return_value=manager), self.assertRaises(uninstall.UninstallError):
            uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker), self.docker, self.log)
        self.assertIn("恢复失败", "\n".join(self.logs))
        self.assertNotIn("FAKE_OFFLINE_SECRET", "\n".join(self.logs))
        self.assertEqual(self.docker.commands, [])

    def test_purge_deletes_only_selected_data_and_not_shared_certificates_with_other_core_present(self):
        with patch.object(uninstall, "purge_preflight"):
            uninstall.execute(uninstall.build_plan(("clouddrive2",), self.docker, purge_data=True), self.docker, self.log)
        self.assertEqual([call.args[0] for call in self.deleted.call_args_list], [Path(PRODUCTS["clouddrive2"].install_dir)])

    def test_purge_all_includes_known_proxy_children_but_never_lock_files_or_backups(self):
        with patch.object(uninstall, "purge_preflight"):
            uninstall.execute(uninstall.build_plan(tuple(PRODUCTS), self.docker, purge_data=True), self.docker, self.log)
        deleted = {call.args[0] for call in self.deleted.call_args_list}
        expected = {Path(product.install_dir) for product in PRODUCTS.values()} | {Path(uninstall.PROXY_ROOT) / child for child in uninstall.PROXY_CHILDREN}
        self.assertEqual(deleted, expected)
        self.assertNotIn(Path(uninstall.PROXY_ROOT), deleted)
        self.assertFalse(any("backup" in str(path) or "lock" in str(path) for path in deleted))

    def test_purge_not_executed_when_network_removal_fails(self):
        self.docker.fail_network = True
        with patch.object(uninstall, "purge_preflight"), self.assertRaises(uninstall.UninstallError):
            uninstall.execute(uninstall.build_plan(("clouddrive2",), self.docker, purge_data=True), self.docker, self.log)
        self.deleted.assert_not_called()

    def test_full_cleanup_includes_selected_backups_but_preserves_other_edition(self):
        root = Path(PRODUCTS["clouddrive2"].backup_dir)
        identity = (1, 2, 3, 0, ())
        with patch.object(uninstall, "purge_preflight"), patch.object(uninstall, "backup_identity", return_value=identity):
            plan = uninstall.build_plan(("clouddrive2",), self.docker, purge_backups=True)
            uninstall.execute(plan, self.docker, self.log)
        self.assertTrue(plan.purge_data)
        self.assertTrue(plan.purge_backups)
        self.assertEqual(set(plan.backups), {root})
        self.assertEqual({call.args[0] for call in self.deleted.call_args_list},
                         {root, Path(PRODUCTS["clouddrive2"].install_dir)})
        self.assertIn(PRODUCTS["openlist"].bot_container, self.docker.containers)

    def test_full_cleanup_all_deletes_generated_backups_and_shared_certificate_children(self):
        with patch.object(uninstall, "purge_preflight"), patch.object(uninstall, "backup_identity", return_value=(1, 2, 3, 0, ())):
            plan = uninstall.build_plan(tuple(PRODUCTS), self.docker, purge_backups=True)
            uninstall.execute(plan, self.docker, self.log)
        expected = {Path(product.install_dir) for product in PRODUCTS.values()}
        expected.update(Path(product.backup_dir) for product in PRODUCTS.values())
        expected.add(uninstall.PROXY_BACKUP_ROOT)
        expected.update(Path(uninstall.PROXY_ROOT) / child for child in uninstall.PROXY_CHILDREN)
        self.assertEqual({call.args[0] for call in self.deleted.call_args_list}, expected)
        self.assertFalse(any("lock" in str(call.args[0]) for call in self.deleted.call_args_list))
        self.assertEqual(set(self.docker.containers), {"unrelated-nginx"})

    def test_backup_change_after_confirmation_aborts_before_runtime_mutation(self):
        identity = Mock(return_value=(1, 2, 3, 0, ()))
        with patch.object(uninstall, "purge_preflight"), patch.object(uninstall, "backup_identity", identity):
            plan = uninstall.build_plan(("clouddrive2",), self.docker, purge_backups=True)
            identity.return_value = (1, 2, 3, 0, ("NEW BACKUP",))
            with self.assertRaisesRegex(uninstall.UninstallError, "变化"):
                uninstall.execute(plan, self.docker, self.log)
        self.assertEqual(self.docker.commands, [])
        self.deleted.assert_not_called()

    def test_backup_change_during_runtime_removal_aborts_all_data_deletion(self):
        with patch.object(uninstall, "purge_preflight"), patch.object(uninstall, "backup_identity", side_effect=[None, None, (1, 2, 3, 0, ())]):
            plan = uninstall.build_plan(("clouddrive2",), self.docker, purge_backups=True)
            with self.assertRaisesRegex(uninstall.UninstallError, "备份范围或内容"):
                uninstall.execute(plan, self.docker, self.log)
        self.assertTrue(self.docker.commands)
        self.deleted.assert_not_called()


class DataSafetyTests(unittest.TestCase):
    def test_backup_metadata_only_allows_generated_regular_private_files(self):
        patterns = uninstall.backup_targets(tuple(PRODUCTS), {}, True)
        for standard, pattern in patterns.items():
            with self.subTest(root=standard), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o700)
                name = ("proxy-20261011T120000Z-" + "a" * 32 + ".tar.gz"
                        if standard == uninstall.PROXY_BACKUP_ROOT else "config-abCD1234.tar.gz")
                archive = root / name
                archive.touch(mode=0o600)
                with patch.object(Path, "read_text", side_effect=AssertionError("must not read secrets")):
                    identity = uninstall.backup_identity(root, pattern)
                self.assertEqual(identity[-1][0][0], name)
                (root / "personal-notes.txt").touch(mode=0o600)
                with self.assertRaisesRegex(uninstall.UninstallError, "未知文件"):
                    uninstall.backup_identity(root, pattern)

    def test_backup_nested_directory_and_symlink_are_never_adopted(self):
        pattern = next(iter(uninstall.backup_targets(("clouddrive2",), {}, False).values()))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            root.chmod(0o700)
            (root / "config-abCD1234.tar.gz").mkdir()
            with self.assertRaisesRegex(uninstall.UninstallError, "未知文件"):
                uninstall.backup_identity(root, pattern)
        if os.name == "posix":
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o700)
                (root / "config-abCD1234.tar.gz").symlink_to("/etc/passwd")
                with self.assertRaisesRegex(uninstall.UninstallError, "链接"):
                    uninstall.backup_identity(root, pattern)

    def test_backup_mount_or_foreign_parent_reference_blocks_purge(self):
        root = Path(PRODUCTS["clouddrive2"].backup_dir)
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(root,)), self.assertRaisesRegex(uninstall.UninstallError, "挂载点"):
            uninstall.purge_preflight(("clouddrive2",), {}, {}, False, (root,))
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(Path("/"),)):
            containers = {"foreign": {"mounts": [{"Source": str(root.parent), "Type": "bind"}]}}
            with self.assertRaisesRegex(uninstall.UninstallError, "其他容器"):
                uninstall.purge_preflight(("clouddrive2",), containers, {}, False, (root,))

    def test_shared_certificates_and_backups_kept_for_retained_other_edition_data(self):
        retained = Path(PRODUCTS["openlist"].install_dir)
        with patch.object(Path, "exists", lambda path: path == retained):
            self.assertTrue(uninstall.other_edition_present(("clouddrive2",), {}))
            self.assertNotIn(uninstall.PROXY_BACKUP_ROOT, uninstall.backup_targets(("clouddrive2",), {}, True))
            with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(Path(uninstall.PROXY_ROOT),)):
                uninstall.purge_preflight(("clouddrive2",), {}, {}, True)

    def test_backup_patterns_are_edition_specific_and_do_not_match_foreign_files(self):
        patterns = uninstall.backup_targets(tuple(PRODUCTS), {}, True)
        cd2 = patterns[Path(PRODUCTS["clouddrive2"].backup_dir)]
        openlist = patterns[Path(PRODUCTS["openlist"].backup_dir)]
        self.assertIsNone(cd2.fullmatch("openlist-state-12345678.tar.gz"))
        self.assertIsNotNone(openlist.fullmatch("openlist-state-12345678.tar.gz"))
        for name in ("config-custom.tar.gz", "../../config-12345678.tar.gz", "database-12345678.db-journal", "personal.zip"):
            self.assertIsNone(cd2.fullmatch(name))

    @unittest.skipUnless(os.name == "posix", "Linux private ownership and safe directory removal")
    def test_full_cleanup_real_temporary_directories_not_real_docker_or_vps(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            products = {}
            for key, product in PRODUCTS.items():
                products[key] = replace(product, install_dir=str(base / key), backup_dir=str(base / (key + "-backups")))
                Path(products[key].install_dir).mkdir(mode=0o700)
                backup = Path(products[key].backup_dir)
                backup.mkdir(mode=0o700)
                (backup / "config-abCD1234.tar.gz").touch(mode=0o600)
            proxy = base / "proxy"
            proxy.mkdir(mode=0o700)
            (proxy / "transaction.lock").touch(mode=0o600)
            proxy_backup = base / "proxy-backups"
            proxy_backup.mkdir(mode=0o700)
            (proxy_backup / ("proxy-20261011T120000Z-" + "a" * 32 + ".tar.gz")).touch(mode=0o600)
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("KEEP", encoding="utf-8")
            with patch.dict(uninstall.PRODUCTS, products), patch.object(uninstall, "PROXY_ROOT", str(proxy)), patch.object(uninstall, "PROXY_BACKUP_ROOT", proxy_backup), patch.object(uninstall, "LAN_ROOT", base / "lan"), patch.object(uninstall, "LOCK_ROOT", base / "locks"), patch.object(uninstall, "mountpoints", return_value=(Path("/"),)), patch.object(uninstall, "edition_lock", return_value=nullcontext()):
                docker = FakeDocker()
                with patch.object(uninstall, "docker_snapshot", side_effect=docker.snapshot):
                    plan = uninstall.build_plan(tuple(products), docker, purge_backups=True)
                    uninstall.execute(plan, docker, SafeLog(lambda _message: None))
            for product in products.values():
                self.assertFalse(Path(product.install_dir).exists())
                self.assertFalse(Path(product.backup_dir).exists())
            self.assertFalse(proxy_backup.exists())
            self.assertTrue((proxy / "transaction.lock").exists())
            self.assertEqual((foreign / "keep.txt").read_text(encoding="utf-8"), "KEEP")
            self.assertEqual(set(docker.containers), {"unrelated-nginx"})

    def test_residual_purge_requires_recognizable_compose_and_does_not_adopt_unknown_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            product = replace(PRODUCTS["clouddrive2"], install_dir=str(root))
            session = Mock()
            with patch.dict(uninstall.PRODUCTS, {"clouddrive2": product}), patch.object(uninstall, "LAN_ROOT", root / "lan"), patch.object(uninstall, "read_state", return_value=uninstall.empty_state()), patch.object(uninstall, "docker_snapshot", return_value=({}, {})), patch.object(uninstall, "purge_preflight"):
                with self.assertRaisesRegex(uninstall.UninstallError, "残留目录"):
                    uninstall.build_plan(("clouddrive2",), session, purge_data=True)
                source = root / "docker-compose.yml"
                source.write_text("services:\n  foreign:\n    container_name: foreign\n", encoding="utf-8")
                with self.assertRaisesRegex(uninstall.UninstallError, "标准 payload"):
                    uninstall.build_plan(("clouddrive2",), session, purge_data=True)
                source.write_text("services:\n  bot:\n    container_name: " + product.bot_container
                                  + "\n  gateway:\n    container_name: " + product.storage_container + "\n", encoding="utf-8")
                plan = uninstall.build_plan(("clouddrive2",), session, purge_data=True)
                self.assertTrue(plan.purge_data)
                self.assertEqual(plan.containers, {})

    def test_child_symlink_is_not_followed_and_targets_require_exact_allowlist(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "owned"
            root.mkdir()
            outside = base / "foreign"
            outside.mkdir()
            (outside / "keep.txt").write_text("KEEP", encoding="utf-8")
            with self.assertRaises(uninstall.UninstallError):
                uninstall.delete_tree(base, {root})
            with patch.object(uninstall, "mountpoints", return_value=(root,)), self.assertRaises(uninstall.UninstallError):
                uninstall.delete_tree(root, {root})
            self.assertTrue(root.exists())
            if os.name == "posix":
                (root / "link").symlink_to(outside, target_is_directory=True)
                with patch.object(uninstall, "mountpoints", return_value=(Path("/"),)):
                    uninstall.delete_tree(root, {root})
                self.assertFalse(root.exists())
                self.assertEqual((outside / "keep.txt").read_text(encoding="utf-8"), "KEEP")

    @unittest.skipUnless(os.name == "posix", "Linux symlink/ownership semantics")
    def test_linked_root_and_parent_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real = base / "real"
            real.mkdir()
            link = base / "link"
            link.symlink_to(real, target_is_directory=True)
            for path in (link, link / "subdir"):
                with self.subTest(path=path), self.assertRaises(uninstall.UninstallError):
                    uninstall.checked_path(path)

    def test_mountinfo_octals_and_cloud_mount_descendants(self):
        data = "1 2 0:1 / / rw - ext4 /dev/test rw\n2 1 0:2 / /opt/tg2cloud-clouddrive2/clouddrive/mounts/Cloud\\040Disk rw - fuse cloud rw\n"
        with patch.object(Path, "read_text", return_value=data):
            points = uninstall.mountpoints()
        self.assertEqual(str(points[1]).replace("\\", "/"), "/opt/tg2cloud-clouddrive2/clouddrive/mounts/Cloud Disk")
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=points), self.assertRaisesRegex(uninstall.UninstallError, "挂载点"):
            uninstall.purge_preflight(("clouddrive2",), {}, {}, False)
        for invalid in ("", "broken line"):
            with patch.object(Path, "read_text", return_value=invalid), self.assertRaises(uninstall.UninstallError):
                uninstall.mountpoints()

    def test_shared_certificate_data_kept_while_other_edition_container_exists(self):
        docker = FakeDocker()
        points = (Path(PRODUCTS["openlist"].install_dir), Path(uninstall.PROXY_ROOT))
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=points):
            uninstall.purge_preflight(("clouddrive2",), docker.containers,
                                      {PRODUCTS["clouddrive2"].bot_container: {}, PRODUCTS["clouddrive2"].storage_container: {}}, True)

    def test_foreign_container_using_data_prevents_purge(self):
        containers = {"foreign": {"mounts": [{"Source": str(Path(PRODUCTS["clouddrive2"].install_dir) / "data")}]}}
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(Path("/"),)), self.assertRaisesRegex(uninstall.UninstallError, "其他容器"):
            uninstall.purge_preflight(("clouddrive2",), containers, {}, False)

    def test_foreign_parent_bind_mount_prevents_data_or_lan_subtree_removal(self):
        root = Path(PRODUCTS["clouddrive2"].install_dir)
        for source in (root, root / "data", root.parent, Path("/")):
            containers = {"foreign": {"mounts": [{"Source": str(source)}]}}
            with self.subTest(source=source), patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(Path("/"),)), self.assertRaisesRegex(uninstall.UninstallError, "其他容器"):
                uninstall.purge_preflight(("clouddrive2",), containers, {}, False)
        self.assertTrue(uninstall.mount_overlaps({"mounts": [{"Source": str(uninstall.LAN_ROOT)}]}, uninstall.LAN_ROOT / "openlist"))
        self.assertFalse(uninstall.mount_overlaps({"mounts": [{"Source": "/srv/unrelated"}]}, root))
        with self.assertRaises(uninstall.UninstallError):
            uninstall.mount_overlaps({"mounts": [{}]}, root)

    def test_foreign_tmpfs_is_not_a_host_data_reference(self):
        root = Path(PRODUCTS["clouddrive2"].install_dir)
        foreign = {"mounts": [{"Type": "tmpfs", "Source": "", "Destination": "/tmp"},
                              {"Type": "bind", "Source": "/srv/unrelated", "Destination": "/data"}]}
        self.assertFalse(uninstall.mount_overlaps(foreign, root))
        with patch.object(uninstall, "checked_path"), patch.object(uninstall, "mountpoints", return_value=(Path("/"),)):
            uninstall.purge_preflight(("clouddrive2",), {"foreign": foreign}, {}, False)
        foreign["mounts"].append({"Type": "bind", "Source": str(root.parent), "Destination": "/opt"})
        self.assertTrue(uninstall.mount_overlaps(foreign, root))

    def test_empty_proxy_lock_root_is_valid_but_unknown_files_are_not_adopted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "transaction.lock").touch()
            with patch.object(uninstall, "PROXY_ROOT", str(root)):
                self.assertEqual(uninstall.read_state(), uninstall.empty_state())
                (root / "unknown.conf").touch()
                with self.assertRaisesRegex(uninstall.UninstallError, "缺少状态"):
                    uninstall.read_state()


class EntryTests(unittest.TestCase):
    def run_main(self, args, *, confirm=True, typed="", failure=None):
        output = io.StringIO()
        docker = FakeDocker()
        plan = uninstall.Plan(tuple(PRODUCTS), {}, {}, uninstall.empty_state(), True,
                              "--keep-data" not in args, "--purge-data" not in args and "--keep-data" not in args)
        ui = Mock()
        ui.confirm.return_value = confirm
        ui.ask.return_value = typed
        with patch.object(uninstall, "SafeLog", return_value=SafeLog(output.write)), patch.object(uninstall, "LocalSession", return_value=docker), patch.object(uninstall, "validate_environment"), patch.object(uninstall, "build_plan", return_value=plan), patch.object(uninstall.vps, "Terminal", return_value=ui), patch.object(uninstall, "execute", side_effect=failure) as execute:
            code = uninstall.main(args)
        return code, output.getvalue(), execute, ui

    def test_check_does_not_prompt_or_execute_even_with_purge_flag(self):
        code, output, execute, ui = self.run_main(["--edition", "all", "--check", "--purge-data"])
        self.assertEqual(code, 0)
        self.assertIn("TG2CLOUD_UNINSTALL_CHECK=OK", output)
        execute.assert_not_called()
        ui.confirm.assert_not_called()

    def test_cancel_and_wrong_delete_token_leave_resources_untouched(self):
        for args, confirmed, typed in ((["--edition", "all"], False, ""), (["--edition", "all", "--purge-data"], True, "DELETE openlist")):
            with self.subTest(args=args):
                code, output, execute, ui = self.run_main(args, confirm=confirmed, typed=typed)
                self.assertEqual(code, 0)
                self.assertIn("CANCELLED", output)
                execute.assert_not_called()
                ui.close.assert_called_once()

    def test_purge_requires_both_confirmations_and_success_only_after_execute(self):
        code, output, execute, ui = self.run_main(["--edition", "all", "--purge-data"], typed="DELETE all")
        self.assertEqual(code, 0)
        execute.assert_called_once()
        ui.confirm.assert_called_once()
        ui.ask.assert_called_once()
        self.assertIn("RESULT=OK", output)

    def test_default_full_cleanup_requires_typed_all_deletion_confirmation(self):
        for args in (["--edition", "all"], ["--edition", "all", "--purge-all"]):
            with self.subTest(args=args):
                code, output, execute, ui = self.run_main(args, typed="DELETE ALL all")
                self.assertEqual(code, 0)
                execute.assert_called_once()
                self.assertTrue(execute.call_args.args[0].purge_backups)
                ui.ask.assert_called_once()
                self.assertIn("历史备份也删除", output)

    def test_default_full_cleanup_wrong_token_does_not_execute(self):
        for token in ("", "DELETE all", "DELETE ALL openlist"):
            code, output, execute, _ui = self.run_main(["--edition", "all"], typed=token)
            self.assertEqual(code, 0)
            self.assertIn("CANCELLED", output)
            execute.assert_not_called()

    def test_keep_data_preserves_prior_runtime_only_behavior(self):
        code, output, execute, ui = self.run_main(["--edition", "all", "--keep-data"])
        self.assertEqual(code, 0)
        execute.assert_called_once()
        self.assertFalse(execute.call_args.args[0].purge_data)
        ui.ask.assert_not_called()
        self.assertIn("--keep-data 保留", output)

    def test_default_full_check_is_read_only_without_prompts(self):
        code, output, execute, ui = self.run_main(["--edition", "all", "--check"])
        self.assertEqual(code, 0)
        execute.assert_not_called()
        ui.confirm.assert_not_called()
        ui.ask.assert_not_called()
        self.assertIn("只是预检", output)

    def test_failure_and_interruption_never_show_success_or_raw_secret(self):
        for failure, expected in ((RuntimeError("FAKE_OFFLINE_SECRET"), 1), (KeyboardInterrupt(), 130), (EOFError(), 130)):
            with self.subTest(error=type(failure).__name__):
                code, output, execute, _ui = self.run_main(["--edition", "all", "--keep-data"], failure=failure)
                self.assertEqual(code, expected)
                self.assertNotIn("RESULT=OK", output)
                self.assertNotIn("FAKE_OFFLINE_SECRET", output)
                execute.assert_called_once()

    def test_environment_rejects_remote_daemon_without_system_mutation(self):
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "COMPOSE_FILE", "COMPOSE_PROJECT_NAME"):
            session = Mock()
            with patch.object(uninstall.vps, "validate_host"), patch.dict(os.environ, {key: "external"}, clear=True), self.assertRaises(uninstall.UninstallError):
                uninstall.validate_environment(session)
            session.run.assert_not_called()
        session = Mock()
        session.run.return_value = (0, '"tcp://external:2375"')
        with patch.object(uninstall.vps, "validate_host"), patch.dict(os.environ, {}, clear=True), self.assertRaises(uninstall.UninstallError):
            uninstall.validate_environment(session)

    def test_inventory_filters_env_and_reports_daemon_failure(self):
        session = Mock()
        item = container(PRODUCTS["clouddrive2"])
        session.run.side_effect = [(0, item["id"] + "\n"), (0, json.dumps(item) + "\n"), (0, "")]
        containers, networks = uninstall.docker_snapshot(session)
        self.assertEqual(set(containers), {PRODUCTS["clouddrive2"].storage_container})
        self.assertEqual(networks, {})
        self.assertFalse(any(".Config.Env" in call.args[0] or "docker logs" in call.args[0] for call in session.run.call_args_list))
        session.run.side_effect = [(1, "FAKE_OFFLINE_SECRET")]
        with self.assertRaises(uninstall.UninstallError):
            uninstall.docker_snapshot(session)

    def test_no_package_removal_prune_remote_operations_or_broad_delete_commands(self):
        source = (ROOT / "scripts/uninstaller.py").read_text(encoding="utf-8")
        for forbidden in ("apt-get", "apt remove", "apt purge", "systemctl", "docker system prune", "docker volume prune", "docker network prune", "docker image rm", "rm -rf", "SSHSession", "requests", "paramiko"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("PySide6", source)
        bootstrap = (ROOT / "uninstall.sh").read_text(encoding="utf-8")
        pin = re.search(r'^installer_commit="([^"]*)"$', bootstrap, re.MULTILINE)
        self.assertIsNotNone(pin)
        self.assertTrue(pin[1] == "" or re.fullmatch(r"[0-9a-f]{40}", pin[1]))
        self.assertIn("scripts/uninstaller.py", bootstrap)
        self.assertIn("python3 -B -m scripts.uninstaller", bootstrap)
        self.assertIn("tg2cloud-uninstall-bootstrap", bootstrap)
        self.assertNotIn("payload_openlist/remote_install.sh", bootstrap)
        self.assertTrue(re.search(r"installer_commit=", bootstrap))


if __name__ == "__main__":
    unittest.main()
