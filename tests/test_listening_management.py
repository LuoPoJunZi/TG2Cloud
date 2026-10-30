"""Synthetic SQLite/Telegram only; exercise confirmations, limits and stale identities."""
from __future__ import annotations

import asyncio
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from test_listening import event, message
from test_scenarios import make_service, make_settings
from test_telethon_compat import callback_data

from tg2cloud.domain.actors import user_scope
from tg2cloud.domain.planning import PlanningError
from tg2cloud.listening import account, management, rules
from tg2cloud.listening.service import Listener
from tg2cloud.persistence.plans import Plans
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.telegram import listening_tools, planning


class ExplanationTests(unittest.TestCase):
    def test_detail_uses_same_decision_and_exposes_exact_threshold_and_word_scope(self):
        config = rules.defaults()
        item = rules.facts(message(size=32 * 1024**2))
        matched, text = rules.explain(config, item, source_allowed=True)
        self.assertFalse(matched)
        self.assertIn("32.00 MB", text)
        self.assertIn("至少 50.00 MB", text)
        for field, label in (("original", "文件名"), ("caption", "说明")):
            value = item | {field: "包含广告", "size": 50 * 1024**2}
            self.assertIn(label + "中包含“广告”", rules.explain(config, value, source_allowed=True)[1])
            self.assertEqual(rules.evaluate(config, value, source_allowed=True)[1], "排除关键词命中")
        self.assertFalse(rules.explain(config, item, source_allowed=False)[0])

    def test_exclusion_scope_is_optional_and_does_not_widen_inclusion(self):
        config = rules.defaults() | {"exclude_scope": "name"}
        item = rules.facts(message(size=50 * 1024**2, caption="旅行 广告合作"))
        self.assertTrue(rules.evaluate(config, item, source_allowed=True)[0])
        self.assertFalse(rules.evaluate(config | {"exclude_scope": "both"}, item, source_allowed=True)[0])
        self.assertFalse(rules.evaluate(config, item | {"kind": "图片"}, source_allowed=True)[0])
        with self.assertRaises(PlanningError):
            rules.validate(config | {"exclude_scope": "invalid"})

    def test_filter_and_duplicate_results_remain_separate(self):
        rendered = listening_tools.test_result(1, False, "重复文件", {
            "file_name": "旅行.mp4", "filter_matched": True, "filter_reason": "包含规则组命中",
            "admission_reason": "重复文件", "effective_destination": "Bot 保存目录/频道/视频"})
        self.assertIn("筛选规则：通过", rendered)
        self.assertIn("接收判断：重复文件", rendered)
        self.assertIn("Bot 保存目录/频道/视频", rendered)


class ManagementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = make_settings(Path(self.temp.name))
        self.db = TaskDB(self.settings.data_dir / "tg2cloud.db")
        self.addCleanup(self.db.close)
        self.owner = make_service(self.settings, self.db)
        self.admin = self.settings.allowed_user_id
        self.listener = self.owner.listener = Listener(self.owner)
        self.repo = self.listener.plans
        account.write_state(self.db, enabled=True, account=42)
        self.messages = [message(i) for i in range(1, 8)]
        async def iterate(*args, **kwargs):
            for m in self.messages:
                yield m
        self.listener.client = NS(iter_messages=iterate, get_messages=AsyncMock(return_value=message()),
                                  download_media=AsyncMock(), disconnect=AsyncMock())
        self.source = self.add_source(-1001)
        self.scope = user_scope(self.admin)
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)
        patched = patch("tg2cloud.listening.management.verified_chat", new=AsyncMock())
        patched.start()
        self.addCleanup(patched.stop)
        self.rows = []
        self.text = ""

    def add_source(self, chat):
        source = self.repo.save_source(self.admin, account=42, chat=chat, title="合成频道" + str(abs(chat)),
                                      cursor=0, config={"rules": {"all_attachments": True}, "confirmation": False},
                                      target_base=self.settings.cd2_target)
        self.repo.change_source(self.admin, source["id"], source["revision"], enabled=True)
        return self.repo.source(self.admin, source["id"])

    def e(self, button=None):
        e = event(self.admin)
        e.edit, e.respond, e.answer = AsyncMock(), AsyncMock(), AsyncMock()
        if button is not None:
            e.data = callback_data(button)
        return e

    def capture(self, e):
        calls = [*e.reply.await_args_list, *e.edit.await_args_list, *e.respond.await_args_list]
        self.text = "\n".join(c.args[0] for c in calls)
        if calls:
            self.rows = calls[-1].kwargs.get("buttons") or []

    async def click(self, label):
        button = next(b for row in self.rows for b in row if b.text == label)
        e = self.e(button)
        await planning.callback(self.owner, e)
        self.capture(e)
        return button

    def save_template(self):
        return management.save_template(self.owner, self.admin, self.source["id"], self.source["revision"], "合成筛选")

    async def test_template_bulk_apply_is_atomic_and_preserves_unrelated_settings(self):
        value = self.save_template()
        other = self.add_source(-1002)
        self.repo.change_source(self.admin, other["id"], other["revision"],
                                config=other["config"] | {"rules": rules.defaults()})
        changed = self.repo.source(self.admin, other["id"])
        before = copy.deepcopy(changed["config"])
        management.apply_template(self.owner, self.admin, value["items"][0]["id"], value["revision"],
                                  [(changed["id"], changed["revision"])])
        result = self.repo.source(self.admin, changed["id"])
        self.assertEqual(result["config"] | {"rules": before["rules"]}, before)
        self.assertEqual(result["config"]["rules"], self.source["config"]["rules"])
        original = self.repo.source(self.admin, self.source["id"])
        with self.assertRaises(PlanningError):
            management.apply_template(self.owner, self.admin, value["items"][0]["id"], value["revision"],
                                      [(original["id"], original["revision"]), (changed["id"], changed["revision"])])
        self.assertEqual(self.repo.source(self.admin, original["id"]), original)
        management.delete_template(self.owner, self.admin, value["items"][0]["id"], value["revision"])
        self.assertEqual(management.template_store(Plans(self.db, self.admin), self.admin)[1]["items"], [])
        self.assertEqual(self.repo.source(self.admin, result["id"]), result)

    async def test_template_buttons_require_preview_and_confirmation_and_are_single_use(self):
        self.save_template()
        e = self.e()
        await listening_tools.templates(self.owner, e, self.source["id"])
        self.capture(e)
        await self.click("合成筛选")
        await self.click("☐ " + self.source["title"][:24])
        await self.click("预览所选来源变化")
        before = self.repo.source(self.admin, self.source["id"])
        self.assertIn("原规则", self.text)
        button = await self.click("确认应用所选来源")
        after = self.repo.source(self.admin, self.source["id"])
        self.assertEqual(after["revision"], before["revision"] + 1)
        again = self.e(button)
        await planning.callback(self.owner, again)
        self.assertTrue(again.answer.await_args.kwargs["alert"])
        self.assertEqual(self.repo.source(self.admin, after["id"]), after)

    async def test_template_name_input_returns_to_menu_without_writing_source(self):
        e = self.e()
        await listening_tools.templates(self.owner, e, self.source["id"])
        self.capture(e)
        original = self.repo.source(self.admin, self.source["id"])
        await self.click("保存当前已生效规则为方案")
        incoming = self.e()
        self.assertTrue(await planning.text(self.owner, incoming, "家庭视频"))
        self.capture(incoming)
        self.assertIn("规则方案已保存", self.text)
        self.assertNotIn(self.admin, planning.interactions(self.owner))
        self.assertIn("家庭视频", [b.text for row in self.rows for b in row])
        self.assertEqual(self.repo.source(self.admin, self.source["id"]), original)

    async def test_history_buttons_preview_then_confirm_without_starting_transfers(self):
        e = self.e()
        await listening_tools.callback(self.owner, e, ("history", self.source["id"]))
        self.capture(e)
        await self.click("预览最近 1 小时")
        self.assertIn("已检查 7 条", self.text)
        self.assertEqual(self.repo.pending(self.admin), [])
        confirmation = await self.click("确认登记本页待确认计划")
        self.assertEqual(len(self.repo.pending(self.admin)), 5)
        self.assertEqual(self.db.counts(), {})
        replay = self.e(confirmation)
        await planning.callback(self.owner, replay)
        self.assertTrue(replay.answer.await_args.kwargs["alert"])
        self.assertEqual(len(self.repo.pending(self.admin)), 5)

    async def test_failure_buttons_require_explicit_confirmation(self):
        task = self.failed_task()
        e = self.e()
        await listening_tools.failures(self.owner, e, self.source["id"])
        self.capture(e)
        await self.click(f"预览恢复 #{task['id']}")
        self.assertEqual(self.db.get(task["id"])["state"], "download_failed")
        with patch("tg2cloud.listening.service.verified_chat", new=AsyncMock()):
            await self.click("确认小批恢复")
        self.assertEqual(self.db.get(task["id"])["state"], "queued")
        self.assertIn("1/1", self.text)

    async def test_history_wrong_chat_and_pending_limit_never_register_outside_scope(self):
        self.messages = [message(chat=-7777)]
        preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        self.assertEqual(preview["found"], 0)
        self.assertEqual(preview["skips"]["消息不属于此来源"], 1)
        self.messages = [message(i) for i in range(1, 4)]
        preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        calls = 0
        original = self.repo.create
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PlanningError("合成容量边界")
            return original(*args, **kwargs)
        with patch.object(Plans, "create", side_effect=fail_second), self.assertRaises(PlanningError):
            await management.register_history(self.owner, self.admin, preview)
        self.assertEqual(self.repo.pending(self.admin), [])
        self.assertEqual(self.repo.c.execute("SELECT count(*) FROM listener_events").fetchone()[0], 0)

    async def test_non_admin_cannot_save_apply_scan_or_access_recovery(self):
        with self.assertRaises(PermissionError):
            management.save_template(self.owner, 2, self.source["id"], self.source["revision"], "x")
        with self.assertRaises(PermissionError):
            await management.history_preview(self.owner, 2, self.source["id"], 1)
        with self.assertRaises(PermissionError):
            management.failed_page(self.owner, 2, self.source["id"])
        with self.assertRaises(PermissionError):
            management.apply_template(self.owner, 2, "x", 0, [(1, 1)])

    async def test_template_name_limits_unknown_format_and_stale_deletion_preserve_data(self):
        value = self.save_template()
        for name in ("", "a" * 33, "bad\nname", "合成筛选"):
            with self.assertRaises(PlanningError):
                management.save_template(self.owner, self.admin, self.source["id"], self.source["revision"], name)
        with self.assertRaises(PlanningError):
            management.delete_template(self.owner, self.admin, value["items"][0]["id"], -1)
        key, _ = management.template_store(self.repo, self.admin)
        raw = json.dumps({"format": 99, "revision": 0, "items": []})
        self.repo.c.execute("UPDATE service_meta SET value=? WHERE key=?", (raw, key))
        with self.assertRaises(PlanningError):
            self.save_template()
        self.assertEqual(self.repo.c.execute("SELECT value FROM service_meta WHERE key=?", (key,)).fetchone()[0], raw)

    async def test_history_preview_is_readonly_then_registers_five_pending_without_cursor_change(self):
        before = self.repo.source(self.admin, self.source["id"])
        preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        self.assertEqual(preview["checked"], 7)
        self.assertEqual(preview["found"], 7)
        self.assertEqual(len(preview["candidates"]), 5)
        self.assertEqual(self.repo.pending(self.admin), [])
        self.assertEqual(self.db.counts(), {})
        self.assertEqual(await management.register_history(self.owner, self.admin, preview), 5)
        self.assertEqual(self.db.counts(), {})
        self.assertEqual(len(self.repo.pending(self.admin)), 5)
        self.assertEqual(self.repo.source(self.admin, self.source["id"]), before)
        self.assertEqual(await management.register_history(self.owner, self.admin, preview), 0)
        next_preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        self.assertEqual(next_preview["found"], 2)
        self.listener.client.download_media.assert_not_awaited()

    async def test_history_timeout_and_scan_limit_are_explicit(self):
        self.messages = [message(i) for i in range(1, 103)]
        preview = await management.history_preview(self.owner, self.admin, self.source["id"], 24)
        self.assertEqual(preview["checked"], 100)
        self.assertFalse(preview["complete"])
        self.assertIn("上限", preview["notice"])
        async def slow(*args, **kwargs):
            yield message()
            await asyncio.sleep(10)
        self.listener.client.iter_messages = slow
        with patch.object(management, "HISTORY_TIMEOUT", .01):
            preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        self.assertFalse(preview["complete"])
        self.assertEqual(preview["checked"], 1)
        self.assertIn("超时", preview["notice"])
        self.assertEqual(self.repo.pending(self.admin), [])

    async def test_history_expiry_rule_change_identity_and_root_change_reject_confirm(self):
        preview = await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        with self.assertRaises(PlanningError):
            await management.register_history(self.owner, self.admin, preview | {"expires": 0})
        with self.assertRaises(PlanningError):
            await management.register_history(self.owner, self.admin, preview | {"base": "other"})
        self.repo.change_source(self.admin, self.source["id"], self.source["revision"], enabled=False)
        with self.assertRaises(PlanningError):
            await management.register_history(self.owner, self.admin, preview)
        self.assertEqual(self.repo.pending(self.admin), [])

    async def test_history_rechecks_connection_and_rules_after_permission_check(self):
        original_client = self.listener.client
        for change in ("connection", "revision"):
            with self.subTest(change=change):
                async def mutate(*args, change=change):
                    if change == "connection":
                        self.listener.client = NS()
                    else:
                        source = self.repo.source(self.admin, self.source["id"])
                        self.repo.change_source(self.admin, source["id"], source["revision"],
                                                config=source["config"] | {"rules": rules.defaults()})
                with patch("tg2cloud.listening.management.verified_chat", new=mutate), self.assertRaises(PlanningError):
                    await management.history_preview(self.owner, self.admin, self.source["id"], 1)
                self.listener.client = original_client
                self.assertEqual(self.repo.pending(self.admin), [])
                self.assertEqual(self.repo.c.execute("SELECT count(*) FROM listener_events").fetchone()[0], 0)

    async def test_history_flood_sets_durable_cooldown_and_does_not_register(self):
        from telethon.errors import FloodWaitError
        async def limited(*args, **kwargs):
            raise FloodWaitError(request=None, capture=60)
            yield  # pragma: no cover - define an async iterator without any message
        self.listener.client.iter_messages = limited
        with self.assertRaises(PlanningError):
            await management.history_preview(self.owner, self.admin, self.source["id"], 1)
        self.assertGreater(account.state(self.db)["cooldown_until"], time.time())
        self.assertEqual(self.repo.pending(self.admin), [])

    def failed_task(self, mid=1, **changes):
        source = self.repo.source(self.admin, self.source["id"])
        item, _, _, naming = self.listener.preview(source, message(mid))
        plan, _ = self.repo.create(self.admin, item, naming, identity="listener:42", source=source["id"],
                                   target_base=self.settings.cd2_target)
        task, _ = self.repo.submit(self.admin, plan["id"], plan["revision"])
        self.db.update(task["id"], state="download_failed", failure_kind="network", error="已脱敏网络原因", **changes)
        return self.db.get(task["id"])

    async def test_recovery_revalidates_original_task_and_cas_rejects_duplicate_click(self):
        task = self.failed_task()
        snapshots = [(task["id"], task["updated_at"])]
        with patch("tg2cloud.listening.service.verified_chat", new=AsyncMock()):
            count = await management.retry_confirmed(self.owner, self.admin, self.source["id"], self.source["revision"], snapshots)
        self.assertEqual(count, 1)
        self.assertEqual(self.db.get(task["id"])["state"], "queued")
        self.assertEqual(await management.retry_confirmed(self.owner, self.admin, self.source["id"], self.source["revision"], snapshots), 0)
        self.assertEqual(sum(self.db.counts().values()), 1)

    async def test_uncertain_remote_cancelled_wrong_owner_and_changed_revisions_are_not_retried(self):
        task = self.failed_task(remote_temp_path="retained-object")
        self.assertEqual(management.recovery_reason(task), "需要单独核对任务和远端状态")
        self.assertEqual(await management.retry_confirmed(self.owner, self.admin, self.source["id"], self.source["revision"], [(task["id"], task["updated_at"])]), 0)
        self.assertEqual(self.db.get(task["id"]), task)
        with self.assertRaises(PlanningError):
            await management.retry_confirmed(self.owner, self.admin, self.source["id"], 0, [(task["id"], task["updated_at"])])
        with self.assertRaises(PlanningError):
            await management.retry_confirmed(self.owner, self.admin, self.source["id"], self.source["revision"], [(1, 1)] * 6)

    async def test_recovery_permission_failure_preserves_task_and_stops_batch(self):
        from telethon.errors import ChannelPrivateError
        task = self.failed_task()
        with patch("tg2cloud.listening.service.verified_chat", new=AsyncMock(side_effect=ChannelPrivateError(request=None))):
            count = await management.retry_confirmed(self.owner, self.admin, self.source["id"], self.source["revision"], [(task["id"], task["updated_at"])])
        self.assertEqual(count, 0)
        self.assertEqual(self.db.get(task["id"])["state"], "download_failed")
        self.assertFalse(self.repo.source(self.admin, self.source["id"])["enabled"])

    async def test_wait_records_are_bounded_throttled_and_readable(self):
        task = {"id": 1, "source_id": self.source["id"]}
        with patch("tg2cloud.listening.service.time.monotonic", return_value=100):
            self.assertTrue(self.listener.record_wait(task, 3))
            self.assertFalse(self.listener.record_wait(task, 3))
            self.assertIn("2 次、累计约 6 秒", self.listener.wait_summary(task_id=1))
            self.listener.finish_wait(1)
            self.assertIn("当前无等待", self.listener.wait_summary(source_id=self.source["id"]))
        for i in range(2, 70):
            self.listener.record_wait(task | {"id": i}, 1)
        self.assertEqual(len(self.listener.wait_records), 64)
        self.assertEqual(self.listener.wait_summary(task_id=1), "")

    async def test_legacy_and_source_directories_preview_effective_relative_destination(self):
        path = management.destination(self.owner, self.admin, self.source)
        self.assertTrue(path.startswith("Bot 保存目录/合成频道"))
        self.assertTrue(path.endswith("/视频"))
        old = self.repo.save_source(self.admin, account=42, chat=-9999, title="旧来源", cursor=0,
                                   config={"rules": {"all_attachments": True}})
        self.assertEqual(management.destination(self.owner, self.admin, old), "Bot 保存目录（无附加子目录）")
