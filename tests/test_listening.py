"""No real accounts: metadata, authorization, transactions, cursors and input identity."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import stat
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from test_scenarios import FakeRclone, make_service, make_settings
from test_telethon_compat import callback_data

from tg2cloud.domain.actors import user_scope
from tg2cloud.domain.planning import fields, name_plan, profile
from tg2cloud.listening import account, rules
from tg2cloud.listening.service import (
    CheckedSource,
    Listener,
    ListenerReadError,
    task_source,
    verified_chat,
)
from tg2cloud.persistence.plans import Plans
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.telegram import planning


def message(
    mid=1,
    *,
    original="Ab83Kd91X.mp4",
    caption="城市漫游 第二季 第03集 1080P",
    kind="video",
    protected=False,
    chat=-1001,
    group=None,
    size=100,
):
    extension = Path(original).suffix
    return NS(
        id=mid,
        chat_id=chat,
        sender_id=42,
        grouped_id=group,
        out=False,
        media=True,
        document=NS(id=1000 + mid) if kind != "photo" else None,
        photo=NS(id=1000 + mid) if kind == "photo" else None,
        video=True if kind == "video" else None,
        audio=None,
        voice=None,
        entities=[],
        file=NS(
            name=original,
            size=size,
            ext=extension,
            mime_type="video/mp4"
            if kind == "video"
            else "image/jpeg"
            if kind == "photo"
            else "application/pdf",
        ),
        raw_text=caption,
        message=caption,
        noforwards=protected,
        date=datetime.now(timezone.utc) - timedelta(seconds=10),
    )


def event(actor, msg=None, text=""):
    msg = msg or NS(media=None, file=None, grouped_id=None)
    return NS(
        sender_id=actor,
        chat_id=actor,
        is_private=True,
        message=msg,
        raw_text=text,
        reply=AsyncMock(),
    )


class RuleTests(unittest.TestCase):
    def match(self, config, **changes):
        item = rules.facts(message()) | changes
        return rules.evaluate(config, item, source_allowed=True)

    def test_and_groups_or_and_excludes_are_hard(self):
        cfg = {
            "groups": [
                {
                    "types": ["视频"],
                    "extensions": [".MP4", "mkv"],
                    "keywords": ["物理", "数学"],
                },
                {"extensions": ["pdf"], "keywords": ["讲义"]},
            ],
            "exclude": ["广告"],
            "max_bytes": 1024,
        }
        self.assertTrue(self.match(cfg, caption="物理", original="原名.MP4")[0])
        self.assertTrue(
            self.match(
                cfg, caption="讲义", original="课件.pdf", extension=".pdf", kind="文档"
            )[0]
        )
        for changes in (
            {"caption": "物理 广告"},
            {"caption": "物理", "size": 2048},
            {"caption": "物理", "size": None},
            {"caption": "旅行"},
        ):
            self.assertFalse(self.match(cfg, **changes)[0])

    def test_unicode_keywords_any_all_and_scopes(self):
        cfg = {"groups": [{"keywords": ["물리", "ＡＢＣ"], "keyword_mode": "all"}]}
        self.assertTrue(self.match(cfg, caption="물리 abc")[0])
        self.assertFalse(self.match(cfg, caption="물리")[0])
        self.assertFalse(self.match(cfg | {"scope": "name"}, caption="물리 abc")[0])
        self.assertTrue(
            self.match(
                {"groups": [{"keywords": ["日本語", "旅行"]}]}, caption="日本語"
            )[0]
        )

    def test_all_attachments_requires_confirmation_and_invalid_never_widens(self):
        for cfg in (
            {},
            {"groups": [{}]},
            {"all_attachments": 1},
            {"scope": "unknown"},
            {"groups": [{"regex": ".*"}]},
            {"min_bytes": 5, "max_bytes": 4},
        ):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                rules.validate(cfg)
        self.assertTrue(self.match({"all_attachments": True})[0])
        self.assertFalse(self.match({"all_attachments": True}, attachment=False)[0])

    def test_names_exact_contains_glob_and_multi_extensions(self):
        for mode, value in (
            ("exact", "AB83KD91X.MP4"),
            ("contains", "83kd"),
            ("glob", "Ab*?.mp4"),
        ):
            self.assertTrue(
                self.match({"groups": [{"names": [value], "name_mode": mode}]})[0]
            )
        self.assertTrue(
            self.match(
                {"groups": [{"extensions": ["tar.gz"]}]}, original="课程.tar.gz"
            )[0]
        )
        with self.assertRaises(ValueError):
            rules.validate({"groups": [{"names": ["[ab]*"], "name_mode": "glob"}]})

    def test_protection_metadata_does_not_replace_permissions_or_size_checks(self):
        item = rules.facts(message(protected=None))
        for flag in (None, True, False):
            self.assertTrue(rules.evaluate({"all_attachments": True}, item | {"protected": flag}, source_allowed=True)[0])
        self.assertFalse(
            rules.evaluate(
                {"all_attachments": True},
                item | {"protected": False},
                source_allowed=False,
            )[0]
        )
        for size in (None, 0, -1, True, "100"):
            self.assertFalse(self.match({"all_attachments": True}, size=size)[0])

    def test_metadata_type_uses_mime_not_document_transport(self):
        m = message(kind="document")
        m.file.mime_type = "video/mp4"
        self.assertEqual(rules.facts(m)["kind"], "视频")
        self.assertEqual(rules.facts(message(kind="photo"))["kind"], "图片")


class NamingPlanTests(unittest.TestCase):
    def test_compatible_preserves_semantic_name_and_caption_modes_preserve_numbers(
        self,
    ):
        p = name_plan(
            "The Last Journey.mp4", "城市旅行 第03集", "fallback.mp4", kind="视频"
        )
        self.assertEqual(p["file_name"], "The Last Journey.mp4")
        p = name_plan(
            "光学实验 第02讲.mp4",
            "光学实验",
            "fallback.mp4",
            kind="视频",
            options={"mode": "caption"},
        )
        self.assertIn("第02讲", p["file_name"])

    def test_template_extracts_only_real_fields(self):
        p = name_plan(
            "Ab83Kd91X.mp4",
            "城市漫游 第2季 第03集 1080P",
            "fallback.mp4",
            kind="视频",
            options={"mode": "template", "template": "{title} {episode}"},
        )
        self.assertIn("S02E03", p["file_name"])
        self.assertNotIn("1080P", p["file_name"])
        self.assertEqual(fields("没有季集的标题")["episode"], "")
        for language in (
            "今日の旅",
            "오늘의 여행",
            "The Last Journey",
            "Café de Paris",
        ):
            self.assertIn(
                language.split()[0],
                name_plan("123456789.mp4", language, "fallback.mp4", kind="视频")[
                    "file_name"
                ],
            )

    def test_missing_template_fields_keep_chapter_without_empty_separators(self):
        p = name_plan(
            "光学实验 第02讲.mp4",
            "光学实验 第02讲",
            "fallback.mp4",
            options={"mode": "template", "template": "{title} - {year} - {episode}"},
        )
        self.assertIn("第02讲", p["file_name"])
        self.assertNotIn("- -", p["file_name"])

    def test_source_prefix_rules_do_not_change_global_naming(self):
        result = name_plan(
            "本期推荐光学实验.mp4",
            "",
            "fallback.mp4",
            options={"prefixes": ["本期推荐"]},
        )
        self.assertEqual(result["file_name"], "光学实验.mp4")
        self.assertIn(
            "本期推荐",
            name_plan("本期推荐光学实验.mp4", "", "fallback.mp4")["file_name"],
        )
        with self.assertRaises(ValueError):
            profile({"template": "{unknown}"})
        for invalid in ([], ["bad"], True, "caption", 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                profile(invalid)

    def test_extension_paths_and_utf8_safety(self):
        p = name_plan(
            "1234.mp4",
            "标题.exe\nhttps://example.com @channel",
            "fallback.mp4",
            kind="视频",
            options={"mode": "caption"},
        )
        self.assertTrue(p["file_name"].endswith(".mp4"))
        p = name_plan("1234.mp4", "标题" * 500, "fallback.mp4", kind="视频")
        self.assertLessEqual(len(p["file_name"].encode()), 180)
        self.assertNotIn(
            "/", name_plan("../../escape.mp4", "", "fallback.mp4")["file_name"]
        )


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = make_settings(self.root)
        self.db = TaskDB(self.root / "tasks.db")
        self.addCleanup(self.db.close)
        zone = patch.dict(os.environ, {"TZ": "UTC"})
        zone.start()
        self.addCleanup(zone.stop)
        self.admin = self.settings.allowed_user_id
        self.repo = Plans(self.db, self.admin)
        record = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": record["revision"]},
        )

    def plan(self, actor=None, mid=1, **kwargs):
        m = message(mid, chat=self.admin if actor is None else actor)
        item = rules.facts(m)
        naming = name_plan(
            item["original"],
            item["caption"],
            "fallback.mp4",
            kind="视频",
            options=kwargs.pop("options", None),
        )
        return self.repo.create(
            actor or self.admin,
            item,
            naming,
            target_base=self.settings.cd2_target,
            **kwargs,
        )[0]

    def source(self):
        s = self.repo.save_source(
            self.admin,
            account=42,
            chat=-1001,
            title="合成课程",
            cursor=100,
            config={"rules": {"groups": [{"types": ["视频"]}]}},
        )
        self.repo.change_source(self.admin, s["id"], s["revision"], enabled=True)
        return self.repo.source(self.admin, s["id"])

    def test_migration_keeps_history_identity_and_unknown_schema_rejected(self):
        task = self.db.create_task(
            chat_id=1, message_id=1, sender_id=1, file_name="old.mp4", file_size=100
        )[0]
        self.assertEqual(task["read_identity"], "bot")
        self.assertEqual(self.db._conn.execute("PRAGMA user_version").fetchone()[0], 3)
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.get(task["id"])["file_name"], "old.mp4")
        self.db._conn.execute("PRAGMA user_version=999")
        with self.assertRaises(RuntimeError):
            TaskDB(self.root / "tasks.db")

    def test_duplicate_submit_concurrent_is_one_task_and_one_reservation(self):
        p = self.plan()
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = list(
                pool.map(
                    lambda _: self.repo.submit(self.admin, p["id"], p["revision"]),
                    range(8),
                )
            )
        self.assertEqual(len({t[0]["id"] for t in tasks}), 1)
        self.assertEqual(sum(created for _, created in tasks), 1)
        self.assertEqual(
            self.db._conn.execute("SELECT count(*) FROM quota_ledger").fetchone()[0], 1
        )

    def test_crash_between_task_and_plan_rolls_back_both(self):
        p = self.plan()
        self.db._conn.execute(
            "CREATE TRIGGER fail_plan BEFORE UPDATE ON transfer_plans WHEN NEW.status='submitted' BEGIN SELECT RAISE(ABORT,'synthetic interruption'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.submit(self.admin, p["id"], p["revision"])
        self.assertEqual(self.db.counts(), {})
        self.assertEqual(self.repo.get(self.admin, p["id"])["status"], "pending")
        self.assertEqual(
            self.db._conn.execute("SELECT count(*) FROM quota_ledger").fetchone()[0], 0
        )

    def test_pending_restarts_and_does_not_reserve(self):
        p = self.plan()
        self.assertEqual(self.db.counts(), {})
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.addCleanup(self.db.close)
        repo = Plans(self.db, self.admin)
        self.assertEqual(repo.pending(self.admin)[0]["id"], p["id"])
        self.assertEqual(repo.pending(2), [])
        with self.assertRaises(PermissionError):
            repo.get(2, p["id"])

    def test_listener_rules_and_tasks_cannot_be_used_by_member(self):
        s = self.source()
        p = self.plan(mid=2)
        for fn in (
            lambda: self.repo.sources(2),
            lambda: self.repo.source(2, s["id"]),
            lambda: self.repo.save_source(
                2, account=42, chat=-2, title="x", cursor=1, config={}
            ),
            lambda: self.repo.create(
                2,
                rules.facts(message()),
                name_plan("", "title", "f.mp4"),
                identity="listener:42",
                source=s["id"],
            ),
        ):
            with self.assertRaises(PermissionError):
                fn()
        with self.assertRaises(PermissionError):
            self.repo.edit(2, p["id"], p["revision"], name="mine")

    def test_revoked_family_cannot_continue_old_plans(self):
        p = self.plan(actor=2)
        record = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin, {"action": "disable", "id": 2, "revision": record["revision"]}
        )
        with self.assertRaises(PermissionError):
            self.repo.submit(2, p["id"], p["revision"])

    def test_directories_are_allowlisted_paths_and_snapshots_frozen(self):
        for path in ("../escape", "/absolute", "a/%2e%2e", "a\\b", "a//b"):
            with self.assertRaises(ValueError):
                self.repo.set_directory(self.admin, "课程", path, [2])
        self.repo.set_directory(self.admin, "课程", "课程/光学", [2])
        p = self.plan(actor=2, directory_alias="课程")
        task, _ = self.repo.submit(2, p["id"], p["revision"])
        self.repo.set_directory(self.admin, "课程", "课程/数学", [])
        self.assertEqual(self.db.get(task["id"])["target_directory"], "课程/光学")
        with self.assertRaises(ValueError):
            self.repo.directory(2, "课程")

    def test_feedback_is_local_until_explicit_save_and_history_retained(self):
        s = self.source()
        item = rules.facts(message())
        item["original"] = "本期推荐光学实验.mp4"
        naming = name_plan(item["original"], "", "fallback.mp4")
        p = self.repo.create(
            self.admin, item, naming, identity="listener:42", source=s["id"]
        )[0]
        self.repo.edit(self.admin, p["id"], p["revision"], name="光学实验")
        self.assertEqual(
            self.repo.source(self.admin, s["id"])["config"]["profile"]["prefixes"], []
        )
        feedback = self.repo.feedback(self.admin)[0]
        self.repo.apply_feedback(self.admin, feedback["id"], s["revision"])
        self.assertIn(
            "本期推荐",
            self.repo.source(self.admin, s["id"])["config"]["profile"]["prefixes"],
        )
        self.assertTrue(self.repo.source_history(self.admin, s["id"]))

    def test_expired_old_revision_and_submitted_cannot_rename(self):
        p = self.plan()
        changed = self.repo.edit(self.admin, p["id"], p["revision"], name="new")
        with self.assertRaises(ValueError):
            self.repo.submit(self.admin, p["id"], p["revision"])
        self.repo.submit(self.admin, changed["id"], changed["revision"])
        with self.assertRaises(ValueError):
            self.repo.edit(self.admin, changed["id"], changed["revision"], name="bad")
        q = self.plan(mid=2)
        self.db._conn.execute(
            "UPDATE transfer_plans SET expires=0 WHERE id=?", (q["id"],)
        )
        with self.assertRaises(ValueError):
            self.repo.submit(self.admin, q["id"], q["revision"])

    def test_source_cas_delete_keeps_task_and_rejects_old_buttons(self):
        s = self.source()
        with self.assertRaises(ValueError):
            self.repo.change_source(
                self.admin, s["id"], s["revision"] - 1, enabled=False
            )
        self.repo.change_source(self.admin, s["id"], s["revision"], delete=True)
        self.assertEqual(self.repo.sources(self.admin), [])
        self.assertTrue(self.repo.source(self.admin, s["id"])["deleted"])

    def test_classification_and_rule_snapshot_frozen_before_approval(self):
        from tg2cloud.persistence import features

        prefs = self.db.feature_settings()
        features.change(self.db._conn, prefs["revision"], {"classification": "type"})
        p = self.plan()
        features.change(
            self.db._conn,
            self.db.feature_settings()["revision"],
            {"classification": "year"},
        )
        task, _ = self.repo.submit(self.admin, p["id"], p["revision"])
        self.assertEqual(task["target_directory"], "视频")
        self.assertEqual(task["created_at"], p["payload"]["created_at"])

    def test_v2_database_and_personal_session_remain_intact(self):
        self.db.create_task(
            chat_id=88,
            message_id=88,
            sender_id=self.admin,
            file_name="历史任务.mp4",
            file_size=10,
        )
        self.db._conn.execute("PRAGMA user_version=2")
        self.db._conn.execute("ALTER TABLE tasks DROP COLUMN read_identity")
        self.db._conn.execute("ALTER TABLE tasks DROP COLUMN source_id")
        self.db.close()
        self.db = TaskDB(self.root / "tasks.db")
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.get(1)["file_name"], "历史任务.mp4")
        self.assertEqual(self.db.get(1)["read_identity"], "bot")
        self.assertEqual(self.db._conn.execute("PRAGMA user_version").fetchone()[0], 3)


class ListenerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = make_settings(Path(self.temp.name))
        self.admin = self.settings.allowed_user_id
        self.db = TaskDB(self.settings.data_dir / "tg115.db")
        self.addCleanup(self.db.close)
        self.owner = make_service(self.settings, self.db)
        self.owner._notify = AsyncMock()
        self.owner._stop = asyncio.Event()
        self.listener = Listener(self.owner)
        self.owner.listener = self.listener
        self.listener.client = NS(get_messages=AsyncMock(), download_media=AsyncMock())
        self.repo = self.listener.plans
        account.write_state(self.db, account=42, enabled=True, status="synthetic")
        s = self.repo.save_source(
            self.admin,
            account=42,
            chat=-1001,
            title="合成来源",
            cursor=0,
            config={"rules": {"groups": [{"types": ["视频"]}]}},
        )
        self.repo.change_source(self.admin, s["id"], s["revision"], enabled=True)
        self.source = self.repo.source(self.admin, s["id"])
        self.verify = patch(
            "tg2cloud.listening.service.verified_chat",
            new=AsyncMock(return_value=NS(title="合成来源")),
        )
        self.checked = self.verify.start()
        self.addCleanup(self.verify.stop)

    async def test_album_rule_preview_matches_poll_without_writing(self):
        self.repo.change_source(
            self.admin, self.source["id"], self.source["revision"],
            config={"rules": {"groups": [{"types": ["视频"], "keywords": ["光学"]}]},
                    "profile": {"mode": "caption"}},
        )
        source = self.repo.source(self.admin, self.source["id"])
        video = message(1, caption="", group=91)
        cover = message(2, original="cover.jpg", caption="光学实验演示", kind="photo", group=91)
        messages = [video, cover]
        self.listener.client.get_messages.return_value = list(reversed(messages))
        before = self.db._conn.total_changes
        result = await self.listener.test(self.admin, source["id"])
        self.assertEqual(self.db._conn.total_changes, before)
        preview = next(row for row in result if row[0] == video.id)
        self.assertTrue(preview[1])
        self.assertIn("光学实验", preview[3]["file_name"])

        async def history(*_, **__):
            for item in messages:
                yield item

        self.listener.client.iter_messages = history
        await self.listener.poll(source)
        plans = self.repo.pending(self.admin)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["payload"]["file_name"], preview[3]["file_name"])

    async def test_preview_keeps_own_episode_and_does_not_borrow_other_group(self):
        messages = [
            message(1, original="光学实验 第01讲.mp4", caption="", group=91),
            message(2, caption="光学实验 第02讲", group=91),
            message(3, caption="", group=92),
        ]
        self.listener.client.get_messages.return_value = messages
        result = await self.listener.test(self.admin, self.source["id"])
        self.assertIn("第01讲", result[0][3]["file_name"])
        self.assertNotIn("第02讲", result[0][3]["file_name"])
        self.assertNotIn("光学实验", result[2][3]["file_name"])

    async def test_poll_does_not_overwrite_pause_while_notifying(self):
        saved = {}

        async def pause(_):
            current = self.repo.source(self.admin, self.source["id"])
            self.repo.change_source(self.admin, current["id"], current["revision"], enabled=False)
            saved.update(self.repo.source(self.admin, current["id"]))

        async def history(*_, **__):
            yield message()

        self.owner._notify.side_effect = pause
        self.listener.client.iter_messages = history
        await self.listener.poll(self.source)
        self.assertEqual(self.repo.source(self.admin, self.source["id"]), saved)
        self.assertEqual(len(self.repo.pending(self.admin)), 1)

    async def test_poll_discards_page_fetched_before_configuration_change(self):
        saved = {}

        async def history(*_, **__):
            current = self.repo.source(self.admin, self.source["id"])
            self.repo.change_source(self.admin, current["id"], current["revision"],
                                    config=current["config"] | {"confirmation": False})
            saved.update(self.repo.source(self.admin, current["id"]))
            yield message()

        self.listener.client.iter_messages = history
        await self.listener.poll(self.source)
        self.assertEqual(self.repo.source(self.admin, self.source["id"]), saved)
        self.assertEqual(self.repo.pending(self.admin), [])
        self.assertEqual(self.db.counts(), {})

    async def test_download_rechecks_account_and_client_after_metadata(self):
        await self.listener.receive(self.source, message())
        plan = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, plan["id"], plan["revision"])
        original_client = self.listener.client
        original_client.get_messages.return_value = message()
        for change in ("account", "client"):
            with self.subTest(change=change):
                account.write_state(self.db, account=42, enabled=True)
                self.listener.client = original_client
                reader = CheckedSource(self.listener, task)
                msg = await reader.get_messages(-1001, ids=1)
                if change == "account":
                    account.write_state(self.db, account=43, enabled=True)
                else:
                    self.listener.client = NS(download_media=AsyncMock())
                with self.assertRaises(ListenerReadError):
                    await reader.download_media(msg, file="unused")
                self.listener.client.download_media.assert_not_awaited()
        original_client.download_media.assert_not_awaited()

    async def test_failed_metadata_recheck_revokes_previous_message(self):
        await self.listener.receive(self.source, message())
        plan = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, plan["id"], plan["revision"])
        reader = CheckedSource(self.listener, task)
        self.listener.client.get_messages.return_value = message()
        old_message = await reader.get_messages(-1001, ids=1)
        self.listener.client.get_messages.return_value = None
        with self.assertRaises(ListenerReadError):
            await reader.get_messages(-1001, ids=1)
        with self.assertRaises(ListenerReadError):
            await reader.download_media(old_message, file="unused")
        self.listener.client.download_media.assert_not_awaited()

    async def test_stale_poll_failure_does_not_pause_reconfigured_source(self):
        current = self.repo.source(self.admin, self.source["id"])
        self.repo.change_source(self.admin, current["id"], current["revision"],
                                config=current["config"] | {"confirmation": False})
        saved = self.repo.source(self.admin, current["id"])
        await self.listener.source_failure(self.source, ListenerReadError("synthetic refusal"))
        self.assertEqual(self.repo.source(self.admin, current["id"]), saved)

    async def test_metadata_request_cannot_cross_account_change(self):
        await self.listener.receive(self.source, message())
        plan = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, plan["id"], plan["revision"])
        client = self.listener.client

        async def change_account(*_args, **_kwargs):
            account.write_state(self.db, account=43, enabled=True)
            return message()

        client.get_messages.side_effect = change_account
        reader = CheckedSource(self.listener, task)
        with self.assertRaises(ListenerReadError):
            await reader.get_messages(-1001, ids=1)
        self.assertIsNone(reader.message)
        client.download_media.assert_not_awaited()

    async def test_configuration_changed_during_permission_check_is_retried(self):
        async def change(*_args):
            current = self.repo.source(self.admin, self.source["id"])
            self.repo.change_source(self.admin, current["id"], current["revision"],
                                    config=current["config"] | {"confirmation": False})

        self.listener._verified_until.clear()
        with patch("tg2cloud.listening.service.verified_chat", side_effect=change):
            await self.listener.receive(self.source, message())
        self.assertEqual(self.repo.pending(self.admin), [])
        self.assertEqual(self.db.counts(), {})
        self.assertEqual(self.repo.source(self.admin, self.source["id"])["cursor"], 0)
        await self.listener.receive(self.source, message())
        self.assertEqual(len(self.repo.pending(self.admin)), 0)
        self.assertEqual(sum(self.db.counts().values()), 1)

    async def test_repeat_receive_is_one_plan_and_no_early_download(self):
        m = message()
        await self.listener.receive(self.source, m)
        await self.listener.receive(self.source, m)
        self.assertEqual(len(self.repo.pending(self.admin)), 1)
        self.assertEqual(self.db.counts(), {})
        self.listener.client.download_media.assert_not_awaited()

    async def test_test_rules_has_no_side_effects_and_reports_duplicates(self):
        self.listener.client.get_messages.return_value = [message()]
        before = self.db._conn.total_changes
        result = await self.listener.test(self.admin, self.source["id"])
        self.assertTrue(result[0][1])
        self.assertEqual(before, self.db._conn.total_changes)
        await self.listener.receive(self.source, message())
        result = await self.listener.test(self.admin, self.source["id"])
        self.assertIn("重复", result[0][2])
        self.listener.client.download_media.assert_not_awaited()

    async def test_protection_flag_is_accepted_but_nonattachment_still_skips(self):
        await self.listener.receive(self.source, message(protected=True))
        m = message(2)
        m.media = None
        m.file = None
        await self.listener.receive(self.source, m)
        self.assertEqual(len(self.repo.pending(self.admin)), 1)
        self.assertEqual(self.repo.pending(self.admin)[0]["message"], 1)
        self.assertEqual(
            self.db._conn.execute("SELECT count(*) FROM listener_events").fetchone()[0],
            2,
        )

    async def test_cursor_progress_does_not_use_live_max_and_replays_dedupe(self):
        await self.listener.receive(self.source, message(3))

        async def history(*_, **__):
            for mid in (1, 2, 3):
                yield message(mid)

        self.listener.client.iter_messages = history
        await self.listener.poll(self.source)
        self.assertEqual(len(self.repo.pending(self.admin)), 3)
        self.assertEqual(self.repo.source(self.admin, self.source["id"])["cursor"], 3)
        await self.listener.poll(self.source)
        self.assertEqual(len(self.repo.pending(self.admin)), 3)

    async def test_receiving_failure_never_advances_cursor(self):
        async def history(*_, **__):
            yield message()

        self.listener.client.iter_messages = history
        with (
            patch.object(
                self.listener,
                "receive",
                new=AsyncMock(side_effect=OSError("synthetic persistence failure")),
            ),
            self.assertRaises(OSError),
        ):
            await self.listener.poll(self.source)
        self.assertEqual(self.repo.source(self.admin, self.source["id"])["cursor"], 0)

    async def test_paused_source_stops_receive_but_keeps_existing_plan(self):
        await self.listener.receive(self.source, message())
        self.repo.change_source(
            self.admin, self.source["id"], self.source["revision"], enabled=False
        )
        await self.listener.receive(self.source, message(2))
        self.assertEqual(len(self.repo.pending(self.admin)), 1)

    async def test_download_routes_by_identity_and_never_member_or_bot_fallback(self):
        await self.listener.receive(self.source, message())
        p = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, p["id"], p["revision"])
        self.listener.client.get_messages.return_value = message()
        reader = task_source(self.owner, task)
        self.assertIsInstance(reader, CheckedSource)
        msg = await reader.get_messages(-1001, ids=1)
        await reader.download_media(
            msg, file="synthetic", progress_callback=lambda *_: None
        )
        self.listener.client.download_media.assert_awaited_once()
        with self.assertRaises(ListenerReadError):
            task_source(self.owner, task | {"sender_id": 2})
        account.write_state(self.db, enabled=False)
        with self.assertRaises(ListenerReadError):
            await reader.get_messages(-1001, ids=1)

    async def test_changed_or_deleted_message_blocks_download(self):
        await self.listener.receive(self.source, message())
        p = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, p["id"], p["revision"])
        reader = CheckedSource(self.listener, task)
        no_media = message()
        no_media.media = None
        for msg in (None, message(2), no_media):
            self.listener.client.get_messages.return_value = msg
            with self.assertRaises(ListenerReadError):
                await reader.get_messages(-1001, ids=1)
        self.listener.client.download_media.assert_not_awaited()

    async def test_missing_session_connect_isolated_from_manual(self):
        self.listener.client = None
        with (
            patch(
                "tg2cloud.listening.account.session_lock",
                side_effect=ValueError("synthetic invalid session"),
            ),
            self.assertRaises(ValueError),
        ):
            await self.listener.connect()
        bot = NS(get_messages=AsyncMock())
        self.owner._source = bot
        self.assertIs(task_source(self.owner, {"read_identity": "bot"}), bot)

    async def test_rule_changes_only_new_plan_snapshots(self):
        await self.listener.receive(self.source, message())
        p = self.repo.pending(self.admin)[0]
        self.repo.change_source(
            self.admin,
            self.source["id"],
            self.source["revision"],
            config={"rules": {"groups": [{"types": ["图片"]}]}},
        )
        self.assertEqual(self.repo.get(self.admin, p["id"])["payload"], p["payload"])

        self.repo.edit(self.admin, p["id"], p["revision"], name="人工修正")
        self.assertEqual(
            self.repo.feedback(self.admin)[0]["rule_revision"],
            p["payload"]["source_revision"],
        )

    async def test_member_forged_callbacks_and_cross_user_tokens_are_denied(self):
        record = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": record["revision"]},
        )
        button = planning.token_button(
            self.owner, self.admin, "管理", ("source", self.source["id"])
        )
        callback = NS(
            sender_id=2,
            chat_id=2,
            data=callback_data(button),
            answer=AsyncMock(),
            edit=AsyncMock(),
        )
        with user_scope(2):
            self.assertTrue(await planning.callback(self.owner, callback))
        callback.answer.assert_awaited_once()
        self.assertTrue(callback.answer.call_args.kwargs["alert"])
        self.assertEqual(
            self.repo.source(self.admin, self.source["id"])["revision"],
            self.source["revision"],
        )
        home = self.owner._home_buttons(admin=False)
        self.assertNotIn(
            b"menu:listen", [callback_data(b) for row in home for b in row]
        )

    async def test_interactions_never_swallow_private_media(self):
        m = message(chat=self.admin)
        m.sender_id = self.admin
        e = event(self.admin, m)
        with user_scope(self.admin):
            await planning.ask(self.owner, e, ("add",), "来源")
        await self.owner._on_message(e)
        self.assertEqual(sum(self.db.counts().values()), 1)
        self.assertIn(self.admin, planning.interactions(self.owner))
        self.assertEqual(len(self.repo.sources(self.admin)), 1)

    async def test_default_manual_delivery_and_confirmation_are_separate(self):
        m = message(chat=self.admin)
        m.sender_id = self.admin
        e = event(self.admin, m)
        await self.owner._on_message(e)
        self.assertEqual(len(self.repo.pending(self.admin)), 0)
        self.repo.preferences(self.admin, {"confirmation": True})
        m = message(2, chat=self.admin)
        m.sender_id = self.admin
        await self.owner._on_message(event(self.admin, m))
        self.assertEqual(len(self.repo.pending(self.admin)), 1)
        self.assertEqual(sum(self.db.counts().values()), 1)

    async def test_token_single_use_and_expired_interaction_do_not_write(self):
        b = planning.token_button(
            self.owner, self.admin, "设置", ("confirmation", True)
        )
        e = NS(data=callback_data(b), answer=AsyncMock(), edit=AsyncMock())
        with user_scope(self.admin):
            await planning.callback(self.owner, e)
            await planning.callback(self.owner, e)
        self.assertTrue(e.answer.call_args.kwargs["alert"])
        planning.interactions(self.owner)[self.admin] = (time.monotonic() - 1, ("add",))
        with user_scope(self.admin):
            self.assertFalse(
                await planning.text(self.owner, event(self.admin), "@example")
            )

    async def test_listener_download_uses_existing_backend_pipeline(self):
        for backend in ("clouddrive2", "openlist"):
            for stream in (False, True):
                with self.subTest(backend=backend, stream=stream):
                    mid = (
                        100
                        + (10 if backend == "openlist" else 0)
                        + (1 if stream else 0)
                    )
                    m = message(mid)
                    await self.listener.receive(self.source, m)
                    p = next(
                        p for p in self.repo.pending(self.admin) if p["message"] == mid
                    )
                    task, _ = self.repo.submit(self.admin, p["id"], p["revision"])
                    self.db.update(
                        task["id"],
                        state="reserved",
                        transfer_mode="stream" if stream else "local",
                    )
                    self.owner.settings = replace(
                        self.settings,
                        storage_backend=backend,
                        destination_label="OpenList"
                        if backend == "openlist"
                        else "CloudDrive2",
                    )
                    self.owner.rclone = FakeRclone()
                    self.listener.client.get_messages.return_value = m

                    async def download(_message, *, file, progress_callback):
                        if isinstance(file, str):
                            Path(file).write_bytes(b"x" * 100)
                        else:
                            await file.write(b"x" * 100)
                        progress_callback(100, 100)
                        return file

                    self.listener.client.download_media = download
                    await self.owner._download_one(task["id"])
                    if not stream:
                        await self.owner._upload_one(task["id"])
                    final = self.db.get(task["id"])
                    self.assertEqual(final["state"], "completed")
                    self.assertEqual(final["read_identity"], "listener:42")
                    self.assertEqual(final["verification_method"], "size")
                    self.assertEqual(len(self.owner.rclone.files), 1)

    async def test_group_member_episode_not_borrowed_and_filter_is_per_file(self):
        a = message(1, original="光学实验 第01讲.mp4", caption="", group=99)
        b = message(
            2, original="光学实验 第02讲.mp4", caption="光学实验 第02讲", group=99
        )
        c = message(3, original="合成封面.jpg", caption="", group=99, kind="photo")

        async def history(*_, **__):
            for m in (a, b, c):
                yield m

        self.listener.client.iter_messages = history
        await self.listener.poll(self.source)
        plans = self.repo.pending(self.admin)
        self.assertEqual(len(plans), 2)
        self.assertIn("第01讲", plans[0]["payload"]["file_name"])
        self.assertIn("第02讲", plans[1]["payload"]["file_name"])
        self.assertEqual(
            self.db._conn.execute(
                "SELECT result FROM listener_events WHERE message=3"
            ).fetchone()[0],
            "类型、名称或关键词不符",
        )

    async def test_global_disable_releases_client_and_loop_exits_without_manual_restart(
        self,
    ):
        personal = NS(disconnect=AsyncMock())
        self.listener.client = personal
        account.write_state(self.db, enabled=False)
        await self.listener.connect()
        personal.disconnect.assert_awaited_once()
        self.assertIsNone(self.listener.client)

    async def test_chat_protection_and_membership_check_use_real_types(self):
        self.verify.stop()
        from telethon.tl import types

        c = NS(get_entity=AsyncMock(), get_permissions=AsyncMock())
        for e in (
            types.User(id=1),
            types.Channel(
                id=1,
                title="fixture",
                photo=types.ChatPhotoEmpty(),
                date=datetime.now(timezone.utc),
                left=True,
            ),
        ):
            c.get_entity.return_value = e
            with self.assertRaises(ListenerReadError):
                await verified_chat(c, "@fixture")
        c.get_entity.return_value = types.Channel(
            id=1,
            title="fixture",
            photo=types.ChatPhotoEmpty(),
            date=datetime.now(timezone.utc),
            left=False,
            noforwards=False,
        )
        from telethon.tl.custom.participantpermissions import ParticipantPermissions

        c.get_permissions.return_value = ParticipantPermissions(
            types.ChannelParticipant(user_id=42, date=datetime.now(timezone.utc)),
            chat=False,
        )
        for flag in (False, True, None):
            c.get_entity.return_value.noforwards = flag
            await verified_chat(c, "@fixture")
        self.assertEqual(c.get_permissions.await_count, 3)
        for left, denied in ((True, False), (False, True), (False, None)):
            member = types.ChannelParticipantBanned(
                peer=types.PeerUser(42),
                kicked_by=1,
                date=datetime.now(timezone.utc),
                banned_rights=types.ChatBannedRights(
                    until_date=None, view_messages=denied
                ),
                left=left,
            )
            c.get_permissions.return_value = ParticipantPermissions(member, chat=False)
            with self.assertRaises(ListenerReadError):
                await verified_chat(c, "@fixture")
        # A joined reader restricted from sending is supported; restriction != unreadability.
        member = types.ChannelParticipantBanned(
            peer=types.PeerUser(42),
            kicked_by=1,
            date=datetime.now(timezone.utc),
            banned_rights=types.ChatBannedRights(
                until_date=None, view_messages=False, send_messages=True
            ),
            left=False,
        )
        c.get_permissions.return_value = ParticipantPermissions(member, chat=False)
        await verified_chat(c, "@fixture")
        c.get_permissions.return_value = None
        with self.assertRaises(ListenerReadError):
            await verified_chat(c, "@fixture")

    async def test_manual_priority_and_backpressure(self):
        s = self.source
        cfg = s["config"] | {"confirmation": False}
        self.repo.change_source(self.admin, s["id"], s["revision"], config=cfg)
        await self.listener.receive(s, message(1))
        self.db.create_task(
            chat_id=self.admin,
            message_id=2,
            sender_id=self.admin,
            file_name="manual.mp4",
            file_size=1,
        )
        batch = next(self.owner._queued_batches(("queued",)))
        self.assertEqual(batch[0]["read_identity"], "bot")
        with (
            patch.object(self.db, "counts", return_value={"queued": 100}),
            self.assertRaises(ValueError),
        ):
            await self.listener.receive(s, message(3))
        self.assertFalse(
            self.db._conn.execute(
                "SELECT 1 FROM listener_events WHERE message=3"
            ).fetchone()
        )

    async def test_empty_listener_loop_keeps_enabled_account(self):
        self.repo.change_source(
            self.admin, self.source["id"], self.source["revision"], enabled=False
        )

        async def halt(_):
            self.owner._stop.set()

        self.listener.client = NS(disconnect=AsyncMock())
        with (
            patch.object(self.listener, "connect", new=AsyncMock(return_value=True)),
            patch(
                "tg2cloud.listening.service.asyncio.sleep",
                new=AsyncMock(side_effect=halt),
            ),
        ):
            await self.listener.run()
        self.assertTrue(account.state(self.db)["enabled"])

    async def test_flood_wait_persists_cooldown_and_does_not_advance(self):
        from telethon.errors import FloodWaitError

        before = time.time()
        result = await self.listener.source_failure(
            self.source, FloodWaitError(request=None, capture=45)
        )
        self.assertFalse(result)
        self.assertGreaterEqual(account.state(self.db)["cooldown_until"], before + 45)
        self.assertEqual(self.repo.source(self.admin, self.source["id"])["cursor"], 0)

    async def test_source_failure_categories_do_not_store_raw_error(self):
        await self.listener.source_failure(self.source, OSError("PRIVATE_RAW_MESSAGE"))
        row = self.repo.source(self.admin, self.source["id"])
        self.assertIn("网络", row["status"])
        self.assertNotIn("PRIVATE_RAW_MESSAGE", row["status"])
        self.assertTrue(row["enabled"])
        await self.listener.source_failure(
            self.source, ListenerReadError("private source")
        )
        self.assertFalse(self.repo.source(self.admin, self.source["id"])["enabled"])
        self.assertTrue(account.state(self.db)["enabled"])

    async def test_enable_callback_sets_current_cursor_and_keeps_private_scope(self):
        self.listener.client.get_messages.return_value = [message(50)]
        self.repo.change_source(
            self.admin, self.source["id"], self.source["revision"], enabled=False
        )
        source = self.repo.source(self.admin, self.source["id"])
        button = planning.token_button(
            self.owner,
            self.admin,
            "启用",
            ("source-enable", source["id"], source["revision"], True),
        )
        callback = NS(data=callback_data(button), answer=AsyncMock(), edit=AsyncMock())
        with user_scope(self.admin):
            await planning.callback(self.owner, callback)
        row = self.repo.source(self.admin, self.source["id"])
        self.assertTrue(row["enabled"])
        self.assertEqual(row["cursor"], 50)
        self.assertGreater(row["polled_at"], 0)

    async def test_long_offline_gap_is_visible_even_without_new_messages(self):
        self.db._conn.execute(
            "UPDATE listener_sources SET polled_at=?", (time.time() - 7 * 3600,)
        )

        async def history(*_, **__):
            if False:
                yield None

        self.listener.client.iter_messages = history
        await self.listener.poll(self.repo.source(self.admin, self.source["id"]))
        row = self.repo.source(self.admin, self.source["id"])
        self.assertTrue(row["gap"])
        self.assertIn("缺口", row["status"])

    async def test_declared_batch_name_and_directory_edits(self):
        self.repo.set_directory(self.admin, "课程", "课程/光学", [])
        a = message(
            11, chat=self.admin, original="旧主题 第01讲.mp4", caption="", group=77
        )
        b = message(
            12, chat=self.admin, original="旧主题 第02讲.mp4", caption="", group=77
        )
        naming1 = name_plan(a.file.name, "", "fallback.mp4")
        naming2 = name_plan(b.file.name, "", "fallback.mp4")
        p1 = self.repo.create(self.admin, rules.facts(a), naming1, batch="test-course")[
            0
        ]
        p2 = self.repo.create(self.admin, rules.facts(b), naming2, batch="test-course")[
            0
        ]
        with user_scope(self.admin):
            planning.interactions(self.owner)[self.admin] = (
                time.monotonic() + 300,
                (
                    "batch-name",
                    [(p1["id"], p1["revision"]), (p2["id"], p2["revision"])],
                ),
            )
            await planning.text(self.owner, event(self.admin), "新主题")
        self.assertIn(
            "第01讲", self.repo.get(self.admin, p1["id"])["payload"]["file_name"]
        )
        self.assertIn(
            "第02讲", self.repo.get(self.admin, p2["id"])["payload"]["file_name"]
        )

    async def test_batch_edit_rolls_back_all_members_when_one_revision_is_stale(self):
        m1, m2 = message(31, chat=self.admin), message(32, chat=self.admin)
        p1 = self.repo.create(
            self.admin,
            rules.facts(m1),
            name_plan("第一讲.mp4", "", "fallback.mp4"),
            batch="rollback-course",
        )[0]
        p2 = self.repo.create(
            self.admin,
            rules.facts(m2),
            name_plan("第二讲.mp4", "", "fallback.mp4"),
            batch="rollback-course",
        )[0]
        self.repo.edit(self.admin, p2["id"], p2["revision"], name="已经单独修改")
        with user_scope(self.admin):
            planning.interactions(self.owner)[self.admin] = (
                time.monotonic() + 300,
                (
                    "batch-name",
                    [(p1["id"], p1["revision"]), (p2["id"], p2["revision"])],
                ),
            )
            await planning.text(self.owner, event(self.admin), "新共同主题")
        self.assertEqual(
            self.repo.get(self.admin, p1["id"])["payload"]["file_name"],
            p1["payload"]["file_name"],
        )

    async def test_download_flood_wait_is_persisted_without_short_retry(self):
        from telethon.errors import FloodWaitError

        await self.listener.receive(self.source, message())
        plan = self.repo.pending(self.admin)[0]
        task, _ = self.repo.submit(self.admin, plan["id"], plan["revision"])
        self.listener.client.get_messages.return_value = message()
        reader = CheckedSource(self.listener, task)
        m = await reader.get_messages(-1001, ids=1)
        self.listener.client.download_media.side_effect = FloodWaitError(
            request=None, capture=90
        )
        with self.assertRaises(ListenerReadError):
            await reader.download_media(
                m, file="synthetic", progress_callback=lambda *_: None
            )
        self.assertGreater(account.state(self.db)["cooldown_until"], time.time() + 85)
        self.listener.client.download_media.assert_awaited_once()

    async def test_cooldown_queue_waits_and_manual_work_continues_then_resumes(self):
        await self.listener.receive(self.source, message())
        p = self.repo.pending(self.admin)[0]
        watched, _ = self.repo.submit(self.admin, p["id"], p["revision"])
        manual, _ = self.db.create_task(
            chat_id=self.admin,
            message_id=22,
            sender_id=self.admin,
            file_name="manual.mp4",
            file_size=1,
        )
        self.owner.destination_healthy = True
        self.owner._sample_fresh = lambda: True
        self.owner._destination_ready = lambda: True
        self.owner.snapshot = NS(filesystems=[], disk_free=100 * 1024**3)
        self.owner.download_window = NS(value=2)
        self.owner.upload_window = NS(value=2)
        self.owner._download_one = AsyncMock()
        account.write_state(self.db, cooldown_until=time.time() + 60)
        with patch(
            "tg2cloud.transfer.scheduler.shutil.disk_usage",
            return_value=NS(free=100 * 1024**3),
        ):
            await self.owner._start_downloads()
            await asyncio.gather(*list(self.owner.download_tasks.values()))
            self.assertEqual(self.db.get(watched["id"])["state"], "queued")
            self.assertIn("冷却", self.db.get(watched["id"])["wait_reason"])
            self.owner._download_one.assert_awaited_once_with(manual["id"])
            account.write_state(self.db, cooldown_until=0)
            await self.owner._start_downloads()
            await asyncio.gather(*list(self.owner.download_tasks.values()))
        self.assertEqual(self.db.get(watched["id"])["state"], "reserved")
        self.assertEqual(self.owner._download_one.await_count, 2)

    async def test_manual_compatible_custom_rules_apply_for_owner_and_family(self):
        record = self.db.family_users(self.admin)
        self.db.change_family_user(
            self.admin,
            {"action": "add", "id": 2, "name": "家人", "revision": record["revision"]},
        )
        for actor in (self.admin, 2):
            for confirmation in (False, True):
                mid = 501 + int(confirmation)
                with self.subTest(actor=actor, confirmation=confirmation):
                    self.repo.preferences(
                        actor,
                        {
                            "confirmation": confirmation,
                            "profile": {"prefixes": ["本期推荐"]},
                        },
                    )
                    m = message(
                        mid, chat=actor, original="本期推荐光学实验.mp4", caption=""
                    )
                    m.sender_id = actor
                    await self.owner._on_message(event(actor, m))
                    if confirmation:
                        plan = self.repo.pending(actor)[0]
                        self.assertEqual(plan["payload"]["file_name"], "光学实验.mp4")
                        self.assertEqual(plan["identity"], "bot")
                    else:
                        task = self.db.list_recent(sender_id=actor)[0]
                        self.assertEqual(task["file_name"], "光学实验.mp4")
                        self.assertEqual(task["read_identity"], "bot")
        self.listener.client.get_messages.assert_not_awaited()

    async def test_stop_during_permission_request_does_not_admit_attachment(self):
        async def stop(*_args):
            account.write_state(self.db, enabled=False, status="已停用")
        self.listener._verified_until.clear()
        with patch("tg2cloud.listening.service.verified_chat", side_effect=stop):
            await self.listener.receive(self.source, message(100))
        self.assertFalse(self.repo.pending(self.admin))
        self.assertEqual(self.db._conn.execute("SELECT count(*) FROM listener_events").fetchone()[0], 0)

    async def test_explicit_new_start_does_not_admit_older_inflight_updates(self):
        self.repo.change_source(
            self.admin,
            self.source["id"],
            self.source["revision"],
            enabled=True,
            cursor=100,
        )
        await self.listener.receive(self.source, message(2))
        self.assertFalse(self.repo.pending(self.admin))
        await self.listener.receive(self.source, message(101))
        self.assertEqual(self.repo.pending(self.admin)[0]["message"], 101)
        self.assertEqual(self.repo.source(self.admin, self.source["id"])["cursor"], 100)


class AccountPermissionsTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "fcntl and UID permissions require Linux")
    def test_session_lock_permissions_and_independent_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bot.session").write_bytes(b"existing-bot-session")
            settings = NS(data_dir=root)
            with account.session_lock(settings) as personal:
                self.assertEqual(personal.name, "personal")
                with self.assertRaises(BlockingIOError), account.session_lock(settings):
                    pass
                self.assertEqual(stat.S_IMODE(personal.parent.stat().st_mode), 0o700)
            self.assertEqual(
                (root / "bot.session").read_bytes(), b"existing-bot-session"
            )
            p = root / "listener/personal.session"
            p.write_bytes(b"synthetic")
            p.chmod(0o644)
            with self.assertRaises(ValueError), account.session_lock(settings):
                pass
            p.unlink()
            p.symlink_to(root / "bot.session")
            with self.assertRaises(ValueError), account.session_lock(settings):
                pass


if __name__ == "__main__":
    unittest.main()
