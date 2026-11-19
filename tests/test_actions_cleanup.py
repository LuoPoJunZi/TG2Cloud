"""Offline retention, race handling, trigger trust and API-scope regression."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cleanup_actions", ROOT / ".github/scripts/cleanup_actions.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def run(number, **changes):
    date = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=number)).isoformat()
    value = {"id": number, "workflow_id": 9, "run_attempt": 1, "head_sha": "a" * 40,
             "repository": {"full_name": cleanup.REPOSITORY}, "head_repository": {"full_name": cleanup.REPOSITORY},
             "created_at": date, "updated_at": date, "status": "completed", "conclusion": "success",
             "path": ".github/workflows/tests.yml", "name": "tests", "head_branch": "main", "event": "push"}
    return value | changes


class FakeGitHub:
    def __init__(self, values):
        self.runs = {r["id"]: copy.deepcopy(r) for r in values}
        self.deleted = []
        self.before_get = lambda _run_id: None
        self.before_latest = lambda: None
        self.reject = set()
        self.fail = set()

    def list_runs(self):
        return copy.deepcopy(list(self.runs.values()))

    def latest(self):
        self.before_latest()
        return cleanup.ordered(self.list_runs())[:50]

    def get_run(self, run_id):
        self.before_get(run_id)
        return copy.deepcopy(self.runs.get(run_id))

    def delete_run(self, run_id):
        if run_id in self.fail:
            raise cleanup.CleanupError("Synthetic failure")
        if run_id in self.reject:
            self.runs[run_id]["status"] = "waiting"
            return "preserved_server_state"
        self.deleted.append(run_id)
        self.runs.pop(run_id)
        return "deleted"


class RetentionPolicyTests(unittest.TestCase):
    def test_latest_fifty_and_every_key_or_unfinished_run_are_preserved_together(self):
        values = [run(i) for i in range(1, 66)]
        values[0].update(path=".github/workflows/release.yml", name="old name")
        values[1].update(path=".github/workflows/compose-images.yml")
        for i, status in enumerate(("queued", "in_progress", "waiting", "pending", "requested"), 3):
            values[i].update(status=status, conclusion=None)
        values[8].update(conclusion="action_required")
        values[9].update(conclusion=None)
        values[10].update(status="future_status")
        values[11].update(conclusion="future_conclusion")
        _, protected, candidates = cleanup.make_plan(values, {3}, {13, 14})
        self.assertEqual({r["id"] for r in candidates}, {15})
        self.assertLessEqual(set(range(16, 66)), set(protected))
        self.assertIn("successful_publication", protected[1])
        self.assertIn("documented_evidence", protected[3])
        self.assertIn("current_or_triggering_workflow", protected[13])

    def test_old_failures_are_eligible_unless_their_evidence_is_documented(self):
        values = [run(i) for i in range(1, 54)]
        values[0].update(path=".github/workflows/release.yml", conclusion="failure")
        values[1].update(conclusion="failure")
        _, protected, candidates = cleanup.make_plan(values, {2})
        self.assertIn(1, {r["id"] for r in candidates})
        self.assertIn(2, protected)

    def test_equal_times_have_deterministic_id_order(self):
        values = [run(i, created_at="2026-01-01T00:00:00Z") for i in range(1, 61)]
        _, protected, _ = cleanup.make_plan(values, set())
        self.assertEqual(set(protected), set(range(11, 61)))

    def test_under_fifty_does_not_delete_anything(self):
        _, protected, candidates = cleanup.make_plan([run(i) for i in range(1, 9)], set())
        self.assertEqual(len(protected), 8)
        self.assertEqual(candidates, [])

    def test_ambiguous_foreign_or_duplicate_data_cannot_form_a_deletion_plan(self):
        for changed in ({"id": True}, {"id": 0}, {"workflow_id": "9"}, {"created_at": "yesterday"},
                        {"updated_at": "2026-01-01"}, {"head_sha": "not-a-sha"}, {"conclusion": {}},
                        {"repository": {"full_name": "other/repo"}}):
            with self.subTest(changed=changed), self.assertRaises(cleanup.CleanupError):
                cleanup.make_plan([run(1, **changed)], set())
        with self.assertRaises(cleanup.CleanupError):
            cleanup.make_plan([run(1), run(1)], set())


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.directory = self.root / "build/audit"
        self.client = FakeGitHub([run(i) for i in range(1, 56)])

    def execute(self, **changes):
        options = {"references": set(), "apply": True, "clock": lambda: 100.0, "sleep": lambda _: None} | changes
        return cleanup.cleanup(self.client, self.root, self.directory, **options)

    def test_preview_writes_a_plan_but_cannot_delete(self):
        report = self.execute(apply=False)
        self.assertEqual(report["state"], "preview")
        self.assertEqual(report["candidates"], 5)
        self.assertEqual(self.client.deleted, [])
        self.assertFalse((self.directory / "journal.jsonl").exists())
        self.assertTrue((self.directory / "plan.json").is_file())

    def test_only_old_completed_candidates_are_removed_and_result_is_verified(self):
        report = self.execute()
        self.assertEqual(set(self.client.deleted), {1, 2, 3, 4, 5})
        self.assertEqual(report["state"], "verified")
        self.assertEqual(report["after"], 50)
        self.assertEqual(set(self.client.runs), set(range(6, 56)))
        self.assertEqual(len((self.directory / "journal.jsonl").read_text().splitlines()), 5)

    def test_queued_running_waiting_and_rerun_changes_are_rechecked_before_delete(self):
        for run_id, change in ((1, {"status": "queued"}), (2, {"status": "in_progress"}),
                               (3, {"status": "waiting"}), (4, {"run_attempt": 2}),
                               (5, {"conclusion": "action_required"})):
            self.client.runs[run_id]["change_on_get"] = change

        def change(run_id):
            value = self.client.runs[run_id]
            value.update(value.pop("change_on_get", {}))
        self.client.before_get = change
        report = self.execute()
        self.assertEqual(self.client.deleted, [])
        self.assertEqual(report["preserved_changed"], 5)

    def test_state_is_read_after_write_pacing_wait(self):
        waits = []
        def during_wait(seconds):
            waits.append(seconds)
            self.client.runs[4].update(status="queued", conclusion=None)
        report = self.execute(sleep=during_wait)
        self.assertTrue(waits)
        self.assertNotIn(4, self.client.deleted)
        self.assertIn(4, self.client.runs)
        self.assertEqual(report["preserved_changed"], 1)

    def test_current_or_documented_run_and_new_runs_survive(self):
        self.client.before_latest = lambda: self.client.runs.setdefault(99, run(99, status="in_progress", conclusion=None))
        report = self.execute(references={1}, current_id=2)
        self.assertEqual(set(self.client.deleted), {3, 4, 5})
        self.assertTrue({1, 2, 99} <= self.client.runs.keys())
        self.assertEqual(report["after"], 53)

    def test_disappeared_and_server_rejected_runs_are_handled_without_repeated_deletion(self):
        self.client.reject.add(2)
        self.client.before_get = lambda i: self.client.runs.pop(i, None) if i == 1 else None
        report = self.execute()
        self.assertEqual(report["already_absent"], 1)
        self.assertEqual(report["preserved_changed"], 1)
        self.assertNotIn(1, self.client.deleted)
        self.assertIn(2, self.client.runs)

    def test_api_failure_stops_and_preserves_audit_of_completed_work(self):
        # Candidates are ordered newest first: 5 succeeds, then 4 fails.
        self.client.fail.add(4)
        with self.assertRaises(cleanup.CleanupError):
            self.execute()
        self.assertEqual(self.client.deleted, [5])
        report = json.loads((self.directory / "summary.json").read_text())
        self.assertEqual(report["state"], "failed")
        self.assertEqual(report["deleted"], 1)
        self.assertTrue({1, 2, 3, 4} <= self.client.runs.keys())

    def test_missing_protected_run_fails_verification_instead_of_claiming_success(self):
        self.client.before_latest = lambda: self.client.runs.pop(55, None)
        with self.assertRaises(cleanup.CleanupError):
            self.execute()
        self.assertEqual(json.loads((self.directory / "summary.json").read_text())["state"], "failed")

    def test_cannot_write_audit_outside_build_or_overwrite_an_existing_directory(self):
        for directory in (self.root / "outside", self.root.parent / "foreign-audit"):
            with self.subTest(directory=directory), self.assertRaises(cleanup.CleanupError):
                cleanup.cleanup(self.client, self.root, directory, references=set())
        self.directory.mkdir(parents=True)
        (self.directory / "owner.txt").write_text("keep me")
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual((self.directory / "owner.txt").read_text(), "keep me")


class APIBoundaryTests(unittest.TestCase):
    def response(self, code, body=None, headers=""):
        return SimpleNamespace(returncode=0 if code < 400 else 1,
            stdout=f"HTTP/2.0 {code}\r\n{headers}\r\n".encode() + (json.dumps(body).encode() if body is not None else b""),
            stderr=b"never echo credentials or raw errors")

    def test_pagination_enumerates_more_than_one_thousand_without_search_filters(self):
        calls = []
        def request(command, **kwargs):
            calls.append(command[-1])
            page = int(command[-1].rsplit("=", 1)[1])
            values = [run(i) for i in range((page-1)*100+1, min(page*100, 1103)+1)]
            return self.response(200, {"total_count": 1103, "workflow_runs": values})
        client = cleanup.GitHub("gh", run=request)
        self.assertEqual(len(client.list_runs()), 1103)
        self.assertEqual(len(calls), 12)
        self.assertFalse(any("created=" in path or "status=" in path for path in calls))

    def test_incomplete_inventory_cannot_be_used_for_deletion(self):
        client = cleanup.GitHub("gh", run=lambda *_a, **_k: self.response(200, {"total_count": 8, "workflow_runs": [run(1)]}))
        with self.assertRaises(cleanup.CleanupError):
            client.list_runs()

    def test_delete_is_limited_to_one_positive_run_id_in_the_fixed_repository(self):
        calls = []
        client = cleanup.GitHub("gh", run=lambda args, **_k: calls.append(args) or self.response(204))
        self.assertEqual(client.delete_run(123), "deleted")
        self.assertEqual(calls[0][-1], "repos/LuoPoJunZi/TG2Cloud/actions/runs/123")
        self.assertNotIn("shell", calls[0])
        for invalid in (True, 0, -1, "123; echo secret"):
            with self.assertRaises(cleanup.CleanupError):
                client.delete_run(invalid)
        for path in ("/releases/123", "/git/refs/tags/v1.6.0", "/actions/runs?per_page=100", "https://other.example/runs/1"):
            with self.subTest(path=path), self.assertRaises(cleanup.CleanupError):
                client.request("DELETE", path)
        self.assertEqual(len(calls), 1)

    def test_rate_limits_obey_delay_and_retry_a_bounded_number_of_times(self):
        responses = [self.response(429, headers="Retry-After: 2\r\n"), self.response(200, run(1))]
        waits = []
        client = cleanup.GitHub("gh", run=lambda *_a, **_k: responses.pop(0), sleep=waits.append)
        self.assertEqual(client.get_run(1)["id"], 1)
        self.assertEqual(waits, [60])
        waits.clear()
        client = cleanup.GitHub("gh", run=lambda *_a, **_k: self.response(429, headers="Retry-After: 1\r\n"), sleep=waits.append)
        with self.assertRaises(cleanup.CleanupError):
            client.get_run(1)
        self.assertEqual(waits, [60, 120, 240])

    def test_rate_limited_delete_is_never_retried_with_a_stale_state(self):
        for response in (self.response(429, headers="Retry-After: 1\r\n"),
                         self.response(403, headers="X-RateLimit-Remaining: 0\r\n")):
            calls, waits = [], []
            client = cleanup.GitHub("gh", sleep=waits.append,
                run=lambda command, value=response, recorded=calls, **_k: recorded.append(command) or value)
            with self.subTest(response=response.stdout[:15]), self.assertRaises(cleanup.CleanupError):
                client.delete_run(1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(waits, [])

    def test_primary_reset_is_respected_and_long_wait_does_not_retry_early(self):
        responses = [self.response(403, headers="X-RateLimit-Remaining: 0\r\nX-RateLimit-Reset: 220\r\n"),
                     self.response(200, run(1))]
        waits = []
        client = cleanup.GitHub("gh", run=lambda *_a, **_k: responses.pop(0), sleep=waits.append, clock=lambda: 100)
        client.get_run(1)
        self.assertEqual(waits, [121])
        client = cleanup.GitHub("gh", run=lambda *_a, **_k: self.response(429, headers="Retry-After: 600\r\n"), sleep=waits.append)
        with self.assertRaises(cleanup.CleanupError):
            client.get_run(1)
        self.assertEqual(waits, [121])

    def test_denied_or_malformed_responses_are_not_retried_or_echoed(self):
        for response in (self.response(403), SimpleNamespace(returncode=1, stdout=b"secret", stderr=b"secret"),
                         self.response(200, run(1))):
            client = cleanup.GitHub("gh", run=lambda *_a, value=response, **_k: value)
            with self.subTest(code=response.stdout[:15]), self.assertRaises(cleanup.CleanupError) as error:
                client.delete_run(1)
            self.assertNotIn("secret", str(error.exception))


class TriggerAndSourceTests(unittest.TestCase):
    def setUp(self):
        self.environment = {"GITHUB_EVENT_NAME": "workflow_run", "GITHUB_REF": "refs/heads/main",
                            "GITHUB_REPOSITORY": cleanup.REPOSITORY, "GITHUB_RUN_ID": "99"}
        parent = run(80, path=".github/workflows/compose-images.yml", name="Compose images and bundles", event="workflow_dispatch")
        self.client = FakeGitHub([parent])
        self.event = {"repository": {"full_name": cleanup.REPOSITORY}, "action": "completed",
                      "workflow_run": {"id": 80, "head_sha": "a" * 40, "conclusion": "success"}}

    def test_successful_default_branch_publisher_is_authorized_and_protected(self):
        self.assertEqual(cleanup.authorize_event(self.environment, self.event, self.client, True), (99, 80))

    def test_failure_fork_branch_wrong_workflow_or_stale_payload_cannot_authorize_deletion(self):
        changes = ({"conclusion": "failure"}, {"status": "queued"}, {"head_branch": "feature"},
                   {"path": ".github/workflows/tests.yml"}, {"event": "pull_request"},
                   {"head_repository": {"full_name": "fork/TG2Cloud"}}, {"head_repository": None},
                   {"head_sha": "b" * 40})
        for change in changes:
            client = FakeGitHub([self.client.runs[80] | change])
            with self.subTest(change=change), self.assertRaises(cleanup.CleanupError):
                cleanup.authorize_event(self.environment, self.event, client, True)

    def test_foreign_or_untrusted_workflow_context_is_rejected(self):
        for key, value in (("GITHUB_REPOSITORY", "fork/TG2Cloud"), ("GITHUB_REF", "refs/heads/feature"),
                           ("GITHUB_RUN_ID", "0"), ("GITHUB_EVENT_NAME", "pull_request")):
            with self.subTest(key=key), self.assertRaises(cleanup.CleanupError):
                cleanup.authorize_event(self.environment | {key: value}, self.event, self.client, True)
        with self.assertRaises(cleanup.CleanupError):
            cleanup.authorize_event({}, {}, self.client, True)

    def test_manual_dispatch_defaults_to_preview_and_requires_explicit_false_to_apply(self):
        environment = self.environment | {"GITHUB_EVENT_NAME": "workflow_dispatch"}
        for value in ({}, {"dry_run": "true"}, {"dry_run": 0}):
            event = self.event | {"inputs": value}
            self.assertEqual(cleanup.authorize_event(environment, event, self.client, False), (99, 0))
            with self.assertRaises(cleanup.CleanupError):
                cleanup.authorize_event(environment, event, self.client, True)
        for value in (False, "false"):
            self.assertEqual(cleanup.authorize_event(environment, self.event | {"inputs": {"dry_run": value}}, self.client, True), (99, 0))

    def test_malformed_event_or_inputs_cannot_enable_deletion(self):
        environment = self.environment | {"GITHUB_EVENT_NAME": "workflow_dispatch"}
        for event in (None, [], {"repository": None}, self.event | {"inputs": None},
                      self.event | {"inputs": []}):
            with self.subTest(event=event), self.assertRaises(cleanup.CleanupError):
                cleanup.authorize_event(environment, event, self.client, True)

    def test_only_tracked_local_markdown_can_supply_documented_run_ids(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        (root / "notes.md").write_text(f"[evidence](https://github.com/{cleanup.REPOSITORY}/actions/runs/123)\n")
        (root / "private.md").write_text(f"https://github.com/{cleanup.REPOSITORY}/actions/runs/999\n")
        subprocess.run(["git", "add", "notes.md"], cwd=root, check=True, capture_output=True)
        self.assertEqual(cleanup.documented_ids(root), {123})

    def test_workflow_uses_only_trusted_code_minimum_permissions_and_safe_defaults(self):
        text = (ROOT / ".github/workflows/actions-cleanup.yml").read_text(encoding="utf-8")
        for required in ('workflows: ["Compose images and bundles"]', "types: [completed]", "branches: [main]",
                         "github.event.workflow_run.conclusion == 'success'", "ref: ${{ github.workflow_sha }}",
                         "persist-credentials: false", "actions: write", "contents: read", "default: true",
                         "cancel-in-progress: false", "if: always()", "retention-days: 30"):
            self.assertIn(required, text)
        for forbidden in ("head_branch }}", "workflow_run.head_sha }}", "contents: write", "packages: write",
                          "pull_request:", "release:\n", "schedule:", "secrets.PAT"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
