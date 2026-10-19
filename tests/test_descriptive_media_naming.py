"""Synthetic captions for polluted originals, photo titles and cover/video pairs."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import events
from telethon.tl import types
from test_scenarios import FakeRclone, make_service, make_settings

from tg2cloud.domain.naming import album_file_name, video_file_name
from tg2cloud.persistence.sqlite import TaskDB


class PollutedOriginalTests(unittest.TestCase):
    def test_url_and_processing_original_uses_delivered_description(self):
        caption = "城市夜景长镜头记录雨后街道和沿途风景\n#旅行 #城市\nhttps://example.test"
        for original in ("processed_www.Example.test@城市夜景_9c2c.MP4",
                         "processed_www.Example.test@城市摄影教程_9c2c.mp4",
                         "www.example.test@sample_video.mp4", "example.com@sample_987.mp4",
                         "processed_123456.mp4"):
            with self.subTest(original=original):
                self.assertEqual(video_file_name(original, caption, "telegram-1.mp4"),
                                 "城市夜景长镜头记录雨后街道和沿途风景" + Path(original).suffix)

    def test_url_pollution_without_a_reliable_caption_keeps_original(self):
        original = "processed_www.Example.test@城市夜景_9c2c.mp4"
        for caption in ("", "#旅行 @sample https://example.test", "关注频道 @sample"):
            with self.subTest(caption=caption):
                self.assertEqual(video_file_name(original, caption, "telegram-1.mp4"), original)

    def test_semantic_originals_and_technical_domain_topics_stay_original(self):
        for original in ("城市夜景2026.mp4", "Processed Memories.mp4", "Node.js 教程.mp4",
                         "www.example.test 配置教程.mp4", "频道管理教程 @example.mp4"):
            with self.subTest(original=original):
                self.assertEqual(video_file_name(original, "另一个可读标题", "telegram-1.mp4"), original)

    def test_unnumbered_pair_names_still_filter_suffixes_paths_and_byte_lengths(self):
        for extension in (".jpg", ".MP4"):
            with self.subTest(extension=extension):
                result = album_file_name("城市/夜景.mp4", "图片", None, extension)
                self.assertEqual(result, "城市_夜景" + extension)
                result = album_file_name("中文长标题" * 200, "视频", None, extension)
                self.assertLessEqual(len(result.encode("utf-8")), 180)
                self.assertTrue(result.endswith(extension))
                self.assertNotIn("/", result)
                self.assertNotIn("\\", result)


class DescriptiveMediaIngestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings = make_settings(Path(temporary.name))
        self.db = TaskDB(self.settings.data_dir / "descriptions.db")
        self.addCleanup(self.db.close)
        self.service = make_service(self.settings, self.db)
        self.service.snapshot = None
        self.service.client = SimpleNamespace(get_messages=AsyncMock(side_effect=AssertionError("no source lookup")))

    def message(self, ident, kind, caption="", *, name=None, group=None):
        extension = Path(name).suffix if name else ".MP4" if kind == "video" else ".jpg"
        return SimpleNamespace(
            id=ident, sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
            grouped_id=group, out=False, media=True, raw_text=caption, entities=[], reply=AsyncMock(),
            video=kind == "video", photo=SimpleNamespace(id=ident) if kind == "photo" else None,
            document=SimpleNamespace(id=ident) if kind != "photo" else None,
            file=SimpleNamespace(size=4, name=name, ext=extension,
                                 mime_type="video/mp4" if kind == "video" else "image/jpeg"),
        )

    def event(self, message):
        return SimpleNamespace(sender_id=message.sender_id, chat_id=message.chat_id, is_private=True,
                               message=message, raw_text=message.raw_text, reply=message.reply)

    def album(self, messages):
        return SimpleNamespace(sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
                               is_private=True, grouped_id=messages[0].grouped_id, messages=messages,
                               reply=AsyncMock())

    async def test_single_photo_uses_its_own_caption_in_both_editions(self):
        for ident, backend in enumerate(("clouddrive2", "openlist"), 1):
            self.service.settings = replace(self.settings, storage_backend=backend)
            message = self.message(ident, "photo", "城市夜景旅行记录\n#城市 #旅行")
            await self.service._on_message(self.event(message))
            self.assertEqual(self.db.get(ident)["file_name"], "城市夜景旅行记录.jpg")
            self.assertEqual(self.db.get(ident)["original_file_name"], f"telegram-{ident}.jpg")
        self.service.client.get_messages.assert_not_awaited()

    async def test_descriptive_photo_original_stays_and_captionless_photo_does_not_guess(self):
        first = self.message(1, "photo", "另一个完整标题", name="已经命名的照片.jpg")
        second = self.message(2, "photo")
        await self.service._on_message(self.event(first))
        await self.service._on_message(self.event(second))
        self.assertEqual(self.db.get(1)["file_name"], "已经命名的照片.jpg")
        self.assertEqual(self.db.get(2)["file_name"], "telegram-2.jpg")

    async def test_photo_defaults_and_polluted_names_use_caption_but_not_a_hidden_link(self):
        for ident, original in enumerate(("123.jpg", "IMG_20261019_120000.jpg",
                                           "processed_www.example.test@sample.jpg"), 1):
            message = self.message(ident, "photo", "城市夜景旅行记录", name=original)
            await self.service._on_message(self.event(message))
            self.assertEqual(self.db.get(ident)["file_name"], "城市夜景旅行记录.jpg")
            self.assertEqual(self.db.get(ident)["original_file_name"], original)
        hidden = self.message(4, "photo", "不应使用的链接标题")
        hidden.entities = [types.MessageEntityTextUrl(offset=0, length=len(hidden.raw_text), url="https://example.test")]
        await self.service._on_message(self.event(hidden))
        self.assertEqual(self.db.get(4)["file_name"], "telegram-4.jpg")

    async def test_one_cover_and_one_video_share_base_without_kind_counters(self):
        for backend, offset in (("clouddrive2", 0), ("openlist", 2)):
            with self.subTest(backend=backend):
                self.service.settings = replace(self.settings, storage_backend=backend)
                video = self.message(offset + 1, "video", name="processed_www.example.test@sample.MP4", group=123 + offset)
                photo = self.message(offset + 2, "photo", "城市夜景旅行记录\n#旅行", group=123 + offset)
                await self.service._on_album(self.album([photo, video]))
                self.assertEqual(self.db.get(offset + 1)["file_name"], "城市夜景旅行记录.MP4")
                self.assertEqual(self.db.get(offset + 2)["file_name"], "城市夜景旅行记录.jpg")
                self.assertEqual(self.db.get(offset + 1)["original_file_name"], video.file.name)
                await self.service._on_album(self.album([video, photo]))
                self.assertEqual(len(self.db.list_recent()), offset + 2)

    async def test_larger_groups_keep_numbering_for_every_member(self):
        messages = [self.message(1, "video", group=123),
                    self.message(2, "photo", "城市夜景旅行记录", group=123),
                    self.message(3, "video", group=123)]
        await self.service._on_album(self.album(messages))
        self.assertEqual([self.db.get(i)["file_name"] for i in (1, 2, 3)],
                         ["城市夜景旅行记录-视频01.MP4", "城市夜景旅行记录-图片01.jpg", "城市夜景旅行记录-视频02.MP4"])

    async def test_pair_with_indistinguishable_or_invalid_suffixes_keeps_counters(self):
        for offset, extension in ((0, ".bin"), (2, ".bad/extension")):
            video = self.message(offset + 1, "video", group=123 + offset, name="123.bin")
            photo = self.message(offset + 2, "photo", "城市夜景旅行记录", group=123 + offset)
            video.file.ext = extension
            photo.file.ext = extension
            await self.service._on_album(self.album([video, photo]))
            self.assertEqual(self.db.get(offset + 1)["file_name"], "城市夜景旅行记录-视频01.bin")
            self.assertEqual(self.db.get(offset + 2)["file_name"], "城市夜景旅行记录-图片01.bin")

    async def test_pair_titles_do_not_propagate_to_unrelated_messages_or_old_tasks(self):
        video = self.message(1, "video", name="123.MP4")
        await self.service._on_message(self.event(video))
        photo = self.message(2, "photo", "城市夜景旅行记录")
        await self.service._on_message(self.event(photo))
        self.assertEqual(self.db.get(1)["file_name"], "123.MP4")
        self.assertEqual(self.db.get(2)["file_name"], "城市夜景旅行记录.jpg")
        photo.raw_text = "迟到的说明不能重命名已登记图片"
        await self.service._on_message(self.event(photo))
        self.assertEqual(self.db.get(2)["file_name"], "城市夜景旅行记录.jpg")
        self.assertEqual(len(self.db.list_recent()), 2)

    async def test_same_photo_title_keeps_existing_remote_conflict_reservations(self):
        self.service.rclone = FakeRclone()
        for ident in (1, 2):
            await self.service._on_message(self.event(self.message(ident, "photo", "城市夜景旅行记录")))
        first = await self.service._choose_remote_final(self.db.get(1)["file_name"], 1)
        self.db.update(1, remote_final_path=first)
        second = await self.service._choose_remote_final(self.db.get(2)["file_name"], 2)
        self.assertEqual(first, "城市夜景旅行记录.jpg")
        self.assertEqual(second, "城市夜景旅行记录 (task-2).jpg")

    async def test_photo_naming_does_not_expand_sender_or_private_chat_authorization(self):
        message = self.message(1, "photo", "城市夜景旅行记录")
        message.sender_id += 1
        await self.service._on_message(self.event(message))
        message = self.message(2, "photo", "城市夜景旅行记录")
        event = self.event(message)
        event.is_private = False
        await self.service._on_message(event)
        self.assertEqual(self.db.list_recent(), [])

    async def test_real_telethon_photo_and_video_pair_share_the_received_caption(self):
        stamp = datetime(2026, 10, 19, tzinfo=timezone.utc)
        document = types.Document(id=1, access_hash=1, file_reference=b"offline", date=stamp,
                                  mime_type="video/mp4", size=4, dc_id=2,
                                  attributes=[types.DocumentAttributeVideo(duration=1, w=16, h=16),
                                              types.DocumentAttributeFilename("processed_www.example.test@sample.mp4")])
        photo = types.Photo(id=2, access_hash=2, file_reference=b"offline", date=stamp, dc_id=2,
                            sizes=[types.PhotoSize(type="x", w=16, h=16, size=4)])
        messages = [types.Message(id=ident, peer_id=types.PeerUser(self.settings.allowed_user_id),
                                 from_id=types.PeerUser(self.settings.allowed_user_id), date=stamp,
                                 message=caption, media=media, grouped_id=123, out=False)
                    for ident, caption, media in ((1, "", types.MessageMediaDocument(document=document)),
                                                  (2, "城市夜景旅行记录 #旅行", types.MessageMediaPhoto(photo=photo)))]
        with patch.object(messages[0], "reply", new=AsyncMock()), patch.object(messages[1], "reply", new=AsyncMock()):
            await self.service._on_album(events.Album.Event(messages))
        self.assertEqual(self.db.get(1)["file_name"], "城市夜景旅行记录.mp4")
        self.assertEqual(self.db.get(2)["file_name"], "城市夜景旅行记录.jpg")
        self.service.client.get_messages.assert_not_awaited()

    async def test_photo_extraction_failure_keeps_original_and_does_not_log_caption(self):
        message = self.message(1, "photo", "只供离线测试的说明")
        with patch("tg2cloud.telegram.handlers.media_file_name", side_effect=ValueError("synthetic-private")):
            await self.service._on_message(self.event(message))
        self.assertEqual(self.db.get(1)["file_name"], "telegram-1.jpg")
        self.assertEqual(self.db.get(1)["state"], "queued")
        self.assertNotIn(message.raw_text, str(self.service.log.mock_calls))
        self.assertNotIn("synthetic-private", str(self.service.log.mock_calls))


if __name__ == "__main__":
    unittest.main()
