"""Bounded administrator operations; reuse plans, admission and identity checks."""
from __future__ import annotations

import asyncio
import copy
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

from tg2cloud.domain.classification import directory as classified_directory
from tg2cloud.domain.errors import needs_review
from tg2cloud.domain.planning import PlanningError
from tg2cloud.domain.source_directories import media_directory
from tg2cloud.listening import account, rules
from tg2cloud.listening.service import (
    AUTH_ERRORS,
    FLOOD_WAITS,
    CheckedSource,
    album_captions,
    message_caption,
    source_error,
    verified_chat,
)
from tg2cloud.persistence.plans import Plans

MAX_TEMPLATES = 8
RECOVERY_BATCH = 5
HISTORY_LIMIT = 100
HISTORY_TIMEOUT = 20


def repository(owner, actor):
    repo = Plans(owner.db, owner.settings.allowed_user_id)
    repo.authorize(actor, admin=True)
    return repo


def live(owner, actor, source_id, revision=None, client=None):
    repo = repository(owner, actor)
    source = repo.source(actor, source_id)
    state = account.state(owner.db)
    current = owner.listener.client
    if (source["deleted"] or not source["enabled"] or not state.get("enabled")
            or source["account"] != state.get("account") or not current
            or client is not None and current is not client):
        raise PlanningError("监听账号、来源或连接已变化；请先启用来源并重新打开。")
    if revision is not None and source["revision"] != revision:
        raise PlanningError("来源规则已变化，请重新预览。")
    if state.get("cooldown_until", 0) > time.time():
        raise PlanningError("Telegram 仍在冷却，请等待后重新预览，不重复请求。")
    return source


def destination(owner, actor, source, *, kind="视频", mime="video/mp4", extension=".mp4"):
    repo = repository(owner, actor)
    cfg = source["config"]
    relative = media_directory(cfg, kind=kind, mime=mime, extension=extension,
                               base=owner.settings.cd2_target)
    if relative is None:
        relative = (repo.directory(actor, cfg["directory"])
                    or cfg["profile"]["directory"]
                    or classified_directory(owner.db.feature_settings(), time.time(),
                                            kind=kind, mime=mime, extension=extension))
    return "Bot 保存目录" + ("/" + relative if relative else "（无附加子目录）")


def template_store(repo, actor):
    repo.authorize(actor, admin=True)
    key = f"listener_rule_templates:{actor}"
    row = repo.c.execute("SELECT value FROM service_meta WHERE key=?", (key,)).fetchone()
    value = json.loads(row[0]) if row else {"format": 1, "revision": 0, "items": []}
    if (set(value) != {"format", "revision", "items"} or type(value["format"]) is not int or value["format"] != 1
            or type(value["revision"]) is not int or not isinstance(value["items"], list)
            or len(value["items"]) > MAX_TEMPLATES):
        raise PlanningError("规则方案格式不能识别；保留原配置，请核对版本。")
    for item in value["items"]:
        rules.validate(item["rules"])
    return key, value


def save_template(owner, actor, source_id, revision, name):
    repo = repository(owner, actor)
    name = name.strip()
    if not 1 <= len(name) <= 32 or any(ord(c) < 32 for c in name):
        raise PlanningError("方案名请填写 1～32 个可见字符。")
    with repo.transaction(actor, admin=True):
        source = repo.source(actor, source_id)
        if source["deleted"] or source["revision"] != revision:
            raise PlanningError("来源已变化，请重新打开。")
        key, value = template_store(repo, actor)
        if len(value["items"]) >= MAX_TEMPLATES or any(x["name"] == name for x in value["items"]):
            raise PlanningError("方案已满或名称重复；请删除旧方案或使用新名称。")
        value["items"].append({"id": secrets.token_hex(6), "name": name,
                               "rules": copy.deepcopy(source["config"]["rules"])})
        value["revision"] += 1
        repo.c.execute("INSERT OR REPLACE INTO service_meta VALUES(?,?)", (key, json.dumps(value)))
    return value


