"""Optional transfer previews and administrator listening UI; no attachment capture."""

from __future__ import annotations

import json
import secrets
import time

from telethon import Button

from tg2cloud.domain.actors import current_user
from tg2cloud.domain.planning import PlanningError, name_plan, profile
from tg2cloud.listening import account, rules
from tg2cloud.persistence.plans import Plans
from tg2cloud.telegram.views import format_bytes


def store(owner):
    return Plans(owner.db, owner.settings.allowed_user_id)


def interactions(owner):
    if not hasattr(owner, "_plan_interactions"):
        owner._plan_interactions = {}
    now = time.monotonic()
    owner._plan_interactions = {
        k: v for k, v in owner._plan_interactions.items() if v[0] > now
    }
    return owner._plan_interactions


def token_button(owner, actor, label, action):
    if not hasattr(owner, "_plan_buttons"):
        owner._plan_buttons = {}
    now = time.monotonic()
    owner._plan_buttons = {k: v for k, v in owner._plan_buttons.items() if v[0] > now}
    if len(owner._plan_buttons) >= 1024:
        owner._plan_buttons.clear()
    token = secrets.token_hex(8)
    owner._plan_buttons[token] = (now + 300, actor, action)
    return Button.inline(label, data=("planui:" + token).encode())


async def output(event, text, buttons=None):
    # Telethon supports reply on messages and edit on callbacks. Plain text, no markup injection.
    # Telegram limits text by UTF-16 units. Long names/feedback must not make
    # an already-persisted operation look like it failed to the user.
    chunks, part, units = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > 3500:
            chunks.append("".join(part))
            part, units = [], 0
        part.append(char)
        units += width
    chunks.append("".join(part))
    for index, chunk in enumerate(chunks):
        keyboard = buttons if index == len(chunks) - 1 else None
        if index == 0:
            send = event.edit if hasattr(event, "data") else event.reply
        else:
            send = event.respond
        await send(chunk, buttons=keyboard, parse_mode=None)


async def ask(owner, event, action, prompt):
    actor = current_user(owner.settings.allowed_user_id)
    interactions(owner)[actor] = (time.monotonic() + 300, action)
    await output(
        event, prompt + "\n5 分钟内回复文本；/cancelinput 取消。发送附件仍正常转存。"
    )


async def plan_card(owner, event, plan):
    actor = current_user(owner.settings.allowed_user_id)
    value = plan["payload"]
    rows = []
    if plan["status"] == "pending":
        key = (plan["id"], plan["revision"])
        rows = [
            [
                token_button(owner, actor, "确认转存", ("approve", *key)),
                token_button(owner, actor, "修改名称", ("rename", *key)),
            ],
            [
                token_button(owner, actor, "选择目录", ("directory", *key)),
                token_button(owner, actor, "忽略本次", ("ignore", *key)),
            ],
            [token_button(owner, actor, "批次操作", ("batch", *key))],
        ]
    text = (
        f"📦 转存计划 #{plan['id']}\n状态：{plan['status']}\n原名：{value['original_file_name'] or '无原名'}"
        f"\n候选：{value['file_name']}\n目录：{value['directory_override'] if value['directory_override'] is not None else '现有分类与默认目录'}"
        f"\n大小：{format_bytes(value['file_size'])}\n依据：{value['basis']}"
    )
    if plan["source"] is not None:
        source = store(owner).source(actor, plan["source"])
        text += f"\n监听来源：{source['title']}\n规则快照：版本 {value['source_revision']}；按接收时的规则匹配"
    await output(event, text, rows)


async def submit(owner, actor, plan_id, revision):
    repo = store(owner)
    p = repo.get(actor, plan_id)
    if p["payload"]["target_base"] != owner.settings.cd2_target:
        raise ValueError("Bot 上传根目录已变化；请重新建立计划，不自动切换目录")
    if p["source"] is not None and p["status"] == "pending":
        from tg2cloud.listening.service import CheckedSource

        owner.listener.require_admin(actor)
        data = p["payload"]
        reader = CheckedSource(
            owner.listener,
            {
                "sender_id": actor,
                "read_identity": p["identity"],
                "source_id": p["source"],
                "message_id": p["message"],
                "media_key": data["media_key"],
            },
        )
        await reader.get_messages(p["chat"], ids=p["message"])
    return repo.submit(actor, plan_id, revision)


