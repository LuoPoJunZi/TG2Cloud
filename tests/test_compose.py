"""Offline direct-Compose configuration, ownership and release boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from tg2cloud.compose import packaging, runtime
from tg2cloud.deployment import configuration, instances, uninstall
from tg2cloud.deployment.profiles import PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/luopojunzi/tg2cloud@sha256:" + "a" * 64
spec = importlib.util.spec_from_file_location("compose_release", ROOT / ".github/scripts/compose_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class UI:
    def __init__(self):
        self.questions = []
    def ask(self, prompt, default="", secret=False, validate=configuration.plain):
        self.questions.append(prompt)
        values = {"Telegram API ID": "123456", "Telegram API Hash（隐藏输入）": "a" * 32,
                  "Bot Token（隐藏输入）": "123456789:FAKE_COMPOSE_TOKEN_FOR_TESTS_ONLY",
                  "管理员 Telegram 用户 ID（仅一个）": "123456789"}
        return validate(values.get(prompt, default))
    def confirm(self, _):
        return True
    def private(self, *_):
        pass


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        original = runtime.private_config_file
        def fixture_private(path):
            # Only this temporary fixture represents root-owned files. Real
            # permission rejection remains covered below and by native Docker.
            info = path.stat()
            original(NS(stat=lambda: NS(st_uid=0, st_mode=info.st_mode)))
        permission = patch.object(runtime, "private_config_file", side_effect=fixture_private)
        permission.start()
        self.addCleanup(permission.stop)
        self.private_check = original

    def candidate(self, edition):
        target = self.root / edition
        target.mkdir()
        for name, content in packaging.bundle_files(ROOT, edition, IMAGE).items():
            (target / name).write_bytes(content)
        return target

    def initialize(self, path, ui=None):
        # Filesystem ownership behavior is independently exercised by native Docker CI.
        with patch.object(runtime.shutil, "disk_usage", return_value=NS(free=100 * 1024**3)), patch.object(runtime.os, "chown", create=True):
            return runtime.setup(path, ui or UI())

    def test_two_editions_keep_native_gateway_and_bot_security(self):
        for edition, product in PRODUCTS.items():
            text = packaging.render(ROOT, edition, IMAGE)
            self.assertNotIn("build:", text)
            self.assertEqual(text.count("image: " + IMAGE), 2)
            self.assertIn('user: "10001:10001"', text)
            self.assertIn("network_mode: none", text)
            self.assertIn("com.tg2cloud.install-mode: compose", text)
            self.assertNotIn("docker.sock", text)
            self.assertIn("${TG2CLOUD_BIND_IP:-127.0.0.1}", text)
            self.assertIn('"/tmp:rw,noexec,nosuid,size=64m"', text)
            self.assertEqual("privileged: true" in text, product.requires_fuse)
            self.assertEqual("/dev/fuse" in text, product.requires_fuse)

    def test_archive_reproducible_and_checksums_cover_both_editions(self):
        one, two = self.root / "one", self.root / "two"
        archives = packaging.build_bundles(ROOT, one, IMAGE, "b" * 40)
        other = packaging.build_bundles(ROOT, two, IMAGE, "b" * 40)
        self.assertEqual(len(archives), 2)
        for first, second in zip(archives, other):
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertIn(hashlib.sha256(first.read_bytes()).hexdigest(), (one / "COMPOSE-SHA256SUMS.txt").read_text())
            with tarfile.open(first) as tar:
                names = {Path(m.name).name for m in tar}
            self.assertEqual(names, {"docker-compose.yml", "compose-bundle.json", ".env.example", "README.md", "LICENSE"})
        with self.assertRaises(FileExistsError):
            packaging.build_bundles(ROOT, one, IMAGE)

    def test_invalid_image_and_commit_are_rejected(self):
        for image in ("latest", "ghcr.io/owner/image", "ghcr.io/owner/image:1;id", "http://bad/x:1"):
            with self.assertRaises(ValueError):
                packaging.render(ROOT, "openlist", image)
        with self.assertRaises(ValueError):
            packaging.bundle_files(ROOT, "openlist", IMAGE, "moving-main")

    def test_initialization_idempotent_preserves_secrets_and_runtime_data(self):
        for edition in PRODUCTS:
            path = self.candidate(edition)
            self.assertTrue(self.initialize(path))
            before = (path / ".env").read_bytes()
            (path / "data/retained.txt").write_text("synthetic existing data")
            ui = UI()
            self.assertFalse(self.initialize(path, ui))
            self.assertEqual(ui.questions, [])
            self.assertEqual((path / ".env").read_bytes(), before)
            self.assertTrue((path / "data/retained.txt").is_file())
            config = runtime.saved_config(path, edition)
            self.assertEqual(config["TG2CLOUD_INSTALL_MODE"], "compose")
            self.assertEqual(runtime.validate_config(path, config, edition).storage_backend, edition)

    def test_interrupted_empty_layout_can_be_retried(self):
        path = self.candidate("openlist")
        (path / "config/rclone").mkdir(parents=True)
        (path / "openlist/data").mkdir(parents=True)
        self.assertTrue(self.initialize(path))

    def test_unknown_data_and_script_installations_are_never_adopted(self):
        for name in ("data", "app"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as temp:
                path = Path(temp)
                for relative, data in packaging.bundle_files(ROOT, "clouddrive2", IMAGE).items():
                    (path / relative).write_bytes(data)
                (path / name).mkdir()
                (path / name / "retained").write_bytes(b"unchanged")
                with self.assertRaises(ValueError):
                    self.initialize(path)
                self.assertEqual((path / name / "retained").read_bytes(), b"unchanged")
                self.assertFalse((path / ".env").exists())

    def test_incomplete_private_configuration_is_not_regenerated(self):
        path = self.candidate("openlist")
        (path / ".env").write_bytes(b"synthetic=retained")
        with self.assertRaises(ValueError):
            self.initialize(path)
        self.assertEqual((path / ".env").read_bytes(), b"synthetic=retained")

    def test_disk_pressure_rejects_before_any_private_file(self):
        path = self.candidate("openlist")
        with patch.object(runtime.shutil, "disk_usage", return_value=NS(free=1)), self.assertRaises(ValueError):
            runtime.setup(path, UI())
        self.assertFalse((path / ".env").exists())

    def test_commit_failure_does_not_leave_a_new_config(self):
        path = self.candidate("openlist")
        original = runtime.write_exclusive
        def fail_marker(target, content):
            if target.name == runtime.MARKER:
                raise KeyboardInterrupt()
            original(target, content)
        with patch.object(runtime, "write_exclusive", side_effect=fail_marker), self.assertRaises(KeyboardInterrupt):
            self.initialize(path)
        self.assertFalse((path / ".env").exists())
        self.assertTrue(self.initialize(path))

    def test_configuration_and_metadata_mismatch_stop_safely(self):
        path = self.candidate("openlist")
        self.initialize(path)
        config = runtime.saved_config(path, "openlist")
        for changes in ({"TG2CLOUD_STORAGE_BACKEND": "clouddrive2"}, {"TG2CLOUD_INSTALL_MODE": "script"}, {"TG2CLOUD_BIND_IP": "0.0.0.0"}):
            with self.assertRaises(ValueError):
                runtime.validate_config(path, config | changes, "openlist")
        metadata = json.loads((path / "compose-bundle.json").read_text())
        metadata["version"] = "0.0.1"
        (path / "compose-bundle.json").write_text(json.dumps(metadata))
        with self.assertRaises(ValueError):
            runtime.metadata(path)

    def test_loopback_and_private_ipv4_only(self):
        for value in ("127.0.0.1", "192.168.26.5", "10.0.0.8", "172.16.1.3"):
            self.assertEqual(runtime.lan_address(value), value)
        for value in ("0.0.0.0", "8.8.8.8", "169.254.1.2", "::1", "https://host"):
            with self.assertRaises(ValueError):
                runtime.lan_address(value)

    def test_host_cli_refuses_direct_compose_identity(self):
        product = PRODUCTS["clouddrive2"]
        with patch.object(instances.configuration, "checked_directory", return_value=self.root), patch.object(instances.configuration, "check_product_directory"), patch.object(instances, "inspect_container", return_value={"labels": {"com.tg2cloud.install-mode": "compose"}}), self.assertRaisesRegex(ValueError, "Compose"):
            instances.discover(product, {product.bot_container, product.storage_container}, Mock(), Mock())

    def test_native_private_config_permissions_are_not_weakened(self):
        if os.name == "posix":
            for uid, mode in ((1001, 0o600), (0, 0o644)):
                with self.assertRaises(ValueError):
                    self.private_check(NS(stat=lambda uid=uid, mode=mode: NS(st_uid=uid, st_mode=mode)))
            self.private_check(NS(stat=lambda: NS(st_uid=0, st_mode=0o600)))

    def test_uninstaller_refuses_compose_even_if_standard_names_match(self):
        product = PRODUCTS["openlist"]
        with self.assertRaisesRegex(uninstall.UninstallError, "Compose"):
            uninstall.core_identity(product, product.bot_container, {"labels": {"com.tg2cloud.install-mode": "compose"}})

    def test_compose_metadata_is_preserved_in_offline_backup(self):
        import sqlite3

        from tg2cloud.persistence.bundle import pack, preflight
        path = self.candidate("openlist")
        self.initialize(path)
        (path / "config/rclone/synthetic.conf").write_text("synthetic")
        (path / "openlist/data/config.json").write_text("{}")
        for name in ("data/tg115.db", "data/bot.session"):
            conn = sqlite3.connect(path / name)
            conn.execute("CREATE TABLE synthetic(id INTEGER)")
            conn.commit()
            conn.close()
        archive = self.root / "synthetic-backup.tar.gz"
        pack(path, archive, "openlist", runtime.VERSION)
        report = preflight(archive, self.root, "openlist", runtime.VERSION)
        self.assertGreater(report["files"], 6)
        with tarfile.open(archive) as tar:
            names = set(tar.getnames())
        self.assertLessEqual({runtime.MARKER, "compose-bundle.json", "data/tg115.db", "data/bot.session"}, names)

    def test_help_uses_standard_library_without_network_or_bot(self):
        code = "import runpy,sys;sys.argv=['compose','--help'];runpy.run_module('tg2cloud.compose',run_name='__main__')"
        result = subprocess.run([sys.executable, "-S", "-B", "-c", code], env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("setup", result.stdout)
        self.assertIn("backup", result.stdout)


class RegistryTests(unittest.TestCase):
    def manifest(self, commit="b" * 40):
        return {"mediaType": "application/vnd.oci.image.index.v1+json",
                "annotations": {"org.opencontainers.image.revision": commit}, "manifests": [
            {"digest": "sha256:" + "a" * 64, "platform": {"os": "linux", "architecture": "amd64"}},
            {"digest": "sha256:" + "c" * 64, "platform": {"os": "linux", "architecture": "arm64"}},
        ]}

    def test_existing_same_commit_index_is_reused_without_mutation(self):
        manifest = self.manifest()
        data = json.dumps(manifest).encode()
        with patch.object(release, "index", return_value=(data, manifest)), patch.object(release, "native_identity") as identity, patch.object(release.subprocess, "run") as run:
            result = release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
        run.assert_not_called()
        self.assertEqual(identity.call_count, 2)
        self.assertTrue(result.endswith(hashlib.sha256(data).hexdigest()))

    def test_foreign_commit_wrong_platform_or_registry_failure_never_overwrites(self):
        wrong = self.manifest("c" * 40)
        bad = self.manifest()
        bad["manifests"] = bad["manifests"][:1]
        for manifest in (wrong, bad):
            with patch.object(release, "index", return_value=(json.dumps(manifest).encode(), manifest)), patch.object(release.subprocess, "run") as run, self.assertRaises(ValueError):
                release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
            run.assert_not_called()
        with patch.object(release, "index", side_effect=ValueError("offline")), patch.object(release.subprocess, "run") as run, self.assertRaises(ValueError):
            release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
        run.assert_not_called()

    def test_only_registry_404_counts_as_absent(self):
        import urllib.error
        opener = Mock()
        for code in (401, 403, 429, 500):
            opener.open.side_effect = urllib.error.HTTPError("https://ghcr.io/v2/synthetic", code, "PRIVATE", {}, None)
            with patch.object(release.urllib.request, "build_opener", return_value=opener), self.assertRaises(ValueError) as error:
                release.request("v2/synthetic/manifests/1.2.3", token="PRIVATE_TOKEN")
            self.assertNotIn("PRIVATE", str(error.exception))
        opener.open.side_effect = urllib.error.HTTPError("https://ghcr.io/v2/synthetic", 404, "absent", {}, None)
        with patch.object(release.urllib.request, "build_opener", return_value=opener):
            self.assertIsNone(release.request("v2/synthetic/manifests/1.2.3"))
        with self.assertRaises(ValueError):
            release.NoRedirect().redirect_request(None, None, 302, "", {}, "https://untrusted.invalid/")

    def test_new_index_must_be_verified_after_creation(self):
        manifest = self.manifest()
        data = json.dumps(manifest).encode()
        with patch.object(release, "index", side_effect=[(None, None), (data, manifest)]), patch.object(release, "native_identity") as identity, patch.object(release.subprocess, "run") as run:
            release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(identity.call_count, 4)
        self.assertIn("imagetools", run.call_args.args[0])


    def test_docker_list_without_annotations_requires_both_exact_native_identities(self):
        manifest = self.manifest()
        manifest["mediaType"] = "application/vnd.docker.distribution.manifest.list.v2+json"
        del manifest["annotations"]
        data = json.dumps(manifest).encode()
        with patch.object(release, "index", return_value=(data, manifest)), patch.object(release, "native_identity") as identity, patch.object(release.subprocess, "run") as mutate:
            result = release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
        mutate.assert_not_called()
        self.assertEqual(identity.call_count, 2)
        self.assertEqual(identity.call_args_list[0].args, ("ghcr.io/owner/tg2cloud", "sha256:" + "a" * 64, "amd64", "b" * 40, "1.2.3"))
        self.assertTrue(result.endswith(hashlib.sha256(data).hexdigest()))

    def test_wrong_child_digest_or_duplicate_platform_never_creates_or_replaces(self):
        wrong = self.manifest()
        wrong["manifests"][0]["digest"] = "sha256:" + "d" * 64
        duplicate = self.manifest()
        duplicate["manifests"][1]["platform"]["architecture"] = "amd64"
        for manifest in (wrong, duplicate):
            with self.subTest(manifest=manifest), patch.object(release, "index", return_value=(json.dumps(manifest).encode(), manifest)), patch.object(release.subprocess, "run") as run, self.assertRaises(ValueError):
                release.publish_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40, "sha256:" + "a" * 64, "sha256:" + "c" * 64)
            run.assert_not_called()

    def test_native_config_version_commit_and_platform_all_must_match(self):
        correct = {"os": "linux", "architecture": "amd64", "config": {"Labels": {
            "org.opencontainers.image.revision": "b" * 40, "org.opencontainers.image.version": "1.2.3"}}}
        with patch.object(release.subprocess, "run", return_value=NS(stdout=json.dumps(correct))) as run:
            release.native_identity("ghcr.io/owner/tg2cloud", "sha256:" + "a" * 64, "amd64", "b" * 40, "1.2.3")
        self.assertEqual(run.call_args.args[0][1:4], ["buildx", "imagetools", "inspect"])
        self.assertEqual(run.call_args.kwargs["timeout"], 60)
        for key, value in (("os", "windows"), ("architecture", "arm64"), ("revision", "c" * 40), ("version", "1.2.2")):
            bad = json.loads(json.dumps(correct))
            if key in ("os", "architecture"):
                bad[key] = value
            else:
                bad["config"]["Labels"]["org.opencontainers.image." + key] = value
            with self.subTest(key=key), patch.object(release.subprocess, "run", return_value=NS(stdout=json.dumps(bad))), self.assertRaises(ValueError):
                release.native_identity("ghcr.io/owner/tg2cloud", "sha256:" + "a" * 64, "amd64", "b" * 40, "1.2.3")

    def test_existing_index_preflight_reuses_only_verified_images(self):
        manifest = self.manifest()
        with patch.object(release, "index", return_value=(json.dumps(manifest).encode(), manifest)), patch.object(release, "native_identity") as identity:
            result = release.inspect_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40)
        self.assertEqual(result, {"reuse": "true", "amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "c" * 64})
        self.assertEqual(identity.call_count, 2)
        with patch.object(release, "index", return_value=(None, None)), patch.object(release.subprocess, "run") as run:
            self.assertEqual(release.inspect_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40), {"reuse": "false"})
        run.assert_not_called()
        with patch.object(release, "index", return_value=(b"{}", manifest)), patch.object(release, "native_identity", side_effect=ValueError("wrong identity")), self.assertRaises(ValueError):
            release.inspect_index("ghcr.io/owner/tg2cloud:1.2.3", "b" * 40)

    def test_publication_tool_is_pinned_separately_from_tag_business_sources(self):
        workflow = (ROOT / ".github/workflows/compose-images.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("ref: ${{ github.sha }}"), 2)
        self.assertEqual(workflow.count("path: build/publication-tools"), 2)
        self.assertIn("ref: refs/tags/${{ inputs.release_tag }}", workflow)
        self.assertIn("python3 .github/scripts/compose_release.py bundle", workflow)
        self.assertIn("needs.prepare.outputs.reuse == 'true'", workflow)
        self.assertIn("needs.native-images.result == 'skipped'", workflow)
        self.assertNotIn("--clobber", workflow)
