"""Bounded polling and persisted inbox; transport continues in the existing queue."""

from __future__ import annotations

import asyncio
import time
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone

from tg2cloud.domain.planning import PlanningError, name_plan
from tg2cloud.domain.source_directories import media_directory
from tg2cloud.listening import account, rules
from tg2cloud.persistence.plans import Plans

BATCH = 100
LOOKBACK = 6 * 3600


class ReceiveLimited(ValueError):
    """Durable backpressure: retry later without consuming a message cursor."""


class ListenerReadError(RuntimeError):
    """Authorization/content failures require review, not automatic identity fallback."""


AUTH_ERRORS = {"AuthKeyUnregisteredError", "SessionRevokedError", "SessionExpiredError",
               "UserDeactivatedError", "UserDeactivatedBanError", "AuthKeyDuplicatedError"}


def source_error(exc):
    from telethon.errors import FloodWaitError

    if isinstance(exc, FloodWaitError):
        return f"Telegram 限流，请等待 {max(5, exc.seconds)} 秒后重试；账号冷却期间不会接收新任务"
    name = type(exc).__name__
    if name in AUTH_ERRORS:
        return "个人监听账号授权失效；请在 tg2cloud 的监听管理中重新登录"
    if name in {"UsernameInvalidError", "UsernameNotOccupiedError", "InviteHashInvalidError", "InviteHashExpiredError", "PeerIdInvalidError"}:
        return "来源用户名、聊天 ID 或邀请链接无效或已失效；请核对后重新填写"
    if name in {"ChatForwardsRestrictedError", "MediaEmptyError"}:
        return "Telegram 拒绝读取此附件；请核对来源权限，本程序不会绕过服务端拒绝"
    if name in {"ChannelPrivateError", "UserNotParticipantError", "ChatAdminRequiredError"}:
        return "监听账号尚未加入来源，或没有读取权限；请先在该个人账号中加入并核对权限"
    if isinstance(exc, ListenerReadError):
        return str(exc)  # Only fixed, locally produced messages use this type.
    if isinstance(exc, (OSError, asyncio.TimeoutError)):
        return "连接 Telegram 失败或超时；请检查 VPS 网络后重试，来源尚未添加"
    if isinstance(exc, ValueError):
        return "无法解析来源；请填写当前个人账号已加入的 @用户名、聊天 ID 或有效链接"
    return "来源核验未完成；请检查监听账号与来源后重试，未显示内部错误或凭据"


async def verified_chat(client, reference):
    from telethon.tl import types

    entity = await client.get_entity(reference)
    if (
        not isinstance(entity, (types.Channel, types.Chat))
        or getattr(entity, "left", True)
        or getattr(entity, "deactivated", False)
    ):
        raise ListenerReadError("来源不是已加入且可访问的频道或群组")
    from telethon.tl.custom.participantpermissions import ParticipantPermissions

    permissions = await client.get_permissions(entity, "me")
    if not isinstance(permissions, ParticipantPermissions) or permissions.has_left:
        raise ListenerReadError("无法确认账号仍在来源中；停止接收")
    if permissions.is_banned:
        # Telegram also uses the banned participant type for restricted, still joined readers.
        member = permissions.participant
        rights = member.banned_rights
        if (
            getattr(member, "left", None) is not False
            or getattr(rights, "view_messages", None) is not False
        ):
            raise ListenerReadError("账号已退出或不能读取此来源")
    elif not (permissions.has_default_permissions or permissions.is_admin):
        raise ListenerReadError("无法确认来源成员权限")
    return entity