async def pending(owner, event, after=0):
    actor = current_user(owner.settings.allowed_user_id)
    plans = store(owner).pending(actor, after)
    buttons = [
        [
            token_button(
                owner,
                actor,
                f"#{p['id']} {p['payload']['file_name'][:25]}",
                ("view", p["id"]),
            )
        ]
        for p in plans
    ]
    if len(plans) == 10:
        buttons.append(
            [token_button(owner, actor, "下一页", ("pending", plans[-1]["id"]))]
        )
    await output(
        event,
        "待确认转存\n\n"
        + (
            "选择计划；最多保留 7 天，确认前不下载、不预留额度。"
            if plans
            else "暂无待确认记录。"
        ),
        buttons,
    )


async def settings(owner, event):
    actor = current_user(owner.settings.allowed_user_id)
    prefs = store(owner).preferences(actor)
    rows = [
        [
            token_button(
                owner,
                actor,
                "切换确认模式",
                ("confirmation", not prefs["confirmation"]),
            ),
            token_button(owner, actor, "命名设置", ("preferences",)),
        ],
        [
            token_button(owner, actor, "待确认列表", ("pending", 0)),
            token_button(owner, actor, "修正记录", ("feedback",)),
        ],
    ]
    if actor == owner.settings.allowed_user_id:
        rows.append([token_button(owner, actor, "目录别名管理", ("aliases",))])
    await output(
        event,
        "转存设置\n确认模式："
        + ("开启" if prefs["confirmation"] else "关闭（默认自动转存）")
        + "\n命名模式："
        + prefs["profile"]["mode"]
        + "\n仅影响新计划；已入队任务保持原名称和目录。",
        rows,
    )


async def listening(owner, event):
    actor = current_user(owner.settings.allowed_user_id)
    owner.listener.require_admin(actor)
    value = account.state(owner.db)
    rows = [
        [
            token_button(owner, actor, "启用监听账号", ("account", True)),
            token_button(owner, actor, "停用监听账号", ("account", False)),
        ],
        [
            token_button(owner, actor, "添加来源", ("add",)),
            token_button(owner, actor, "待确认列表", ("pending", 0)),
        ],
    ]
    for source in store(owner).sources(actor):
        rows.append(
            [
                token_button(
                    owner,
                    actor,
                    source["title"][:30]
                    + (" · 启用" if source["enabled"] else " · 暂停"),
                    ("source", source["id"]),
                )
            ]
        )
    await output(
        event,
        "监听管理（仅管理员）\n\n账号："
        + value["status"]
        + "\n首次登录：在 VPS 交互终端运行 tg2cloud listen login --edition <当前 Edition>\n默认关闭；仅接收已加入来源的新附件，不读取评论、不自动重处理消息编辑。",
        rows,
    )


async def source_card(owner, event, source_id):
    actor = current_user(owner.settings.allowed_user_id)
    owner.listener.require_admin(actor)
    repo = store(owner)
    s = repo.source(actor, source_id)
    sid, rev = s["id"], s["revision"]
    buttons = [
        [
            token_button(
                owner,
                actor,
                "暂停" if s["enabled"] else "启用",
                ("source-enable", sid, rev, not s["enabled"]),
            ),
            token_button(owner, actor, "测试规则", ("test", sid)),
        ],
        [
            token_button(owner, actor, "筛选规则", ("rules", sid, rev)),
            token_button(owner, actor, "命名方案", ("profile", sid, rev)),
        ],
        [
            token_button(owner, actor, "保存目录", ("source-directory", sid, rev)),
            token_button(owner, actor, "切换自动与确认", ("source-confirm", sid, rev)),
        ],
        [
            token_button(owner, actor, "删除来源", ("delete-offer", sid, rev)),
            token_button(owner, actor, "返回监听管理", ("listen",)),
        ],
    ]
    buttons.append([token_button(owner, actor, "命名规则历史与撤销", ("history", sid))])
    stats = {
        r[0]: r[1]
        for r in owner.db._conn.execute(
            "SELECT result,count(*) FROM listener_events WHERE source=? GROUP BY result",
            (sid,),
        )
    }
    counts = owner.db._conn.execute(
        "SELECT count(*),COALESCE(sum(is_attachment),0),COALESCE(sum(matched),0) FROM listener_events WHERE source=?",
        (sid,),
    ).fetchone()
    waiting = owner.db._conn.execute(
        "SELECT count(*) FROM transfer_plans WHERE source=? AND status='pending' AND expires>?",
        (sid, time.time()),
    ).fetchone()[0]
    summary = f"收到 {counts[0]} · 附件 {counts[1]} · 匹配 {counts[2]} · 跳过 {counts[0] - counts[2]} · 待确认 {waiting} · 入队 {stats.get('已入队', 0)}"
    await output(
        event,
        f"来源 #{sid}：{s['title']}\n启用从当前时点开始，暂停期间不补抓；重启补拉最多 6 小时。\n状态：{s['status']}\n规则版本：{rev}\n模式：{'确认后转存' if s['config']['confirmation'] else '自动转存'}"
        f"\n目录别名：{s['config']['directory'] or '命名方案、分类或默认目录'}\n规则：{json.dumps(s['config']['rules'], ensure_ascii=False)[:1200]}\n{summary}\n最近接收结果（有界保留）：{json.dumps(stats, ensure_ascii=False)}",
        buttons,
    )


