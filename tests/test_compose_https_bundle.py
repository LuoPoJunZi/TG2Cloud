"""Offline HTTPS host bundles: complete helpers, isolated launch and fail closed."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from tg2cloud.compose import packaging
from tg2cloud.deployment.payload import payload_sources
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.runtime import files as host_files

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/owner/tg2cloud@sha256:" + "a" * 64
_git = shutil.which("git")
_git_bash = Path(_git).resolve().parents[1] / "bin/bash.exe" if _git else None
BASH = os.getenv("TG115_TEST_BASH") or (
    str(_git_bash) if os.name == "nt" and _git_bash and _git_bash.is_file()
    else shutil.which("bash") if os.name != "nt" else None)
spec = importlib.util.spec_from_file_location("https_source_release", ROOT / ".github/scripts/source_release.py")
source_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_release)


def bash_path(path: Path) -> str:
    value = path.as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


class HTTPSBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tg2cloud https ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def candidate(self):
        root = self.root / "bundle with spaces"
        for name, content in packaging.bundle_files(ROOT, "openlist", IMAGE).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return root

    def test_complete_shared_source_and_compose_resources_are_hashed(self):
        files = packaging.bundle_files(ROOT, "openlist", IMAGE)
        metadata = json.loads(files["compose-bundle.json"])
        self.assertEqual((metadata["format"], metadata["https_tools"]), (2, 1))
        manifest = json.loads(files["https-tools/manifest.json"])
        expected = set(host_files(ROOT))
        expected.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "src/tg2cloud/compose").rglob("*.py"))
        expected.update("packaging/compose/docker-compose." + edition + ".yml" for edition in PRODUCTS)
        self.assertEqual(set(manifest["files"]), expected)
        self.assertEqual(list(manifest["files"]), sorted(expected))
        for name, digest in manifest["files"].items():
            body = files["https-tools/" + name]
            self.assertEqual(body, (ROOT / name).read_bytes())
            self.assertEqual(digest, hashlib.sha256(body).hexdigest())
        launcher = files["https.sh"].decode()
        self.assertIn(hashlib.sha256(files["https-tools/manifest.json"]).hexdigest(), launcher)
        self.assertIn('exec python3 -I -S -B -c "$launcher" "$bundle_root" "$@"', launcher)
        self.assertNotIn("@HTTPS_MANIFEST_SHA256@", launcher)
        self.assertEqual(files, packaging.bundle_files(ROOT, "openlist", IMAGE))

    def environment(self):
        # Exercise the installed interpreter, including Python 3.10 CI. Git Bash
        # on Windows may otherwise find the Microsoft Store python3 alias.
        binaries = self.root / "binaries"
        binaries.mkdir(exist_ok=True)
        wrapper = binaries / "python3"
        wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(bash_path(Path(sys.executable))) + ' "$@"\n', encoding="utf-8", newline="\n")
        wrapper.chmod(0o755)
        return dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get("PATH", ""),
                    PYTHONPATH=str(self.root / "untrusted cwd"), PYTHONSTARTUP="untrusted.py")

    def launch(self, root, *arguments, input=""):
        unrelated = self.root / "untrusted cwd"
        unrelated.mkdir(exist_ok=True)
        for name in ("sitecustomize.py", "tg2cloud.py"):
            (unrelated / name).write_text('raise RuntimeError("must not import cwd or site code")\n', encoding="utf-8")
        return subprocess.run([BASH, bash_path(root / "https.sh"), *arguments], cwd=unrelated,
                              env=self.environment(), input=input, capture_output=True, text=True,
                              timeout=30, check=False)

    @unittest.skipUnless(BASH, "Requires Bash; Linux CI must run the offline host launcher")
    def test_help_works_from_unrelated_cwd_without_site_docker_or_root(self):
        root = self.candidate()
        result = self.launch(root, "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HTTPS", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertFalse((root / ".env").exists())
        self.assertFalse(any(root.rglob("*.pyc")))

    @unittest.skipUnless(BASH, "Requires Bash; Linux CI must run the offline host launcher")
    def test_tampered_extra_missing_and_hardlinked_helpers_are_rejected_before_import(self):
        root = self.candidate()
        code = root / "https-tools/src/tg2cloud/compose/https.py"
        original = code.read_bytes()
        manifest = root / "https-tools/manifest.json"
        original_manifest = manifest.read_bytes()
        extra = code.parent / "unexpected.py"
        retained = self.root / "retained-helper.py"
        retained.write_bytes(original)
        for case in ("tampered", "extra", "missing", "hardlink", "manifest"):
            with self.subTest(case=case):
                if case == "tampered":
                    code.write_bytes(b'raise RuntimeError("must not execute tampered helper")\n')
                elif case == "extra":
                    extra.write_bytes(b'raise RuntimeError("must not import extra helper")\n')
                elif case == "missing":
                    code.unlink()
                elif case == "hardlink":
                    code.unlink()
                    os.link(retained, code)
                else:
                    manifest.write_bytes(b"{}\n")
                result = self.launch(root, "--help")
                self.assertEqual(result.returncode, 1)
                self.assertIn("validation failed", result.stderr)
                self.assertNotIn("RuntimeError", result.stderr)
                if code.exists():
                    code.unlink()
                code.write_bytes(original)
                if extra.exists():
                    extra.unlink()
                manifest.write_bytes(original_manifest)
        self.assertEqual(retained.read_bytes(), original)
        # Native Linux additionally exercises actual file/directory symlinks.
        if os.name == "posix":
            for linked in (code, root / "https-tools/src/tg2cloud/compose"):
                with self.subTest(linked=linked.name):
                    saved = linked.with_name(linked.name + "-saved")
                    linked.rename(saved)
                    linked.symlink_to(saved, target_is_directory=saved.is_dir())
                    result = self.launch(root, "--help")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("validation failed", result.stderr)
                    linked.unlink()
                    saved.rename(linked)

    @unittest.skipUnless(BASH, "Requires Bash; Linux CI must run the offline host launcher")
    def test_launcher_preserves_arguments_stdin_and_exit_status(self):
        root = self.candidate()
        code = root / "https-tools/src/tg2cloud/compose/https.py"
        code.write_bytes(b'import json,sys\nprint(json.dumps({"argv":sys.argv[1:], "stdin":sys.stdin.readline().rstrip("\\n")}))\nraise SystemExit(7)\n')
        manifest = root / "https-tools/manifest.json"
        old = hashlib.sha256(manifest.read_bytes()).hexdigest()
        data = json.loads(manifest.read_bytes())
        data["files"][code.relative_to(root / "https-tools").as_posix()] = hashlib.sha256(code.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        launcher = root / "https.sh"
        launcher.write_bytes(launcher.read_bytes().replace(old.encode(), hashlib.sha256(manifest.read_bytes()).hexdigest().encode()))
        arguments = ["status", "space here", "$(printf injected)", "a;b", "测试"]
        result = self.launch(root, *arguments, input="synthetic input\n")
        self.assertEqual(result.returncode, 7, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(Path(output["argv"][1]), root)
        self.assertEqual(output["argv"][0], "--root")
        self.assertEqual(output["argv"][2:], arguments)
        self.assertEqual(output["stdin"], "synthetic input")


class HTTPSReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = set(source_release.REQUIRED)
        for product in PRODUCTS.values():
            names.update(path.relative_to(ROOT).as_posix() for path in payload_sources(ROOT, product).values())
        names.update({"packaging/compose-release.json", "packaging/compose-https.sh",
                      ".github/scripts/compose_release.py", ".github/workflows/compose-images.yml", "docs/COMPOSE.md"})
        cls.files = {name: (ROOT / name).read_bytes() for name in names}

    def verify(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tag = "v" + packaging.VERSION
            name = source_release.artifact_name(tag)
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                for relative, body in files.items():
                    info = tarfile.TarInfo("TG2Cloud-" + tag + "/" + relative)
                    info.size = len(body)
                    archive.addfile(info, io.BytesIO(body))
            content = gzip.compress(buffer.getvalue(), mtime=0)
            (root / name).write_bytes(content)
            (root / "SHA256SUMS.txt").write_text(hashlib.sha256(content).hexdigest() + "  " + name + "\n", encoding="ascii")
            source_release.verify(root, tag)

    def test_new_contract_requires_https_launcher_and_accepts_historical_format_one(self):
        self.verify(self.files)
        files = dict(self.files)
        del files["packaging/compose-https.sh"]
        with self.assertRaisesRegex(ValueError, "incomplete direct Compose HTTPS"):
            self.verify(files)
        old = json.loads(files["packaging/compose-release.json"])
        old["format"] = 1
        del old["https_tools"]
        files["packaging/compose-release.json"] = json.dumps(old).encode()
        self.verify(files)

    def test_unknown_or_inexact_https_contracts_are_rejected(self):
        current = json.loads(self.files["packaging/compose-release.json"])
        for changes in ({"format": 3}, {"https_tools": 2}, {"https_tools": True}, {"extra": 1}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "unsupported direct Compose"):
                self.verify(self.files | {"packaging/compose-release.json": json.dumps(current | changes).encode()})


if __name__ == "__main__":
    unittest.main()