class CheckedSource:
    def __init__(self, listener, task):
        self.listener, self.task = listener, task
        self.message = None

    async def get_messages(self, entity, *, ids):
        l, task = self.listener, self.task
        if (
            not l.client
            or l.admin != l.owner.settings.allowed_user_id
            or not l.owner._authorized(l.admin)
            or task["sender_id"] != l.admin
        ):
            raise ListenerReadError("监听账号未连接或任务归属不匹配")
        current = account.state(l.db)
        if not current["enabled"] or task["read_identity"] != "listener:" + str(
            current["account"]
        ):
            raise ListenerReadError(
                "监听授权已停用或读取身份变化，请重新授权后手动重试"
            )
        source = l.plans.source(l.admin, task["source_id"])
        if (
            source["chat"] != entity
            or task["message_id"] != ids
            or source["account"] != current["account"]
        ):
            raise ListenerReadError("来源身份不一致")
        try:
            await verified_chat(l.client, entity)
            message = await l.client.get_messages(entity, ids=ids)
        except ListenerReadError:
            raise
        except Exception as exc:
            await self.classify_error(source, exc)
            if isinstance(exc, (OSError, asyncio.TimeoutError)):
                raise
            raise ListenerReadError("监听来源不可访问，请检查来源或账号状态") from None
        if (
            not message
            or not rules.facts(message)["attachment"]
        ):
            raise ListenerReadError("消息已删除或无可读取的附件；停止下载")
        if rules.facts(message)["media_key"] != task["media_key"]:
            raise ListenerReadError("来源附件已变化；停止原任务，避免下载错误文件")
        self.message = message
        return message

    async def download_media(self, message, **options):
        if (
            message is not self.message
            or not account.state(self.listener.db)["enabled"]
        ):
            raise ListenerReadError("未核验的监听附件不能下载")
        try:
            return await self.listener.client.download_media(message, **options)
        except Exception as exc:
            source = self.listener.plans.source(
                self.listener.admin, self.task["source_id"]
            )
            await self.classify_error(source, exc)
            raise

    async def classify_error(self, source, exc):
        from telethon.errors import FloodWaitError

        if isinstance(exc, FloodWaitError):
            await self.listener.source_failure(source, exc)
            raise ListenerReadError(
                "Telegram 限流，已记录冷却；结束冷却后可手动重试本任务"
            ) from None
        if type(exc).__name__ in AUTH_ERRORS | {
            "ChannelPrivateError",
            "UserNotParticipantError",
            "ChatAdminRequiredError", "ChatForwardsRestrictedError", "MediaEmptyError",
        }:
            await self.listener.source_failure(source, exc)
            raise ListenerReadError(
                source_error(exc)
            ) from None


def task_source(owner, task):
    if task.get("read_identity", "bot") == "bot":
        return owner.source
    listener = getattr(owner, "listener", None)
    if listener is None or task["sender_id"] != owner.settings.allowed_user_id:
        raise ListenerReadError("监听任务无法取得匹配的管理员读取身份")
    return CheckedSource(listener, task)


