"""Backend capability boundary, independent of rclone process execution."""
from __future__ import annotations

from typing import Protocol

from .clouddrive2 import CloudDrive2Commit
from .openlist import OpenListCommit


class CommitPolicy(Protocol):
    direct_final: bool
    allow_legacy_temp_resume: bool
    probe_cooldown: bool

    async def begin(self, service, task_id, task, safe_name, state, remote_temp, **fields) -> str: ...


def policy_for(settings) -> CommitPolicy:
    return OpenListCommit() if getattr(settings, "storage_backend", "clouddrive2") == "openlist" else CloudDrive2Commit()
