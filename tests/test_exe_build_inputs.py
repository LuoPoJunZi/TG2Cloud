"""Branch CI keeps tests but avoids rebuilding unchanged EXE inputs."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exe_build_inputs", ROOT / ".github/scripts/exe_build_inputs.py")
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


class ExeBuildInputTests(unittest.TestCase):
    def test_auxiliary_script_docs_and_tests_do_not_build(self):
        paths = ["install.sh", "scripts/vps_installer.py", "scripts/vps_runtime.py", "README.md",
                 "README_EN.md", "docs/VPS-INSTALL.md", "tests/test_vps_installer.py",
                 "tests/test_exe_build_inputs.py", ".github/workflows/vps-installer.yml",
                 ".github/workflows/tests.yml", ".github/scripts/exe_build_inputs.py"]
        self.assertFalse(inputs.requires_build(paths))

    def test_each_exe_source_and_resource_builds(self):
        for path in sorted(inputs.INPUT_FILES) + [prefix + "resource" for prefix in inputs.INPUT_DIRECTORIES] + ["new_shared_helper.py"]:
            with self.subTest(path=path):
                self.assertTrue(inputs.requires_build([path]))

    def test_push_compares_entire_batch_without_rename_blind_spot(self):
        event = {"before": "a" * 40, "after": "b" * 40}
        with patch.object(inputs, "git", return_value="scripts/vps_installer.py\0README.md\0") as git:
            self.assertFalse(inputs.event_requires_build("push", event))
            git.assert_called_once_with("diff", "--name-only", "-z", "--no-renames", "a" * 40, "b" * 40, "--")
        with patch.object(inputs, "git", return_value="installer.py"):
            self.assertTrue(inputs.event_requires_build("push", event))

    def test_unicode_and_spaces_in_resource_paths_still_build(self):
        event = {"before": "a" * 40, "after": "b" * 40}
        with patch.object(inputs, "git", return_value="README.md\0assets/brand/正式 图标.svg\0"):
            self.assertTrue(inputs.event_requires_build("push", event))

    def test_pr_uses_merge_base(self):
        event = {"pull_request": {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}
        git = Mock(side_effect=["c" * 40, "README.md"])
        with patch.object(inputs, "git", git):
            self.assertFalse(inputs.event_requires_build("pull_request", event))
        self.assertEqual(git.call_args_list[0].args, ("merge-base", "a" * 40, "b" * 40))

    def test_manual_unknown_or_missing_history_builds(self):
        for name, event in (("workflow_dispatch", {}), ("unknown", {}), ("push", {}),
                            ("pull_request", {}), ("push", {"before": "0" * 40, "after": "b" * 40}),
                            ("push", {"before": "--help", "after": "b" * 40})):
            with self.subTest(name=name, event=event), patch.object(inputs, "git") as git:
                self.assertTrue(inputs.event_requires_build(name, event))
                git.assert_not_called()

    def test_build_step_condition_and_full_history(self):
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("if: steps.exe-inputs.outputs.build == 'true'", workflow)
        release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertNotIn("exe-inputs", release)