class Listener:
    def __init__(self, owner):
        self.owner, self.db, self.admin = (
            owner,
            owner.db,
            owner.settings.allowed_user_id,
        )
        self.plans = Plans(self.db, self.admin)
        self.client = None
        self._session = None
        self._last_notice = 0.0
        self._verified_until = {}

    def require_admin(self, actor):
        self.plans.authorize(actor, admin=True)
        if actor != self.owner.settings.allowed_user_id or not self.owner._authorized(
            actor
        ):
            raise PermissionError("管理员授权已失效")

    async def close(self):
        if self.client:
            await self.client.disconnect()
            self.client = None
        if self._session:
            self._session.close()
            self._session = None

    async def connect(self):
        value = account.state(self.db)
        if not value["enabled"]:
            await self.close()
            return False
        if self.client:
            return True
        stack = ExitStack()
        try:
            path = stack.enter_context(account.session_lock(self.owner.settings))
            if not path.with_suffix(".session").is_file():
                raise ListenerReadError("未登录；请先在 Linux 终端授权")
            self.client = account.client(self.owner.settings, path)
            await self.client.connect()
            me = (
                await self.client.get_me()
                if await self.client.is_user_authorized()
                else None
            )
            if (
                not me
                or getattr(me, "bot", None) is not False
                or me.id != value["account"]
            ):
                raise ListenerReadError("授权失效或个人账号不匹配")
            self._session = stack
            account.write_state(self.db, status="正常监听")
            return True
        except BaseException:
            await self.close()
            stack.close()
            raise

    async def add(self, actor, reference, config):
        self.require_admin(actor)
        self.plans.source_config(actor, config)
        if not self.client:
            raise PlanningError("请先在终端登录并启用监听账号")
        try:
            entity, latest = await self._resolve(reference)
        except Exception as exc:  # noqa: BLE001 - map private Telegram exceptions to fixed safe messages
            from telethon.errors import FloodWaitError
            if isinstance(exc, FloodWaitError) or type(exc).__name__ in AUTH_ERRORS:
                await self.source_failure(None, exc)
            raise ListenerReadError(source_error(exc)) from None
        from telethon.utils import get_peer_id

        source = self.plans.save_source(
            actor, account=account.state(self.db)["account"], chat=get_peer_id(entity),
            title=entity.title, cursor=latest[0].id if latest else 0, config=config,
            target_base=self.owner.settings.cd2_target,
        )
        try:
            return await self.prepare_directory(actor, source)
        except ListenerReadError:
            # Registration is durable and paused; show the source and a repair button, not a duplicate-add trap.
            return self.plans.source(actor, source["id"])

    async def prepare_directory(self, actor, source):
        self.require_admin(actor)
        source = self.plans.source(actor, source["id"])
        if source["deleted"]:
            raise PlanningError("来源已删除")
        if source["config"].get("directory_mode", "legacy") != "source_type":
            return source
        try:
            media_directory(source["config"], base=self.owner.settings.cd2_target)
        except ValueError:
            self._directory_failed(actor, source, "保存根目录已变化；请恢复原配置后重试")
            raise ListenerReadError("来源保存根目录已变化；来源已暂停，请核对并恢复原 Bot 保存配置") from None
        try:
            await self.owner.rclone.ensure_directory(source["config"]["source_folder"])
        except BaseException as exc:
            self._directory_failed(actor, source, "请检查网关后点击重试创建目录")
            if not isinstance(exc, Exception):
                raise
            raise ListenerReadError("来源已登记并暂停；目录创建未完成，请检查网关连接、权限和保存目录后重试") from None
        current = self.plans.source(actor, source["id"])
        if current["revision"] != source["revision"] or current["deleted"]:
            raise PlanningError("来源配置已变化，请刷新；已创建的空目录保留")
        with self.plans.transaction(actor, admin=True):
            self.db._conn.execute(
                "UPDATE listener_sources SET status=? WHERE id=? AND revision=? AND deleted=0",
                ("等待检查" if current["enabled"] else "暂停；来源目录已就绪", source["id"], source["revision"]),
            )
        return self.plans.source(actor, source["id"])

    def _directory_failed(self, actor, source, reason):
        with self.plans.transaction(actor, admin=True):
            self.db._conn.execute(
                "UPDATE listener_sources SET enabled=0,status=? WHERE id=? AND revision=? AND deleted=0",
                ("目录创建未完成；" + reason, source["id"], source["revision"]),
            )

    async def _resolve(self, reference):
        reference = reference.strip()
        if reference.lstrip("-").isdigit():
            reference = int(reference)
        elif reference.startswith(("https://t.me/+", "https://t.me/joinchat/")):
            # Check invite without joining; already-member result exposes only the allowed chat.
            from telethon.tl.functions.messages import CheckChatInviteRequest
            from telethon.tl.types import ChatInviteAlready

            invite = await self.client(
                CheckChatInviteRequest(reference.rsplit("/", 1)[1].lstrip("+"))
            )
            if not isinstance(invite, ChatInviteAlready):
                raise ListenerReadError("尚未加入该来源；请先在个人 Telegram 中申请加入")
            reference = invite.chat
        entity = await verified_chat(self.client, reference)
        latest = await self.client.get_messages(entity, limit=1)
        return entity, latest

    def preview(self, source, message, caption=None):
        item = rules.facts(message, caption)
        matched, reason = rules.evaluate(
            source["config"]["rules"], item, source_allowed=True
        )
        naming = name_plan(
            item["original"],
            item["caption"],
            f"telegram-{item['message_id']}{item['extension'] or '.bin'}",
            kind=item["kind"],
            extension=item["extension"],
            entities=getattr(message, "entities", ())
            if caption is None
            or caption
            == (getattr(message, "raw_text", "") or getattr(message, "message", ""))
            else (),
            options=source["config"]["profile"],
        )
        return item, matched, reason, naming

    async def test(self, actor, source_id, *, config=None):
        self.require_admin(actor)
        source = self.plans.source(actor, source_id)
        if config is not None:
            source = source | {"config": self.plans.source_config(actor, config)}
        if not self.client:
            raise PlanningError("监听账号未连接")
        await verified_chat(self.client, source["chat"])
        messages = await self.client.get_messages(source["chat"], limit=10)
        result = []
        for m in messages:
            item, matched, reason, naming = self.preview(source, m)
            naming["directory_preview"] = media_directory(source["config"], kind=item["kind"],
                                                         mime=item["mime"], extension=item["extension"],
                                                         base=self.owner.settings.cd2_target)
            if self.db._conn.execute(
                "SELECT 1 FROM tasks WHERE sender_id=? AND media_key=?",
                (actor, rules.facts(m)["media_key"]),
            ).fetchone():
                matched, reason = False, "重复文件（沿用原有去重规则）"
            if self.db._conn.execute(
                "SELECT 1 FROM listener_events WHERE account=? AND chat=? AND message=?",
                (source["account"], source["chat"], m.id),
            ).fetchone():
                matched, reason = False, "重复事件（编辑不自动重处理）"
            result.append((m.id, matched, reason, naming))
        return result

    def journal(self, source, message_id, result, *, attachment=False):
        with self.plans.transaction(self.admin, admin=True):
            self.db._conn.execute(
                "INSERT OR IGNORE INTO listener_events(account,chat,message,source,result,plan,created,is_attachment) VALUES(?,?,?,?,?,NULL,?,?)",
                (
                    source["account"],
                    source["chat"],
                    message_id,
                    source["id"],
                    result,
                    time.time(),
                    int(attachment),
                ),
            )

    async def receive(self, source, message, caption=None):
        # Every event decision is persisted before the poll cursor moves; duplicate edits are ignored.
        self.require_admin(self.admin)
        if self._verified_until.get(source["chat"], 0) < time.monotonic():
            await verified_chat(self.client, source["chat"])
            self._verified_until[source["chat"]] = time.monotonic() + 10
        source = self.plans.source(self.admin, source["id"])
        current = account.state(self.db)
        if not current["enabled"]:
            return  # A stop during the awaited permission check must not admit a new plan.
        if source["account"] != current["account"]:
            raise PermissionError("监听账号身份发生变化")
        if not source["enabled"] or source["deleted"] or message.id <= source["cursor"]:
            return
        c = self.db._conn
        if c.execute(
            "SELECT 1 FROM listener_events WHERE account=? AND chat=? AND message=?",
            (source["account"], source["chat"], message.id),
        ).fetchone():
            return
        if c.execute("SELECT count(*) FROM listener_events").fetchone()[0] >= 20000:
            raise ReceiveLimited("接收记录达到上限，暂停推进；请处理待确认记录")
        item, matched, reason, naming = self.preview(source, message, caption)
        if not matched:
            self.journal(source, message.id, reason, attachment=item["attachment"])
            return
        counts = self.db.counts()
        if (
            sum(
                counts.get(k, 0)
                for k in ("queued", "reserved", "downloading", "streaming")
            )
            >= 100
        ):
            raise ReceiveLimited(
                "资源受限：队列达到监听接收上限；保留进度，优先处理手动任务"
            )
        plan, created = self.plans.create(
            self.admin,
            item,
            naming,
            identity="listener:" + str(source["account"]),
            source=source["id"],
            batch=f"{source['id']}:{item['group'] or message.id}",
            directory_alias=source["config"]["directory"],
            target_base=self.owner.settings.cd2_target,
        )
        if not source["config"]["confirmation"]:
            try:
                self.plans.submit(self.admin, plan["id"], plan["revision"])
            except (ValueError, RuntimeError):
                # Persist the exact admission boundary: registered is not the same as queued.
                self.db._conn.execute(
                    "UPDATE listener_events SET result='等待额度或配置核对（待确认保留）' WHERE plan=?",
                    (plan["id"],),
                )
        if created and time.monotonic() - self._last_notice > 60:
            self._last_notice = time.monotonic()
            await self.owner._notify(
                "监听已登记新附件；使用 /pending 查看待确认，/queue 查看已入队任务。"
            )

    async def poll(self, source):
        await verified_chat(self.client, source["chat"])
        self._verified_until[source["chat"]] = time.monotonic() + 10
        gap = bool(source.get("gap")) or bool(
            source.get("polled_at") and time.time() - source["polled_at"] > LOOKBACK
        )
        if gap:
            self.db._conn.execute(
                "UPDATE listener_sources SET gap=1,status='超出补拉窗口，可能存在缺口；请核对历史' WHERE id=?",
                (source["id"],),
            )
        # Ascending pages, never a live-event maximum watermark. A batch is bounded.
        messages = [
            m
            async for m in self.client.iter_messages(
                source["chat"],
                min_id=source["cursor"],
                offset_date=datetime.now(timezone.utc) - timedelta(seconds=LOOKBACK),
                reverse=True,
                limit=BATCH + 10,
            )
        ]
        if len(messages) > BATCH:
            tail = getattr(messages[BATCH - 1], "grouped_id", None)
            messages = messages[:BATCH] + (
                [m for m in messages[BATCH:] if getattr(m, "grouped_id", None) == tail]
                if tail
                else []
            )
        # Same fetched group only; no replies/comments/history crawling for captions.
        groups = {}
        for m in messages:
            if getattr(m, "grouped_id", None):
                groups.setdefault(m.grouped_id, []).append(m)
        for m in messages:
            if time.time() - m.date.timestamp() < 2:
                break  # Allow a short bounded wait for Album members on the next poll.
            latest = self.plans.source(self.admin, source["id"])
            if (
                not latest["enabled"]
                or latest["deleted"]
                or not account.state(self.db)["enabled"]
            ):
                break
            if time.time() - m.date.timestamp() > LOOKBACK:
                self.journal(source, m.id, "超过 6 小时补拉窗口，存在缺口")
            else:
                siblings = groups.get(getattr(m, "grouped_id", None), [])
                from tg2cloud.domain.planning import fields

                original_fields = fields(
                    getattr(getattr(m, "file", None), "name", "") or ""
                )
                if original_fields["episode"] or original_fields["chapter"]:
                    siblings = []  # Never borrow another episode's caption for a member with its own number.
                # Preserve explicit member text. Shared text is only a fallback from this group.
                caption = getattr(m, "raw_text", "") or next(
                    (
                        getattr(s, "raw_text", "")
                        for s in siblings
                        if getattr(s, "raw_text", "")
                    ),
                    None,
                )
                await self.receive(latest, m, caption)
            with self.plans.transaction(self.admin, admin=True):
                self.db._conn.execute(
                    "UPDATE listener_sources SET cursor=?,status=? WHERE id=? AND cursor<?",
                    (
                        m.id,
                        "补拉窗口外可能存在缺口，请核对历史"
                        if gap
                        else "正常监听"
                        if time.time() - m.date.timestamp() <= LOOKBACK
                        else "补拉窗口外存在缺口",
                        source["id"],
                        m.id,
                    ),
                )

        self.db._conn.execute(
            "UPDATE listener_sources SET polled_at=?,status=CASE WHEN enabled=0 THEN '暂停' WHEN gap=1 THEN '超出补拉窗口，可能存在缺口；请核对历史' ELSE '正常监听' END WHERE id=?",
            (time.time(), source["id"]),
        )

    async def source_failure(self, source, exc):
        """Return false when the account needs to cool down or be reauthorized."""
        from telethon.errors import FloodWaitError

        if isinstance(exc, FloodWaitError):
            account.write_state(
                self.db,
                status="Telegram 限流冷却",
                cooldown_until=time.time() + max(5, exc.seconds),
            )
            return False
        if type(exc).__name__ in AUTH_ERRORS:
            account.write_state(
                self.db, enabled=False, status="授权失效，请在终端重新登录"
            )
            await self.close()
            await self.owner._notify(
                "监听账号授权失效，已停止监听；普通 Bot 转存保持可用。请在终端重新登录。"
            )
            return False
        paused = False
        if isinstance(exc, ListenerReadError) or type(exc).__name__ in {
            "ChannelPrivateError",
            "UserNotParticipantError",
            "ChatAdminRequiredError", "ChatForwardsRestrictedError", "MediaEmptyError",
        }:
            status, paused = "来源或附件读取被拒绝，已暂停；核对权限后手动启用", True
        elif (
            isinstance(exc, ReceiveLimited)
            or isinstance(exc, ValueError)
            and str(exc) == "待确认已达 200 项；请先处理"
        ):
            status = "资源受限：队列或待确认达到上限，60 秒后重查"
        elif isinstance(exc, ValueError):
            status, paused = "规则或计划配置无效，已暂停；请核对后启用", True
        else:
            status = "网络或接收持久化失败，60 秒后重查；未推进失败消息"
        with self.db._lock:
            self.db._conn.execute(
                "UPDATE listener_sources SET status=?,enabled=CASE WHEN ? THEN 0 ELSE enabled END,next_retry=? WHERE id=?",
                (status, int(paused), time.time() + 60, source["id"]),
            )
        return True

    async def run(self):
        try:
            while not self.owner._stop.is_set():
                try:
                    value = account.state(self.db)
                    if not value["enabled"]:
                        await self.close()
                    elif (
                        value.get("cooldown_until", 0) <= time.time()
                        and await self.connect()
                    ):
                        for source in self.plans.sources(self.admin):
                            if (
                                source["enabled"]
                                and source.get("next_retry", 0) <= time.time()
                            ):
                                try:
                                    await self.poll(source)
                                except Exception as exc:  # noqa: BLE001 - isolate optional external Telegram failures
                                    if not await self.source_failure(source, exc):
                                        break
                    with self.db._lock:
                        self.plans.expire()
                except Exception as exc:  # noqa: BLE001 - private boundary must not expose credentials
                    await self.close()
                    from telethon.errors import FloodWaitError

                    if isinstance(exc, FloodWaitError):
                        await self.source_failure(None, exc)
                    else:
                        account.write_state(
                            self.db,
                            enabled=False,
                            status="授权或连接失败，请在终端检查后重新启用",
                        )
                        await self.owner._notify(
                            "监听账号连接失败，已停用监听；普通转存不受影响。请在 VPS 终端核对授权，再从监听管理启用。"
                        )
                await asyncio.sleep(5)
        finally:
            await self.close()
