"""Caption-derived titles and non-destructive weekly dashboard counts."""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import events
from telethon.tl import types
from telethon.tl.types import MessageEntityHashtag, MessageEntityTextUrl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload_clouddrive2"))
from app.db import TaskDB
from app.naming import album_file_name, video_file_name
from test_scenarios import make_service, make_settings


class VideoNameTests(unittest.TestCase):
    def test_caption_filters_noise_but_preserves_episode_numbers(self):
        cases = [
            ("https://example.test/x\n#课程 #视频\n标题：家庭 NAS 部署 第01集", "家庭 NAS 部署 第01集.mp4"),
            ("📺 Ubuntu 24.04 安装教程 #Linux @example\n下载链接：https://example.test", "Ubuntu 24.04 安装教程.mp4"),
            ("关注频道 @example\n密码：secret\n文件大小：2GB\n1080P 60FPS\n**本地部署教程**", "本地部署教程.mp4"),
            ("[下载](https://example.test)\nwww.example.test\nt.me/example\n教程 第二集", "教程 第二集.mp4"),
            ("help@example.test\n192.168.1.2:8080/path\n教程 中文版", "教程 中文版.mp4"),
            ("标题：NAS 部署\u202e\u200b教程 #标签", "NAS 部署教程.mp4"),
            ("教程大全 | 欢迎关注 @channel", "教程大全.mp4"),
            ("ＣＯＮ\n视频标题：完整教程.mp4", "完整教程.mp4"),
        ]
        for caption, expected in cases:
            with self.subTest(caption=caption):
                self.assertEqual(video_file_name("123456.mp4", caption, "fallback.mp4"), expected)

    def test_original_titles_and_fallback_are_not_guessed(self):
        for name in ("第01集.mp4", "NAS 部署2026.mp4", "1984电影.mp4"):
            self.assertEqual(video_file_name(name, "另一标题", "fallback.mp4"), name)
        for caption in ("", "#主题 #视频", "https://example.test", "example.test?token=secret#here",
                        "192.168.1.1?token=secret", "点击这里", "1080P 60FPS", "123456"):
            self.assertEqual(video_file_name("12345.mp4", caption, "fallback.mp4"), "12345.mp4")
        for name in ("", "video_20261014_100000.mp4", "abcdef1234567890.mp4", "12345"):
            self.assertEqual(video_file_name(name, "家庭部署教程", "telegram-1.mp4"), "家庭部署教程.mp4")

    def test_hidden_links_and_hashtags_use_utf16_offsets_after_emoji(self):
        caption = "😀 点击入口\n正片部署教程 #技术"
        entities = [MessageEntityTextUrl(offset=3, length=4, url="https://example.test"),
                    MessageEntityHashtag(offset=15, length=3)]
        self.assertEqual(video_file_name("123.mp4", caption, "fallback.mp4", entities), "正片部署教程.mp4")
        caption = "😀 推荐资源\n正片部署教程"
        entities = [MessageEntityTextUrl(offset=3, length=4, url="https://example.test")]
        self.assertEqual(video_file_name("123.mp4", caption, "fallback.mp4", entities), "正片部署教程.mp4")

    def test_bounded_safe_filename_retains_real_extension(self):
        result = video_file_name("123.MKV", "标题：" + "很长的中文标题" * 100 + ": test?", "f.mp4")
        self.assertLessEqual(len(result.encode("utf-8")), 180)
        self.assertTrue(result.endswith(".MKV"))
        self.assertNotIn(":", result)
        self.assertNotIn("?", result)


class MetadataIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = make_settings(Path(self.temp.name))
        self.db = TaskDB(self.settings.data_dir / "metadata.db")
        self.addCleanup(lambda: self.db.close())
        self.service = make_service(self.settings, self.db)
        self.service.snapshot = None

    def album_message(self, ident, kind, caption="", *, group=123, name=None):
        return SimpleNamespace(
            id=ident, sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
            out=False, grouped_id=group, media=True, raw_text=caption, entities=[], reply=AsyncMock(),
            file=SimpleNamespace(size=4, name=name, ext=".mp4" if kind == "video" else ".jpg",
                                 mime_type="video/mp4" if kind == "video" else "image/jpeg"),
            video=True if kind == "video" else None,
            document=SimpleNamespace(id=ident) if kind == "video" else None,
            photo=SimpleNamespace(id=ident) if kind == "photo" else None,
        )

    def album_event(self, messages):
        return SimpleNamespace(sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
                               is_private=True, grouped_id=messages[0].grouped_id,
                               messages=messages, reply=AsyncMock())

    def single_event(self, message):
        return SimpleNamespace(sender_id=message.sender_id, chat_id=message.chat_id, is_private=True,
                               message=message, raw_text=message.raw_text, reply=message.reply)

    async def test_album_caption_on_photo_unifies_names_in_message_order(self):
        video = self.album_message(1, "video", name="原本有意义的视频.mp4")
        photo = self.album_message(2, "photo", "NAS 部署教程 #NAS https://example.test")
        second = self.album_message(3, "video", name="12345.mp4")
        await self.service._on_album(self.album_event([second, photo, video, photo]))
        self.assertEqual([self.db.get(i)["file_name"] for i in (1, 2, 3)],
                         ["NAS 部署教程-视频01.mp4", "NAS 部署教程-图片01.jpg", "NAS 部署教程-视频02.mp4"])
        self.assertEqual(self.db.get(1)["original_file_name"], "原本有意义的视频.mp4")
        for message in (video, photo, second):
            message.reply.assert_awaited_once()

    async def test_real_telethon_album_photo_caption_and_video_properties(self):
        stamp = datetime(2026, 10, 14, tzinfo=timezone.utc)
        document = types.Document(id=1, access_hash=1, file_reference=b"fixture", date=stamp,
                                  mime_type="video/mp4", size=4, dc_id=2,
                                  attributes=[types.DocumentAttributeVideo(duration=1, w=16, h=16),
                                              types.DocumentAttributeFilename("original.mp4")])
        photo = types.Photo(id=2, access_hash=2, file_reference=b"fixture", date=stamp, dc_id=2,
                            sizes=[types.PhotoSize(type="x", w=16, h=16, size=4)])
        messages = [types.Message(id=index, peer_id=types.PeerUser(self.settings.allowed_user_id),
                                 from_id=types.PeerUser(self.settings.allowed_user_id), date=stamp,
                                 message=caption, media=media, grouped_id=123, out=False)
                    for index, caption, media in (
                        (1, "", types.MessageMediaDocument(document=document)),
                        (2, "真实对象测试标题 #测试", types.MessageMediaPhoto(photo=photo)),
                    )]
        with patch.object(messages[0], "reply", new=AsyncMock()), patch.object(messages[1], "reply", new=AsyncMock()):
            await self.service._on_album(events.Album.Event(messages))
        self.assertEqual(self.db.get(1)["file_name"], "真实对象测试标题-视频01.mp4")
        self.assertEqual(self.db.get(2)["file_name"], "真实对象测试标题-图片01.jpg")

    async def test_album_and_new_message_race_only_register_and_ack_once(self):
        video = self.album_message(1, "video")
        photo = self.album_message(2, "photo", "媒体组测试标题")
        started, release = asyncio.Event(), asyncio.Event()

        async def wait_for_album(_seconds):
            started.set()
            await release.wait()

        with patch("app.main.asyncio.sleep", side_effect=wait_for_album):
            fallback = asyncio.create_task(self.service._on_message(self.single_event(video)))
            await started.wait()
            await asyncio.gather(self.service._on_album(self.album_event([video, photo])),
                                 self.service._on_album(self.album_event([video, photo])))
            release.set()
            await fallback
        self.assertEqual(len(self.db.list_recent()), 2)
        self.assertEqual(self.db.get(1)["file_name"], "媒体组测试标题-视频01.mp4")
        video.reply.assert_awaited_once()
        photo.reply.assert_awaited_once()

    async def test_grouped_single_video_falls_back_without_guessing(self):
        video = self.album_message(1, "video", name="123456.mp4")
        with patch("app.main.asyncio.sleep", new=AsyncMock()) as wait:
            await self.service._on_message(self.single_event(video))
        wait.assert_awaited_once_with(2)
        self.assertEqual(self.db.get(1)["file_name"], "123456.mp4")
        video.reply.assert_awaited_once()

    async def test_late_caption_does_not_rename_an_existing_task(self):
        video = self.album_message(1, "video", name="123456.mp4")
        with patch("app.main.asyncio.sleep", new=AsyncMock()):
            await self.service._on_message(self.single_event(video))
        photo = self.album_message(2, "photo", "迟到的标题")
        await self.service._on_album(self.album_event([video, photo]))
        self.assertEqual(self.db.get(1)["file_name"], "123456.mp4")
        self.assertEqual(self.db.get(2)["file_name"], "迟到的标题-图片01.jpg")
        video.reply.assert_awaited_once()

    async def test_album_without_title_keeps_originals_and_never_reuses_previous_group(self):
        first = [self.album_message(1, "video"), self.album_message(2, "photo", "第一组标题")]
        await self.service._on_album(self.album_event(first))
        second = [self.album_message(3, "video", name="9876.mp4", group=456),
                  self.album_message(4, "photo", "#标签 https://example.test", group=456)]
        await self.service._on_album(self.album_event(second))
        self.assertEqual(self.db.get(3)["file_name"], "9876.mp4")
        self.assertEqual(self.db.get(4)["file_name"], "telegram-4.jpg")

    async def test_album_rejects_foreign_chat_sender_group_and_outgoing(self):
        for field, value in (("chat_id", 999), ("sender_id", 999), ("grouped_id", 456), ("out", True)):
            with self.subTest(field=field):
                video = self.album_message(1, "video")
                photo = self.album_message(2, "photo", "不可信的标题")
                setattr(photo, field, value)
                await self.service._on_album(self.album_event([video, photo]))
                self.assertEqual(self.db.list_recent(), [])
        event = self.album_event([self.album_message(1, "video")])
        event.is_private = False
        await self.service._on_album(event)
        self.assertEqual(self.db.list_recent(), [])

    async def test_slow_or_failed_reply_does_not_prevent_other_members_persisting(self):
        video = self.album_message(1, "video")
        photo = self.album_message(2, "photo", "组标题")
        release = asyncio.Event()
        registered = asyncio.Event()

        async def slow_reply(*args, **kwargs):
            await release.wait()

        async def failed_reply(*args, **kwargs):
            registered.set()
            raise ConnectionError("synthetic offline reply failure")

        photo.reply.side_effect = failed_reply
        video.reply.side_effect = slow_reply
        delivery = asyncio.create_task(self.service._on_album(self.album_event([video, photo])))
        await asyncio.wait_for(registered.wait(), timeout=2)
        self.assertEqual(len(self.db.list_recent()), 2)
        release.set()
        await delivery

    def test_long_album_title_keeps_kind_counter_and_extension(self):
        for kind in ("视频", "图片"):
            name = album_file_name("中文长标题" * 100, kind, 12, ".mp4")
            self.assertLessEqual(len(name.encode("utf-8")), 180)
            self.assertTrue(name.endswith(f"-{kind}12.mp4"))

    async def test_ingestion_video_only_preserves_original_and_dedup(self):
        for index, mime in enumerate(("video/mp4", "application/pdf"), 1):
            event = SimpleNamespace(sender_id=self.settings.allowed_user_id, is_private=True,
                                    chat_id=self.settings.allowed_user_id, raw_text="部署教程 #tag https://example.test",
                                    reply=AsyncMock(), message=SimpleNamespace(id=index, media=True,
                                    document=SimpleNamespace(id=index), entities=[],
                                    file=SimpleNamespace(size=4, ext=".mp4", name="12345.mp4", mime_type=mime)))
            await self.service._on_message(event)
            task = self.db.get(index)
            self.assertEqual(task["file_name"], "部署教程.mp4" if index == 1 else "12345.mp4")
            self.assertEqual(task["original_file_name"], "12345.mp4")
            if index == 1:
                self.assertIn("原文件名称：12345.mp4", self.service._format_task(task, verbose=True))
            event.raw_text = "另一标题"
            await self.service._on_message(event)
            self.assertEqual(self.db.get(index)["file_name"], task["file_name"])
        self.assertEqual(len(self.db.list_recent()), 2)

    def make_task(self, ident=1):
        return self.db.create_task(chat_id=1, sender_id=1, message_id=ident,
                                   file_name="example.mp4", file_size=4)[0]

    def test_monday_reset_survives_restart_without_changing_history(self):
        monday = time.mktime((2026, 10, 12, 0, 0, 0, 0, 0, -1))
        old = self.make_task()
        with patch("app.db.time.time", return_value=monday - 1):
            self.db.update(old["id"], state="upload_failed_retained", error="old")
        before = self.db.get(old["id"])
        events = self.db.events(old["id"])
        self.assertEqual(self.db.weekly_failed_count(now=monday - 1), 1)
        self.assertEqual(self.db.weekly_failed_count(now=monday), 0)
        with patch("app.db.time.time", return_value=monday + 3600):
            self.db.update(old["id"], error="progress edit is not a fresh failure")
        self.db.close()
        self.db = TaskDB(self.settings.data_dir / "metadata.db")
        self.assertEqual(self.db.weekly_failed_count(now=monday + 7200), 0)
        self.assertEqual(self.db.get(old["id"])["state"], before["state"])
        self.assertEqual(self.db.events(old["id"]), events)
        self.assertEqual(self.db.counts()["upload_failed_retained"], 1)

    def test_retries_count_once_and_resolved_tasks_leave_display(self):
        monday = time.mktime((2026, 10, 12, 0, 0, 0, 0, 0, -1))
        task = self.make_task()
        with patch("app.db.time.time", return_value=monday):
            self.db.update(task["id"], state="download_failed")
            self.db.update(task["id"], state="queued")
            self.db.update(task["id"], state="download_failed")
        self.assertEqual(self.db.weekly_failed_count(now=monday), 1)
        self.db.update(task["id"], state="completed")
        self.assertEqual(self.db.weekly_failed_count(now=monday), 0)

    def test_year_boundary_and_legacy_failure_timestamp(self):
        task = self.make_task()
        sunday = time.mktime((2028, 12, 31, 23, 59, 59, 0, 0, -1))
        with patch("app.db.time.time", return_value=sunday):
            self.db.update(task["id"], state="download_failed")
        self.db._conn.execute("DELETE FROM task_events")  # synthetic legacy fixture only
        self.db.close()
        self.db = TaskDB(self.settings.data_dir / "metadata.db")
        self.assertEqual(self.db.weekly_failed_count(now=sunday), 1)
        monday = sunday + 1
        self.assertEqual(self.db.weekly_failed_count(now=monday), 0)
        with patch("app.db.time.time", return_value=monday):
            self.db.update(task["id"], error="updated legacy detail")
        self.assertEqual(self.db.weekly_failed_count(now=monday), 0)

    def test_home_style_has_no_new_week_label(self):
        self.service.db.weekly_failed_count = lambda: 3
        text = self.service._format_status()
        self.assertIn("❌ 3", text)
        self.assertNotIn("本周", text)

    def test_week_boundary_uses_local_calendar_not_a_fixed_seven_days(self):
        # A mocked local Wednesday; mktime must resolve Monday's timezone/DST.
        local = time.struct_time((2026, 10, 14, 12, 0, 0, 2, 287, 1))
        with patch("app.db.time.localtime", return_value=local), patch("app.db.time.mktime", return_value=100) as convert:
            self.assertEqual(self.db.weekly_failed_count(now=1000), 0)
            convert.assert_called_once_with((2026, 10, 12, 0, 0, 0, 0, 0, -1))


if __name__ == "__main__":
    unittest.main()
