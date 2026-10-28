"""Readiness is local, bounded, non-secret and independent of liveness."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tg2cloud.deployment import readiness as host
from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.monitoring import readiness
from tg2cloud.transfer.scheduler import _resource_loop
from tg2cloud.version import VERSION


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = SimpleNamespace(data_dir=self.root, storage_backend="openlist", control_interval=3,
                                        min_free_disk_bytes=100, local_budget_bytes=1000,
                                        bot_token="SYNTHETIC_NEVER_EXPORT")
        self.service = SimpleNamespace(settings=self.settings, client=SimpleNamespace(is_connected=lambda: True),
                                       snapshot=SimpleNamespace(disk_free=10000, filesystems=()),
                                       destination_scope="target", destination_last_checked=time.time(),
                                       _destination_ready=lambda: True, _destination_next_probe_at=0,
                                       db=SimpleNamespace(is_paused=lambda: False, used_local_bytes=lambda: 10),
                                       download_tasks={}, upload_tasks={})
        # A known past instant avoids filesystem/clock rounding at now == mtime.
        observed = time.time() - 1
        for name in ("heartbeat", "resource-heartbeat"):
            path = self.root / name
            path.touch()
            os.utime(path, (observed, observed))

    def report(self):
        readiness.publish(self.service, {"queued": 2})
        return readiness.read(self.root, now=time.time())

    def test_ready_uses_recent_observations_without_tokens_client_calls_or_webdav(self):
        report = self.report()
        self.assertTrue(report["ready"])
        self.assertEqual(report["queued"], 2)
        self.assertNotIn("SYNTHETIC_NEVER_EXPORT", (self.root / "readiness.json").read_text())
        self.assertEqual(set(report["checks"]), set(readiness.CHECKS))

    def test_future_heartbeat_is_not_ready(self):
        future = time.time() + 10
        os.utime(self.root / "heartbeat", (future, future))
        report = self.report()
        self.assertFalse(report["ready"])
        self.assertEqual(report["checks"]["heartbeat"], "failed")

    def test_disconnected_pause_target_fallback_and_disk_pressure_are_distinguished(self):
        self.service.client.is_connected = lambda: False
        self.service.db.is_paused = lambda: True
        self.service.destination_scope = "root_fallback"
        self.service.snapshot.filesystems = (("private-label-not-exported", 1),)
        report = self.report()
        self.assertFalse(report["ready"])
        self.assertEqual(report["checks"]["telegram"], "failed")
        self.assertEqual(report["checks"]["queue"], "paused")
        self.assertEqual(report["checks"]["destination"], "partial")
        self.assertEqual(report["checks"]["capacity"], "failed")
        self.assertNotIn("private-label", json.dumps(report))

    def test_cooldown_is_preserved_without_forcing_a_probe(self):
        self.service._destination_ready = lambda: False
        self.service._destination_next_probe_at = time.monotonic() + 300
        self.assertEqual(self.report()["checks"]["destination"], "cooldown")

    def test_stale_previous_process_future_and_malformed_observations_never_pass(self):
        self.report()
        source = self.root / "readiness.json"
        original = source.read_text()
        for change in ({"sampled_at": 0}, {"schema": 99}, {"sampled_at": time.time() + 10},
                       {"ttl": float("nan")}, {"queued": "SECRET"}, {"checks": {"telegram": "ok"}}):
            with self.subTest(change=tuple(change)):
                source.write_text(json.dumps({**json.loads(original), **change}))
                self.assertFalse(readiness.read(self.root, now=time.time())["ready"])
        source.write_text(original)
        self.assertFalse(readiness.read(self.root, now=time.time(), started_at=time.time() + 1)["ready"])
        source.write_text("PRIVATE_INVALID_JSON")
        self.assertFalse(readiness.read(self.root, now=time.time())["ready"])

    def test_missing_protocol_and_hostile_subprocess_output_are_not_echoed(self):
        instance = SimpleNamespace(product=PRODUCTS["openlist"], version=VERSION)
        messages = []
        session = SimpleNamespace(run=lambda *a, **k: (1, "PRIVATE_TRACEBACK_TOKEN"))
        self.assertFalse(host.check(instance, session, messages.append))
        self.assertNotIn("PRIVATE_TRACEBACK_TOKEN", "".join(messages))
        report = self.report()
        session.run = lambda *a, **k: (0, json.dumps(report))
        self.assertTrue(host.check(instance, session, messages.append))

    def test_different_bot_version_remains_unverified(self):
        instance = SimpleNamespace(product=PRODUCTS["openlist"], version="0.0.0")
        session = SimpleNamespace(run=lambda *a, **k: (0, json.dumps(self.report())))
        messages = []
        self.assertFalse(host.check(instance, session, messages.append))
        self.assertIn("业务就绪未核实", "".join(messages))

    def test_diagnostic_export_failure_does_not_invalidate_resource_sample_or_scheduler(self):
        async def run():
            service = self.service
            service._stop = asyncio.Event()
            original = service.snapshot
            service.monitor = SimpleNamespace(sample=lambda: original)
            service.db.counts = lambda **_: {}
            service._enforce_disk_emergency = AsyncMock()
            service._stream_count = lambda: 0
            service._errors_in_last_minute = lambda value: 0
            service._stage_rate = lambda value: 0
            service.recent_download_errors = service.recent_upload_errors = []
            service.download_window = service.upload_window = SimpleNamespace(update=Mock())
            service.log = Mock()

            async def stop(_):
                service._stop.set()

            with patch.object(readiness, "publish", side_effect=OSError("private failure")), patch("tg2cloud.transfer.scheduler.asyncio.sleep", side_effect=stop):
                await _resource_loop(service)
            self.assertIs(service.snapshot, original)
            service.log.exception.assert_not_called()
            self.assertNotIn("private failure", str(service.log.warning.call_args))
        asyncio.run(run())


    def test_resource_cycle_reuses_only_its_own_counts_budget_and_stream_sample(self):
        from tg2cloud.domain.states import SCHEDULING_STATES

        async def run():
            service = self.service
            service._stop = asyncio.Event()
            original = service.snapshot
            service.monitor = SimpleNamespace(sample=lambda: original)
            service.db.counts = Mock(return_value={"queued": 2, "uploading": 1})
            service.db.used_local_bytes = Mock(side_effect=[1500, 100])
            service._enforce_disk_emergency = AsyncMock()
            service._stream_count = Mock(return_value=1)
            service._errors_in_last_minute = lambda value: 0
            service._stage_rate = lambda value: 0
            service.recent_download_errors = service.recent_upload_errors = []
            service.download_window = SimpleNamespace(update=Mock())
            service.upload_window = SimpleNamespace(update=Mock())
            service.log = Mock()
            snapshots = []
            async def next_cycle(_):
                snapshots.append(json.loads((self.root / "readiness.json").read_text()))
                if len(snapshots) == 2:
                    service._stop.set()
            with patch("tg2cloud.transfer.scheduler.asyncio.sleep", side_effect=next_cycle):
                await _resource_loop(service)
            self.assertEqual(service.db.counts.call_count, 2)
            service.db.counts.assert_called_with(states=SCHEDULING_STATES)
            self.assertEqual(service.db.used_local_bytes.call_count, 2)
            self.assertEqual(service._stream_count.call_count, 2)
            self.assertEqual([s["checks"]["capacity"] for s in snapshots], ["failed", "ok"])
            self.assertEqual([c.kwargs["backlog_pressure"] for c in service.download_window.update.call_args_list], [True, False])
            self.assertEqual([c.kwargs["active_count"] for c in service.upload_window.update.call_args_list], [1, 1])
            service.log.exception.assert_not_called()
        asyncio.run(run())