def apply_template(owner, actor, identity, store_revision, targets):
    repo = repository(owner, actor)
    if not targets or len(targets) > 8 or len({sid for sid, _ in targets}) != len(targets):
        raise PlanningError("请选择 1～8 个来源，不能重复。")
    with repo.transaction(actor, admin=True):
        _, value = template_store(repo, actor)
        if value["revision"] != store_revision:
            raise PlanningError("规则方案已变化，请重新预览。")
        item = next((x for x in value["items"] if x["id"] == identity), None)
        if item is None:
            raise PlanningError("规则方案已删除。")
        for sid, revision in targets:
            source = repo.source(actor, sid)
            if source["deleted"] or source["revision"] != revision:
                raise PlanningError("所选来源已变化；全部未应用，请重新预览。")
        for sid, revision in targets:
            source = repo.source(actor, sid)
            repo.change_source(actor, sid, revision,
                               config=source["config"] | {"rules": copy.deepcopy(item["rules"])})
    return len(targets)


def delete_template(owner, actor, identity, revision):
    repo = repository(owner, actor)
    with repo.transaction(actor, admin=True):
        key, value = template_store(repo, actor)
        if value["revision"] != revision:
            raise PlanningError("方案列表已变化，请刷新。")
        value["items"] = [x for x in value["items"] if x["id"] != identity]
        value["revision"] += 1
        repo.c.execute("INSERT OR REPLACE INTO service_meta VALUES(?,?)", (key, json.dumps(value)))


def recovery_reason(task):
    if (task["state"] != "download_failed" or task.get("cancel_requested") or needs_review(task)
            or any(task.get(k) for k in ("remote_path", "remote_temp_path", "remote_final_path"))):
        return "需要单独核对任务和远端状态"
    kind = task.get("failure_kind")
    if kind in {"network", "server", "rate_limited"}:
        return "可确认重试"
    if not kind and (task.get("error") or "").startswith("下载重试次数已经用完"):
        return "旧版下载失败；确认后仍需重新核验来源"
    return "请先核对来源授权或具体失败原因"


def failed_page(owner, actor, source_id, before=0):
    repo = repository(owner, actor)
    repo.source(actor, source_id)
    return [dict(row) for row in repo.c.execute(
        "SELECT * FROM tasks WHERE sender_id=? AND source_id=? AND read_identity!='bot' "
        "AND state IN ('download_failed','upload_failed_retained','verification_failed_retained') "
        "AND (?=0 OR id<?) ORDER BY id DESC LIMIT 6", (actor, source_id, before, before))]


async def retry_confirmed(owner, actor, source_id, revision, snapshots):
    if not snapshots or len(snapshots) > RECOVERY_BATCH or len({tid for tid, _ in snapshots}) != len(snapshots):
        raise PlanningError("一次确认最多恢复 5 项，不能重复。")
    source = live(owner, actor, source_id, revision)
    client = owner.listener.client
    count = 0
    deadline = time.monotonic() + 30
    for tid, updated in snapshots:
        remaining = min(20, deadline - time.monotonic())
        if remaining <= 0 or owner.db.count_states(("queued", "reserved", "downloading", "streaming")) >= 100:
            break
        live(owner, actor, source_id, revision, client)
        task = owner.db.get(tid)
        if (not task or task["source_id"] != source_id or task["sender_id"] != actor
                or task["read_identity"] != f"listener:{source['account']}"
                or task["updated_at"] != updated
                or recovery_reason(task) not in {"可确认重试", "旧版下载失败；确认后仍需重新核验来源"}
                or task.get("target_base") != owner.settings.cd2_target):
            continue
        if tid in owner.download_tasks or tid in owner.upload_tasks:
            continue
        reader = CheckedSource(owner.listener, task)
        try:
            await asyncio.wait_for(reader.get_messages(task["chat_id"], ids=task["message_id"]), remaining)
        except (ValueError, RuntimeError, OSError, asyncio.TimeoutError):
            break  # Preserve remaining tasks; never switch identities or loop on a denial.
        live(owner, actor, source_id, revision, client)
        count += bool(owner.db.requeue(tid, sender_id=actor, expected_updated_at=updated,
                                      local_complete=owner._local_complete(task)))
    return count


def duplicate(owner, source, item):
    c = owner.db._conn
    if item["media_key"] and c.execute("SELECT 1 FROM tasks WHERE sender_id=? AND media_key=?",
                                      (owner.settings.allowed_user_id, item["media_key"])).fetchone():
        return "重复文件（沿用原有去重规则）"
    if c.execute("SELECT 1 FROM listener_events WHERE account=? AND chat=? AND message=?",
                 (source["account"], source["chat"], item["message_id"])).fetchone():
        return "已处理的消息（不自动重处理）"
    return ""


