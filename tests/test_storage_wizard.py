"""Offline first-install advice and pre-write disk guard regressions."""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import tg2cloud.cli.terminal as tgdep_terminal
import tg2cloud.deployment.instances as tgdep_instances
import tg2cloud.deployment.preflight as tgdep_preflight
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.deployment.resources import GIB, VpsResources, recommend_storage


def resources(**changes):
    return replace(VpsResources(
        architecture="x86_64", cpu_cores=2,
        memory_total_bytes=4 * GIB, memory_available_bytes=3 * GIB,
        swap_total_bytes=GIB, filesystem_type="ext4",
        storage_total_bytes=39 * GIB, storage_available_bytes=36 * GIB,
        inodes_total=100000, inodes_available=90000,
        install_present=False, install_used_bytes=0, downloads_used_bytes=0,
        backups_used_bytes=0, docker_same_filesystem=True, docker_root_detected=True,
        docker_storage_total_bytes=39 * GIB, docker_storage_available_bytes=36 * GIB,
        docker_inodes_total=100000, docker_inodes_available=90000,
        fuse_available=True,
    ), **changes)


class StorageWizardTests(unittest.TestCase):
    def setUp(self):
        self.product = PRODUCTS["clouddrive2"]
        self.instance = tgdep_instances.Instance(self.product, Path(self.product.install_dir), False)
        self.messages = []
        self.log = SafeLog(self.messages.append)
        self.ui = Mock()
        self.ui.ask.side_effect = lambda prompt, **kwargs: kwargs["default"]

    def choose(self, sample):
        with patch.object(tgdep_preflight, "probe_resources", return_value=sample):
            return tgdep_preflight.choose_storage(self.instance, Mock(), self.log, self.ui)

    def test_small_disk_default_matches_existing_recommendation(self):
        sample = resources()
        for product in PRODUCTS.values():
            with self.subTest(edition=product.key):
                self.instance = tgdep_instances.Instance(product, Path(product.install_dir), False)
                expected = recommend_storage(sample, **tgdep_preflight.storage_options(product)).preferred
                self.assertEqual(self.choose(sample), (str(expected.budget_gb), str(expected.reserve_gb)))
                self.assertEqual(self.ui.ask.call_args.kwargs["default"], "1")
        self.assertIn("（推荐）", "\n".join(self.messages))

    def test_large_disk_prefers_balanced(self):
        self.assertEqual(self.choose(resources(storage_total_bytes=200 * GIB, storage_available_bytes=180 * GIB)), ("20", "20"))
        self.assertEqual(self.ui.ask.call_args.kwargs["default"], "2")

    def test_manual_valid_values_preserve_decimals(self):
        self.ui.ask.side_effect = ["3", "6.5", "8.5"]
        self.assertEqual(self.choose(resources()), ("6.5", "8.5"))

    def test_unsafe_manual_budget_or_reserve_can_cancel_without_config(self):
        for budget, reserve in (("100", "8"), ("8", "7")):
            with self.subTest(budget=budget, reserve=reserve):
                self.ui.ask.side_effect = ["3", budget, reserve]
                self.ui.confirm.return_value = False
                with patch.object(tgdep_terminal, "collect_config") as collect, self.assertRaisesRegex(ValueError, "未写入配置"):
                    self.choose(resources())
                collect.assert_not_called()

    def test_invalid_manual_values_can_be_reselected(self):
        self.ui.ask.side_effect = ["3", "100", "8", "1"]
        self.ui.confirm.return_value = True
        self.assertEqual(self.choose(resources()), ("8", "8"))

    def test_independent_docker_full_disk_blocks_otherwise_safe_choice(self):
        self.ui.ask.side_effect = ["1"]
        self.ui.confirm.return_value = False
        with self.assertRaisesRegex(ValueError, "未写入配置"):
            self.choose(resources(docker_same_filesystem=False, docker_storage_available_bytes=GIB))
        self.assertIn("分别校验", "\n".join(self.messages))

    def test_openlist_does_not_require_clouddrive_fuse_or_memory(self):
        sample = resources(fuse_available=False, memory_total_bytes=GIB)
        self.ui.ask.side_effect = ["1"]
        self.ui.confirm.return_value = False
        with self.assertRaises(ValueError):
            self.choose(sample)
        product = PRODUCTS["openlist"]
        self.instance = tgdep_instances.Instance(product, Path(product.install_dir), False)
        self.ui.ask.side_effect = ["1"]
        self.assertEqual(self.choose(sample), ("8", "8"))

    def test_existing_instance_cannot_be_reconfigured_by_recommendation(self):
        self.instance.present = True
        self.instance.config = {"LOCAL_TEMP_BUDGET_GB": "13", "MIN_FREE_DISK_GB": "9"}
        with patch.object(tgdep_preflight, "probe_resources") as probe, self.assertRaisesRegex(ValueError, "保留磁盘配置"):
            tgdep_preflight.choose_storage(self.instance, Mock(), self.log, self.ui)
        probe.assert_not_called()
        self.ui.ask.assert_not_called()
        self.assertEqual(self.instance.config, {"LOCAL_TEMP_BUDGET_GB": "13", "MIN_FREE_DISK_GB": "9"})

    def test_failed_or_incomplete_probe_does_not_guess(self):
        for result in ((1, ""), (0, "partial probe")):
            session = Mock()
            session.run.return_value = result
            with self.subTest(result=result), self.assertRaises(ValueError):
                tgdep_preflight.choose_storage(self.instance, session, self.log, self.ui)
        self.ui.ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