async def command(owner, event, text):
    command = text.split()[0].split("@")[0].lower()
    if command not in {"/listen", "/pending", "/transfer", "/cancelinput"}:
        return False
    actor = current_user(owner.settings.allowed_user_id)
    try:
        store(owner).authorize(actor, admin=command == "/listen")
        if command == "/listen":
            await listening(owner, event)
        elif command == "/pending":
            await pending(owner, event)
        elif command == "/transfer":
            await settings(owner, event)
        else:
            interactions(owner).pop(actor, None)
            await output(event, "已取消文本设置；转存任务保持不变。")
    except (ValueError, PermissionError):
        await output(event, "无权操作，或设置暂不可用；请刷新菜单。")
    return True


async def callback(owner, event):
    raw = bytes(event.data)
    if raw == b"menu:listen":
        await event.answer()
        try:
            await listening(owner, event)
        except PermissionError:
            await output(event, "此功能仅限管理员。")
        return True
    if raw == b"menu:transfer":
        await event.answer()
        await settings(owner, event)
        return True
    if not raw.startswith(b"planui:"):
        return False
    actor = current_user(owner.settings.allowed_user_id)
    token = raw[7:].decode("ascii", errors="replace")
    record = getattr(owner, "_plan_buttons", {}).get(token)
    if not record or record[0] < time.monotonic() or record[1] != actor:
        await event.answer("按钮已失效或无权使用，请重新打开菜单。", alert=True)
        return True
    # Consume only for the authorized actor. Concurrent clicks cannot perform two writes.
    owner._plan_buttons.pop(token, None)
    await event.answer()
    action, *args = record[2]
    repo = store(owner)
    try:
        repo.authorize(actor)
        if action in {
            "listen",
            "add",
            "account",
            "source",
            "source-enable",
            "test",
            "rules",
            "profile",
            "source-directory",
            "source-confirm",
            "delete-offer",
            "delete",
            "history",
            "restore-rule",
            "save-feedback",
        }:
            owner.listener.require_admin(actor)
        if action == "listen":
            await listening(owner, event)
        elif action == "account":
            if args[0] and not account.state(owner.db)["account"]:
                raise ValueError("请先在 VPS 终端登录个人账号")
            account.write_state(
                owner.db, enabled=args[0], status="等待连接" if args[0] else "已停用"
            )
            await listening(owner, event)
        elif action == "add":
            await ask(
                owner,
                event,
                ("add",),
                "发送已加入来源的 @用户名、聊天 ID 或链接；添加后默认为暂停，规则默认仅视频、确认后转存。",
            )
        elif action == "source":
            await source_card(owner, event, args[0])
        elif action in {"source-enable", "delete", "source-confirm"}:
            sid, rev = args[:2]
            s = repo.source(actor, sid)
            if action == "source-enable" and args[2]:
                from tg2cloud.listening.service import verified_chat

                if not owner.listener.client:
                    raise ValueError("监听账号未连接")
                await verified_chat(owner.listener.client, s["chat"])
            cursor = None
            if action == "source-enable" and args[2]:
                latest = await owner.listener.client.get_messages(s["chat"], limit=1)
                cursor = latest[0].id if latest else 0
            config = (
                s["config"] | {"confirmation": not s["config"]["confirmation"]}
                if action == "source-confirm"
                else None
            )
            repo.change_source(
                actor,
                sid,
                rev,
                config=config,
                enabled=args[2] if action == "source-enable" else None,
                delete=action == "delete",
                cursor=cursor,
            )
            await listening(owner, event) if action == "delete" else await source_card(
                owner, event, sid
            )
        elif action == "delete-offer":
            await output(
                event,
                "确认删除此监听来源？停止新接收，保留任务和云端文件。",
                [[token_button(owner, actor, "确认删除", ("delete", *args))]],
            )
        elif action == "test":
            results = await owner.listener.test(actor, args[0])
            s = repo.source(actor, args[0])
            directory = (
                repo.directory(actor, s["config"]["directory"])
                or s["config"]["profile"]["directory"]
                or "现有分类/默认目录"
            )
            await output(
                event,
                "规则测试（只读，无任务、额度和进度副作用）\n"
                + "\n".join(
                    f"#{mid} {'匹配' if matched else '跳过'}：{reason}\n{name['file_name']} → {directory}"
                    for mid, matched, reason, name in results
                ),
            )
        elif action in {"rules", "profile", "source-directory"}:
            if action == "rules":
                prompt = '发送 JSON（大小单位为字节）：{"groups":[{"types":["视频"],"extensions":["mp4","mkv"],"keywords":["物理","数学"]}],"exclude":["广告","试看"],"max_bytes":2147483648}'
            elif action == "profile":
                prompt = '发送命名 JSON，例如 {"mode":"template","template":"{title} {episode}"}；compatible 保留有效原名，caption 说明优先。prefixes/suffixes 为显式清理列表；完整替换，发送 {} 撤销新增规则。'
            else:
                prompt = "发送目录别名；输入 默认 取消来源目录覆盖。可选：" + "、".join(
                    repo.directories(actor)
                )
            await ask(owner, event, (action, *args), prompt)
        elif action == "pending":
            await pending(owner, event, args[0])
        elif action == "view":
            await plan_card(owner, event, repo.get(actor, args[0]))
        elif action in {"approve", "ignore", "rename", "directory", "batch"}:
            plan = repo.get(actor, args[0])
            if plan["status"] != "pending" or plan["revision"] != args[1]:
                raise ValueError("计划已变化或已处理")
            if action == "approve":
                task, _ = await submit(owner, actor, *args)
                await output(
                    event,
                    f"已持久化到现有队列：任务 #{task['id']}\n最终重名后缀以任务详情为准。",
                )
            elif action == "ignore":
                await plan_card(owner, event, repo.edit(actor, *args, ignore=True))
            elif action == "rename":
                await ask(
                    owner,
                    event,
                    ("rename", *args),
                    "输入本次名称；保留原媒体扩展名，不会自动保存为规则。",
                )
            elif action == "directory":
                rows = [
                    [
                        token_button(
                            owner, actor, alias, ("choose-directory", *args, alias)
                        )
                    ]
                    for alias in repo.directories(actor)
                ]
                await output(
                    event, "选择已授权目录（替换分类子目录，不重复追加）：", rows
                )
            else:
                await output(
                    event,
                    "本批次最多 20 项；逐项重新核验权限、版本和额度，部分失败会保留待确认。",
                    [
                        [
                            token_button(
                                owner, actor, "确认本批次", ("batch-approve", *args)
                            )
                        ],
                        [
                            token_button(
                                owner, actor, "批次选择目录", ("batch-directory", *args)
                            )
                        ],
                        [
                            token_button(
                                owner, actor, "批次修改共同主题", ("batch-name", *args)
                            )
                        ],
                    ],
                )
        elif action == "choose-directory":
            await plan_card(
                owner,
                event,
                repo.edit(actor, args[0], args[1], directory_alias=args[2]),
            )
        elif action in {"batch-approve", "batch-directory", "batch-name"}:
            p = repo.get(actor, args[0])
            if not p["batch"] or p["revision"] != args[1] or p["status"] != "pending":
                raise ValueError("批次已变化或不可用")
            ids = [
                (r["id"], r["revision"])
                for r in owner.db._conn.execute(
                    "SELECT id,revision FROM transfer_plans WHERE owner=? AND batch=? AND status='pending' AND expires>? ORDER BY id LIMIT 21",
                    (actor, p["batch"], time.time()),
                )
            ]
            if len(ids) > 20:
                raise ValueError("批次超过 20 项，请逐项处理")
            if action == "batch-approve":
                good = 0
                for pid, rev in ids:
                    try:
                        await submit(owner, actor, pid, rev)
                        good += 1
                    except (ValueError, RuntimeError):
                        pass
                await output(
                    event,
                    f"本批次已入队 {good}/{len(ids)} 项；其余保留待确认，请核对额度、有效期和权限。",
                )
            else:
                await ask(
                    owner,
                    event,
                    (action, ids),
                    "发送新的共同主题（各成员集数、章节和扩展名保留）。"
                    if action == "batch-name"
                    else "发送已授权目录别名：" + "、".join(repo.directories(actor)),
                )
        elif action == "confirmation":
            repo.preferences(actor, {"confirmation": args[0]})
            await settings(owner, event)
        elif action == "preferences":
            await ask(
                owner,
                event,
                ("preferences",),
                '发送个人命名 JSON，例如 {"mode":"caption"}；默认 {"mode":"compatible"}。',
            )
        elif action == "aliases":
            repo.authorize(actor, admin=True)
            await ask(
                owner,
                event,
                ("aliases",),
                '发送目录别名 JSON，例如 {"alias":"课程","path":"课程/光学","owners":[123]}；仅管理员，path 是 Bot 上传根目录内的相对目录。授权列表为空表示只给管理员。',
            )
        elif action == "history":
            source = repo.source(actor, args[0])
            history = repo.source_history(actor, args[0])
            await output(
                event,
                "选择恢复某次完整来源配置；仅作用于新计划。",
                [
                    [
                        token_button(
                            owner,
                            actor,
                            f"恢复版本 {r['revision']}",
                            ("restore-rule", source["id"], source["revision"], r["id"]),
                        )
                    ]
                    for r in history
                ],
            )
        elif action == "restore-rule":
            history = repo.source_history(actor, args[0])
            old = next((r for r in history if r["id"] == args[2]), None)
            if not old:
                raise ValueError("历史版本已失效")
            repo.change_source(
                actor, args[0], args[1], config=json.loads(old["config"])
            )
            await source_card(owner, event, args[0])
        elif action == "save-feedback":
            repo.apply_feedback(actor, *args)
            await output(
                event,
                "已明确保存为此来源的前缀规则；其他来源和已提交任务保持不变，可在命名规则历史中撤销。",
            )
        elif action == "feedback":
            items = repo.feedback(actor)
            buttons = []
            if actor == owner.settings.allowed_user_id:
                from pathlib import Path

                for r in items:
                    before, after = (
                        Path(r["before_name"]).stem,
                        Path(r["after_name"]).stem,
                    )
                    if (
                        r["source"] is not None
                        and r["operation"] == "仅本次"
                        and after
                        and before.endswith(after)
                        and 1 <= len(before) - len(after) <= 80
                    ):
                        source = repo.source(actor, r["source"])
                        buttons.append(
                            [
                                token_button(
                                    owner,
                                    actor,
                                    "确认保存前缀规则 #" + str(r["id"]),
                                    ("save-feedback", r["id"], source["revision"]),
                                )
                            ]
                        )
            await output(
                event,
                "最近人工修正（只影响本次，没有自动学习规则）\n"
                + "\n".join(
                    f"#{r['id']} {r['before_name']} → {r['after_name']}" for r in items
                )
                + "\n明确保存为来源规则：在监听来源的命名方案中填写 prefixes/suffixes；发送 {} 撤销。",
                buttons,
            )
    except (ValueError, PermissionError, RuntimeError) as exc:
        from tg2cloud.listening.service import ListenerReadError
        from tg2cloud.persistence.quotas import QuotaExceeded

        message = (
            str(exc)
            if isinstance(exc, (PlanningError, ListenerReadError, QuotaExceeded))
            else "设置、权限或记录版本不可确认；请刷新对应页面核对后重试。"
        )
        await output(event, message[:300])
    except Exception:  # noqa: BLE001 - private boundary must not expose credentials
        await output(
            event,
            "操作未完成；请检查监听账号、来源权限及限流状态后重试。未输出账号凭据。",
        )
    return True


