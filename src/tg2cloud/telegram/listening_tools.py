"""Administrator button flows for rules, recovery and bounded historical intake."""
from __future__ import annotations

import copy

from telethon import Button

from tg2cloud.domain.actors import current_user
from tg2cloud.domain.errors import safe_failure
from tg2cloud.domain.planning import PlanningError
from tg2cloud.listening import management as service
from tg2cloud.telegram import planning
from tg2cloud.telegram.editor import rule_summary


def test_result(mid, matched, reason, naming):
    text = f"#{mid} {'匹配' if matched else '跳过'}：{reason}"
    if "filter_matched" in naming:
        text += "\n筛选规则：" + ("通过；" if naming["filter_matched"] else "未通过；") + naming["filter_reason"]
        text += "\n接收判断：" + naming["admission_reason"]
    return text + "\n" + naming["file_name"] + " → " + naming.get("effective_destination", naming.get("directory_preview") or "Bot 保存目录")


async def templates(owner, event, sid, notice=""):
    actor = current_user(owner.settings.allowed_user_id)
    repo = service.repository(owner, actor)
    source = repo.source(actor, sid)
    _, value = service.template_store(repo, actor)
    b = lambda label, *action: planning.token_button(owner, actor, label, ("listen-tool", *action))
    rows = [[b("保存当前已生效规则为方案", "save-name", sid, source["revision"])]]
    rows += [[b(item["name"], "choose-template", sid, item["id"], value["revision"])] for item in value["items"]]
    rows += [[planning.token_button(owner, actor, "返回来源", ("source", sid))]]
    await planning.output(event, notice + "\n规则方案（仅管理员）\n最多保存 8 个方案；仅复制筛选条件，不改命名、保存目录或自动／确认模式。\n点击方案可选择来源、预览并应用。", rows)


async def selection(owner, event, context):
    actor = current_user(owner.settings.allowed_user_id)
    repo = service.repository(owner, actor)
    _, store = service.template_store(repo, actor)
    item = next((x for x in store["items"] if x["id"] == context["template"]), None)
    if item is None or store["revision"] != context["revision"]:
        raise PlanningError("规则方案已变化，请重新打开。")
    b = lambda label, *action: planning.token_button(owner, actor, label, ("listen-tool", *action))
    rows = []
    for source in repo.sources(actor):
        label = ("☑ " if source["id"] in context["targets"] else "☐ ") + source["title"][:24]
        rows.append([b(label, "toggle-source", context, source["id"], source["revision"])])
    rows += [[b("预览所选来源变化", "template-offer", context)],
             [b("删除此方案", "template-delete-offer", context)],
             [b("返回规则方案", "templates", context["sid"])]]
    await planning.output(event, "应用规则方案：" + item["name"] + "\n" + rule_summary(item["rules"], compact=True)
                          + f"\n已选 {len(context['targets'])} 个来源，一次最多 8 个；预览确认后生效。", rows)


async def failures(owner, event, sid, before=0, notice=""):
    actor = current_user(owner.settings.allowed_user_id)
    rows = service.failed_page(owner, actor, sid, before)
    source = service.repository(owner, actor).source(actor, sid)
    b = lambda label, *action: planning.token_button(owner, actor, label, ("listen-tool", *action))
    text = notice + "\n监听失败恢复\n只恢复确认过的下载失败；授权错误和远端不确定文件需单独核对。\n"
    buttons, candidates = [], []
    for task in rows[:5]:
        reason = service.recovery_reason(task)
        text += f"\n#{task['id']} {task['file_name'][:80]}\n{safe_failure(task.get('error') or '')}\n{reason}\n"
        buttons.append([Button.inline(f"查看任务 #{task['id']}", data=f"task:view:{task['id']}".encode())])
        if reason in {"可确认重试", "旧版下载失败；确认后仍需重新核验来源"}:
            snapshot = (task["id"], task["updated_at"])
            candidates.append(snapshot)
            buttons.append([b(f"预览恢复 #{task['id']}", "retry-offer", sid, source["revision"], [snapshot])])
    if candidates:
        buttons.append([b("预览恢复本页可重试任务", "retry-offer", sid, source["revision"], candidates)])
    if len(rows) > 5:
        buttons.append([b("下一页", "failures", sid, rows[4]["id"])])
    buttons.append([planning.token_button(owner, actor, "返回来源", ("source", sid))])
    await planning.output(event, text + ("暂无失败记录。" if not rows else ""), buttons)


