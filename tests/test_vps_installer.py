"""Offline boundary tests: no VPS, Docker daemon, Telegram or cloud requests."""

from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from deployer_products import PRODUCTS
from domain_proxy import ProxyEnvironment, ProxyReport
from scripts import vps_installer as cli
from scripts.vps_runtime import LocalFiles, LocalSession, SafeLog, edition_lock
from vps_resources import StorageAssessment

ROOT = Path(__file__).resolve().parents[1]
RELEASE = cli.Release("v1.1.3", "a" * 40)
VALUES = {
    "api_id": "123456", "user_id": "123456789", "api_hash": "a" * 32,
    "bot_token": "123456789:FAKE_LOCAL_TEST_VALUE_NOT_A_REAL_TOKEN",
    "webdav_user": "tg2cloud", "webdav_password": "FAKE $() #@ secret", "target": "Telegram",
    "budget": "20", "reserve": "8", "timezone": "Asia/Shanghai", "admin_password": "FAKE_ADMIN_SECRET",
}


def report(state="healthy", domain="files.example.test"):
    return ProxyReport(domain, state, "local test report", ())


class ApiTests(unittest.TestCase):
    def client(self, *, tag="v1.1.3", draft=False, prerelease=False):
        client = cli.ReleaseClient()
        client.json = Mock(side_effect=[
            {"tag_name": tag, "draft": draft, "prerelease": prerelease},
            {"object": {"type": "commit", "sha": RELEASE.commit}},
        ])
        return client

    def test_latest_pins_commit_not_main(self):
        client = self.client()
        self.assertEqual(client.resolve(), RELEASE)
        self.assertEqual(client.json.call_args_list[0].args[0], cli.API + "/releases/latest")
        self.assertEqual(client.json.call_args_list[1].args[0], cli.API + "/git/ref/tags/v1.1.3")

    def test_reject_rc_draft_and_nonsemver(self):
        for kwargs in ({"tag": "v1.1.3-rc.1"}, {"draft": True}, {"prerelease": True}, {"tag": "main"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.client(**kwargs).resolve()

    def test_specific_tag_cannot_select_prerelease(self):
        with self.assertRaises(ValueError):
            self.client().resolve("v1.1.3-rc.1")

    def test_tag_mismatch_and_invalid_sha(self):
        with self.assertRaises(ValueError):
            self.client().resolve("v1.1.2")
        client = self.client()
        client.json.side_effect = [
            {"tag_name": RELEASE.tag, "draft": False, "prerelease": False},
            {"object": {"type": "commit", "sha": "main"}},
        ]
        with self.assertRaises(ValueError):
            client.resolve()

    def test_annotated_tag_is_peeled(self):
        client = self.client()
        client.json.side_effect = [
            {"tag_name": RELEASE.tag, "draft": False, "prerelease": False},
            {"object": {"type": "tag", "sha": "b" * 40}},
            {"object": {"type": "commit", "sha": RELEASE.commit}},
        ]
        self.assertEqual(client.resolve(), RELEASE)

    def test_download_checks_source_version_without_execution(self):
        with tempfile.TemporaryDirectory() as private:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                info = tarfile.TarInfo("repo/app/version.py")
                content = b'VERSION="9.9.9"\n'
                info.name = "repo/payload_clouddrive2/app/version.py"
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            with patch.object(cli, "open_public", return_value=io.BytesIO(data.getvalue())), self.assertRaisesRegex(ValueError, "Tag"):
                cli.ReleaseClient().download(RELEASE, Path(private))

    def test_only_public_https_urls_including_redirects(self):
        cli.validate_public_url(cli.API + "/releases/latest")
        for url in ("file:///etc/passwd", "http://api.github.com/x", "https://api.github.com.evil/x", "https://user:secret@api.github.com/x", "https://api.github.com:8443/x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                cli.validate_public_url(url)
        with self.assertRaises(ValueError):
            cli.PublicRedirect().redirect_request(None, None, 302, "", {}, "http://api.github.com/x")


class ArchiveTests(unittest.TestCase):
    def extract(self, members):
        with tempfile.TemporaryDirectory() as private:
            archive = Path(private) / "source.tar.gz"
            with tarfile.open(archive, "w:gz") as writer:
                for name, kind in members:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    info.linkname = "/etc/passwd"
                    content = b"test"
                    info.size = len(content) if kind == tarfile.REGTYPE else 0
                    writer.addfile(info, io.BytesIO(content) if info.size else None)
            cli.extract_source(archive, Path(private) / "source")

    def test_normal_source(self):
        self.extract([("repo/app/version.py", tarfile.REGTYPE)])

    def test_unsafe_paths_and_types(self):
        for name, kind in (("repo/../../escape", tarfile.REGTYPE), ("/tmp/escape", tarfile.REGTYPE),
                           ("repo/link", tarfile.SYMTYPE), ("repo/hard", tarfile.LNKTYPE),
                           ("repo/device", tarfile.CHRTYPE), ("repo\\escape", tarfile.REGTYPE)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.extract([(name, kind)])

    def test_duplicate_and_two_roots(self):
        for names in (("repo/a", "repo/a"), ("repo/a", "other/b")):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.extract([(name, tarfile.REGTYPE) for name in names])


class VersionSourceTests(unittest.TestCase):
    def read_version(self, legacy, current=None):
        with tempfile.TemporaryDirectory() as private:
            root = Path(private).resolve()
            (root / "app").mkdir()
            (root / "app/__init__.py").write_text(legacy, encoding="utf-8")
            if current is not None:
                (root / "app/version.py").write_text(current, encoding="utf-8")
            return cli.source_version(root)

    def test_published_legacy_literal_without_execution(self):
        self.assertEqual(self.read_version('__version__ = "1.0.2"\nraise RuntimeError("not executed")'), "1.0.2")

    def test_new_version_source_takes_precedence(self):
        self.assertEqual(self.read_version('__version__ = "1.0.2"', 'VERSION = "1.1.2"'), "1.1.2")

    def test_invalid_new_source_never_falls_back(self):
        for current in ('', 'VERSION = "bad"', 'VERSION = "1.1.2"\nVERSION = "1.1.3"', 'VERSION = "1.1.2-rc.1"'):
            with self.subTest(current=current), self.assertRaises(ValueError):
                self.read_version('__version__ = "1.0.2"', current)

    def test_legacy_dynamic_duplicate_or_nonstable_version_rejected(self):
        for legacy in ('__version__ = get_version()', '__version__ = "1.0.2"\n__version__ = "1.0.3"',
                       '__version__ = "1.0.2-rc.1"', 'VERSION = "1.0.2"'):
            with self.subTest(legacy=legacy), self.assertRaises(ValueError):
                self.read_version(legacy)

    def test_legacy_baseline_still_requires_exact_official_payload(self):
        with tempfile.TemporaryDirectory() as private:
            root = Path(private).resolve()
            source = root / "official"
            shutil.copytree(ROOT / "payload_clouddrive2", source / "payload_clouddrive2",
                            ignore=shutil.ignore_patterns("__pycache__"))
            payload = source / "payload_clouddrive2"
            (payload / "app/version.py").unlink()
            (payload / "app/__init__.py").write_text('__version__ = "1.0.2"\n', encoding="utf-8")
            destination = root / "installed"
            shutil.copytree(payload, destination)
            instance = cli.Instance(PRODUCTS["clouddrive2"], destination, True, "1.0.2")
            cli.assert_unmodified(instance, source)
            (destination / "app/main.py").write_text("# custom code\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "已发布版本不一致"):
                cli.assert_unmodified(instance, source)


class ConfigPayloadTests(unittest.TestCase):
    def test_payloads_are_assembled_from_existing_manifest(self):
        for product in PRODUCTS.values():
            with self.subTest(edition=product.key), tempfile.TemporaryDirectory() as private:
                dest = Path(private) / "payload"
                cli.build_payload(ROOT, product, dest)
                for name, source in cli.payload_sources(ROOT, product).items():
                    self.assertEqual((dest / name).read_bytes(), source.read_bytes())
                self.assertTrue((dest / "LICENSE").is_file())
                self.assertFalse((dest / "tg2cloud-release.json").exists())
                self.assertEqual(cli.source_version(dest), product.app_version)

    def test_missing_resource_stops(self):
        with tempfile.TemporaryDirectory() as private, self.assertRaises(ValueError):
            cli.payload_sources(Path(private), PRODUCTS["openlist"])

    def test_config_matches_existing_gui_without_importing_qt(self):
        tree = ast.parse((ROOT / "installer.py").read_text(encoding="utf-8"))
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_build_config")
        namespace = {"b64": cli.encoded}
        module = ast.Module(body=[function], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<existing-config-contract>", "exec"), namespace)  # noqa: S102 - trusted repository AST, no external input
        gui_values = {
            "telegram_api_id": VALUES["api_id"], "telegram_api_hash": VALUES["api_hash"],
            "bot_token": VALUES["bot_token"], "allowed_user_id": VALUES["user_id"],
            "cd2_username": VALUES["webdav_user"], "cd2_password": VALUES["webdav_password"],
            "cd2_target": VALUES["target"], "local_budget_gb": VALUES["budget"],
            "min_free_disk_gb": VALUES["reserve"], "timezone": VALUES["timezone"],
            "deploy_clouddrive2": "true", "openlist_admin_password": VALUES["admin_password"],
        }
        for product in PRODUCTS.values():
            fake = SimpleNamespace(product=product, _effective_webdav_url=lambda _values, product=product: product.webdav_url)
            expected = cli.parse_config(namespace["_build_config"](fake, gui_values).encode())
            self.assertEqual(cli.new_config(product, VALUES), expected)

    def test_shell_characters_in_password_stay_encoded(self):
        config = cli.new_config(PRODUCTS["openlist"], VALUES)
        self.assertEqual(base64.b64decode(config["WEBDAV_PASSWORD_B64"]).decode(), VALUES["webdav_password"])
        self.assertNotIn(VALUES["webdav_password"], "\n".join(config.values()))

    def test_duplicate_config_and_invalid_cover_flag_rejected(self):
        for raw in (b"A=1\nA=2\n", b"export A=1", b"TG2CLOUD_REDEPLOY_APPLY_CONFIG=maybe"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                cli.parse_config(raw)
        self.assertEqual(cli.parse_config(b"A=$(touch /tmp/not-executed)\r\n"), {"A": "$(touch /tmp/not-executed)"})

    def test_logging_redacts_plain_encoded_and_unregistered_tokens(self):
        log = SafeLog()
        log.register(cli.new_config(PRODUCTS["openlist"], VALUES))
        text = "\n".join(VALUES[key] for key in ("api_hash", "bot_token", "webdav_password", "admin_password"))
        text += "\n" + cli.encoded(VALUES["webdav_password"]) + "\nhttps://user:UNKNOWN@host/\nPassword=UNKNOWN\nCookie: UNKNOWN"
        text += '\n{"access_token":"UNKNOWN","cookie":"UNKNOWN"}'
        result = log.clean(text)
        self.assertNotIn("UNKNOWN", result)
        for key in ("api_hash", "bot_token", "webdav_password", "admin_password"):
            self.assertNotIn(VALUES[key], result)

    def test_numeric_and_control_validators(self):
        for value in ("0", "-1", "$(id)"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cli.positive(value)
        for value in ("nan", "inf", "-1", "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cli.size_gb(value)
        with self.assertRaises(ValueError):
            cli.plain("password\nINJECTION=true")

    def test_install_paths_cannot_overlap_another_component(self):
        product = PRODUCTS["clouddrive2"]
        cli.check_product_directory(product, Path(product.install_dir))
        for path in ("/opt/tg2cloud-proxy", "/opt/tg2cloud-proxy/child", "/opt/tg2cloud-openlist", "/opt/tg2cloud-clouddrive2-backups", "/opt/tg115"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                cli.check_product_directory(product, Path(path))

    def test_foreign_cd2_repair_candidates_cannot_be_adopted(self):
        product = PRODUCTS["clouddrive2"]
        session = Mock()
        for listing in ("my-clouddrive2 unrelated/image:latest", "other vendor/clouddrive2@sha256:abc"):
            session.run.return_value = (0, listing)
            with self.subTest(listing=listing), self.assertRaisesRegex(ValueError, "其他 CloudDrive2"):
                cli.check_foreign_gateway(product, session)
        session.run.return_value = (0, product.bot_container + " bot-image\n" + product.storage_container + " cloudnas/clouddrive2@sha256:abc")
        cli.check_foreign_gateway(product, session)


class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        # Windows hosted runners may expose TEMP through an 8.3 alias or a
        # junction. Canonicalize fixtures, not the production fail-closed checks.
        self.directory = Path(self.private.name).resolve() / "install"
        self.product = PRODUCTS["openlist"]
        cli.build_payload(ROOT, self.product, self.directory)
        for name in ("data", "config", "downloads", "logs", "openlist/data"):
            (self.directory / name).mkdir(parents=True)
        self.raw = ("# retained comment\r\n" + "\r\n".join(k + "=" + v for k, v in cli.new_config(self.product, VALUES).items()) + "\r\n").encode()
        (self.directory / ".env").write_bytes(self.raw)
        (self.directory / ".env").chmod(0o600)
        self.instance = cli.Instance(self.product, self.directory, True, self.product.app_version,
                                     False, cli.gateway_image(ROOT, self.product), cli.parse_config(self.raw), self.raw)
        self.log = SafeLog(lambda _text: None)

    def test_current_newer_upgrade_and_major_boundaries(self):
        self.assertEqual(cli.action_for(self.instance, RELEASE), "upgrade")
        self.assertEqual(cli.action_for(self.instance, cli.Release("v" + self.instance.version, "b" * 40)), "current")
        self.assertEqual(cli.action_for(self.instance, cli.Release("v1.0.0", "b" * 40)), "newer")
        with self.assertRaises(ValueError):
            cli.action_for(self.instance, cli.Release("v2.0.0", "b" * 40))

    def test_official_payload_with_crlf_is_not_a_local_edit(self):
        cli.assert_unmodified(self.instance, ROOT)
        path = self.directory / "manage.sh"
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        cli.assert_unmodified(self.instance, ROOT)
        path.write_bytes(path.read_bytes() + b"# LOCAL EDIT\n")
        with self.assertRaisesRegex(ValueError, "manage.sh"):
            cli.assert_unmodified(self.instance, ROOT)

    def test_extra_app_source_is_not_overwritten(self):
        (self.directory / "app/custom.py").write_text("# private extension", encoding="utf-8")
        with self.assertRaises(ValueError):
            cli.assert_unmodified(self.instance, ROOT)

    def test_partial_container_and_orphan_directory_stop(self):
        with patch.object(cli, "checked_directory", return_value=self.directory):
            for inventory in (set(), {self.product.bot_container}, {self.product.storage_container}):
                with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                    cli.discover(self.product, inventory, Mock(), self.log)

    def test_docker_daemon_failure_is_not_fresh_install(self):
        session = Mock()
        session.run.side_effect = [(0, ""), (1, "")]
        with self.assertRaises(RuntimeError):
            cli.docker_inventory(session)

    def containers(self):
        labels = {"com.docker.compose.project.working_dir": str(self.directory),
                  "com.docker.compose.project": "tg2cloud-openlist", "com.docker.compose.service": self.product.bot_service}
        bot = {"labels": labels, "image": "bot", "running": False, "mounts": [
            {"Type": "bind", "Destination": "/" + name, "Source": str(self.directory / name)}
            for name in ("data", "config", "downloads", "logs")
        ]}
        gateway = {"labels": {**labels, "com.docker.compose.service": "openlist"}, "image": self.instance.gateway_image,
                   "mounts": [{"Type": "bind", "Destination": "/opt/openlist/data", "Source": str(self.directory / "openlist/data")}]}
        return bot, gateway

    def discover(self, bot, gateway, actual=None):
        session = Mock()
        services = {self.product.bot_service: {"container_name": self.product.bot_container}, "openlist": {"container_name": self.product.storage_container}}
        session.run.return_value = (0, json.dumps({"services": services}))
        if actual is not None:
            session.run.side_effect = [(0, json.dumps({"services": services})), (0, json.dumps(actual))]
        with patch.object(cli, "checked_directory", return_value=self.directory), patch.object(cli, "inspect_container", side_effect=[bot, gateway]), patch.object(cli, "regular_private", side_effect=lambda path: path.read_bytes()):
            return cli.discover(self.product, {self.product.bot_container, self.product.storage_container}, session, self.log)

    def test_complete_instance_retains_raw_config(self):
        result = self.discover(*self.containers())
        self.assertEqual(result.raw_config, self.raw)
        self.assertNotIn(VALUES["admin_password"], repr(result))
        # CD2's installer normalizes env line endings: refuse before writing.
        self.product = PRODUCTS["clouddrive2"]
        bot, gateway = self.containers()
        gateway["labels"]["com.docker.compose.service"] = "clouddrive2"
        gateway["mounts"] = []
        for destination, relative in (("/Config", "clouddrive/config"), ("/CloudNAS", "clouddrive/mounts")):
            (self.directory / relative).mkdir(parents=True)
            gateway["mounts"].append({"Type": "bind", "Destination": destination, "Source": str(self.directory / relative)})
        with self.assertRaisesRegex(ValueError, "CRLF"):
            self.discover(bot, gateway)

    def test_running_code_fingerprint_is_required(self):
        bot, gateway = self.containers()
        bot["running"] = True
        manifest = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  app/{path.name}\n" for path in sorted((self.directory / "app").glob("*.py")))
        actual = {"version": self.instance.version, "fingerprint": hashlib.sha256(manifest.encode()).hexdigest()}
        self.assertTrue(self.discover(bot, gateway, actual).running)
        actual["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "运行代码"):
            self.discover(bot, gateway, actual)

    def test_foreign_labels_and_gateway_mounts_stop(self):
        bot, gateway = self.containers()
        gateway["mounts"][0]["Source"] = "/opt/other/openlist/data"
        with self.assertRaises(ValueError):
            self.discover(bot, gateway)
        bot, gateway = self.containers()
        gateway["labels"]["com.docker.compose.project"] = "foreign"
        with self.assertRaises(ValueError):
            self.discover(bot, gateway)

    def test_upgrade_does_not_collect_credentials_or_configure_healthy_https(self):
        manager = Mock()
        manager.read_state.return_value = {"domains": {"openlist": {"domain": "files.example.test"}}}
        manager.status.return_value = report()
        ui, session = Mock(), Mock()
        session.run.return_value = (0, "")
        with patch.object(cli, "DomainProxyManager", return_value=manager), patch.object(cli, "resource_check"):
            plan = cli.make_plan(self.instance, RELEASE, ROOT, ROOT, session, self.log, ui)
        ui.ask.assert_not_called()
        manager.configure.assert_not_called()
        self.assertFalse(plan.configure_https)
        self.assertEqual(plan.config, self.instance.config)

    def test_gateway_image_change_is_not_automatic_database_migration(self):
        self.instance.gateway_image = "openlistteam/openlist@sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "网关镜像"), patch.object(cli, "DomainProxyManager") as manager:
            cli.make_plan(self.instance, RELEASE, ROOT, ROOT, Mock(), self.log, Mock())
        manager.assert_not_called()

    def test_upgrade_candidate_contains_only_preserve_flag(self):
        session = Mock()
        seen = []

        def install(command, **kwargs):
            # No credential can be in argv; read only the private candidate path.
            import shlex
            candidate = Path(shlex.split(command)[-1])
            seen.append(candidate.read_text(encoding="utf-8"))
            self.assertNotIn(VALUES["admin_password"], command)
            return 0, "TG2CLOUD_RESULT=SUCCESS\nTG2CLOUD_BOT_HEALTH=healthy\n"

        session.run.side_effect = install
        plan = cli.Plan(self.instance, "upgrade", Mock(), self.instance.config)
        with patch.object(cli, "regular_private", side_effect=lambda path: path.read_bytes()):
            cli.apply_base(plan, RELEASE, ROOT, session, self.log)
        self.assertEqual(seen, ["TG2CLOUD_REDEPLOY_APPLY_CONFIG=false\n"])
        self.assertEqual((self.directory / ".env").read_bytes(), self.raw)
        self.assertEqual(json.loads((self.directory / "tg2cloud-release.json").read_text())["commit"], RELEASE.commit)

    def test_failed_install_does_not_record_new_version(self):
        cli.record_release(self.directory, cli.Release("v1.1.2", "b" * 40))
        session = Mock()
        session.run.return_value = (1, "TG2CLOUD_RESULT=FAILED\n")
        with self.assertRaises(RuntimeError):
            cli.apply_base(cli.Plan(self.instance, "upgrade", Mock()), RELEASE, ROOT, session, self.log)
        self.assertEqual(json.loads((self.directory / "tg2cloud-release.json").read_text())["tag"], "v1.1.2")

    def test_verified_marker_requires_exit_success_and_explicit_confirmation(self):
        ui, session = Mock(), Mock()
        plan = cli.Plan(self.instance, "current", Mock())
        ui.confirm.return_value = False
        self.assertFalse(cli.verify_destination(plan, session, self.log, ui))
        session.run.assert_not_called()
        ui.confirm.return_value = True
        session.run.return_value = (1, "TG2CLOUD_DESTINATION=OK\n")
        with self.assertRaises(RuntimeError):
            cli.verify_destination(plan, session, self.log, ui)
        session.run.return_value = (0, "TG2CLOUD_DESTINATION=OK\n")
        self.assertTrue(cli.verify_destination(plan, session, self.log, ui))

    def test_execute_rechecks_env_before_write(self):
        changed = cli.Instance(self.product, self.directory, True, self.instance.version, raw_config=b"CHANGED=1\n")
        with patch.object(cli, "edition_lock", return_value=nullcontext()), patch.object(cli, "docker_inventory", return_value=set()), patch.object(cli, "discover", return_value=changed), patch.object(cli, "apply_base") as apply, self.assertRaisesRegex(ValueError, "已变更"):
            cli.execute_plan(cli.Plan(self.instance, "upgrade", Mock()), RELEASE, ROOT, ROOT, Mock(), self.log, Mock())
        apply.assert_not_called()

    def test_https_failure_does_not_report_acceptance(self):
        manager = Mock()
        manager.status.return_value = report("running_error")
        with patch.object(cli, "edition_lock", return_value=nullcontext()), patch.object(cli, "docker_inventory", return_value=set()), patch.object(cli, "discover", return_value=self.instance), patch.object(cli, "apply_base"), patch.object(cli, "verify_destination") as verify, self.assertRaisesRegex(RuntimeError, "HTTPS"):
            cli.execute_plan(cli.Plan(self.instance, "upgrade", manager), RELEASE, ROOT, ROOT, Mock(), self.log, Mock(), verify=True)
        verify.assert_not_called()

    def test_main_cancelled_and_readonly_never_mutate(self):
        plan = cli.Plan(self.instance, "upgrade", Mock())
        for args in (["--edition", "openlist"], ["--edition", "openlist", "--check"]):
            ui = Mock()
            ui.confirm.return_value = False
            client = Mock()
            client.resolve.side_effect = [RELEASE, cli.Release("v" + self.instance.version, "b" * 40)]
            client.download.return_value = ROOT
            with self.subTest(args=args), patch.object(cli, "validate_host"), patch.object(cli, "docker_inventory", return_value=set()), patch.object(cli, "discover", return_value=self.instance), patch.object(cli, "ReleaseClient", return_value=client), patch.object(cli, "Terminal", return_value=ui), patch.object(cli, "make_plan", return_value=plan), patch.object(cli, "execute_plan") as execute, patch.object(cli, "SafeLog", return_value=self.log):
                self.assertEqual(cli.main(args), 0)
            execute.assert_not_called()

    def test_wizard_defaults_to_single_detected_edition_not_a_new_install(self):
        ui = Mock()
        ui.ask.return_value = "2"
        ui.confirm.return_value = False
        client = Mock()
        client.resolve.side_effect = [RELEASE, cli.Release("v" + self.instance.version, "b" * 40)]
        client.download.return_value = ROOT
        with patch.object(cli, "validate_host"), patch.object(cli, "docker_inventory", return_value={self.product.bot_container, self.product.storage_container}), patch.object(cli, "discover", return_value=self.instance) as discover, patch.object(cli, "ReleaseClient", return_value=client), patch.object(cli, "Terminal", return_value=ui), patch.object(cli, "make_plan", return_value=cli.Plan(self.instance, "upgrade", Mock())), patch.object(cli, "execute_plan") as execute, patch.object(cli, "SafeLog", return_value=self.log):
            self.assertEqual(cli.main([]), 0)
        self.assertEqual(ui.ask.call_args.kwargs["default"], "2")
        self.assertEqual(discover.call_args.args[0].key, "openlist")
        execute.assert_not_called()

    def test_resource_gate_uses_existing_assessment(self):
        session = Mock()
        session.run.return_value = (0, "probe fixture")
        with patch.object(cli, "build_probe_command", return_value="probe"), patch.object(cli, "parse_probe_output", return_value=Mock()), patch.object(cli, "assess_storage_choice", return_value=StorageAssessment(False, 100, "insufficient")), self.assertRaisesRegex(ValueError, "资源不足"):
            cli.resource_check(self.instance, self.instance.config, session, self.log)

    def test_fresh_config_requires_safe_dns_ports(self):
        fresh = cli.Instance(self.product, self.directory, False)
        manager = Mock()
        manager.read_state.return_value = {"domains": {}}
        manager.status.return_value = report("not_configured", "")
        manager.probe.return_value = ProxyEnvironment("FAILED", "FAILED", "FREE", "FREE", ("203.0.113.10",), (), ("203.0.113.20",))
        ui = Mock()
        ui.ask.side_effect = ["files.example.test", ""]
        session = Mock()
        session.run.return_value = (0, "")
        with patch.object(cli, "DomainProxyManager", return_value=manager), patch.object(cli, "docker_inventory", return_value=set()), self.assertRaisesRegex(ValueError, "DNS"):
            cli.make_plan(fresh, RELEASE, ROOT, None, session, self.log, ui)
        manager.configure.assert_not_called()

    def test_fresh_collects_but_never_installs_before_confirmation(self):
        fresh = cli.Instance(self.product, self.directory, False)
        manager = Mock()
        manager.read_state.return_value = {"domains": {}}
        manager.status.return_value = report("not_configured", "")
        manager.probe.return_value = ProxyEnvironment("FAILED", "FAILED", "FREE", "FREE", ("203.0.113.10",), (), ("203.0.113.10",))
        ui = Mock()
        ui.ask.side_effect = ["files.example.test", ""]
        session = Mock()
        session.run.return_value = (1, "")  # Docker missing on a fresh VPS
        with patch.object(cli, "DomainProxyManager", return_value=manager), patch.object(cli, "docker_inventory", return_value=set()), patch.object(cli, "collect_config", return_value=cli.new_config(self.product, VALUES)), patch.object(cli, "resource_check"), patch.object(cli, "apply_base") as apply:
            plan = cli.make_plan(fresh, RELEASE, ROOT, None, session, self.log, ui)
        self.assertTrue(plan.configure_https)
        self.assertEqual(plan.domain, "files.example.test")
        apply.assert_not_called()
        manager.configure.assert_not_called()

    def test_explicit_https_resume_reuses_domain(self):
        manager = Mock()
        manager.read_state.return_value = {"domains": {"openlist": {"domain": "original.example.test"}}}
        manager.status.return_value = report("running_error", "original.example.test")
        manager.detect.return_value = report("detected", "original.example.test")
        ui = Mock()
        ui.ask.return_value = ""
        current = cli.Release("v" + self.instance.version, "b" * 40)
        with patch.object(cli, "DomainProxyManager", return_value=manager):
            plan = cli.make_plan(self.instance, current, ROOT, ROOT, Mock(), self.log, ui, configure_https=True)
        self.assertEqual(plan.domain, "original.example.test")
        self.assertTrue(plan.configure_https)
        self.assertEqual(ui.ask.call_count, 1)  # optional email only, never a domain switch
        manager.configure.assert_not_called()

    def test_unhealthy_https_blocks_implicit_upgrade(self):
        manager = Mock()
        manager.read_state.return_value = {"domains": {}}
        manager.status.return_value = report("not_configured", "")
        session = Mock()
        session.run.return_value = (0, "")
        with patch.object(cli, "DomainProxyManager", return_value=manager), self.assertRaisesRegex(ValueError, "HTTPS"):
            cli.make_plan(self.instance, RELEASE, ROOT, ROOT, session, self.log, Mock())

    def test_same_version_and_newer_never_call_base_installer(self):
        for action in ("current", "newer"):
            with self.subTest(action=action):
                session = Mock()
                cli.apply_base(cli.Plan(self.instance, action, Mock()), RELEASE, ROOT, session, self.log)
                session.run.assert_not_called()

    def test_linux_permissions_are_checked_before_loading_secrets(self):
        if os.name != "posix":
            self.skipTest("POSIX owner and mode checks")
        path = self.directory / ".env"
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "root"):
            cli.regular_private(path)


class LocalRuntimeTests(unittest.TestCase):
    def test_local_adapter_rejects_arbitrary_sftp_targets(self):
        for path in ("/etc/passwd", "/tmp/unknown/file", "/tmp/tg2cloud-proxy-" + "a" * 32 + "/../escape"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                LocalFiles.validate(path)

    @unittest.skipUnless(os.name == "posix", "Linux flock integration; Windows is not a target VPS")
    def test_edition_lock_is_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as private:
            path = Path(private) / "locks" / "openlist.lock"
            with edition_lock(path), self.assertRaises(RuntimeError), edition_lock(path):
                pass
            with edition_lock(path):
                pass

    def bash(self):
        result = shutil.which("bash")
        if not result and os.name == "nt":
            git = shutil.which("git")
            result = str(Path(git).parents[1] / "bin/bash.exe") if git else None
        if not result:
            self.skipTest("Bash unavailable")
        return result

    def test_stream_redaction_and_exit(self):
        messages = []
        log = SafeLog(messages.append)
        log.register({"BOT_TOKEN_B64": cli.encoded(VALUES["bot_token"])})
        session = LocalSession(log, bash=self.bash())
        code, output = session.run("printf '%s\\n' '" + VALUES["bot_token"] + "'; exit 7", stream=log, timeout=10)
        self.assertEqual(code, 7)
        self.assertIn(VALUES["bot_token"], output)  # private parser output only
        self.assertNotIn(VALUES["bot_token"], "".join(messages))

    @unittest.skipUnless(os.name == "posix", "Linux process-group cancellation")
    def test_timeout_kills_only_own_command(self):
        session = LocalSession(SafeLog(lambda _text: None), bash=self.bash())
        with self.assertRaises(TimeoutError):
            session.run("sleep 30", timeout=0.1)

    def test_entry_bash_syntax(self):
        result = subprocess.run([self.bash(), "-n", str(ROOT / "install.sh")], capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_without_root_or_qt(self):
        import sys
        result = subprocess.run([sys.executable, "-B", "-m", "scripts.vps_installer", "--help"], cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--configure-https", result.stdout)

    def test_existing_build_has_no_cli_dependency(self):
        for name in ("installer.py", "build.ps1", "installer_clouddrive2.py", "installer_openlist.py"):
            self.assertNotIn("scripts.vps_installer", (ROOT / name).read_text(encoding="utf-8"))

    def test_bootstrap_python_is_syntactically_valid(self):
        content = (ROOT / "install.sh").read_text(encoding="utf-8")
        embedded = content.split("<<'PY' &\n", 1)[1].split("\nPY\n", 1)[0]
        ast.parse(embedded)
        self.assertNotIn("/main/", embedded)
        self.assertIn(".bootstrap-release.json", embedded)


if __name__ == "__main__":
    unittest.main()