async def text(owner, event, value):
    actor = current_user(owner.settings.allowed_user_id)
    pending_action = interactions(owner).get(actor)
    if not pending_action:
        return False
    action, *args = pending_action[1]
    repo = store(owner)
    try:
        repo.authorize(
            actor,
            admin=action in {"add", "rules", "profile", "source-directory", "aliases"},
        )
        if len(value) > 8192:
            raise ValueError("文本过长")
        if action == "add":
            source = await owner.listener.add(
                actor,
                value,
                {"rules": {"groups": [{"types": ["视频"]}]}, "confirmation": True},
            )
            interactions(owner).pop(actor, None)
            await source_card(owner, event, source["id"])
            return True
        if action in {"rules", "profile", "source-directory"}:
            s = repo.source(actor, args[0])
            config = s["config"].copy()
            key = {
                "rules": "rules",
                "profile": "profile",
                "source-directory": "directory",
            }[action]
            config[key] = (
                ("" if value == "默认" else value)
                if action == "source-directory"
                else json.loads(value)
            )
            repo.change_source(actor, *args, config=config)
            await source_card(owner, event, args[0])
        elif action == "rename":
            await plan_card(owner, event, repo.edit(actor, *args, name=value))
        elif action in {"batch-name", "batch-directory"}:
            from tg2cloud.domain.planning import fields

            with repo.transaction(actor):
                for pid, rev in args[0]:
                    p = repo.get(actor, pid)
                    data = fields(
                        p["payload"]["original_file_name"]
                        + " "
                        + p["payload"]["file_name"]
                    )
                    name = (
                        value
                        + " "
                        + " ".join(s for s in (data["episode"], data["chapter"]) if s)
                        if action == "batch-name"
                        else None
                    )
                    repo.edit(
                        actor,
                        pid,
                        rev,
                        name=name,
                        directory_alias=value if action == "batch-directory" else None,
                    )
            await pending(owner, event)
        elif action == "preferences":
            repo.preferences(actor, {"profile": json.loads(value)})
            await settings(owner, event)
        elif action == "aliases":
            data = json.loads(value)
            repo.set_directory(actor, **data)
            await output(event, "目录别名已保存；只作用于新选择，不更改已入队任务。")
        interactions(owner).pop(actor, None)
    except (ValueError, PermissionError, TypeError):
        await output(
            event,
            "设置未保存：请检查格式、字段、目录授权或记录版本；可重新输入或 /cancelinput。",
        )
    except Exception:  # noqa: BLE001 - private boundary must not expose credentials
        await output(
            event,
            "设置未完成：来源权限、网络或账号状态暂不可确认。可重试或 /cancelinput。",
        )
    return True