async def callback(owner, event, args):
    actor = current_user(owner.settings.allowed_user_id)
    repo = service.repository(owner, actor)
    action, *values = args
    b = lambda label, *a: planning.token_button(owner, actor, label, ("listen-tool", *a))
    try:
        if action == "templates":
            await templates(owner, event, values[0])
        elif action == "save-name":
            await planning.ask(owner, event, ("tools-name", *values), "填写规则方案名称（1～32 字）；保存当前来源已生效的筛选条件。")
        elif action == "choose-template":
            sid, identity, revision = values
            await selection(owner, event, {"sid": sid, "template": identity, "revision": revision, "targets": {}})
        elif action == "toggle-source":
            context, sid, revision = values
            context = copy.deepcopy(context)
            if sid in context["targets"]:
                context["targets"].pop(sid)
            elif len(context["targets"]) < 8:
                context["targets"][sid] = revision
            else:
                raise PlanningError("一次最多选择 8 个来源。")
            await selection(owner, event, context)
        elif action == "template-offer":
            context = values[0]
            _, store = service.template_store(repo, actor)
            item = next((x for x in store["items"] if x["id"] == context["template"]), None)
            if not context["targets"] or item is None or store["revision"] != context["revision"]:
                raise PlanningError("请选择来源；方案变化后请重新预览。")
            text = "确认应用以下筛选变化？命名、目录、启停和转存模式保持原值。\n新规则：\n" + rule_summary(item["rules"], compact=True)
            for sid, revision in context["targets"].items():
                source = repo.source(actor, sid)
                if source["deleted"] or source["revision"] != revision:
                    raise PlanningError("来源已变化，请重新选择。")
                text += "\n\n" + source["title"] + " 原规则：\n" + rule_summary(source["config"]["rules"], compact=True)
            await planning.output(event, text, [[b("确认应用所选来源", "template-apply", context)], [b("返回选择", "selection", context)]])
        elif action == "selection":
            await selection(owner, event, values[0])
        elif action == "template-apply":
            context = values[0]
            count = service.apply_template(owner, actor, context["template"], context["revision"], list(context["targets"].items()))
            await templates(owner, event, context["sid"], f"已应用 {count} 个来源；历史任务保持接收时的规则。")
        elif action == "template-delete-offer":
            context = values[0]
            await planning.output(event, "确认删除这个规则方案？已应用到来源的规则继续保留。", [[b("确认删除方案", "template-delete", context)], [b("取消返回", "selection", context)]])
        elif action == "template-delete":
            context = values[0]
            service.delete_template(owner, actor, context["template"], context["revision"])
            await templates(owner, event, context["sid"], "规则方案已删除。")
        elif action == "failures":
            await failures(owner, event, *values)
        elif action == "retry-offer":
            sid, revision, snapshots = values
            service.live(owner, actor, sid, revision)
            await planning.output(event, f"确认恢复 {len(snapshots)} 个下载失败任务？\n将逐项重新核验附件；只排队原任务，不新建副本。限流、资源与额度检查继续有效。", [[b("确认小批恢复", "retry-commit", sid, revision, snapshots)], [b("取消返回失败列表", "failures", sid)]])
        elif action == "retry-commit":
            sid, revision, snapshots = values
            await planning.output(event, "正在逐项核验原附件；本批最多 5 项、30 秒，尚未核验的任务保持原状态。")
            count = await service.retry_confirmed(owner, actor, sid, revision, snapshots)
            await failures(owner, event, sid, notice=f"已重新排队 {count}/{len(snapshots)} 项；变化、受限或需核对的任务保持原记录。")
        elif action == "history":
            sid = values[0]
            service.live(owner, actor, sid)
            await planning.output(event, "历史补拉（管理员手动操作）\n先只读预览，最多检查 100 条、20 秒；确认后最多登记 5 个待确认计划，不改变正常监听进度。", [[b(f"预览最近 {hours} 小时", "history-preview", sid, hours)] for hours in (1, 6, 24)] + [[planning.token_button(owner, actor, "返回来源", ("source", sid))]])
        elif action == "history-preview":
            sid, hours = values
            await planning.output(event, "正在只读预览历史；最多检查 100 条、20 秒，不会开始下载。")
            preview = await service.history_preview(owner, actor, sid, hours)
            text = (f"历史预览：最近 {hours} 小时\n已检查 {preview['checked']} 条；符合且未重复 {preview['found']} 个附件。\n"
                    + ("本次范围扫描完成。" if preview["complete"] else preview["notice"])
                    + "\n本页最多登记 5 项，余下可重新预览；全部进入待确认，不自动转存。")
            for key, count in preview["skips"].items():
                text += f"\n{key}：{count}"
            for candidate in preview["candidates"]:
                text += f"\n#{candidate['item']['message_id']} {candidate['naming']['file_name']}"
            rows = [[b("确认登记本页待确认计划", "history-commit", preview)]] if preview["candidates"] else []
            rows += [[b("返回时间范围", "history", sid)]]
            await planning.output(event, text, rows)
        elif action == "history-commit":
            preview = values[0]
            count = await service.register_history(owner, actor, preview)
            await planning.output(event, f"已登记 {count} 个待确认计划；没有推进正常监听进度。\n请在待确认列表核对名称、目录并确认转存。", [[planning.token_button(owner, actor, "打开待确认列表", ("pending", 0))], [b("继续历史预览", "history", preview["source"])]])
        else:
            raise PlanningError("监听操作无效，请刷新。")
    except Exception as exc:  # noqa: BLE001 - never expose remote exceptions/credentials
        from tg2cloud.listening.service import source_error
        message = str(exc) if isinstance(exc, PlanningError) else source_error(exc)
        await planning.output(event, "操作未完成：" + message, [[planning.token_button(owner, actor, "返回监听管理", ("listen",))]])


async def name_input(owner, event, args, value):
    actor = current_user(owner.settings.allowed_user_id)
    sid, revision = args
    service.save_template(owner, actor, sid, revision, value)
    planning.interactions(owner).pop(actor, None)
    await templates(owner, event, sid, "规则方案已保存。")
