"""Least-privilege Compose credentials and container memory admission."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from tg2cloud.compose import packaging
from tg2cloud.monitoring import memory, readiness
from tg2cloud.monitoring.resources import AdaptiveWindow, ResourceSnapshot
from tg2cloud.transfer.scheduler import _start_downloads

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/example/tg2cloud@sha256:" + "a" * 64


class ComposeSecurityTests(unittest.TestCase):
    def test_bot_only_receives_declared_runtime_settings_for_both_editions(self):
        for edition in ("clouddrive2", "openlist"):
            with self.subTest(edition=edition):
                rendered = packaging.render(ROOT, edition, IMAGE)
                bot = rendered.split("  tg2cloud-" + edition + "-bot:", 1)[1].split("  setup:", 1)[0]
                self.assertNotIn("env_file:", bot)
                for name in ("OPENLIST_ADMIN_PASSWORD", "DOCKER_HOST", "PYTHONPATH", "TG2CLOUD_BIND_IP"):
                    self.assertNotIn(name + ":", bot)
                for name in packaging.BOT_ENVIRONMENT:
                    self.assertIn("      " + name + ":", bot)
                self.assertIn("MEMORY_HARD_MIN_MB: ${MEMORY_HARD_MIN_MB:-512}", bot)
                if edition == "openlist":
                    self.assertIn("OPENLIST_ADMIN_PASSWORD: ${OPENLIST_ADMIN_PASSWORD:-}", rendered)

    def test_legacy_render_is_explicit_and_new_contract_is_versioned(self):
        self.assertIn("path: .env", packaging.render(ROOT, "openlist", IMAGE, legacy=True))
        files = packaging.bundle_files(ROOT, "openlist", IMAGE)
        self.assertEqual(json.loads(files["compose-bundle.json"])["format"], 3)


class CgroupMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def files(self, **values):
        for name, value in values.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(value, encoding="ascii")

    def test_v2_clips_host_memory_and_counts_only_reclaimable_cache(self):
        self.files(**{"memory.max": "1000", "memory.current": "800", "memory.stat": "inactive_file 100\nactive_file 200\n"})
        self.assertEqual(memory.available(1800, 2000, root=self.root), (300, 1000))
        self.assertEqual(memory.available(50, 2000, root=self.root), (50, 1000))

    def test_v1_unlimited_missing_and_invalid_observations(self):
        self.assertEqual(memory.available(1000, 2000, root=self.root), (1000, None))
        self.files(**{"memory/memory.limit_in_bytes": "900", "memory/memory.usage_in_bytes": "100",
                      "memory/memory.stat": "total_inactive_file 50\n"})
        self.assertEqual(memory.available(1000, 2000, root=self.root), (850, 900))
        self.files(**{"memory.max": "max"})
        self.assertEqual(memory.available(1000, 2000, root=self.root), (1000, None))
        self.files(**{"memory.max": "bad", "memory/memory.limit_in_bytes": "-1"})
        self.assertEqual(memory.available(1000, 2000, root=self.root), (1000, None))

    def test_above_limit_and_oversized_stats_remain_bounded(self):
        self.files(**{"memory.max": "1000", "memory.current": "1200", "memory.stat": "x" * 32769})
        self.assertEqual(memory.available(1800, 2000, root=self.root), (0, 1000))

    def test_low_memory_does_not_report_ready_and_recovers_without_changing_thresholds(self):
        settings = SimpleNamespace(data_dir=self.root, storage_backend="openlist", control_interval=3,
                                   min_free_disk_bytes=100, local_budget_bytes=1000, memory_hard_min_bytes=512)
        window = AdaptiveWindow(settings, "download")
        service = SimpleNamespace(settings=settings, client=SimpleNamespace(is_connected=lambda: True),
            destination_scope="target", destination_last_checked=time.time(), _destination_ready=lambda: True,
            db=SimpleNamespace(is_paused=lambda: False, used_local_bytes=lambda: 0),
            download_tasks={}, upload_tasks={}, download_window=window)
        for name in ("heartbeat", "resource-heartbeat"):
            path = self.root / name
            path.touch()
            os.utime(path, (time.time() - 1, time.time() - 1))
        service.snapshot = ResourceSnapshot(0, 256, 0, 10000, 0, time.time(), memory_limit=1024)
        window.update(service.snapshot, recent_errors=0, destination_healthy=True, demand_present=True)
        readiness.publish(service, {"queued": 1})
        result = readiness.read(self.root, now=time.time())
        self.assertFalse(result["ready"])
        self.assertEqual(result["checks"]["capacity"], "failed")
        self.assertEqual(result["admission"]["download_window"], 0)
        self.assertIn("memory", result["admission"]["blocked_by"])
        service.snapshot = ResourceSnapshot(0, 800, 0, 10000, 0, time.time())
        # No Settings or database mutation is required when resources recover.
        window.value = 1
        readiness.publish(service, {"queued": 1})
        self.assertTrue(readiness.read(self.root, now=time.time())["ready"])
        self.assertIsNone(readiness.validated_admission(result["admission"] | {"blocked_by": ["PRIVATE_TEXT"]}))


class DownloadAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_gate_prevents_reservation_and_recovers_without_restarting(self):
        queued = Mock(return_value=())
        service = SimpleNamespace(destination_healthy=True, _sample_fresh=lambda: True, _destination_ready=lambda: True,
            db=SimpleNamespace(is_paused=lambda: False), snapshot=SimpleNamespace(memory_available=256, filesystems=()),
            settings=SimpleNamespace(memory_hard_min_bytes=512), download_window=SimpleNamespace(value=1),
            download_tasks={}, _queued_batches=queued)
        await _start_downloads(service)
        queued.assert_not_called()
        self.assertIn("内存", service._resource_pause_reason)
        service.snapshot.memory_available = 1024
        await _start_downloads(service)
        queued.assert_called_once_with(("queued",))
        self.assertEqual(service._resource_pause_reason, "")


if __name__ == "__main__":
    unittest.main()
