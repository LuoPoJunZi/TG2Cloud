"""Stdlib-only stats parsing and observation tests; no VPS or rclone required."""
from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tg2cloud.monitoring.progress import (
    _record_progress,
    _stage_rate,
    dashboard_rates,
    sample_rate,
)
from tg2cloud.storage.rclone import RcloneClient, _read_progress_tail, parse_progress


class ProgressTests(unittest.IsolatedAsyncioTestCase):
    def sample(self, stats):
        return parse_progress(json.dumps({"stats": stats}).encode())

    def test_current_speed_precedes_file_and_process_averages(self):
        self.assertEqual(self.sample({"bytes": 20, "speed": 2,
            "transferring": [{"bytes": 10, "speed": 3, "speedAvg": 4}]}), (10, 4))

    def test_missing_file_speed_falls_back_to_aggregate_instead_of_zero(self):
        self.assertEqual(self.sample({"bytes": 10, "speed": 3, "transferring": [{"bytes": 10}]}), (10, 3))
        self.assertEqual(self.sample({"bytes": 10, "speed": 3, "transferring": [{"speed": 2}]}), (10, 2))

    def test_real_zero_speed_is_preserved_not_replaced_by_old_average(self):
        self.assertEqual(self.sample({"bytes": 10, "speed": 3,
            "transferring": [{"bytes": 10, "speed": 2, "speedAvg": 0}]}), (10, 0))

    def test_missing_speed_remains_unknown_for_delta_measurement(self):
        self.assertEqual(self.sample({"bytes": 10}), (10, None))

    def test_invalid_stats_rejected_without_echo_or_exception(self):
        for line in (b"not json", b"[]", b'{"stats":null}', b'{"stats":{"bytes":true,"speed":1}}'):
            self.assertIsNone(parse_progress(line))
        for stats in ({"bytes": -1, "speed": 5}, {"bytes": 1, "speed": "nan"},
                      {"bytes": 1, "speed": float("inf")}, {"bytes": float("inf"), "speed": 1},
                      {"bytes": 1, "speed": True}, {"bytes": 1, "speed": -1}):
            with self.subTest(stats=stats):
                self.assertIsNone(self.sample(stats))
        self.assertEqual(self.sample({"bytes": 1, "speed": 5, "transferring": [{"speedAvg": "nan"}]}), (1, 5))

    async def test_partial_lines_and_last_record_without_newline_are_read(self):
        stream = asyncio.StreamReader()
        stream.feed_data(b'{"stats":{"bytes":2,')
        stream.feed_data(b'"speed":3}}\n{"stats":{"bytes":4}}')
        stream.feed_eof()
        callback = Mock()
        await _read_progress_tail(stream, callback)
        self.assertEqual([call.args for call in callback.call_args_list], [(2, 3), (4, None)])

    async def test_oversized_and_non_stats_logs_are_bounded(self):
        stream = asyncio.StreamReader()
        stream.feed_data(b"x" * 100000 + b'\n{"message":"PRIVATE_NAME"}\n{"stats":{"bytes":4,"speed":2}}\n')
        stream.feed_eof()
        callback = Mock()
        tail = await _read_progress_tail(stream, callback)
        self.assertLessEqual(len(tail.encode()), 65536)
        callback.assert_called_once_with(4, 2)

    def test_reset_and_successive_byte_counts_derive_rate(self):
        service = SimpleNamespace(_progress={})
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=10):
            _record_progress(service, 1, "upload", 0, reset=True)
        self.assertIsNone(service._progress[1]["speed"])
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=11):
            _record_progress(service, 1, "upload", 1024)
        self.assertEqual(service._progress[1]["speed"], 1024)
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=12):
            _record_progress(service, 1, "upload", 1024)
        self.assertEqual(service._progress[1]["speed"], 0)
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=13):
            _record_progress(service, 1, "upload", 0, reset=True)
        self.assertIsNone(service._progress[1]["speed"])
        self.assertEqual(service._progress[1]["started"], 13)

    def test_regressed_count_or_new_stage_does_not_reuse_old_speed(self):
        service = SimpleNamespace(_progress={1: {"stage": "upload", "bytes": 500, "speed": 99, "at": 9, "started": 1}})
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=10):
            _record_progress(service, 1, "upload", 5)
        self.assertIsNone(service._progress[1]["speed"])
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=11):
            _record_progress(service, 1, "stream", 5)
        self.assertIsNone(service._progress[1]["speed"])

    def test_display_stale_unknown_and_scheduler_numeric_api_are_separate(self):
        service = SimpleNamespace(_progress={
            1: {"stage": "upload", "speed": None, "at": 99},
            2: {"stage": "upload", "speed": 5, "at": 90},
        })
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=100):
            self.assertEqual(_stage_rate(service, "upload"), 5)
            self.assertIsNone(sample_rate(service._progress[1]))
            self.assertIsNone(sample_rate(service._progress[2]))
            self.assertIsNone(sample_rate({"at": 101, "speed": 5}))
            self.assertEqual(sample_rate({"at": 99, "speed": 0}), 0)

    async def test_both_backends_request_one_second_json_stats_without_changing_retries(self):
        for backend, retries in (("clouddrive2", "2"), ("openlist", "1")):
            client = RcloneClient(SimpleNamespace(storage_backend=backend))
            client.prepare_destination = AsyncMock()
            client.remote = lambda path: "test:" + path
            client._run = AsyncMock()
            await client.upload("test.bin", "target.bin", progress=Mock())
            args = client._run.await_args.args
            self.assertEqual(args[args.index("--stats") + 1], "1s")
            self.assertEqual(args[args.index("--retries") + 1], retries)
            self.assertIn("--use-json-log", args)


