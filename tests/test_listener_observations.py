"""Listener diagnostics remain independent, bounded and safe under old snapshots."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tg2cloud.monitoring import observations as obs
from tg2cloud.monitoring import readiness
from tg2cloud.persistence.sqlite import TaskDB


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = TaskDB(self.root / "tg2cloud.db")
        self.addCleanup(self.db.close)
        self.now = time.time()
        self.tick = time.monotonic()
        self.db._conn.execute(
            "INSERT OR REPLACE INTO service_meta VALUES('listener_account',?)",
            (
                json.dumps(
                    {
                        "enabled": True,
                        "account": 123,
                        "status": "SYNTHETIC_PRIVATE_STATUS",
                    }
                ),
            ),
        )
        self.db._conn.execute(
            "INSERT INTO listener_sources(account,chat,title,config,cursor,enabled,polled_at) VALUES(123,1,'SYNTHETIC_PRIVATE_CHANNEL','{}',1,1,?)",
            (self.now - 5,),
        )
        self.listener = SimpleNamespace(
            client=SimpleNamespace(is_connected=Mock(return_value=True)),
            _last_loop_at=self.tick - 2,
        )
        self.service = SimpleNamespace(db=self.db, listener=self.listener)

    def test_healthy_observation_contains_no_identity_names_or_credentials(self):
        value = obs.listener_observation(self.service, now=self.now)
        self.assertEqual(value["state"], "healthy")
        self.assertEqual(value["sources"], 1)
        self.assertEqual(value["poll_age_seconds"], 5)
        self.assertNotIn("PRIVATE", json.dumps(value))
        self.assertNotIn("account", value)
        self.listener.client.is_connected.assert_called_once_with()

    def test_disabled_connecting_cooldown_stalled_loop_and_source_gaps_are_distinct(
        self,
    ):
        for state, change in (
            (
                "disabled",
                lambda: self.db._conn.execute(
                    "UPDATE service_meta SET value=? WHERE key='listener_account'",
                    (json.dumps({"enabled": False}),),
                ),
            ),
            ("connecting", lambda: setattr(self.listener, "client", None)),
            (
                "cooldown",
                lambda: self.db._conn.execute(
                    "UPDATE service_meta SET value=? WHERE key='listener_account'",
                    (json.dumps({"enabled": True, "cooldown_until": self.now + 300}),),
                ),
            ),
            (
                "stale",
                lambda: setattr(self.listener, "_last_loop_at", time.monotonic() - 200),
            ),
            (
                "stale",
                lambda: self.db._conn.execute(
                    "UPDATE listener_sources SET polled_at=?", (self.now - 181,)
                ),
            ),
            (
                "partial",
                lambda: self.db._conn.execute("UPDATE listener_sources SET gap=1"),
            ),
            (
                "partial",
                lambda: self.db._conn.execute(
                    "UPDATE listener_sources SET next_retry=?", (self.now + 60,)
                ),
            ),
        ):
            with self.subTest(state=state):
                self.db._conn.execute(
                    "UPDATE service_meta SET value=? WHERE key='listener_account'",
                    (json.dumps({"enabled": True}),),
                )
                self.db._conn.execute(
                    "UPDATE listener_sources SET polled_at=?,gap=0,next_retry=0",
                    (self.now - 5,),
                )
                self.listener.client = SimpleNamespace(is_connected=lambda: True)
                self.listener._last_loop_at = self.tick
                change()
                self.assertEqual(
                    obs.listener_observation(self.service, now=self.now)["state"], state
                )

    def test_unknown_or_incomplete_metadata_never_claims_listener_healthy(self):
        self.db._conn.execute(
            "UPDATE service_meta SET value='PRIVATE_INVALID_JSON' WHERE key='listener_account'"
        )
        self.assertEqual(obs.listener_observation(self.service)["state"], "unknown")
        self.db._conn.execute(
            "UPDATE service_meta SET value=? WHERE key='listener_account'",
            (json.dumps({"enabled": True}),),
        )
        self.listener._last_loop_at = time.monotonic() + 30
        self.assertEqual(obs.listener_observation(self.service)["state"], "unknown")

    def test_untrusted_optional_protocol_data_never_appears_in_output(self):
        for bad in (
            [],
            None,
            {"state": "PRIVATE"},
            obs.unknown_listener() | {"state": []},
            obs.unknown_listener() | {"enabled": "PRIVATE"},
            obs.unknown_listener() | {"sources": True},
            obs.unknown_listener() | {"gap_sources": 1},
            obs.unknown_listener() | {"state": "healthy"},
        ):
            with self.subTest(value=bad):
                self.assertIsNone(obs.validate_listener(bad))
                self.assertNotIn("PRIVATE", obs.listener_line(bad))
        for bad in (
            {"PRIVATE": {}},
            {"listener_wait": {"count": True, "last_at": 0, "bounded": False}},
            {"listener_wait": {"count": 1, "last_at": float("nan"), "bounded": False}},
        ):
            self.assertIsNone(obs.validate_events(bad))

    def test_transient_events_are_bounded_expire_and_do_not_store_error_messages(self):
        with patch.object(obs.time, "time", return_value=self.now):
            for _ in range(70):
                obs.record_event(self.service, "listener_wait")
            obs.record_event(self.service, "destination_network")
            obs.record_event(self.service, "PRIVATE_RAW_ERROR")
        events = obs.recent_events(self.service, now=self.now + 1)
        self.assertEqual(events["listener_wait"]["count"], 64)
        self.assertTrue(events["listener_wait"]["bounded"])
        self.assertEqual(events["destination_network"]["count"], 1)
        self.assertLessEqual(
            sum(len(v["times"]) for v in self.service._diagnostic_events.values()), 65
        )
        self.assertNotIn("PRIVATE", json.dumps(events))
        self.assertEqual(obs.recent_events(self.service, now=self.now + 86401), {})
        self.assertEqual(obs.recent_events(SimpleNamespace(), now=self.now), {})

    def test_listener_issue_does_not_falsify_bot_base_readiness(self):
        self.service.settings = SimpleNamespace(
            data_dir=self.root,
            storage_backend="openlist",
            control_interval=3,
            min_free_disk_bytes=100,
            local_budget_bytes=1000,
            memory_hard_min_bytes=100,
        )
        self.service.client = SimpleNamespace(is_connected=lambda: True)
        self.service.snapshot = SimpleNamespace(disk_free=10000, filesystems=(), memory_available=10000)
        self.service.destination_scope = "root"
        self.service.destination_last_checked = self.now
        self.service._destination_ready = lambda: True
        self.service.download_tasks = {}
        self.service.upload_tasks = {}
        self.listener._last_loop_at = time.monotonic() - 200
        for name in ("heartbeat", "resource-heartbeat"):
            path = self.root / name
            path.touch()
            os.utime(path, (self.now - 1, self.now - 1))
        readiness.publish(self.service, {})
        value = readiness.read(self.root, now=time.time())
        self.assertTrue(value["ready"])
        self.assertEqual(value["listener"]["state"], "stale")
        path = self.root / "readiness.json"
        raw = json.loads(path.read_text())
        raw["listener"] = {"state": []}
        raw["observations"] = {"PRIVATE": {}}
        path.write_text(json.dumps(raw))
        value = readiness.read(self.root, now=time.time())
        self.assertTrue(value["ready"])
        self.assertEqual(value["listener"]["state"], "unknown")
        self.assertNotIn("PRIVATE", json.dumps(value))
        raw.pop("listener")
        raw.pop("observations")
        path.write_text(json.dumps(raw))
        self.assertTrue(readiness.read(self.root, now=time.time())["ready"])
        raw["sampled_at"] = self.now - 1000
        path.write_text(json.dumps(raw))
        self.assertFalse(readiness.read(self.root, now=time.time())["ready"])
        self.assertIsNone(readiness.read(self.root, now=time.time())["observations"])

    def test_readonly_observation_performs_no_state_writes(self):
        before = list(self.db._conn.iterdump())
        for _ in range(3):
            obs.listener_observation(self.service)
        self.assertEqual(before, list(self.db._conn.iterdump()))
