"""Naming regressions for conservative title selection and attachment suffixes."""
from __future__ import annotations

import unittest

from tg2cloud.domain.naming import caption_title, safe_file_name, video_file_name


class CaptionQualityTests(unittest.TestCase):
    def test_ordinary_work_titles_are_not_advertisements_or_metadata(self):
        titles = ("广告狂人", "大小谎言", "密码疑云", "Password to Paradise", "Size Matters")
        for title in titles:
            for caption in (title, "标题：" + title):
                with self.subTest(caption=caption):
                    self.assertEqual(video_file_name("123.mp4", caption, "telegram-1.mp4"), title + ".mp4")

    def test_explicit_title_label_does_not_make_promotion_or_credentials_valid(self):
        noise = ("广告合作", "关注频道 @sample", "更多精彩内容请加入会员获取全部资源",
                 "密码：private-example", "提取码：AB12", "文件大小：2GB", "Password: private-example", "Size: 2GB")
        for text in noise:
            for caption in (text, "标题：" + text):
                with self.subTest(caption=caption):
                    self.assertEqual(caption_title(caption), "")
                    self.assertEqual(video_file_name("123.mp4", caption, "telegram-1.mp4"), "123.mp4")

    def test_unlabelled_structured_metadata_does_not_become_a_title(self):
        values = ("Password secret123", "PASSWORD abc123", "密码 abc123", "提取码AB12", "解压abc123",
                  "Size 2GB", "文件大小 2GB", "时长 12:34", "格式 MP4", "duration 01:23:45")
        for value in values:
            for caption in (value, "标题：" + value, "春日旅行\n" + value):
                with self.subTest(caption=caption):
                    expected = "春日旅行" if caption.startswith("春日旅行\n") else ""
                    self.assertEqual(caption_title(caption), expected)

    def test_emoji_before_title_label_keeps_explicit_title_priority(self):
        caption = "🎬 标题：星际穿越\n这是一段很长的背景介绍，解释影片拍摄过程和观众讨论但不是作品名称"
        self.assertEqual(video_file_name("123.mp4", caption, "telegram-1.mp4"), "星际穿越.mp4")

    def test_meaningful_long_wrapped_description_still_beats_generic_heading(self):
        caption = "本期推荐\n\n视频说明：青海湖环线自驾实拍，沿途记录清晨湖岸\n以及高原天气变化和路线补给点。\n\n大小：377MB"
        self.assertEqual(caption_title(caption), "青海湖环线自驾实拍,沿途记录清晨湖岸 以及高原天气变化和路线补给点。")

    def test_a_long_membership_promotion_does_not_beat_a_short_real_title(self):
        promotion = "更多精彩内容请加入会员获取全部资源"
        for caption in ("春日旅行\n" + promotion, promotion + "\n春日旅行"):
            with self.subTest(caption=caption):
                self.assertEqual(caption_title(caption), "春日旅行")

    def test_adjacent_work_title_and_episode_can_be_joined(self):
        for caption, expected in (("三体\n第12集", "三体 第12集"),
                                  ("One Piece\nS01E02", "One Piece S01E02")):
            with self.subTest(caption=caption):
                self.assertEqual(video_file_name("123.mp4", caption, "telegram-1.mp4"), expected + ".mp4")

    def test_episode_join_never_crosses_a_blank_link_or_advertisement(self):
        for separator in ("", "https://example.test", "关注频道 @sample", "密码：AB12", "1080P"):
            caption = "三体\n" + separator + "\n第12集"
            with self.subTest(separator=separator):
                # Both independent lines remain legitimate candidates. Neither
                # boundary implies that they identify the same work episode.
                self.assertIn(caption_title(caption), ("三体", "第12集"))

    def test_two_episode_lines_are_not_merged_into_a_fabricated_title(self):
        self.assertEqual(caption_title("三体 第11集\n第12集"), "三体 第11集")
        self.assertEqual(caption_title("One Piece S01E01\nS01E02"), "One Piece S01E01")

    def test_slashes_in_an_ordinary_caption_preserve_both_title_parts(self):
        for caption, expected in (("AC/DC Live 2026", "AC_DC Live 2026.mp4"),
                                  ("海边旅行 / 日出篇", "海边旅行 _ 日出篇.mp4")):
            with self.subTest(caption=caption):
                self.assertEqual(video_file_name("123.mp4", caption, "telegram-1.mp4"), expected)

    def test_caption_slash_improvement_does_not_change_raw_path_safety(self):
        self.assertEqual(safe_file_name("../outside.mp4", "fallback.mp4"), "outside.mp4")
        for caption in ("标题：Movie/..", "标题：Movie/.", "标题：Movie/.exe"):
            with self.subTest(caption=caption):
                self.assertEqual(video_file_name("123.MKV", caption, "telegram-1.mp4"), "123.MKV")

    def test_a_domain_touching_chinese_text_does_not_swallow_the_title(self):
        for caption, expected in (("三体 第12集www.example.com", "三体 第12集"),
                                  ("海边旅行www.example.com", "海边旅行")):
            with self.subTest(caption=caption):
                self.assertEqual(caption_title(caption), expected)

    def test_non_domain_titles_with_dots_years_or_versions_are_preserved(self):
        for title in ("2026.东京旅行", "Node.js 入门教程", "ASP.NET Core 教程", "Python 3.12 v1.2.0",
                      "Ubuntu 24.04 安装教程"):
            with self.subTest(title=title):
                self.assertEqual(caption_title(title), title)

    def test_standalone_domains_including_unknown_suffixes_remain_filtered(self):
        for domain in ("example.com", "example.photography", "example.customsuffix", "EXAMPLE.UNKNOWN",
                       "www.example.test", "example.com@sample", "*.com@", "пример.com", "示例.net",
                       "пример.рф", "示例.中国", "示例.customsuffix"):
            with self.subTest(domain=domain):
                self.assertEqual(caption_title(domain), "")

    def test_episode_does_not_discard_the_start_of_a_wrapped_description(self):
        caption = "青海湖环线自驾实拍，\n以及高原天气变化和路线补给点。\n第12集"
        result = caption_title(caption)
        self.assertNotEqual(result, "以及高原天气变化和路线补给点。 第12集")
        self.assertIn(result, ("青海湖环线自驾实拍, 以及高原天气变化和路线补给点。", "第12集"))

    def test_quality_tags_and_caption_extensions_do_not_duplicate_a_suffix(self):
        for extension in (".mp4", ".MKV"):
            for caption in ("三体 第12集.mp4 [1080P]", "三体 第12集.mp4 1080P", "三体 第12集 [1080P]"):
                with self.subTest(extension=extension, caption=caption):
                    self.assertEqual(video_file_name("123" + extension, caption, "telegram-1.mp4"),
                                     "三体 第12集" + extension)

    def test_quality_words_that_are_part_of_a_real_title_are_not_removed(self):
        for title in ("HDR摄影教程", "HDR 摄影教程", "高清时代", "1080P 摄影工作流"):
            with self.subTest(title=title):
                self.assertEqual(caption_title(title), title)

    def test_ambiguous_alphabetic_names_keep_the_conservative_original_priority(self):
        for original in ("Microsoft.mp4", "community.mp4", "XkLmNpQr.mp4", "ItIsSoFunToBeMeNow.mp4"):
            with self.subTest(original=original):
                self.assertEqual(video_file_name(original, "春日旅行", "telegram-1.mp4"), original)


