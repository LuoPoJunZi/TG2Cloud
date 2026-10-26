"""End-to-end Telegram form events against a temporary SQLite repository."""

from __future__ import annotations

import asyncio
import copy
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
from tg2cloud.listening import account, rules
from tg2cloud.listening.service import Listener
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.telegram import editor, planning


class EditorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = make_settings(Path(self.temp.name))
        self.db = TaskDB(settings.data_dir / "tg115.db")
        self.addCleanup(self.db.close)
        self.owner = make_service(settings, self.db)
        self.admin = settings.allowed_user_id
        self.actor = self.admin
        self.owner.listener = Listener(self.owner)
        self.repo = self.owner.listener.plans
        account.write_state(self.db, account=42, enabled=True)
        self.source = self.repo.save_source(
            self.admin,
            account=42,
            chat=-1001,
            title="测试来源",
            cursor=0,
            config={"rules": {"groups": [{"types": ["视频"]}]}},
        )
        self.scope = user_scope(self.admin)
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)
        self.rows, self.text = [], ""
        await self.open("rules")

    def capture(self, e):
        calls = [
            *e.reply.await_args_list,
            *e.edit.await_args_list,
            *e.respond.await_args_list,
        ]
        if calls:
            self.text = "\n".join(c.args[0] for c in calls)
            self.rows = calls[-1].kwargs.get("buttons") or []
        return e

    def e(self, button=None):
        value = event(self.actor)
        value.edit, value.respond, value.answer = AsyncMock(), AsyncMock(), AsyncMock()
        if button is not None:
            value.data = callback_data(button)
        return value

    async def open(self, kind):
        s = self.repo.source(self.admin, self.source["id"])
        e = self.e()
        await editor.start(self.owner, e, kind, s["id"], s["revision"])
        self.capture(e)

    def find(self, label):
        for row in self.rows:
            for button in row:
                if button.text == label:
                    return button
        self.fail(
            f"Missing button {label}; found {[b.text for r in self.rows for b in r]}"
        )

    async def click(self, label, *, button=None):
        e = self.e(button or self.find(label))
        await planning.callback(self.owner, e)
        return self.capture(e)

    async def type(self, text):
        e = self.e()
        self.assertTrue(await planning.text(self.owner, e, text))
        return self.capture(e)

    def config(self):
        return self.repo.source(self.admin, self.source["id"])["config"]

    async def test_keyword_lists_are_multiple_editable_drafts_and_explicit_save(self):
        original = copy.deepcopy(self.config())
        await self.click("包含关键词")
        await self.click("添加")
        await self.type("物理\n数学")
        await self.click("添加")
        await self.type("天文\n物理")
        self.assertEqual(
            editor.drafts(self.owner)[self.admin].config["rules"]["groups"][0][
                "keywords"
            ],
            ["物理", "数学", "天文"],
        )
        await self.click("删除一项")
        await self.click("2. 数学")
        await self.click("全部包含")
        self.assertEqual(self.config(), original)
        await self.click("返回编辑")
        await self.click("保存修改")
        g = self.config()["rules"]["groups"][0]
        self.assertEqual(g["keywords"], ["物理", "天文"])
        self.assertEqual(g["keyword_mode"], "all")
        self.assertNotIn(self.admin, editor.drafts(self.owner))

    async def test_cancel_and_cancel_input_do_not_write(self):
        original = copy.deepcopy(self.config())
        await self.click("包含关键词")
        await self.click("添加")
        await self.click("取消填写")
        self.assertNotIn(self.admin, planning.interactions(self.owner))
        await self.click("添加")
        await self.type("课程")
        await self.click("返回编辑")
        await self.click("取消返回")
        self.assertEqual(original, self.config())
        self.assertNotIn(self.admin, editor.drafts(self.owner))

    async def test_stale_revision_blocks_save_and_single_use_buttons(self):
        old = self.find("媒体类型")
        await self.click("媒体类型")
        replay = await self.click("", button=old)
        self.assertTrue(replay.answer.await_args.kwargs["alert"])
        s = self.repo.source(self.admin, self.source["id"])
        self.repo.change_source(
            self.admin,
            s["id"],
            s["revision"],
            config=s["config"] | {"confirmation": False},
        )
        await self.click("☐ 图片")
        self.assertIn("已被修改", self.text)
        self.assertEqual(self.config()["rules"]["groups"][0]["types"], ["视频"])
        self.assertFalse(self.config()["confirmation"])

    async def test_token_and_draft_cannot_be_used_by_family_or_after_revocation(self):
        r = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": r["revision"]},
        )
        old = self.find("媒体类型")
        self.actor = 2
        with user_scope(2):
            e = await self.click("", button=old)
            self.assertTrue(e.answer.await_args.kwargs["alert"])
            with self.assertRaises(PermissionError):
                await editor.start(
                    self.owner,
                    self.e(),
                    "rules",
                    self.source["id"],
                    self.source["revision"],
                )
        self.assertEqual(self.config()["rules"]["groups"][0]["types"], ["视频"])

    async def test_invalid_and_oversized_input_leaves_list_unchanged(self):
        await self.click("包含关键词")
        await self.click("添加")
        for text in ("\n".join(str(i) for i in range(21)), "a" * 101, "x\x00y"):
            await self.type(text)
            self.assertEqual(
                editor.drafts(self.owner)[self.admin].config["rules"]["groups"][0][
                    "keywords"
                ],
                [],
            )
        await self.type("有效标题")
        self.assertIn("有效标题", self.text)

    async def test_size_scope_extensions_and_all_fields_can_be_edited(self):
        await self.click("文件后缀")
        await self.click("替换列表")
        await self.type(".MP4, mkv，webm")
        await self.click("返回编辑")
        await self.click("文件大小")
        await self.click("修改最小值")
        await self.type("1.5 MB")
        await self.click("修改最大值")
        await self.type("2 GB")
        await self.click("返回规则")
        await self.click("匹配范围")
        await self.click("说明文字")
        await self.click("返回规则")
        await self.click("排除关键词")
        await self.click("添加")
        await self.type("广告\n试看")
        await self.click("返回编辑")
        await self.click("文件名条件")
        await self.click("添加")
        await self.type("课程*")
        await self.click("通配匹配（*、?）")
        await self.click("返回编辑")
        await self.click("保存修改")
        r = self.config()["rules"]
        self.assertEqual(r["min_bytes"], 1572864)
        self.assertEqual(r["max_bytes"], 2 * 1024**3)
        self.assertEqual(r["scope"], "caption")
        self.assertEqual(r["exclude"], ["广告", "试看"])
        self.assertEqual(r["groups"][0]["extensions"], ["mp4", "mkv", "webm"])
        self.assertEqual(r["groups"][0]["name_mode"], "glob")

    async def test_empty_group_rejected_and_all_attachments_requires_confirmation(self):
        await self.click("组合条件")
        await self.click("删除此组")
        await self.click("返回规则")
        await self.click("保存修改")
        self.assertIn("未保存", self.text)
        self.assertEqual(len(self.config()["rules"]["groups"]), 1)
        await self.click("返回编辑")
        await self.click("组合条件")
        await self.click("接收全部附件")
        self.assertFalse(
            editor.drafts(self.owner)[self.admin].config["rules"]["all_attachments"]
        )
        await self.click("确认接收全部")
        await self.click("保存修改")
        self.assertTrue(self.config()["rules"]["all_attachments"])
        self.assertEqual(self.config()["rules"]["groups"], [])

    async def test_group_edits_preserve_other_groups_and_cancel_remains_safe(self):
        await self.click("组合条件")
        await self.click("添加条件组")
        await self.click("媒体类型")
        await self.click("☐ 图片")
        await self.click("返回规则")
        await self.click("保存修改")
        self.assertEqual(
            [g["types"] for g in self.config()["rules"]["groups"]], [["视频"], ["图片"]]
        )

    async def test_naming_modes_cleaning_template_preview_and_authorized_directory(
        self,
    ):
        self.repo.set_directory(self.admin, "课程", "课程/物理", [])
        await self.open("profile")
        await self.click("命名方式")
        await self.click("说明标题优先")
        await self.click("清理前缀")
        await self.click("添加")
        await self.type("本期推荐")
        await self.click("返回编辑")
        await self.click("模板字段")
        await self.click("☐ 年份")
        await self.click("返回命名")
        await self.click("保存目录")
        await self.click("课程")
        await self.click("预览命名")
        await self.click("测试当前样例")
        self.assertIn("命名预览", self.text)
        self.assertEqual(self.config()["profile"]["mode"], "compatible")
        await self.click("返回编辑")
        await self.click("保存修改")
        p = self.config()["profile"]
        self.assertEqual(p["mode"], "caption")
        self.assertEqual(p["prefixes"], ["本期推荐"])
        self.assertIn("{year}", p["template"])
        self.assertEqual(p["directory"], "课程/物理")

    async def test_source_directory_buttons_default_and_revoked_alias(self):
        self.repo.set_directory(self.admin, "课程", "课程/物理", [])
        await self.open("directory")
        await self.click("课程")
        self.assertEqual(self.config()["directory"], "")
        await self.click("保存修改")
        self.assertEqual(self.config()["directory"], "课程")
        await self.open("directory")
        await self.click("沿用默认设置")
        await self.click("保存修改")
        self.assertEqual(self.config()["directory"], "")

    async def test_draft_tests_do_not_create_tasks_or_advance_cursor(self):
        before = (
            sum(self.db.counts().values()),
            self.repo.source(self.admin, self.source["id"])["cursor"],
        )
        await self.click("测试规则")
        await self.click("修改说明")
        await self.type("广告")
        await self.click("修改文件名")
        await self.type("../../evil.mp4")
        self.assertIn("不含路径", self.text)
        await self.type("课程.mp4")
        await self.click("修改大小")
        await self.type("100 MB")
        await self.click("修改类型")
        await self.click("图片")
        await self.click("测试当前样例")
        self.assertIn("跳过", self.text)
        after = (
            sum(self.db.counts().values()),
            self.repo.source(self.admin, self.source["id"])["cursor"],
        )
        self.assertEqual(before, after)
        self.assertEqual(
            self.db._conn.execute("SELECT count(*) FROM listener_events").fetchone()[0],
            0,
        )

    async def test_recent_tests_use_unsaved_config_without_side_effects(self):
        await self.click("包含关键词")
        await self.click("添加")
        await self.type("物理")
        await self.click("返回编辑")
        self.owner.listener.client = NS(
            get_messages=AsyncMock(return_value=[message(caption="数学")])
        )
        await self.click("测试规则")
        with patch("tg2cloud.listening.service.verified_chat", new=AsyncMock()):
            await self.click("测试最近消息（草稿）")
        self.assertIn("跳过", self.text)
        self.assertEqual(self.config()["rules"]["groups"][0]["keywords"], [])
        self.assertEqual(sum(self.db.counts().values()), 0)

    async def test_expiry_rejects_pending_text_and_does_not_write(self):
        await self.click("包含关键词")
        await self.click("添加")
        editor.drafts(self.owner)[self.admin].expires = time.monotonic() - 1
        await self.type("不应生效")
        self.assertIn("过期", self.text)
        self.assertEqual(self.config()["rules"]["groups"][0]["keywords"], [])

    async def test_personal_naming_and_alias_wizard_no_json(self):
        e = self.e()
        await editor.start(self.owner, e, "personal")
        self.capture(e)
        await self.click("命名方式")
        await self.click("说明标题优先")
        await self.click("保存修改")
        self.assertEqual(
            self.repo.preferences(self.admin)["profile"]["mode"], "caption"
        )
        e = self.e()
        await editor.start(self.owner, e, "aliases")
        self.capture(e)
        await self.click("新增目录别名")
        await self.click("填写别名")
        await self.type("课程")
        await self.click("填写相对目录")
        await self.type("../outside")
        self.assertIn("尚未保存", self.text)
        await self.type("课程/物理")
        await self.click("保存修改")
        self.assertEqual(self.repo.directories(self.admin), {"课程": "课程/物理"})

    async def test_history_requires_preview_and_confirmation(self):
        s = self.repo.source(self.admin, self.source["id"])
        self.repo.change_source(
            self.admin,
            s["id"],
            s["revision"],
            config=s["config"] | {"confirmation": False},
        )
        e = self.e()
        await planning.source_card(self.owner, e, s["id"])
        self.capture(e)
        await self.click("命名规则历史与撤销")
        await self.click("恢复版本 1")
        self.assertFalse(self.config()["confirmation"])
        self.assertIn("拟恢复版本", self.text)
        await self.click("确认恢复此版本")
        self.assertTrue(self.config()["confirmation"])

    async def test_card_has_human_summary_and_no_raw_rule_keys(self):
        e = self.e()
        await planning.source_card(self.owner, e, self.source["id"])
        self.capture(e)
        self.assertNotIn('"groups"', self.text)
        self.assertNotIn("{}", self.text)
        self.assertIn("类型：视频", self.text)

    async def test_concurrent_save_and_duplicate_click_make_one_revision(self):
        await self.click("媒体类型")
        await self.click("☐ 图片")
        await self.click("返回规则")
        button = self.find("保存修改")
        first, second = self.e(button), self.e(button)
        await asyncio.gather(
            planning.callback(self.owner, first), planning.callback(self.owner, second)
        )
        current = self.repo.source(self.admin, self.source["id"])
        self.assertEqual(current["revision"], self.source["revision"] + 1)
        self.assertTrue(second.answer.await_args.kwargs["alert"])
        self.assertEqual(
            current["config"]["rules"]["groups"][0]["types"], ["视频", "图片"]
        )

    async def test_pending_text_cannot_modify_a_replaced_draft(self):
        await self.click("包含关键词")
        await self.click("添加")
        stale = planning.interactions(self.owner)[self.admin]
        await self.open("profile")
        planning.interactions(self.owner)[self.admin] = stale
        await self.type("不可串到新草稿")
        self.assertIn("已变化", self.text)
        self.assertEqual(
            editor.drafts(self.owner)[self.admin].config["profile"]["prefixes"], []
        )

    async def test_directory_revocation_before_save_is_detected(self):
        r = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": r["revision"]},
        )
        self.repo.set_directory(self.admin, "课程", "课程", [2])
        self.actor = 2
        with user_scope(2):
            e = self.e()
            await editor.start(self.owner, e, "personal")
            self.capture(e)
            await self.click("保存目录")
            await self.click("课程")
            self.repo.set_directory(self.admin, "课程", "课程", [])
            await self.click("保存修改")
            self.assertIn("管理员授权的目录别名", self.text)
            self.assertEqual(self.repo.preferences(2)["profile"]["directory"], "")

    async def test_draft_recent_result_cannot_overwrite_newer_edit(self):
        await self.click("测试规则")
        started, finish = asyncio.Event(), asyncio.Event()

        async def slow(*args, **kwargs):
            started.set()
            await finish.wait()
            return []

        button = self.find("测试最近消息（草稿）")
        with patch.object(self.owner.listener, "test", new=AsyncMock(side_effect=slow)):
            pending = asyncio.create_task(self.click("", button=button))
            await started.wait()
            await self.click("修改说明")
            finish.set()
            await pending
        self.assertEqual(
            editor.drafts(self.owner)[self.admin].sample["caption"],
            "城市漫游 第3集 1080P",
        )
        self.assertIn(self.admin, planning.interactions(self.owner))

    async def test_alias_permissions_are_selected_from_existing_family(self):
        record = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": record["revision"]},
        )
        e = self.e()
        await editor.start(self.owner, e, "aliases")
        self.capture(e)
        await self.click("新增目录别名")
        await self.click("填写别名")
        await self.type("课程")
        await self.click("填写相对目录")
        await self.type("课程/物理")
        await self.click("选择授权成员")
        await self.click("☐ 家人")
        await self.click("返回目录设置")
        await self.click("保存修改")
        self.assertEqual(self.repo.directories(2), {"课程": "课程/物理"})

    async def test_personal_confirmation_requires_save(self):
        e = self.e()
        await planning.settings(self.owner, e)
        self.capture(e)
        await self.click("切换确认模式")
        await self.click("确认后转存")
        self.assertFalse(self.repo.preferences(self.admin)["confirmation"])
        await self.click("保存修改")
        self.assertTrue(self.repo.preferences(self.admin)["confirmation"])


    async def test_text_success_returns_updated_list_then_requires_explicit_save(self):
        await self.click("文件后缀")
        await self.click("替换列表")
        await self.type("mp4\nmkv\nmov")
        self.assertIn("1. mp4\n2. mkv\n3. mov", self.text)
        self.assertNotIn("请输入", self.text)
        self.assertNotIn(self.admin, planning.interactions(self.owner))
        self.assertEqual(self.config()["rules"]["groups"][0]["extensions"], [])
        await self.click("返回编辑")
        await self.click("保存修改")
        self.assertEqual(self.config()["rules"]["groups"][0]["extensions"], ["mp4", "mkv", "mov"])

    async def test_plan_status_root_directory_and_navigation_are_readable(self):
        item = rules.facts(message(original="城市漫游.mp4"))
        from tg2cloud.domain.planning import name_plan
        plan, _ = self.repo.create(self.admin, item, name_plan(item["original"], item["caption"], "fallback.mp4"), batch="preview-batch", target_base=self.owner.settings.cd2_target)
        e = self.e()
        await planning.plan_card(self.owner, e, plan)
        self.capture(e)
        self.assertIn("状态：待确认", self.text)
        self.assertIn("目录：Bot 保存目录（无附加子目录）", self.text)
        await self.click("选择目录")
        await self.click("返回计划详情")
        await self.click("批次操作")
        self.find("返回计划详情")
        await self.click("批次选择目录")
        await self.click("返回计划详情")
        await self.click("忽略本次")
        self.assertIn("状态：已忽略", self.text)
        self.assertNotIn("pending", self.text)
        self.find("返回待确认列表")


    async def test_source_directory_layout_is_explicit_draft_and_pauses_on_save(self):
        self.owner.rclone = NS(ensure_directory=AsyncMock())
        await self.open("directory")
        await self.click("来源名称下按类型保存")
        self.assertIn("按来源名称创建/文件类型", self.text)
        self.assertEqual(self.config().get("directory_mode"), "legacy")
        await self.click("保存修改")
        self.assertEqual(self.config()["source_folder"], "测试来源")
        self.assertEqual(self.config()["directory_mode"], "source_type")
        self.assertIn("已暂停", self.text)
        self.owner.rclone.ensure_directory.assert_awaited_once_with("测试来源")
        await self.open("directory")
        await self.click("沿用默认设置")
        await self.click("取消返回")
        self.assertEqual(self.config()["directory_mode"], "source_type")

    async def test_source_directory_failure_after_save_returns_repairable_source(self):
        self.owner.rclone = NS(ensure_directory=AsyncMock(side_effect=OSError("private-token")))
        await self.open("directory")
        await self.click("来源名称下按类型保存")
        await self.click("保存修改")
        self.assertIn("目录创建未完成", self.text)
        self.assertNotIn("private-token", self.text)
        self.find("重试创建目录")
        self.owner.rclone.ensure_directory.side_effect = None
        await self.click("重试创建目录")
        self.assertIn("已就绪", self.text)
        self.assertNotIn(self.admin, editor.drafts(self.owner))


    async def test_history_restores_pre_folder_config_but_keeps_folder_binding(self):
        self.owner.rclone = NS(ensure_directory=AsyncMock())
        await self.open("directory")
        await self.click("来源名称下按类型保存")
        await self.click("保存修改")
        s = self.repo.source(self.admin, self.source["id"])
        folder = s["config"]["source_folder"]
        e = self.e()
        await planning.source_card(self.owner, e, s["id"])
        self.capture(e)
        await self.click("命名规则历史与撤销")
        await self.click("恢复版本 1")
        self.assertIn("沿用分类或默认目录", self.text)
        await self.click("确认恢复此版本")
        self.assertEqual(self.config()["directory_mode"], "legacy")
        self.assertEqual(self.config()["source_folder"], folder)
        self.assertFalse(self.repo.source(self.admin, s["id"])["enabled"])


class FieldParsingTests(unittest.TestCase):
    def test_sizes_are_exact_bounded_and_do_not_accept_expressions(self):
        for text, wanted in [
            ("100 MB", 100 * 1024**2),
            ("1.5GB", 3 * 1024**3 // 2),
            ("3", 3 * 1024**2),
            ("0", 0),
        ]:
            self.assertEqual(editor.size_input(text), wanted)
        for text in ("nan", "-1", "1e9", "101 TB", "1.0000001 MB", "1; rm -rf /"):
            with self.assertRaises(ValueError):
                editor.size_input(text)
