"""Synthetic filenames only; never mutate existing saved files."""
import unittest

from tg2cloud.domain.naming import caption_title, explain_media_name, media_file_name
from tg2cloud.domain.planning import name_plan


class ContactAffixTests(unittest.TestCase):
    def test_unicode_domain_disguises_at_both_edges_and_all_media(self):
        for token in ("489155_com@示例账号", "489155.com@sample", "example_net@示例账号", "sample.io@Été"):
            for suffix in (".mp4", ".MP4", ".jpg", ".mkv", ".pdf", ".mp3"):
                for original in (token + "【作品】旅行 第12集" + suffix,
                                 "【作品】旅行 第12集_" + token + suffix,
                                 token + "_【作品】旅行 第12集_" + token + suffix,
                                 "[" + token + "]【作品】旅行 第12集" + suffix):
                    with self.subTest(token=token, suffix=suffix, original=original):
                        expected = "【作品】旅行 第12集" + suffix
                        self.assertEqual(media_file_name(original, "", "fallback" + suffix), expected)
                        self.assertEqual(name_plan(original, "", "fallback" + suffix)["file_name"], expected)

    def test_descriptive_remaining_name_wins_and_all_promotion_uses_caption_or_fallback(self):
        self.assertEqual(media_file_name("489155_com@sample_【电影】旅行.mp4", "无关说明", "fallback.mp4"),
                         "【电影】旅行.mp4")
        name = "489155_com@示例账号.mp4"
        self.assertEqual(media_file_name(name, "城市旅行", "fallback.mp4"), "城市旅行.mp4")
        self.assertEqual(media_file_name(name, "", "fallback.mp4"), "fallback.mp4")
        result = explain_media_name("489155_com@示例账号【作品】旅行.mp4", "", "fallback.mp4")
        self.assertEqual(result["reason"], "promotional_affixes_removed")

    def test_normal_titles_episode_year_technical_names_and_middle_text_survive(self):
        for name in ("2026年东京旅行.mp4", "S02E12.mp4", "The Last Journey.mp4", "Node.js 使用教程.mp4",
                     "ASP.NET Guide.mp4", "comedy_2026.mp4", "关于 sample.com@example 账号的教程.mp4",
                     "旅行_489155_com@示例账号_主题.mp4"):
            with self.subTest(name=name):
                self.assertEqual(media_file_name(name, "", "fallback.mp4"), name)

    def test_caption_edge_contacts_do_not_leak_into_caption_or_album_title(self):
        for caption in ("489155_com@示例账号 城市旅行", "城市旅行 489155_com@示例账号",
                        "489155.com@sample 城市旅行"):
            with self.subTest(caption=caption):
                self.assertEqual(caption_title(caption), "城市旅行")
                self.assertEqual(media_file_name("123.mp4", caption, "f.mp4"), "城市旅行.mp4")

    def test_custom_prefix_cleaning_does_not_reintroduce_half_a_contact(self):
        name = "489155_com@示例账号【作品】城市旅行.mp4"
        result = name_plan(name, "", "fallback.mp4", options={"prefixes": ["489155_", "【作品】"]})
        self.assertEqual(result["file_name"], "城市旅行.mp4")

    def test_original_cleanup_preserves_unchanged_caption_entity_mask(self):
        from telethon.tl.types import MessageEntityTextUrl
        promotion = "这是一个不应该成为文件名的频道推广文字"
        caption = promotion + "\n城市旅行"
        entities = [MessageEntityTextUrl(offset=0, length=len(promotion), url="https://example.test/promo")]
        for original, options in (("489155_com@sample.mp4", None),
                                  ("PREFIX-123.mp4", {"prefixes": ["PREFIX-"]})):
            with self.subTest(original=original):
                result = name_plan(original, caption, "fallback.mp4", entities=entities, options=options)
                self.assertEqual(result["file_name"], "城市旅行.mp4")

    def test_safe_suffix_and_user_cleaning_remain_effective(self):
        name = "489155_com@示例账号【作品】旅行.MP4"
        self.assertTrue(media_file_name(name, "标题.exe", "f.mp4").endswith(".MP4"))
        for mode in ("compatible", "caption", "template"):
            result = name_plan(name, "城市旅行", "f.mp4", options={"mode": mode})
            self.assertNotIn("489155", result["file_name"])
            self.assertTrue(result["file_name"].endswith(".MP4"))