class DashboardRateTests(unittest.TestCase):
    def service(self, tasks, progress=None, downloads=(), uploads=()):
        return SimpleNamespace(db=SimpleNamespace(get=lambda ident: tasks.get(ident)),
            _progress=progress or {}, download_tasks=dict.fromkeys(downloads), upload_tasks=dict.fromkeys(uploads))

    def test_idle_is_zero_but_active_without_sample_is_unknown(self):
        self.assertEqual(dashboard_rates(self.service({}), {}), (0, 0))
        service = self.service({1: {"state": "uploading", "sender_id": 1}}, uploads=(1,))
        self.assertEqual(dashboard_rates(service, {"uploading": 1}), (0, None))
        self.assertEqual(dashboard_rates(self.service({}), {"downloading": 1}), (None, 0))

    def test_stale_and_partial_active_totals_not_reported_as_zero_or_full_sum(self):
        tasks = {1: {"state": "uploading"}, 2: {"state": "uploading"}}
        service = self.service(tasks, {1: {"stage": "upload", "at": 99, "speed": 5}}, uploads=(1, 2))
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=100):
            self.assertEqual(dashboard_rates(service, {"uploading": 2}), (0, None))
            service._progress[2] = {"stage": "upload", "at": 99, "speed": 7}
            self.assertEqual(dashboard_rates(service, {"uploading": 2}), (0, 12))
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=110):
            self.assertEqual(dashboard_rates(service, {"uploading": 2}), (0, None))

    def test_completed_verifying_and_cleanup_do_not_keep_old_upload_speed(self):
        for state in ("completed", "cancelled", "verifying", "finalizing", "cleanup_pending"):
            service = self.service({1: {"state": state}}, {1: {"stage": "upload", "at": 99, "speed": 5}}, uploads=(1,))
            with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=100):
                self.assertEqual(dashboard_rates(service, {state: 1}), (0, 0))

    def test_member_only_gets_own_speed_and_stream_is_pipeline_rate_in_both_directions(self):
        tasks = {1: {"sender_id": 11, "state": "streaming"}, 2: {"sender_id": 22, "state": "uploading"}}
        service = self.service(tasks, {1: {"stage": "stream", "speed": 5, "at": 99},
                                      2: {"stage": "upload", "speed": 90, "at": 99}}, downloads=(1,), uploads=(2,))
        with patch("tg2cloud.monitoring.progress.time.monotonic", return_value=100):
            self.assertEqual(dashboard_rates(service, {"streaming": 1}, sender_id=11), (5, 5))
            self.assertEqual(dashboard_rates(service, {"uploading": 1}, sender_id=22), (0, 90))
            self.assertEqual(dashboard_rates(service, {}, sender_id=33), (0, 0))
