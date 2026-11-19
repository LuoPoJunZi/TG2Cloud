"""Maintain Actions history after verified publication; never alter release assets."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "LuoPoJunZi/TG2Cloud"
KEEP_RECENT = 50
PUBLISHERS = {".github/workflows/release.yml", ".github/workflows/compose-images.yml"}
TERMINAL = {"success", "failure", "neutral", "cancelled", "timed_out", "skipped", "stale", "startup_failure"}
IDENTITY_FIELDS = ("head_sha", "workflow_id", "run_attempt", "updated_at", "status", "conclusion")


class CleanupError(ValueError):
    """Safe error text only; API responses and credentials are never echoed."""


def valid_id(value):
    if type(value) is not int or value <= 0:
        raise CleanupError("Invalid run identity")
    return value


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed
    except (AttributeError, ValueError):
        pass
    raise CleanupError("Invalid run timestamp")


def validate_run(run):
    try:
        valid_id(run["id"])
        valid_id(run["workflow_id"])
        valid_id(run["run_attempt"])
        if run["repository"]["full_name"].lower() != REPOSITORY.lower():
            raise CleanupError("Foreign repository response")
        if not isinstance(run["status"], str) or not isinstance(run["path"], str):
            raise CleanupError("Invalid workflow run state")
        if run.get("conclusion") is not None and not isinstance(run["conclusion"], str):
            raise CleanupError("Invalid workflow run conclusion")
        if not isinstance(run["name"], str) or not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]):
            raise CleanupError("Invalid workflow run identity")
        timestamp(run["created_at"])
        timestamp(run["updated_at"])
    except (AttributeError, KeyError, TypeError):
        raise CleanupError("Incomplete workflow run response") from None
    return run


def unfinished(run):
    return run["status"] != "completed" or run.get("conclusion") not in TERMINAL


def publication(run):
    path = run["path"].split("@", 1)[0]
    return (run["status"] == "completed" and run.get("conclusion") == "success"
            and (path in PUBLISHERS or run["name"].lower() in {"release", "compose images and bundles"}))


def ordered(runs):
    return sorted(runs, key=lambda item: (timestamp(item["created_at"]), item["id"]), reverse=True)


def make_plan(runs, references, protected_ids=()):
    runs = ordered([validate_run(run) for run in runs])
    if len({run["id"] for run in runs}) != len(runs):
        raise CleanupError("Duplicate workflow run identities")
    recent = {run["id"] for run in runs[:KEEP_RECENT]}
    reasons = {}
    for run in runs:
        why = []
        if run["id"] in recent:
            why.append("latest_50")
        if unfinished(run):
            why.append("unfinished_or_approval_required")
        if publication(run):
            why.append("successful_publication")
        if run["id"] in references:
            why.append("documented_evidence")
        if run["id"] in protected_ids:
            why.append("current_or_triggering_workflow")
        if why:
            reasons[run["id"]] = why
    candidates = [run for run in runs if run["id"] not in reasons]
    return runs, reasons, candidates


def documented_ids(root):
    result = subprocess.run(["git", "ls-files", "-z", "--", "*.md"], cwd=root,
                            capture_output=True, check=False, timeout=30)  # nosec B603 B607
    if result.returncode:
        raise CleanupError("Cannot inventory tracked documentation")
    pattern = re.compile(r"https://github[.]com/" + re.escape(REPOSITORY) + r"/actions/runs/(\d+)", re.IGNORECASE)
    identities = set()
    for name in result.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise CleanupError("Unsafe documentation source")
        identities.update(map(int, pattern.findall(path.read_text(encoding="utf-8"))))
    return identities


class GitHub:
    def __init__(self, executable, *, run=subprocess.run, sleep=time.sleep, clock=time.time):
        self.executable, self.run, self.sleep, self.clock = executable, run, sleep, clock

    def request(self, method, resource):
        if method not in {"GET", "DELETE"} or not re.fullmatch(r"/actions/runs(?:/\d+|\?per_page=100(?:&page=\d+)?)?", resource):
            raise CleanupError("API operation outside Actions run scope")
        if method == "DELETE" and not re.fullmatch(r"/actions/runs/[1-9]\d*", resource):
            raise CleanupError("Only an explicit workflow run can be deleted")
        command = [self.executable, "api", "--hostname", "github.com", "--method", method, "--include",
                   "repos/" + REPOSITORY + resource]
        for attempt in range(4):
            result = self.run(command, capture_output=True, check=False, timeout=65)  # nosec B603
            parts = re.split(rb"\r?\n\r?\n", result.stdout, maxsplit=1)
            match = re.search(rb"^HTTP/\S+\s+(\d+)", parts[0])
            if not match:
                raise CleanupError("GitHub returned no verifiable HTTP result")
            status = int(match[1])
            headers = {key.decode().lower(): value.decode().strip() for key, value in
                       re.findall(rb"(?m)^([^:\r\n]+):\s*([^\r\n]*)", parts[0])}
            body = parts[1] if len(parts) > 1 else b""
            limited = status in {403, 429} and ("retry-after" in headers
                        or headers.get("x-ratelimit-remaining") == "0" or b"rate limit" in body.lower())
            if limited:
                if attempt == 3:
                    raise CleanupError("GitHub rate limit persists; inspect audit and retry later")
                delay = max(60 * 2**attempt, int(headers.get("retry-after", "0")))
                if headers.get("x-ratelimit-remaining") == "0":
                    delay = max(delay, int(headers.get("x-ratelimit-reset", "0")) - self.clock() + 1)
                if delay > 300:
                    raise CleanupError("GitHub rate limit reset is too far away; retry after reset")
                self.sleep(delay)
                continue
            allowed = {200, 404} if method == "GET" else {204, 404, 409, 422}
            if status in allowed:
                return status, json.loads(body) if status == 200 else None
            raise CleanupError(f"GitHub Actions request failed (HTTP {status})")
        raise CleanupError("GitHub request did not complete")

    def get_run(self, run_id):
        status, value = self.request("GET", "/actions/runs/" + str(valid_id(run_id)))
        return validate_run(value) if status == 200 else None

    def latest(self):
        status, value = self.request("GET", "/actions/runs?per_page=100")
        if status != 200:
            raise CleanupError("Cannot read recent workflow runs")
        return ordered([validate_run(run) for run in value["workflow_runs"]])[:KEEP_RECENT]

    def list_runs(self):
        # No search filters: filtered Actions searches are capped at 1,000 results.
        identities, expected = {}, 0
        for page in range(1, 101):
            status, value = self.request("GET", f"/actions/runs?per_page=100&page={page}")
            if status != 200:
                raise CleanupError("Cannot enumerate workflow runs")
            if page == 1:
                expected = value["total_count"]
            for run in value["workflow_runs"]:
                identities[validate_run(run)["id"]] = run
            if len(value["workflow_runs"]) < 100:
                if len(identities) < expected:
                    raise CleanupError("Run inventory changed or is incomplete; retry before deleting")
                return ordered(identities.values())
        raise CleanupError("Run inventory exceeds this maintenance window; no deletion started")

    def delete_run(self, run_id):
        status, _ = self.request("DELETE", "/actions/runs/" + str(valid_id(run_id)))
        return {204: "deleted", 404: "already_absent", 409: "preserved_server_state", 422: "preserved_server_state"}[status]


def authorize_event(environment, event, client, apply):
    if not environment.get("GITHUB_EVENT_NAME") and not apply:
        return 0, 0
    if not isinstance(event, dict) or not isinstance(event.get("repository"), dict):
        raise CleanupError("Invalid workflow event")
    if (environment.get("GITHUB_REPOSITORY") != REPOSITORY
            or event.get("repository", {}).get("full_name") != REPOSITORY
            or environment.get("GITHUB_REF") != "refs/heads/main"):
        raise CleanupError("Cleanup requires the trusted repository default branch")
    try:
        current_id = valid_id(int(environment["GITHUB_RUN_ID"]))
    except (KeyError, ValueError):
        raise CleanupError("Invalid current workflow identity") from None
    name = environment["GITHUB_EVENT_NAME"]
    if name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        if not isinstance(inputs, dict):
            raise CleanupError("Invalid manual workflow inputs")
        dry_run = inputs.get("dry_run", "true")
        if apply and dry_run is not False and dry_run != "false":
            raise CleanupError("Manual execution defaults to preview; deletion was not selected")
        return current_id, 0
    if name != "workflow_run" or event.get("action") != "completed":
        raise CleanupError("Unsupported cleanup event")
    supplied = event.get("workflow_run", {})
    if not isinstance(supplied, dict):
        raise CleanupError("Invalid triggering workflow")
    parent = client.get_run(valid_id(supplied.get("id")))
    if (not parent or parent["path"].split("@", 1)[0] != ".github/workflows/compose-images.yml"
            or parent.get("event") != "workflow_dispatch" or parent.get("head_branch") != "main"
            or (parent.get("head_repository") or {}).get("full_name") != REPOSITORY
            or parent.get("status") != "completed" or parent.get("conclusion") != "success"
            or supplied.get("head_sha") != parent["head_sha"]
            or supplied.get("conclusion") != "success"):
        raise CleanupError("Trigger was not a successful trusted Compose publication")
    return current_id, parent["id"]


def write_json(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write("\n")
    path.chmod(0o600)


def audit_row(run, reasons):
    return {key: run.get(key) for key in ("id", "name", "path", "created_at", "updated_at", "status", "conclusion",
                                        "head_sha", "head_branch", "workflow_id", "run_attempt")} | {"reasons": reasons}


def cleanup(client, root, directory, *, apply=False, current_id=0, parent_id=0,
            references=None, sleep=time.sleep, clock=time.monotonic):
    root = root.resolve()
    if (directory.is_symlink() or not directory.resolve().is_relative_to(root / "build")
            or directory.absolute() != directory.resolve()):
        raise CleanupError("Audit directory must be a regular build subdirectory")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    summary = {"repository": REPOSITORY, "mode": "apply" if apply else "preview", "state": "failed",
               "keep_recent": KEEP_RECENT, "deleted": 0, "already_absent": 0, "preserved_changed": 0}
    try:
        references = documented_ids(root) if references is None else references
        runs, protected, candidates = make_plan(client.list_runs(), references, {current_id, parent_id})
        summary.update(before=len(runs), protected=len(protected), candidates=len(candidates),
                       missing_documented_references=len(set(references) - {r["id"] for r in runs}))
        write_json(directory / "plan.json", {"repository": REPOSITORY, "created_at": datetime.now(timezone.utc).isoformat(),
                   "keep": [audit_row(r, protected[r["id"]]) for r in runs if r["id"] in protected],
                   "delete_candidates": [audit_row(r, []) for r in candidates]})
        if not apply:
            summary["state"] = "preview"
            return summary
        removed, changed = set(), set()
        next_write = 0.0
        with (directory / "journal.jsonl").open("x", encoding="utf-8", newline="\n") as journal:
            for index, snapshot in enumerate(candidates):
                if index % 25 == 0:
                    for run in client.latest():
                        protected.setdefault(run["id"], ["fresh_latest_50"])
                run_id = snapshot["id"]
                fresh = client.get_run(run_id)
                if fresh is None:
                    outcome = "already_absent"
                elif (run_id in protected or unfinished(fresh) or publication(fresh)
                      or any(fresh.get(key) != snapshot.get(key) for key in IDENTITY_FIELDS)):
                    outcome = "preserved_changed"
                else:
                    delay = max(0, next_write - clock())
                    if delay:
                        sleep(delay)
                    next_write = clock() + 1
                    outcome = client.delete_run(run_id)
                if outcome in {"deleted", "already_absent"}:
                    removed.add(run_id)
                    summary[outcome] += 1
                else:
                    changed.add(run_id)
                    summary["preserved_changed"] += 1
                journal.write(json.dumps({"id": run_id, "outcome": outcome}) + "\n")
                journal.flush()
        remaining = {r["id"] for r in client.list_runs()}
        # Only snapshot/fresh protected IDs actually observed in inventory are checked.
        if not set(protected) <= remaining or not changed <= remaining or removed & remaining:
            raise CleanupError("Post-cleanup inventory did not preserve the protected set")
        summary.update(state="verified", after=len(remaining), protected=len(protected))
        return summary
    finally:
        write_json(directory / "summary.json", summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Only allowed by a verified workflow event")
    args = parser.parse_args(argv)
    directory = ROOT / "build/actions-cleanup"
    try:
        executable = shutil.which("gh")
        if not executable:
            raise CleanupError("GitHub CLI is required")
        client = GitHub(executable)
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        event = json.loads(Path(event_path).read_text(encoding="utf-8")) if event_path else {}
        current, parent = authorize_event(os.environ, event, client, args.apply)
        report = cleanup(client, ROOT, directory, apply=args.apply, current_id=current, parent_id=parent)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (CleanupError, OSError, ValueError, subprocess.SubprocessError):
        print("Actions cleanup did not complete; inspect the audit summary before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
