"""Source release tests in disposable Git repositories; no real tags or network."""
from __future__ import annotations

import ast
import gzip
import hashlib
import importlib.util
import io
import json
import re
import tarfile
import tempfile
import unittest
from pathlib import Path

from tg2cloud.deployment.payload import payload_sources
from tg2cloud.deployment.profiles import PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_release", ROOT / ".github/scripts/source_release.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
bootstrap_spec = importlib.util.spec_from_file_location("prepare_bootstrap", ROOT / ".github/scripts/prepare_bootstrap.py")
bootstrap = importlib.util.module_from_spec(bootstrap_spec)
bootstrap_spec.loader.exec_module(bootstrap)


class SourceReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Validate public release inputs in a disposable two-commit A/B history.
        # Copy only explicit public runtime/build inputs, never private archives.
        names = set(package.REQUIRED) | {"install-webdav.sh", "packaging/external-webdav.json"}
        for product in PRODUCTS.values():
            names.update(path.relative_to(ROOT).as_posix() for path in payload_sources(ROOT, product).values())
        cls.snapshot = {name: (ROOT / name).read_bytes() for name in names}
        for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
            cls.snapshot[name] = bootstrap.render_entry(ROOT, name).encode()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        for name, content in self.snapshot.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        # Isolate fixture history and user identity from the working repository.
        package.git(self.root, "init", "-q")
        package.git(self.root, "config", "user.email", "test@example.invalid")
        package.git(self.root, "config", "user.name", "Offline Test")
        package.git(self.root, "config", "commit.gpgsign", "false")
        package.git(self.root, "config", "tag.gpgsign", "false")
        package.git(self.root, "config", "core.autocrlf", "false")
        package.git(self.root, "config", "core.hooksPath", str(Path(self.temp.name) / "no-hooks"))
        # A detached maintenance process can recreate .git files during cleanup.
        # Fixture repositories are short-lived and need no background maintenance.
        package.git(self.root, "config", "gc.auto", "0")
        package.git(self.root, "config", "gc.autoDetach", "false")
        package.git(self.root, "config", "maintenance.auto", "false")
        self.commit()
        pin = package.git(self.root, "rev-parse", "HEAD").decode().strip()
        for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
            path = self.root / name
            text = re.sub(r'^(installer_commit\s*=\s*)"[0-9a-f]{40}"$', lambda match: match[1] + f'"{pin}"', path.read_text(encoding="utf-8"), flags=re.MULTILINE)
            path.write_text(text, encoding="utf-8", newline="\n")
        self.commit()
        tree = ast.parse((self.root / "src/tg2cloud/version.py").read_text(encoding="utf-8"))
        version = next(node.value.value for node in tree.body if hasattr(node, "targets"))
        self.tag = "v" + version
        package.git(self.root, "tag", self.tag)
        self.output = Path(self.temp.name) / "artifacts"

    def commit(self):
        package.git(self.root, "add", "--all")
        package.git(self.root, "commit", "-qm", "fixture")

    def build(self):
        package.build(self.root, self.output, self.tag)

    def test_build_and_verify_exact_source_without_local_outputs(self):
        (self.root / "private-untracked.txt").write_text("FAKE_OFFLINE_SECRET", encoding="utf-8")
        self.build()
        package.verify(self.output, self.tag)
        with tarfile.open(self.output / package.artifact_name(self.tag)) as archive:
            self.assertFalse(any("private-untracked" in member.name for member in archive))
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            self.build()

    def test_uncommitted_source_is_rejected(self):
        with (self.root / "src/tg2cloud/deployment/resources.py").open("a", encoding="utf-8") as writer:
            writer.write("\n# changed\n")
        with self.assertRaisesRegex(ValueError, "committed"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_old_online_helper_pin_blocks_release(self):
        with (self.root / "src/tg2cloud/deployment/resources.py").open("a", encoding="utf-8") as writer:
            writer.write("\n# changed helper\n")
        self.commit()
        commit = package.git(self.root, "rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(ValueError, "stale bootstrap helper"):
            package.validate_pins(self.root, commit)

    def test_wrong_checkout_or_invalid_tag_stops_before_output(self):
        (self.root / "extra.txt").write_text("fixture", encoding="utf-8")
        self.commit()
        with self.assertRaisesRegex(ValueError, "checkout must match"):
            self.build()
        with self.assertRaises(ValueError):
            package.build(self.root, self.output, "--help")
        self.assertFalse(self.output.exists())

    def test_corrupted_checksum_and_extra_asset_are_rejected(self):
        self.build()
        sums = self.output / "SHA256SUMS.txt"
        original = sums.read_bytes()
        sums.write_bytes(b"0" * 64 + b"\n")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            package.verify(self.output, self.tag)
        sums.write_bytes(original)
        (self.output / "unexpected.exe").write_bytes(b"not-an-executable")
        with self.assertRaisesRegex(ValueError, "asset set"):
            package.verify(self.output, self.tag)

    def test_missing_payload_and_unsafe_archive_rejected_even_with_matching_checksum(self):
        self.build()
        path = self.output / package.artifact_name(self.tag)
        original = path.read_bytes()
        for case in ("missing", "unsafe", "desktop"):
            with self.subTest(case=case):
                result = io.BytesIO()
                with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as source, tarfile.open(fileobj=result, mode="w:gz") as dest:
                    for member in source:
                        if case != "desktop" and member.name.endswith("/src/tg2cloud/storage/rclone.py"):
                            continue
                        dest.addfile(member, source.extractfile(member) if member.isfile() else None)
                    if case == "unsafe":
                        member = tarfile.TarInfo(f"TG2Cloud-{self.tag}/../../outside")
                        dest.addfile(member, io.BytesIO())
                    if case == "desktop":
                        member = tarfile.TarInfo(f"TG2Cloud-{self.tag}/legacy/desktop/installer.py")
                        dest.addfile(member, io.BytesIO())
                path.write_bytes(result.getvalue())
                (self.output / "SHA256SUMS.txt").write_text(hashlib.sha256(result.getvalue()).hexdigest() + "  " + path.name + "\n", encoding="ascii")
                with self.assertRaisesRegex(ValueError, "unsafe|source manifest|build output"):
                    package.verify(self.output, self.tag)

    def test_helper_manifest_cannot_omit_nested_code_or_escape_root(self):
        path = self.root / "packaging/bootstrap-manifest.json"
        original = path.read_bytes()
        for files in (["../outside.py"], ["scripts/run_source.py"]):
            with self.subTest(files=files):
                import json
                path.write_text(json.dumps({"format": 1, "files": files}), encoding="utf-8")
                self.commit()
                commit = package.git(self.root, "rev-parse", "HEAD").decode().strip()
                with self.assertRaisesRegex(ValueError, "source manifest"):
                    package.validate_pins(self.root, commit)
        path.write_bytes(original)

    def test_live_entries_keep_their_actual_published_helper_contract(self):
        # Local unreleased additions must not manufacture a remote SHA or make
        # historical bootstrap tests compare against an unpublished manifest.
        # validate_pins still rejects these old lists for the NEW release below.
        for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            pin = re.search(r'^installer_commit\s*=\s*"([0-9a-f]{40})"$', text, re.MULTILINE)[1]
            block = text.split("<<'PY' &\n", 1)[1].split("\nPY\n", 1)[0]
            paths = [ast.literal_eval(node.value) for node in ast.walk(ast.parse(block))
                     if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "files" for t in node.targets)]
            published = json.loads(package.git(ROOT, "show", f"{pin}:packaging/bootstrap-manifest.json"))["files"]
            self.assertEqual(paths, [tuple(published)])

    def test_unpublished_addon_cannot_ship_with_existing_old_helper_list(self):
        (self.root / "install.sh").write_bytes(package.git(ROOT, "show", "83cabf8c734aa98f8475b0e6cdb18a4bea8469b3:install.sh"))
        self.commit()
        commit = package.git(self.root, "rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(ValueError, "stale bootstrap helper layout"):
            package.validate_pins(self.root, commit)

    def test_old_download_list_cannot_pass_new_layout_release_checks(self):
        path = self.root / "install.sh"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "'src/tg2cloud/cli/vps.py'", "'scripts/vps_installer.py'"), encoding="utf-8", newline="\n")
        self.commit()
        commit = package.git(self.root, "rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(ValueError, "stale bootstrap helper layout"):
            package.validate_pins(self.root, commit)


class HistoricalSourceReleaseTests(unittest.TestCase):
    def test_immutable_previous_layout_still_verifies(self):
        tag = "v1.3.0"
        # Both hashes are public main ancestors. The root-layout fixture must
        # not depend on a maintainer-local tag absent from a fresh checkout.
        for commit in ("e673cdb0683e2d02b0c3fd35b96143164392b898",
                       "c07734cab666defb6ae5b5351a06361711d24190"):
            with self.subTest(historical_layout=commit), tempfile.TemporaryDirectory() as private:
                archive = gzip.compress(package.git(ROOT, "archive", "--format=tar", f"--prefix=TG2Cloud-{tag}/", commit), mtime=0)
                root = Path(private)
                name = package.artifact_name(tag)
                (root / name).write_bytes(archive)
                (root / "SHA256SUMS.txt").write_text(hashlib.sha256(archive).hexdigest() + "  " + name + "\n", encoding="ascii")
                package.verify(root, tag)


if __name__ == "__main__":
    unittest.main()
