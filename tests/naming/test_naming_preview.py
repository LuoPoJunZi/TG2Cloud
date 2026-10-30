"""Preview and production names share a single selection path; no real media."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tg2cloud.cli import naming
from tg2cloud.domain.naming import explain_media_name, media_file_name

ROOT = Path(__file__).resolve().parents[2]


class PreviewTests(unittest.TestCase):
    def test_synthetic_multilingual_corpus_matches_existing_media_api_and_expected_names(self):
        cases = json.loads((ROOT / "tests/fixtures/naming-cases.json").read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(caption=case["input"].get("caption", "")):
                result = naming.preview(case["input"])
                value = case["input"]
                self.assertEqual(result["file_name"], case["expected"])
                if "source" in case:
                    self.assertEqual(result["source"], case["source"])
                self.assertEqual(result["file_name"], media_file_name(value["file_name"], value["caption"], "telegram-preview.mp4",
                                 media_extension=value.get("media_extension", "")))
                self.assertFalse(result["writes"])

    def test_affix_cleaning_preview_uses_same_name_and_has_human_readable_reason(self):
        for name in ("489155_com@示例账号【作品】城市旅行.mp4", "489155_com@示例账号.mp4"):
            result = naming.preview({"file_name": name, "caption": ""})
            self.assertNotIn("489155_com", result["file_name"])
            self.assertTrue(result["reason_text"])
            self.assertFalse(result["writes"])

    def test_selection_reasons_distinguish_original_caption_and_fallback(self):
        self.assertEqual(explain_media_name("River Walk.mp4", "旅行", "fallback.mp4")["reason"], "meaningful_original")
        self.assertEqual(explain_media_name("123.mp4", "河边旅行", "fallback.mp4")["source"], "caption")
        self.assertEqual(explain_media_name("", "", "fallback.mp4")["source"], "fallback")
        self.assertEqual(explain_media_name("123.mp4", "@only_channel", "fallback.mp4")["reason"], "no_valid_title")

    def test_json_cli_has_no_cwd_or_bot_dependency_and_creates_no_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, "-S", "-B", str(ROOT / "scripts/run_source.py"), "naming-preview", "--input",
                                     str(ROOT / "tests/fixtures/naming-preview.json"), "--json"], cwd=temporary,
                                    capture_output=True, text=True, timeout=15, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["source"], "caption")
            self.assertFalse(list(Path(temporary).iterdir()))

    def test_invalid_or_oversized_input_never_echoes_private_contents(self):
        for value in ({"caption": "x" * 8193}, {"file_name": []}, {"url": "PRIVATE_URL_TOKEN"}):
            with self.subTest(keys=tuple(value)), self.assertRaises(ValueError):
                naming.preview(value)
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "input.json"
            file.write_text("PRIVATE_INVALID_INPUT")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(naming.main(["--input", str(file)]), 1)
            self.assertNotIn("PRIVATE_INVALID_INPUT", output.getvalue())

    def test_interactive_preview_is_only_a_rendering_operation(self):
        ui = Mock()
        ui.ask.side_effect = ["123.mp4", ".mp4", "河边旅行", "."]
        lines = []
        naming.interactive(ui, lines.append)
        self.assertIn("预览文件名：河边旅行.mp4", lines)
        self.assertTrue(any("不修改" in line for line in lines))
