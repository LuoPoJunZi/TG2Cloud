"""Offline release planning and shared CI contracts; no remote operations."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github/scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(ROOT / ".github/scripts"), *sys.path]):
        spec.loader.exec_module(module)
    return module


planning, validation = load("prepare_release"), load("linux_validation")


class PlanningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ("src/tg2cloud/version.py", "install.sh", "website/package.json",
                     "website/package-lock.json", "website/site.config.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.current = planning.source_version(self.root)
        parts = list(map(int, self.current.split('.')))
        parts[-1] += 1
        self.next = '.'.join(map(str, parts))

    def digest(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_plan_does_not_change_sources_or_forge_a_helper(self):
        before = self.digest()
        report, diff = planning.prepare(self.root, self.next)
        self.assertEqual(before, self.digest())
        self.assertFalse(report["source_modified"])
        self.assertIn('installer_version = "' + self.next + '"', diff)
        self.assertNotIn('+installer_commit', diff)
        self.assertIn('"releaseStatus": "unreleased"', diff)
        self.assertNotIn('+' + '  "publishedVersion": "' + self.next, diff)
        self.assertEqual(len(report["release_gates"]), 5)

    def test_rejects_same_old_and_invalid_versions(self):
        for value in (self.current, '0.0.0', 'v' + self.next, '01.2.3', '1.2.3; echo secret'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                planning.prepare(self.root, value)

    def test_missing_or_ambiguous_version_field_is_not_silently_skipped(self):
        path = self.root / 'install.sh'
        path.write_text('installer_version="1.0.0"\ninstaller_version="1.0.0"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            planning.prepare(self.root, self.next)

    def test_only_new_build_directory_can_receive_candidates(self):
        report, diff = planning.prepare(self.root, self.next)
        before = self.digest()
        directory = self.root / 'build/release-plan'
        planning.write_candidates(self.root, directory, report, diff)
        self.assertEqual(json.loads((directory / 'plan.json').read_text())['target'], self.next)
        self.assertEqual((directory / 'version.patch').read_text(), diff)
        self.assertTrue(all(self.digest()[name] == digest for name, digest in before.items()))
        for target in (directory, self.root, self.root / 'build', self.root / 'outside', self.root / 'build/../outside'):
            with self.subTest(target=str(target)), self.assertRaises(ValueError):
                planning.write_candidates(self.root, target, report, diff)


class ValidationTests(unittest.TestCase):
    def test_shell_stage_checks_all_entries_and_every_managed_hook(self):
        commands = validation.commands('shell')
        self.assertEqual(len([c for c in commands if c[:2] == ['bash', '-n']]), 4)
        hooks = commands[-1]
        for path in (ROOT / 'packaging/hooks').glob('*/*.sh'):
            self.assertIn(path.relative_to(ROOT).as_posix(), hooks)
        self.assertIn('tests/manage_harness.sh', hooks)

    def test_quality_preserves_both_audits_and_manifest_validation(self):
        commands = validation.commands('quality')
        self.assertEqual(len(commands), 7)
        self.assertTrue(all(c[0] == sys.executable for c in commands))
        for lock in ('requirements/bot.lock.txt', 'requirements/dev.lock.txt'):
            self.assertIn([sys.executable, '-m', 'pip_audit', '-r', lock], commands)
        self.assertTrue(any('.github/scripts/prepare_bootstrap.py' in c for c in commands))
        with self.assertRaises(ValueError):
            validation.commands('unknown')

    def test_first_failure_stops_further_commands(self):
        with patch.object(validation.subprocess, 'run', return_value=Mock(returncode=17)) as run:
            self.assertEqual(validation.main(['quality']), 17)
        run.assert_called_once()
        self.assertFalse(run.call_args.kwargs['shell'])

    def test_branch_and_release_share_current_checks_keep_historical_fallback(self):
        for name in ('tests.yml', 'release.yml'):
            text = (ROOT / '.github/workflows' / name).read_text(encoding='utf-8')
            for stage in ('shell', 'test', 'quality'):
                self.assertIn('.github/scripts/linux_validation.py ' + stage, text)
        release = (ROOT / '.github/workflows/release.yml').read_text(encoding='utf-8')
        self.assertIn('elif [[ -f src/tg2cloud/version.py ]]', release)
        self.assertIn('payload_clouddrive2/requirements.txt', release)
        cli = (ROOT / '.github/workflows/vps-installer.yml').read_text(encoding='utf-8')
        for name in ('.github/scripts/prepare_release.py', '.github/scripts/linux_validation.py',
                     'tests/test_release_preparation.py', 'tests/test_proxy_rendering.py'):
            self.assertEqual(cli.count('      - "' + name + '"'), 2)
