from __future__ import annotations

from pathlib import Path
from typing import Any

from tg2cloud.domain.errors import RemoteReviewRequired, needs_review
from tg2cloud.domain.states import FAILED_STATES
from tg2cloud.storage.policies import policy_for


async def _resume_remote(
    self, task_id: int, task: dict[str, Any], local_path: Path | None,
    safe_name: str,
) -> bool:
    current = self.db.get(task_id) or task
    legacy = str(current.get("remote_path") or "")
    final = str(current.get("remote_final_path") or
                (legacy if legacy and not legacy.startswith(".uploading-") else ""))
    temp = str(current.get("remote_temp_path") or
               (legacy if legacy.startswith(".uploading-") else ""))
    if final and await self.rclone.exists(final):
        if await self.rclone.remote_size(final) != int(task["file_size"]):
            raise RemoteReviewRequired("记录的正式文件大小不符；停止覆盖并保留本地数据")
        await self._complete_cloud_receive(task_id, task, local_path, final)
        return True
    if temp and await self.rclone.exists(temp):
        if not policy_for(self.settings).allow_legacy_temp_resume:
            raise RemoteReviewRequired(
                "检测到旧版 OpenList 临时文件；不会自动改名或覆盖，请先人工核对"
            )
        if await self.rclone.remote_size(temp) == int(task["file_size"]):
            await self._finalize_stream_remote(task_id, task, temp, safe_name, local_path)
            return True
        raise RemoteReviewRequired("远端临时文件不完整；保留现场，请确认换名重传")
    return False

def _local_complete(self, task: dict[str, Any]) -> bool:
    if not task.get("local_path"):
        return False
    path = Path(task["local_path"])
    try:
        return (path.resolve().is_relative_to(self.settings.download_dir.resolve())
                and not path.is_symlink() and path.is_file()
                and not path.name.endswith(".part") and path.stat().st_size == task["file_size"])
    except OSError:
        return False

def _retry_task(self, task: dict[str, Any]) -> bool:
    task_id = int(task["id"])
    if (task_id in getattr(self, "_cancelling", set())
            or task_id in self.download_tasks or task_id in self.upload_tasks):
        return False
    task = self.db.get(task_id) or task
    if task.get("sender_id") != self.settings.allowed_user_id or needs_review(task):
        return False
    state = task["state"]
    if task.get("cancel_requested"):
        # A manual retry withdraws the cancellation intent, not its paths.
        self.db.update(task_id, cancel_requested=0)
        self.db.recover(self.settings.download_dir, task_id=task_id)
        task = self.db.get(task_id) or task
        state = task["state"]
    if state in FAILED_STATES:
        return self.db.requeue(
            task_id, sender_id=self.settings.allowed_user_id,
            expected_updated_at=task["updated_at"], local_complete=self._local_complete(task),
        )
    return state in {"queued", "waiting_upload"}
