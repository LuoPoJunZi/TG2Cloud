"""Existing guarded task operations; extracted without changing eligibility or order."""
from __future__ import annotations

import asyncio
import secrets
import time
from pathlib import Path
from typing import Any, Protocol

from tg2cloud.domain.errors import (
    STAGING_PATTERN,
    StagingScan,
    needs_review,
    safe_failure,
)

ORPHAN_CLEANUP_LIMIT = 100
TERMINAL_TASK_STATES = {"completed", "confirmed", "cancelled"}

class ReplySink(Protocol):
    async def reply(self, text: str, **kwargs) -> Any: ...

def _is_orphan_staging(self, task_id: int, remote_path: str) -> bool:
    match = STAGING_PATTERN.fullmatch(remote_path)
    if not match or int(match[1]) != task_id or self.db.protected_remote(remote_path):
        return False
    task = self.db.get(task_id)
    if task is None:
        return True
    recorded_paths = {
        str(task.get("remote_temp_path") or ""),
        str(task.get("remote_final_path") or ""),
        str(task.get("remote_path") or ""),
    }
    if remote_path in recorded_paths:
        return False
    # Any non-terminal task with the same id may be about to claim its
    # deterministic staging name. Keep it even when the path is not yet saved.
    return task["state"] in TERMINAL_TASK_STATES

async def _find_orphan_staging(self) -> list[tuple[int, str]]:
    self._last_staging_scan = StagingScan(complete=False, reason="未取得完整清单")
    inspect_staging = getattr(self.rclone, "list_staging_objects", None)
    if not callable(inspect_staging):
        raise NotImplementedError
    objects = await asyncio.wait_for(inspect_staging(), timeout=45)
    scan = objects if isinstance(objects, StagingScan) else StagingScan(objects, len(objects), len(objects))
    self._last_staging_scan = scan
    if not scan.complete:
        raise RuntimeError("扫描未完成；禁止生成或执行清理计划")
    return [
        (task_id, remote_path)
        for task_id, remote_path in objects
        if self._is_orphan_staging(task_id, remote_path)
    ]

async def _confirm_orphan_cleanup(
    self, event: ReplySink, token: str
) -> None:
    plan = getattr(self, "_orphan_cleanup_plan", None)
    if not plan or time.monotonic() > float(plan["expires_at"]):
        self._orphan_cleanup_plan = None
        await event.reply(
            "清理结果\n\n执行状态：没有执行\n"
            "失败原因：确认码不存在或已过期\n"
            "后续操作：请重新发送 /orphans clean"
        )
        return
    if not secrets.compare_digest(str(plan["token"]), token):
        await event.reply(
            "清理结果\n\n执行状态：没有执行\n"
            "失败原因：清理确认码不正确\n"
            "安全处理：未删除任何内容"
        )
        return
    # Consume before any mutation so retries cannot replay a partially used plan.
    self._orphan_cleanup_plan = None
    try:
        current = set(await self._find_orphan_staging())
    except Exception as exc:  # noqa: BLE001 - fail closed on rescan
        self.log.warning("清理前重新巡检远端临时文件失败：%s", exc)
        await event.reply(
            "清理结果\n\n执行状态：清理中止\n"
            "失败原因：清理前重新巡检失败\n"
            "安全处理：未删除任何内容，请重新发起巡检"
        )
        return
    deleted = 0
    protected = 0
    for task_id, remote_path in plan["objects"]:
        if (task_id, remote_path) not in current or not self._is_orphan_staging(
            task_id, remote_path
        ):
            protected += 1
            continue
        try:
            await asyncio.wait_for(self.rclone.remove(remote_path), timeout=60)
            if await asyncio.wait_for(self.rclone.exists(remote_path), timeout=45):
                raise RuntimeError("远端文件删除后仍然存在")
        except Exception as exc:  # noqa: BLE001 - fail closed on remote cleanup
            self.log.warning("远端遗留临时文件清理失败：%s", exc)
            await event.reply(
                "清理结果\n\n"
                f"执行状态：清理在删除 {deleted} 个后停止\n"
                "失败原因：无法确认下一项已经安全删除\n"
                f"跳过数量：{protected} 个已消失或受任务保护\n"
                "后续操作：请重新执行 /orphans 巡检"
            )
            return
        deleted += 1
    await event.reply(
        "清理结果\n\n"
        "执行状态：清理完成\n"
        f"删除数量：已删除并复查 {deleted} 个遗留临时文件\n"
        f"跳过数量：跳过 {protected} 个已消失或受任务保护的文件"
    )