class VideoExtensionQualityTests(unittest.TestCase):
    def test_valid_video_attachment_suffix_still_has_priority(self):
        for extension in (".MKV", ".mov", ".webm"):
            with self.subTest(extension=extension):
                self.assertEqual(video_file_name("123" + extension, "海边旅行", "telegram-1.mp4",
                                                 media_extension=".mp4"), "海边旅行" + extension)

    def test_confirmed_video_type_replaces_a_non_video_attachment_suffix(self):
        for original in ("123.exe", "123.bin", "123.pdf"):
            with self.subTest(original=original):
                self.assertEqual(video_file_name(original, "海边旅行", "telegram-1.mp4",
                                                 media_extension=".mp4"), "海边旅行.mp4")

    def test_extension_mismatch_correction_does_not_replace_a_descriptive_stem(self):
        self.assertEqual(video_file_name("原本有意义的标题.exe", "另一段无关说明", "telegram-1.mp4",
                                         media_extension=".mp4"), "原本有意义的标题.mp4")

    def test_caption_cannot_override_a_confirmed_attachment_type(self):
        self.assertEqual(video_file_name("123.exe", "标题：海边旅行.exe", "telegram-1.mp4",
                                         media_extension=".mp4"), "海边旅行.mp4")

    def test_absent_or_invalid_detected_type_does_not_guess_a_new_suffix(self):
        for detected in ("", ".exe", ".MP4/../../escape", ".mp4\n"):
            with self.subTest(detected=detected):
                self.assertEqual(video_file_name("123.exe", "海边旅行", "telegram-1.mp4",
                                                 media_extension=detected), "海边旅行.exe")


if __name__ == "__main__":
    unittest.main()
