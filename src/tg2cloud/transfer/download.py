from __future__ import annotations

import asyncio
import os
import time

from tg2cloud.domain.errors import (
    safe_failure,
)
from tg2cloud.domain.naming import (
    safe_file_name,
)


async def _download_one(self, task_id: int) -> None:
    task = self.db.get(task_id)
    if not task:
        return
    if task.get("transfer_mode") == "stream":
        await self._stream_one(task_id)
        return
    part_path = self.settings.download_dir / f"{task_id}.part"
    final_name = f"{task_id}-{safe_file_name(task['file_name'], str(task_id))}"
    final_path = self.settings.download_dir / final_name
    last_progress_at = 0.0

    def progress(received: int, total: int) -> None:
        nonlocal last_progress_at
        now = time.monotonic()
        if now - last_progress_at >= 1 or received >= total:
            self.db.update(task_id, downloaded_bytes=int(received))
            self._record_progress(task_id, "download", int(received))
            last_progress_at = now

    try:
        for attempt in range(
            int(task["download_retries"]), self.settings.max_retries
        ):
            self.db.transition(
                task_id,
                "downloading",
                downloaded_bytes=0,
                download_retries=attempt,
                local_path=str(part_path),
                error=None,
                wait_reason=None,
            )
            if part_path.exists():
                part_path.unlink()
            try:
                message = await self.source.get_messages(
                    int(task["chat_id"]), ids=int(task["message_id"])
                )
                if not message or not message.media:
                    raise RuntimeError("Telegram 消息或文件已经不可访问")
                result = await self.source.download_media(
                    message, file=str(part_path), progress_callback=progress
                )
                if not result or not part_path.is_file():
                    raise RuntimeError("Telethon 没有生成下载文件")
                actual_size = part_path.stat().st_size
                if actual_size != int(task["file_size"]):
                    raise RuntimeError(
                        f"本地大小错误：{actual_size} != {task['file_size']}"
                    )
                # Persist the final path before the atomic rename. A crash
                # after the rename can then recover the completed file.
                self.db.transition(
                    task_id,
                    "downloaded",
                    local_path=str(final_path),
                    downloaded_bytes=actual_size,
                )
                os.replace(part_path, final_path)
                self.db.transition(
                    task_id,
                    "waiting_upload",
                    local_path=str(final_path),
                    downloaded_bytes=actual_size,
                    download_retries=attempt,
                    error=None,
                    wait_reason=None,
                    next_retry_at=0,
                )
                await self._notify(
                    f"⬇️ 下载完成，等待上传\n任务：#{task_id}\n"
                    f"文件：{task['file_name']}"
                )
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry external I/O
                self.recent_download_errors.append(time.time())
                self.log.warning(
                    "任务 #%s 下载第 %s 次失败：%s", task_id, attempt + 1, exc
                )
                self.db.update(
                    task_id,
                    download_retries=attempt + 1,
                    error=safe_failure(exc),
                )
                if attempt + 1 < self.settings.max_retries:
                    await asyncio.sleep(min(60, 2 ** (attempt + 1)))
        if part_path.exists():
            part_path.unlink()
        self.db.transition(
            task_id,
            "download_failed",
            local_path=None,
            error="下载重试次数已经用完",
            wait_reason=None,
        )
        await self._notify(
            f"❌ 下载失败\n任务：#{task_id}\n"
            "不完整文件已清理，可使用 /retry 重新排队。"
        )
    except asyncio.CancelledError:
        current = self.db.get(task_id)
        if current and current["state"] not in {"cancelled", "completed", "confirmed", "cleanup_pending"}:
            if final_path.is_file() and final_path.stat().st_size == int(task["file_size"]):
                self.db.transition(task_id, "waiting_upload", local_path=str(final_path))
            else:
                if not current.get("cancel_requested") and part_path.exists():
                    part_path.unlink()
                self.db.transition(task_id, "queued", local_path=None, downloaded_bytes=0)
        raise
    except Exception as exc:
        self.log.exception("任务 #%s 下载发生未处理异常", task_id)
        if part_path.exists():
            part_path.unlink()
        self.db.transition(
            task_id,
            "download_failed",
            local_path=None,
            error=safe_failure(exc),
        )