async def _command_cancel(
    self, event: ReplySink, parts: list[str]
) -> None:
    task_id = self._parse_task_id(parts)
    if not hasattr(self, "_cancelling"):
        self._cancelling: set[int | None] = set()
    if task_id in self._cancelling:
        await event.reply("这个任务正在取消清理，请等待结果。")
        return
    self._cancelling.add(task_id)
    try:
        await self._cancel_task_command(event, parts)
    finally:
        self._cancelling.discard(task_id)

async def _cancel_task_command(
    self, event: ReplySink, parts: list[str]
) -> None:
    task_id = self._parse_task_id(parts)
    task = self.db.get(task_id) if task_id else None
    if task is None:
        await event.reply("使用说明\n\n正确格式：/cancel <任务编号>")
        return
    if needs_review(task):
        await event.reply("远端文件归属或完整性待核对，取消不会删除这些文件。请先使用 /recover 换名恢复，或人工核对。")
        return
    if task["state"] in {
        "completed",
        "confirmed",
        "cleanup_pending",
        "cancelled",
    }:
        await event.reply(
            self._format_operation_result(
                status="没有执行",
                operation="取消任务",
                note="当前任务已经结束或正在执行最终清理",
                task=task,
            )
        )
        return
    self.db.update(
        task_id,
        cancel_requested=1,
        wait_reason="取消清理待完成；失败后可再次 /cancel 或手动 /retry",
    )
    running = self.download_tasks.get(task_id) or self.upload_tasks.get(task_id)
    if running:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
    task = self.db.get(task_id)
    if task is None:
        await event.reply(
            "操作结果\n\n执行状态：已经中止\n"
            "执行操作：取消任务\n后续说明：任务记录已经不存在"
        )
        return
    if needs_review(task):
        self.db.update(task_id, cancel_requested=0)
        await event.reply("任务已进入远端结果待核对状态；保留本地和远端文件，请刷新详情。")
        return
    if task["state"] in {
        "completed",
        "confirmed",
        "cleanup_pending",
        "cancelled",
    }:
        await event.reply(
            self._format_operation_result(
                status="没有执行",
                operation="取消任务",
                note="任务已在等待期间结束或进入最终清理",
                task=task,
            )
        )
        self.db.update(task_id, cancel_requested=0)
        return
    remote_paths = dict.fromkeys(
        str(task.get(key) or "")
        for key in ("remote_temp_path", "remote_final_path", "remote_path")
    )
    for remote_path in filter(None, remote_paths):
        try:
            if await self.rclone.exists(remote_path):
                await self.rclone.remove(remote_path)
            if await self.rclone.exists(remote_path):
                raise RuntimeError("远端文件删除后仍然存在")
        except Exception as exc:  # noqa: BLE001 - fail closed on remote cleanup
            await event.reply(
                self._format_operation_result(
                status="取消中止",
                    operation="取消任务",
                    note=f"远端无法确认安全清理，本地副本已保留：{safe_failure(exc)}",
                    task=task,
                )
            )
            return
    local_path = Path(task["local_path"]) if task.get("local_path") else None
    if local_path and local_path.exists():
        try:
            local_path.unlink()
        except OSError as exc:
            await event.reply(
                self._format_operation_result(
                    status="取消中止",
                    operation="取消任务",
                    note=f"无法安全删除本地文件：{exc}",
                    task=task,
                )
            )
            return
    part = self.settings.download_dir / f"{task_id}.part"
    if part.exists():
        try:
            part.unlink()
        except OSError as exc:
            await event.reply(
                self._format_operation_result(
                    status="取消中止",
                    operation="取消任务",
                    note=f"无法安全删除下载临时文件：{exc}",
                    task=task,
                )
            )
            return
    self.db.transition(
        task_id,
        "cancelled",
        local_path=None,
        remote_path=None,
        remote_temp_path=None,
        remote_final_path=None,
        cancel_requested=0,
        downloaded_bytes=0,
        uploaded_bytes=0,
        error=None,
        wait_reason=None,
    )
    updated = self.db.get(task_id)
    await event.reply(
        self._format_operation_result(
            status="操作成功",
            operation="取消任务",
            note="本地临时文件和本任务远端文件已经清理",
            task=updated,
        )
    )
