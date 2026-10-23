"""Trusted historical compatibility, no network or live instance changes."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from tg2cloud.deployment import baselines, releases
from tg2cloud.deployment.profiles import PRODUCTS

ROOT = Path(__file__).resolve().parents[1]


class BaselineTests(unittest.TestCase):
    def test_reviewed_catalog_matches_original_git_objects_for_both_editions(self):
        spec = importlib.util.spec_from_file_location("baseline_metadata", ROOT / ".github/scripts/baseline_metadata.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        for tag, record in baselines.CATALOG.items():
            with self.subTest(tag=tag):
                self.assertEqual(tool.entry(tag, record["commit"]), record)

    def test_known_baseline_does_not_require_deleted_release_or_tag(self):
        client = Mock()
        client.download.return_value = Path("verified-source")
        record = baselines.CATALOG["v1.3.4"]
        with patch.object(baselines, "verify") as verify:
            result = releases.download_baseline(client, "v1.3.4", Path("temp"), Mock())
        self.assertEqual(result, Path("verified-source"))
        client.resolve.assert_not_called()
        client.download.assert_called_once_with(releases.Release("v1.3.4", record["commit"]), Path("temp"))
        verify.assert_called_once_with(result, "v1.3.4", record["commit"])

    def test_unknown_version_still_requires_official_release(self):
        client = Mock()
        client.resolve.side_effect = releases.ReleaseLookupError("missing", status=404)
        with self.assertRaises(releases.ReleaseLookupError):
            releases.download_baseline(client, "v0.9.9", Path("temp"), Mock())
        client.download.assert_not_called()
        for tag in ("main", "a" * 40, "v1.3.4-rc.1", "../v1.3.4"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                releases.download_baseline(client, tag, Path("temp"), Mock())

    def test_corrupt_payload_or_wrong_commit_stops(self):
        record = baselines.CATALOG["v1.3.4"]
        with self.assertRaisesRegex(ValueError, "可信目录"):
            baselines.verify(ROOT, "v1.3.4", "0" * 40)
        with patch.object(baselines, "payload_digest", return_value="0" * 64), self.assertRaisesRegex(ValueError, "不匹配"):
            baselines.verify(ROOT, "v1.3.4", record["commit"])

    def test_digest_covers_path_content_addition_and_crlf_normalization(self):
        with tempfile.TemporaryDirectory() as private:
            root = Path(private)
            first, second = root / "a.py", root / "b.py"
            first.write_bytes(b"value = 1\n")
            second.write_bytes(b"value = 1\n")
            product = PRODUCTS["clouddrive2"]
            with patch.object(baselines, "payload_sources", return_value={"app/a.py": first}) as sources:
                original = baselines.payload_digest(root, product)
                first.write_bytes(b"value = 1\r\n")
                self.assertEqual(original, baselines.payload_digest(root, product))
                sources.return_value = {"app/nested/a.py": first}
                self.assertNotEqual(original, baselines.payload_digest(root, product))
                sources.return_value = {"app/a.py": first, "app/b.py": second}
                self.assertNotEqual(original, baselines.payload_digest(root, product))
                sources.return_value = {"app/a.py": first}
                first.write_bytes(b"raise RuntimeError('must never execute')\n")
                self.assertNotEqual(original, baselines.payload_digest(root, product))

    def test_http_failures_are_classified_without_remote_body_or_secret(self):
        for status in (404, 403, 429, 500):
            error = urllib.error.HTTPError("https://api.github.com/secret", status, "PRIVATE_BODY", {}, None)
            with self.subTest(status=status), patch.object(releases, "open_public", side_effect=error):
                with self.assertRaises(releases.ReleaseLookupError) as caught:
                    releases.ReleaseClient().json(releases.API + "/releases/latest")
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn("PRIVATE_BODY", str(caught.exception))
                self.assertNotIn("/secret", str(caught.exception))
