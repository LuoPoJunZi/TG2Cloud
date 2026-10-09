"""Skip branch-only EXE builds when their inputs did not change (stdlib only)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

INPUT_FILES = {
    "build.ps1", "requirements-build.txt", ".gitattributes",
    "installer.py", "installer_clouddrive2.py", "installer_openlist.py",
    "deployer_products.py", "domain_proxy.py", "operation_feedback.py",
    "proxy_maintenance.py", "vps_resources.py",
}
INPUT_DIRECTORIES = ("assets/brand/", "packaging/windows/", "payload_clouddrive2/", "payload_openlist/")
SHA = re.compile(r"[0-9a-f]{40}")


def requires_build(paths: list[str]) -> bool:
    return any(path in INPUT_FILES or path.startswith(INPUT_DIRECTORIES)
               or ("/" not in path and path.endswith(".py")) for path in paths)


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


def event_requires_build(event_name: str, event: dict) -> bool:
    if event_name == "workflow_dispatch":
        return True
    if event_name == "push":
        base = event.get("before", "")
        head = event.get("after", "")
    elif event_name == "pull_request":
        request = event.get("pull_request", {})
        base = request.get("base", {}).get("sha", "")
        head = request.get("head", {}).get("sha", "")
        if not SHA.fullmatch(base) or not SHA.fullmatch(head):
            return True
        base = git("merge-base", base, head)
    else:
        return True
    # Unknown history must build, never silently skip validation.
    if not SHA.fullmatch(base) or not SHA.fullmatch(head) or base == "0" * 40:
        return True
    paths = git("diff", "--name-only", "-z", "--no-renames", base, head, "--").split("\0")
    return requires_build(paths)


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    try:
        build = event_requires_build(os.environ["GITHUB_EVENT_NAME"], event)
    except subprocess.CalledProcessError:
        build = True
    value = str(build).lower()
    print("EXE inputs changed: " + value)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write("build=" + value + "\n")


if __name__ == "__main__":
    main()
