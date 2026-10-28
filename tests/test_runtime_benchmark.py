"""Smoke coverage for the opt-in synthetic benchmark, with no production path."""
from __future__ import annotations

import contextlib
import io
import json
import runpy
import unittest
from pathlib import Path


class RuntimeBenchmarkTests(unittest.TestCase):
    def test_small_database_run_checks_invariants_and_emits_measurements(self):
        tool = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".github/scripts/benchmark_runtime.py"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tool["main"](["--tasks", "1000", "--cycles", "20", "--interval-ms", "0"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["cycles"], 20)
        self.assertEqual(result["history_tasks"], 1000)
        self.assertEqual(result["row_changes_during_cycles"], 0)
        self.assertEqual(result["integrity_check"], "ok")
        self.assertGreater(result["db_bytes"], 0)
        self.assertGreaterEqual(result["first_reopen_ms"], 0)
        self.assertEqual(result["recent_samples"], 20)

    def test_resource_limits_and_existing_database_paths_are_rejected(self):
        tool = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".github/scripts/benchmark_runtime.py"))
        for args in (["--tasks", "0"], ["--tasks", "1000001"], ["--duration-seconds", "3601"],
                     ["--cycles", "0"], ["--interval-ms", "-1"], ["--db", "production.db"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                tool["main"](args)
            self.assertEqual(error.exception.code, 2)
