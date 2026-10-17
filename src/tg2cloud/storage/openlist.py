"""OpenList writes a reserved fresh final path; legacy MOVE stays conservative."""
from __future__ import annotations

from tg2cloud.domain.errors import RemoteReviewRequired


class OpenListCommit:
    direct_final = True
    allow_legacy_temp_resume = False
    probe_cooldown = True

    async def begin(self, service, task_id, task, safe_name, state, remote_temp, **fields):
        async with service._finalize_lock:
            current = service.db.get(task_id) or task
            final_remote = str(current.get("remote_final_path") or "")
            if not final_remote:
                final_remote = await service._choose_remote_final(safe_name, task_id)
            elif await service.rclone.exists(final_remote):
                raise RemoteReviewRequired("预留的 OpenList 最终路径已经存在；保留文件并等待复核")
            service.db.transition(task_id, state, remote_path=final_remote,
                                  remote_temp_path=None, remote_final_path=final_remote, **fields)
            return final_remote
