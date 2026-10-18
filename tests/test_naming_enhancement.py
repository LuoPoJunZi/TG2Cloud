"""Offline, additive regressions for caption quality and ingestion fallbacks."""
from __future__ import annotations

import asyncio
import tempfile
import unicodedata
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import events
from telethon.tl import types
from test_scenarios import FakeRclone, make_service, make_settings

from tg2cloud.domain.naming import (
    album_file_name,
    caption_candidate,
    caption_title,
    safe_file_name,
    video_file_name,
)
from tg2cloud.persistence.sqlite import TaskDB


class MultilingualNamingTests(unittest.TestCase):
    def test_requested_multiline_chinese_and_japanese_examples(self):
        self.assertEqual(video_file_name("89457236812.mp4", "三体：黑暗森林 第12集\n高清视频完整版\n@movie_share\nwww.example.com", "f.mp4"),
                         "三体_黑暗森林 第12集.mp4")
        self.assertEqual(video_file_name("Ab83Kd91X.mp4", "君の名は。 君の名は\n1080P\n资源分享 @abc123", "f.mp4"),
                         "君の名は.mp4")

    def test_unicode_titles_no_script_preference(self):
        titles = ["三体 第12集", "黑暗森林 第十二集", "你的名字 君の名は", "오늘의 여행", "The Last Journey",
                  "2026年东京旅行", "One Piece 第1080集", "臺灣環島旅行", "Été à Montréal", "Straße über München",
                  "Путешествие домой", "رحلة إلى الوطن", "यात्रा की कहानी", "Καλοκαιρινό ταξίδι"]
        for title in titles:
            with self.subTest(title=title):
                self.assertEqual(video_file_name("A8k3P91zX7.mp4", title + "\n@channel_name\n1080P", "f.mp4"), title + ".mp4")
        # Explicit titles win across scripts, not according to ASCII/CJK identity.
        for title, background in (("The Last Journey", "这是另一段中文背景介绍而不是影片名称"),
                                  ("오늘의 여행", "A long descriptive English background sentence, not the title")):
            self.assertEqual(caption_title(f"{background}\n\nTitle: {title}"), title)

    def test_random_names_are_weak_but_meaningful_originals_keep_priority(self):
        for name in ("Ab83Kd91X.mp4", "A8k3P91zX7.mp4", "a8k3p91zx7.mp4", "aBqCdEfGhIjKlMnOpQrS.mp4", "_____ABC_____.mp4"):
            with self.subTest(name=name):
                self.assertEqual(video_file_name(name, "오늘의 여행", "f.mp4"), "오늘의 여행.mp4")
        for name in ("The Last Journey.mp4", "Python3v12.mp4", "ISO9001v2.mp4", "OnePiece1080.mp4",
                     "Microsoft.mp4", "community.mp4", "S01E03v2.mp4", "C++ 2026.mp4", "Déjà Vu.mp4", "오늘의 여행.mp4",
                     "你的名字 君の名は.mp4", "2026年东京旅行.mp4", "La La Land.mp4", "ItIsSoFunToBeMeNow.mp4"):
            with self.subTest(name=name):
                self.assertEqual(video_file_name(name, "不应该覆盖原有名称", "f.mp4"), name)

    def test_domains_accounts_tags_and_ad_tails_do_not_replace_title(self):
        addresses = ["example.com", "www.example.com", "https://example.com/x?a=1", "http://example.com",
                     "abc.com@", "abc.com@channel", "*.com", "*.com@", "t.me/channel", "telegram.me/channel",
                     "example.de", "example.xyz", "example.cloud", "example.co.uk", "example.photography",
                     "示例.中国", "пример.рф", "example.xn--p1ai", "help@example.test", "@abc123", "#主题",
                     "192.168.1.2:8080/path", "https://[::1]/x"]
        for address in addresses:
            with self.subTest(address=address):
                self.assertEqual(caption_title(address + "\n标题：远方的旅程\n" + address), "远方的旅程")
                self.assertEqual(caption_title(address), "")
        for tail in ("@movie_share", "www.example.com", "abc.com@channel", "example.photography", "#旅行 #纪录片", "| 更多资源请关注 @sample",
                     "| 欢迎订阅 @sample", "| follow us @sample", "资源分享 @sample"):
            self.assertEqual(caption_title("旅途纪事 " + tail), "旅途纪事")
        self.assertEqual(caption_title("旅途纪事@movie_share"), "旅途纪事")
        self.assertEqual(caption_title("The Last Journey@movie_share"), "The Last Journey")

    def test_promotions_quality_and_random_caption_lines_are_rejected(self):
        noise = ["点击链接获取更多", "加入频道", "关注获取更新", "资源来自某某频道", "欢迎订阅", "广告合作",
                 "备用网址", "資源來源：@abc", "關注頻道 @abc", "更多资源请关注@xxxx", "更多資源請關注@xxxx",
                 "精选资源关注TG频道@sample_G01_S01", "subscribe to our channel", "follow us @example",
                 "チャンネル登録", "구독 해주세요", "###@@@###", "_____ABC_____", "894736281936", "A8k3P91zX7",
                 "1080P 60FPS", "4K HDR HEVC", "高清视频完整版", "文件大小：2GB"]
        for line in noise:
            with self.subTest(line=line):
                self.assertEqual(caption_title(line), "")
                self.assertEqual(caption_title(line + "\n标题：春日旅行\n" + line), "春日旅行")
        self.assertEqual(caption_title("_____ABC_____\n一段关于海边旅行的完整实拍记录"), "一段关于海边旅行的完整实拍记录")

    def test_normal_words_symbols_and_metadata_numbers_are_not_overfiltered(self):
        for title in ("Follow the Stars", "Join the Journey", "The Comedy Show", "Community Stories",
                      "Node.js 入门教程", "ASP.NET Core 教程", "Ubuntu 24.04 安装教程", "C# 基础教程",
                      "高清时代", "HDR 摄影教程", "花样年华 2000", "Bye Bye", "AC/DC Live 2026"):
            with self.subTest(title=title):
                self.assertEqual(video_file_name("123.mp4", title, "f.mp4"), safe_file_name(title + ".mp4", "f.mp4"))

    def test_explicit_numeric_titles_episode_year_and_versions(self):
        for caption, expected in (("标题：1984", "1984"), ("《1917》", "1917"), ("Title: 2001", "2001"),
                                  ("作品名：1917", "1917"), ("標題：黑暗森林 第12集", "黑暗森林 第12集"),
                                  ("제목: 오늘의 여행", "오늘의 여행"), ("題名：君の名は", "君の名は"),
                                  ("One Piece S01E03", "One Piece S01E03"), ("Python 3.12 v1.2.0", "Python 3.12 v1.2.0")):
            with self.subTest(caption=caption):
                self.assertEqual(caption_title(caption), expected)
        self.assertEqual(caption_title("123456"), "")

    def test_candidate_selection_separates_title_from_unrelated_lines(self):
        caption = "资源分享\n894736281936\nA8k3P91zX7\n三体 第12集\n一段比标题更长的补充说明介绍了拍摄背景和摄像设备\n4K HDR\n加入频道 @example"
        self.assertEqual(caption_title(caption), "三体 第12集")
        self.assertGreater(caption_candidate("标题：旅行")[1], caption_candidate("一些更长但没有明确标题的背景描述")[1])
        self.assertEqual(caption_title("君の名は。 君の名は"), "君の名は")
        self.assertEqual(caption_title("The Last Journey The Last Journey"), "The Last Journey")

    def test_no_useful_caption_preserves_old_fallback(self):
        for caption in ("", "@channel #标签", "www.example.com", "广告合作\n1080P", "A8k3P91zX7\n123456"):
            for original in ("12345.mp4", "Ab83Kd91X.mp4", "", "video_20261018_1900.mp4"):
                with self.subTest(caption=caption, original=original):
                    self.assertEqual(video_file_name(original, caption, "telegram-1.mp4"),
                                     safe_file_name(original, "telegram-1.mp4"))

    def test_true_extensions_and_existing_album_override(self):
        for extension in (".MKV", ".mov", ".webm", ".mp4"):
            self.assertEqual(video_file_name("123" + extension, "标题：旅程.exe", "f.bin"), "旅程" + extension)
        self.assertEqual(video_file_name("12345", "标题：旅程.mp4", "telegram-1.mkv"), "旅程.mkv")
        self.assertEqual(video_file_name("", "标题：旅程.mp4", "telegram-1.webm"), "旅程.webm")
        self.assertEqual(video_file_name("123.mp4", "君の名は.mp4", "f.mp4"), "君の名は.mp4")
        for caption in ("标题：Movie/..", "标题：Movie/.", "标题：Movie/.exe"):
            self.assertEqual(video_file_name("123.MKV", caption, "f.mp4"), "123.MKV")
        self.assertEqual(album_file_name("旅程", "图片", 1, ".jpg"), "旅程-图片01.jpg")

    def test_utf8_normalization_unsafe_paths_and_invalid_unicode(self):
        self.assertEqual(safe_file_name("Cafe\u0301.mp4", "f.mp4"), "Café.mp4")
        for name in ("../../outside\x00.mp4", "..\\..\\outside.mp4", "\ud800\u202efilm.mp4", "\x85\x9bfilm.mp4", "../", "\x00"):
            result = safe_file_name(name, "../fallback.mp4")
            self.assertNotIn("/", result)
            self.assertNotIn("\\", result)
            self.assertTrue(result)
            result.encode("utf-8")
            self.assertFalse(any(unicodedata.category(c).startswith("C") for c in result))
        self.assertEqual(video_file_name("123.mp4", "标题：../../安全视频\u202e\ud800.exe", "f.mp4"), "安全视频.mp4")
        result = video_file_name("123.MKV", "标题：" + "很长中文标题" * 5000, "f.mp4")
        self.assertLessEqual(len(result.encode("utf-8")), 180)
        self.assertTrue(result.endswith(".MKV"))

    def test_long_prose_uses_clause_or_word_boundary(self):
        caption = "标题：海边旅行" + "清晨沿着海岸行走" * 3 + "，" + "随后介绍交通与补给细节" * 20
        name = video_file_name("123.mp4", caption, "f.mp4")
        self.assertNotIn("随后", name)
        self.assertLessEqual(len(name.encode("utf-8")), 180)

    def test_bounded_input_and_malformed_entity_metadata(self):
        entities = [object(), SimpleNamespace(offset="bad", length=1), SimpleNamespace(offset=-20, length=-1)]
        self.assertEqual(caption_title("标题：安全标题", entities), "安全标题")
        self.assertEqual(caption_title("标题：安全标题", 1), "安全标题")
        self.assertEqual(caption_title(None), "")
        self.assertEqual(caption_title("@channel\n" * 64 + "标题：不在扫描范围"), "")
        # Repeated metadata used to be vulnerable to ambiguous regex alternatives.
        self.assertEqual(caption_title("完整版" * 2000 + "X\n标题：安全标题"), "安全标题")


class CaptionIngestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = make_settings(Path(self.temp.name))
        self.db = TaskDB(self.settings.data_dir / "names.db")
        self.addCleanup(self.db.close)
        self.service = make_service(self.settings, self.db)
        self.service.snapshot = None

    def message(self, ident=1, caption="", *, name="Ab83Kd91X.mp4", group=None, mime="video/mp4"):
        return SimpleNamespace(id=ident, sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
                               out=False, grouped_id=group, media=True, raw_text=caption, entities=[], reply=AsyncMock(),
                               video=None, photo=None, document=SimpleNamespace(id=ident),
                               file=SimpleNamespace(size=4, name=name, ext=Path(name).suffix, mime_type=mime))

    def event(self, message, raw_text=None):
        return SimpleNamespace(sender_id=message.sender_id, chat_id=message.chat_id, is_private=True,
                               message=message, raw_text=message.raw_text if raw_text is None else raw_text,
                               reply=message.reply)

    def album(self, messages):
        return SimpleNamespace(sender_id=self.settings.allowed_user_id, chat_id=self.settings.allowed_user_id,
                               is_private=True, grouped_id=messages[0].grouped_id, messages=messages, reply=AsyncMock())

    async def test_event_missing_caption_uses_actual_same_message_text(self):
        message = self.message(caption="三体 第12集\n1080P")
        await self.service._on_message(self.event(message, raw_text=""))
        self.assertEqual(self.db.get(1)["file_name"], "三体 第12集.mp4")
        message = self.message(2)
        message.message = "오늘의 여행"
        await self.service._on_message(self.event(message, raw_text=""))
        self.assertEqual(self.db.get(2)["file_name"], "오늘의 여행.mp4")

    async def test_real_forwarded_telethon_media_no_network_lookup(self):
        from datetime import datetime, timezone

        document = types.Document(id=1, access_hash=1, file_reference=b"fixture", date=datetime.now(timezone.utc),
                                  mime_type="video/mp4", size=4, dc_id=2,
                                  attributes=[types.DocumentAttributeVideo(duration=1, w=16, h=16),
                                              types.DocumentAttributeFilename("Ab83Kd91X.mp4")])
        message = types.Message(id=1, peer_id=types.PeerUser(self.settings.allowed_user_id),
                                from_id=types.PeerUser(self.settings.allowed_user_id), date=datetime.now(timezone.utc),
                                message="君の名は。 君の名は\n1080P", media=types.MessageMediaDocument(document=document),
                                fwd_from=types.MessageFwdHeader(date=datetime.now(timezone.utc), from_name="推广频道名称"))
        self.service.client = SimpleNamespace(get_messages=AsyncMock(side_effect=AssertionError("must not fetch")))
        with patch.object(message, "reply", new=AsyncMock()):
            await self.service._on_message(events.NewMessage.Event(message))
        self.assertEqual(self.db.get(1)["file_name"], "君の名は.mp4")
        self.service.client.get_messages.assert_not_awaited()

    async def test_group_uses_quality_not_longest_and_custom_names_still_win(self):
        first = self.message(1, "较长但没有明确影片标题的一段背景资料，不能覆盖明确标题", group=123)
        second = self.message(2, "标题：春日旅行", name="有意义的原名.mp4", group=123)
        await self.service._on_album(self.album([first, second]))
        self.assertEqual(self.db.get(1)["file_name"], "春日旅行-视频01.mp4")
        self.assertEqual(self.db.get(2)["file_name"], "春日旅行-视频02.mp4")
        message = self.message(3, "标题：不能覆盖指定名称")
        await self.service._on_message(self.event(message), album_name="已指定名称-视频03.mp4")
        self.assertEqual(self.db.get(3)["file_name"], "已指定名称-视频03.mp4")

    async def test_optional_title_failure_still_persists_safe_original_without_leaking_text(self):
        message = self.message(caption="仅作为测试的私密说明")
        with patch("tg2cloud.telegram.handlers.video_file_name", side_effect=ValueError("private-metadata")):
            await self.service._on_message(self.event(message))
        self.assertEqual(self.db.get(1)["file_name"], "Ab83Kd91X.mp4")
        self.assertEqual(self.db.get(1)["state"], "queued")
        self.assertNotIn("private-metadata", str(self.service.log.mock_calls))
        self.assertNotIn(message.raw_text, str(self.service.log.mock_calls))

    async def test_optional_album_failure_keeps_every_task(self):
        messages = [self.message(1, "说明", group=123), self.message(2, "第二条", group=123)]
        with patch("tg2cloud.telegram.handlers.caption_candidate", side_effect=RuntimeError("private")), \
             patch("tg2cloud.telegram.handlers.video_file_name", side_effect=RuntimeError("private")):
            await self.service._on_album(self.album(messages))
        self.assertEqual(len(self.db.list_recent()), 2)
        self.assertTrue(all(task["file_name"] == "Ab83Kd91X.mp4" for task in self.db.list_recent()))

    async def test_documents_audio_and_single_photos_keep_existing_names(self):
        for ident, name, mime in ((1, "123.pdf", "application/pdf"), (2, "123.mp3", "audio/mpeg"),
                                   (3, "123.jpg", "image/jpeg"), (4, "123.zip", "application/zip")):
            await self.service._on_message(self.event(self.message(ident, "标题：不覆盖非视频", name=name, mime=mime)))
            self.assertEqual(self.db.get(ident)["file_name"], name)

    async def test_same_generated_title_keeps_original_conflict_and_dedup_rules(self):
        self.service.rclone = FakeRclone()
        messages = [self.message(ident, "标题：春日旅行") for ident in (1, 2)]
        await asyncio.gather(*(self.service._on_message(self.event(message)) for message in messages))
        self.assertEqual([task["file_name"] for task in self.db.list_recent()], ["春日旅行.mp4"] * 2)
        first = await self.service._choose_remote_final(self.db.get(1)["file_name"], 1)
        self.db.update(1, remote_final_path=first)
        second = await self.service._choose_remote_final(self.db.get(2)["file_name"], 2)
        self.assertEqual(first, "春日旅行.mp4")
        self.assertEqual(second, "春日旅行 (task-2).mp4")
        # Existing remote objects as well as SQLite claims still protect names.
        self.service.rclone.files[second] = b"data"
        self.assertEqual(await self.service._choose_remote_final("春日旅行.mp4", 2), "春日旅行 (task-2-2).mp4")
        await self.service._on_message(self.event(messages[0]))
        self.assertEqual(len(self.db.list_recent()), 2)
        self.assertEqual(self.db.get(1)["original_file_name"], "Ab83Kd91X.mp4")

    async def test_ingest_download_restart_and_upload_in_both_editions(self):
        async def download(_message, *, file, progress_callback):
            Path(file).write_bytes(b"data")
            progress_callback(4, 4)
            return file

        cases = [("clouddrive2", "三体 第12集", "Ab83Kd91X.mp4", "三体 第12集.mp4"),
                 ("openlist", "오늘의 여행", "A8k3P91zX7.mp4", "오늘의 여행.mp4"),
                 ("clouddrive2", "", "12345.mp4", "12345.mp4"),
                 ("openlist", "", "67890.mp4", "67890.mp4")]
        for ident, (backend, caption, original, expected) in enumerate(cases, 1):
            with self.subTest(backend=backend, caption=caption):
                settings = replace(self.settings, storage_backend=backend,
                                   destination_label="OpenList" if backend == "openlist" else "CloudDrive2")
                self.service.settings = settings
                await self.service._on_message(self.event(self.message(ident, caption, name=original)))
                self.db.update(ident, state="reserved")
                self.service.client = SimpleNamespace(get_messages=AsyncMock(return_value=SimpleNamespace(media=True)),
                                                      download_media=AsyncMock(side_effect=download))
                self.service._notify = AsyncMock()
                await self.service._download_one(ident)
                downloaded = self.db.get(ident)
                self.assertEqual(downloaded["state"], "waiting_upload")
                local_path = Path(downloaded["local_path"])
                self.assertTrue(local_path.name.endswith(expected))
                # Reopen the persisted DB and assemble a new service, as after a
                # restart. No caption re-extraction or filename migration occurs.
                self.db.close()
                self.db = TaskDB(settings.data_dir / "names.db")
                self.addCleanup(self.db.close)
                self.service = make_service(settings, self.db)
                self.service.rclone = FakeRclone()
                self.service.rclone.move = AsyncMock(wraps=self.service.rclone.move)
                self.service._notify = AsyncMock()
                await self.service._upload_one(ident)
                completed = self.db.get(ident)
                self.assertEqual(completed["state"], "completed")
                self.assertEqual(completed["file_name"], expected)
                self.assertEqual(completed["original_file_name"], original)
                self.assertEqual(completed["verification_method"], "size")
                self.assertEqual(self.service.rclone.files, {expected: b"data"})
                self.assertFalse(local_path.exists())
                self.assertEqual(self.service.rclone.move.await_count, int(backend == "clouddrive2"))


if __name__ == "__main__":
    unittest.main()
