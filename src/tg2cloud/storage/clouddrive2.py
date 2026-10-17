"""CloudDrive2 commit policy: staging, size verification, rename and recheck."""
from __future__ import annotations


class CloudDrive2Commit:
    direct_final = False
    allow_legacy_temp_resume = True
    probe_cooldown = False

    async def begin(self, service, task_id, task, safe_name, state, remote_temp, **fields):
        service.db.transition(task_id, state, remote_path=remote_temp,
                              remote_temp_path=remote_temp, **fields)
        return remote_temp