async def history_preview(owner, actor, source_id, hours):
    if type(hours) is not int or hours not in {1, 6, 24}:
        raise PlanningError("补拉仅支持最近 1、6、24 小时。")
    source = live(owner, actor, source_id)
    client = owner.listener.client
    messages = []
    stopped = ""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    async def scan():
        await verified_chat(client, source["chat"])
        live(owner, actor, source_id, source["revision"], client)
        async for message in client.iter_messages(source["chat"], offset_date=cutoff,
                                                  reverse=True, limit=HISTORY_LIMIT + 1):
            if len(messages) >= HISTORY_LIMIT:
                return "达到 100 条扫描上限，本次范围未完整扫描"
            messages.append(message)
        return ""

    try:
        stopped = await asyncio.wait_for(scan(), HISTORY_TIMEOUT)
    except asyncio.TimeoutError:
        stopped = "扫描超时，结果未完成；仅列出已检查消息"
    except Exception as exc:  # noqa: BLE001 - map private SDK errors, never expose raw exceptions
        live(owner, actor, source_id, source["revision"], client)
        if isinstance(exc, FLOOD_WAITS) or type(exc).__name__ in AUTH_ERRORS:
            await owner.listener.source_failure(source, exc)
        raise PlanningError(source_error(exc)) from None
    live(owner, actor, source_id, source["revision"], client)
    captions = album_captions(messages)
    candidates, counts = [], {}
    now = time.time()
    for message in messages:
        if not cutoff.timestamp() <= message.date.timestamp() <= now - 2:
            counts["不在时间范围或媒体组尚未稳定"] = counts.get("不在时间范围或媒体组尚未稳定", 0) + 1
            continue
        if message.chat_id != source["chat"]:
            counts["消息不属于此来源"] = counts.get("消息不属于此来源", 0) + 1
            continue
        item, matched, reason, naming = owner.listener.preview(source, message, message_caption(message, captions))
        skip = duplicate(owner, source, item) or ("" if matched else reason)
        if skip:
            counts[skip] = counts.get(skip, 0) + 1
        else:
            candidates.append({"item": item, "naming": naming})
    return {"source": source_id, "revision": source["revision"], "client": client,
            "base": owner.settings.cd2_target, "expires": time.monotonic() + 300,
            "checked": len(messages), "complete": not stopped, "notice": stopped,
            "hours": hours, "candidates": candidates[:RECOVERY_BATCH],
            "found": len(candidates), "skips": counts}


async def register_history(owner, actor, preview):
    if preview["expires"] < time.monotonic() or preview["base"] != owner.settings.cd2_target:
        raise PlanningError("补拉预览已过期或保存根目录变化，请重新预览。")
    if not isinstance(preview["candidates"], list) or len(preview["candidates"]) > RECOVERY_BATCH:
        raise PlanningError("历史补拉一次最多登记 5 项。")
    repo = repository(owner, actor)
    created = 0
    with repo.transaction(actor, admin=True):
        source = live(owner, actor, preview["source"], preview["revision"], preview["client"])
        for candidate in preview["candidates"]:
            item = candidate["item"]
            if item["chat_id"] != source["chat"]:
                raise PlanningError("预览附件不属于此来源；本批未登记。")
            if duplicate(owner, source, item):
                continue
            if (owner.db.count_states(("queued", "reserved", "downloading", "streaming")) >= 100
                    or repo.c.execute("SELECT count(*) FROM listener_events").fetchone()[0] >= 20000):
                raise PlanningError("接收队列或记录达到上限；本批未登记，请先处理现有任务。")
            _plan, fresh = repo.create(actor, item, candidate["naming"],
                                      identity=f"listener:{source['account']}", source=source["id"],
                                      directory_alias=source["config"]["directory"],
                                      target_base=owner.settings.cd2_target,
                                      batch=f"history:{source['id']}:{item['group'] or item['message_id']}")
            created += int(fresh)
    # Always enter the existing approval flow, even for an automatic source.
    # Its final action revalidates each actual attachment via CheckedSource.
    return created