async def manual(
    owner, event, message, file_name, *, created_at=None, classification_options=None
):
    repo = store(owner)
    actor = current_user(owner.settings.allowed_user_id)
    prefs = repo.preferences(actor)
    if not prefs["confirmation"] and prefs["profile"] == profile():
        return False
    item = rules.facts(message)
    # A private Bot delivery has a verified actor; no personal-client fallback is allowed.
    naming = name_plan(
        item["original"],
        item["caption"],
        file_name,
        kind=item["kind"],
        extension=item["extension"],
        entities=getattr(message, "entities", ()),
        options=prefs["profile"],
    )
    if prefs["profile"]["mode"] == "compatible" and not any(
        prefs["profile"][key] for key in ("prefixes", "suffixes", "label")
    ):
        naming["file_name"] = file_name
    plan, _ = repo.create(
        actor,
        item,
        naming,
        batch=f"bot:{event.chat_id}:{item['group'] or message.id}",
        target_base=owner.settings.cd2_target,
        created_at=created_at,
        classification_options=classification_options,
    )
    if prefs["confirmation"]:
        await plan_card(owner, event, plan)
    else:
        task, _ = repo.submit(actor, plan["id"], plan["revision"])
        await output(
            event,
            f"✅ 已接收并持久化\n任务：#{task['id']}\n文件：{task['file_name']}\n状态：在排队",
        )
    return True
