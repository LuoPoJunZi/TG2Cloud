"""Maintenance UX, isolated private backup, renewal and release guard regressions."""

from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import os
import shlex
import subprocess
import tarfile
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import test_review_regressions as review
from test_deployment import BASH, bash_path

import installer
import proxy_maintenance as backups
from deployer_products import CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT, RELEASE_VERSION
from domain_proxy import (
    DomainProxyManager,
    ProxyReport,
    empty_state,
    render_certbot_loop,
    renewal_dry_run_command,
    renewal_summary,
    renewal_warnings,
    state_with_route,
)
from operation_feedback import failure_details, stage_from_log, version_summary

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_metadata", ROOT / ".github/scripts/release_metadata.py")
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class FeedbackTests(unittest.TestCase):
    def test_versions_are_distinct_and_unknown_is_not_latest(self):
        self.assertIn("版本较旧", version_summary("1.1.1", "1.1.0"))
        self.assertIn("版本较新", version_summary("1.1.1", "1.10.0"))
        self.assertIn("版本一致", version_summary("1.1.1", "1.1.1"))
        for unknown in ("", "secret\nTG2CLOUD_STATUS=RUNNING", "1.1", "v1.1.1"):
            text = version_summary("1.1.1", unknown)
            self.assertIn("未获取", text)
            self.assertNotIn("secret", text)
            self.assertNotIn("版本一致", text)
        self.assertIn("未安装", version_summary("1.1.1", "", installed=False))

    def test_stage_markers_are_whitelisted(self):
        self.assertEqual(stage_from_log("TG2CLOUD_STAGE=CERTIFICATE\n"), "CERTIFICATE")
        self.assertEqual(stage_from_log("TG2CLOUD_STAGE=SECRET"), "")
        self.assertEqual(stage_from_log("prefix TG2CLOUD_STAGE=BOT"), "")
        detail = failure_details(RuntimeError("原因未确定"), "CERTIFICATE")
        self.assertIn("失败阶段：申请或复用证书", detail)
        self.assertIn("原因未确定", detail)
        self.assertNotIn("连接超时", detail)

    def test_self_test_requires_bundled_private_backup_helper(self):
        resolve = installer.resource_path
        for product in (CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT):
            with self.subTest(product=product.key):
                self.assertNotIn("proxy_maintenance.py", installer.dependency_report(product)["payload_missing"])
                with patch.object(installer, "resource_path", side_effect=lambda name: Path("/not-a-bundle/proxy_maintenance.py") if name == "proxy_maintenance.py" else resolve(name)):
                    report = installer.dependency_report(product)
                self.assertIn("proxy_maintenance.py", report["payload_missing"])
                self.assertFalse(report["ready"])

    def test_runtime_status_reports_actual_bot_version(self):
        for product in (CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT):
            with self.subTest(product=product.key):
                session = Mock()
                session.run.side_effect = [(0, "0"), (0,
                    "TG2CLOUD_STATUS=RUNNING\nTG2CLOUD_BOT_HEALTH=healthy\nTG2CLOUD_VERSION=1.0.4\n")]
                backend = installer.InstallerBackend(Mock(), Mock(), Mock(), session_factory=Mock(return_value=session), product=product)
                values = installer.defaults_for(product) | {"vps_host": "example.invalid", "vps_password": "test-only"}
                result = backend.runtime_status(values)
                self.assertIn("VPS Bot 版本：v1.0.4", result.message)
                self.assertIn("部署器版本：v" + RELEASE_VERSION, result.message)
                self.assertIn("不代表 WebDAV", result.message)
                session.close.assert_called_once()

    @unittest.skipUnless(hasattr(installer, "InstallerWindow"), "Qt unavailable")
    def test_shared_ui_reuses_progress_and_maintenance_cannot_mark_https_passed(self):
        app = installer.make_app()
        for product in (CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT):
            window = installer.InstallerWindow(preview=True, product=product)
            dialog = installer.DomainAccessDialog(window)
            try:
                window.append_log("TG2CLOUD_STAGE=BOT")
                self.assertIn("构建并启动 Bot", window.step_summary.text())
                self.assertIn("阶段：", window.console.toPlainText())
                dialog._success("proxy_backup", installer.OperationResult("备份完成", "私密备份已保留"))
                self.assertEqual(dialog.configured_state, "not_configured")
                self.assertEqual(dialog.configured_domain, "")
                self.assertEqual(dialog.status_text.height(), 112)
                self.assertTrue(any(action.text() == "管理历史代理备份…" for action in dialog.maintenance_button.menu().actions()))
                app.processEvents()
            finally:
                dialog.close()
                window.close()

    @unittest.skipUnless(os.name == "nt" and hasattr(installer, "InstallerWindow"), "Windows CJK font QA only")
    def test_real_windows_cjk_font_does_not_squeeze_domain_actions(self):
        from PySide6.QtGui import QFont, QFontDatabase
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        if not font.is_file():
            self.skipTest("Windows system CJK font unavailable")
        app = installer.make_app()
        font_id = QFontDatabase.addApplicationFont(str(font))
        if font_id < 0:
            self.skipTest("Qt cannot load system CJK font")
        previous = app.font()
        app.setFont(QFont("Microsoft YaHei UI", 10))
        try:
            for product in (CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT):
                window = installer.InstallerWindow(preview=True, product=product)
                dialog = installer.DomainAccessDialog(window)
                dialog.show()
                app.processEvents()
                self.assertLessEqual(dialog.layout().minimumSize().height(), dialog.height())
                self.assertEqual(dialog.status_text.height(), 112)
                dialog.close()
                window.close()
        finally:
            app.setFont(previous)
            QFontDatabase.removeApplicationFont(font_id)

    @unittest.skipUnless(hasattr(installer, "InstallerWindow"), "Qt unavailable")
    def test_backup_cleanup_requires_preview_and_defaults_to_cancel(self):
        installer.make_app()
        window = installer.InstallerWindow(preview=True)
        owner = installer.DomainAccessDialog(window)
        dialog = installer.ProxyBackupDialog(owner)
        item = {"name": "proxy-20261008T000000Z-" + "a" * 32 + ".tar.gz", "created_utc": "2026-10-08 00:00:00 UTC", "size_bytes": 1024, "integrity": "OK"}
        plan = {"keep": 5, "retain": [item["name"].replace("a" * 32, "b" * 32)], "remove": [item], "plan_id": "f" * 64}
        try:
            dialog.backend = Mock()
            window.preview = False  # Do not schedule the initial SSH inventory timer.
            dialog._success("proxy_backup_list", installer.OperationResult("清单", "", backup_data={"items": [item]}))
            dialog._set_busy(False)
            self.assertEqual(dialog.archives.currentData(), item["name"])
            self.assertFalse(dialog.buttons["proxy_backup_prune"].isEnabled())
            dialog._success("proxy_backup_preview", installer.OperationResult("预览", "", backup_data={"plan": plan}))
            dialog._set_busy(False)
            self.assertTrue(dialog.buttons["proxy_backup_prune"].isEnabled())
            with patch.object(installer.QMessageBox, "question", return_value=installer.QMessageBox.StandardButton.No) as question, patch.object(installer, "OperationThread") as worker:
                dialog._run("proxy_backup_prune")
                self.assertEqual(question.call_args.args[-1], installer.QMessageBox.StandardButton.No)
                worker.assert_not_called()
            dialog.keep.setValue(6)
            self.assertIsNone(dialog.plan)
            self.assertFalse(dialog.buttons["proxy_backup_prune"].isEnabled())
        finally:
            dialog.close()
            owner.close()
            window.close()


class PrivateBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "proxy"
        self.backup_root = Path(self.temp.name) / "backups"
        for relative in ("state", "nginx/conf.d", "certbot/letsencrypt/archive/example.test", "certbot/status"):
            (self.root / relative).mkdir(parents=True)
        (self.root / "state/domains.json").write_text(json.dumps(empty_state()), encoding="utf-8")
        (self.root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "nginx/nginx.conf").write_text("events {}\n", encoding="utf-8")
        (self.root / "certbot/letsencrypt/archive/example.test/privkey1.pem").write_text("synthetic-test-material", encoding="utf-8")

    def test_archive_checksum_and_isolated_recovery_leave_live_files_untouched(self):
        original = backups.snapshot(self.root)
        archive = backups.create_backup(self.root, self.backup_root)
        records = backups.verify_backup(archive)
        self.assertEqual(records, original)
        self.assertEqual(backups.recovery_drill(archive, self.backup_root), len(records))
        self.assertEqual(backups.snapshot(self.root), original)
        self.assertFalse(list(self.backup_root.glob("recovery-drill-*")))
        if os.name != "nt":
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.backup_root.stat().st_mode & 0o777, 0o700)

    def test_certificate_links_are_preserved(self):
        live = self.root / "certbot/letsencrypt/live/example.test"
        live.mkdir(parents=True)
        try:
            (live / "privkey.pem").symlink_to("../../archive/example.test/privkey1.pem")
        except OSError:
            self.skipTest("OS does not allow this process to create symlinks")
        archive = backups.create_backup(self.root, self.backup_root)
        self.assertEqual(backups.verify_backup(archive)["proxy/certbot/letsencrypt/live/example.test/privkey.pem"]["kind"], "symlink")
        backups.recovery_drill(archive, self.backup_root)

    def test_corrupt_backup_is_rejected_before_extraction(self):
        archive = backups.create_backup(self.root, self.backup_root)
        with archive.open("ab") as handle:
            handle.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            backups.recovery_drill(archive, self.backup_root)
        self.assertFalse(list(self.backup_root.glob("recovery-drill-*")))

    def test_change_during_backup_removes_partial_archive(self):
        original = backups.snapshot(self.root)
        with patch.object(backups, "snapshot", side_effect=[original, original | {"changed": {}}]), self.assertRaisesRegex(ValueError, "source changed"):
            backups.create_backup(self.root, self.backup_root)
        self.assertEqual(list(self.backup_root.iterdir()), [])

    def test_unsafe_tar_members_are_rejected_even_with_valid_checksum(self):
        self.backup_root.mkdir()
        for name, kind, link in (
            ("../outside", "file", ""), ("/absolute", "file", ""),
            ("proxy/C:/outside", "file", ""), ("proxy//alias", "file", ""),
            ("proxy/escape", "symlink", "../../outside"),
            ("proxy/special", "fifo", ""),
        ):
            with self.subTest(name=name):
                archive = self.backup_root / "proxy-20261008T000000Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.tar.gz"
                with tarfile.open(archive, "w:gz") as tar:
                    member = tarfile.TarInfo(name)
                    if kind == "symlink":
                        member.type, member.linkname = tarfile.SYMTYPE, link
                        tar.addfile(member)
                    elif kind == "fifo":
                        member.type = tarfile.FIFOTYPE
                        tar.addfile(member)
                    else:
                        member.size = 1
                        tar.addfile(member, io.BytesIO(b"x"))
                archive.with_name(archive.name + ".sha256").write_text(backups.digest(archive), encoding="ascii")
                with self.assertRaises(ValueError):
                    backups.verify_backup(archive)

    def test_safe_link_bounds(self):
        self.assertTrue(backups.safe_link("proxy/certbot/letsencrypt/live/test/key.pem", "../../archive/test/key1.pem"))
        for target in ("/etc/passwd", "../../../../outside", "C:\\outside", "C:/outside", ""):
            self.assertFalse(backups.safe_link("proxy/one/key", target))

    def test_select_old_archive_and_prune_only_confirmed_verified_leaves(self):
        archives = [backups.create_backup(self.root, self.backup_root) for _ in range(3)]
        oldest = backups.selected_archive(self.backup_root, archives[0].name)
        self.assertEqual(oldest, archives[0])
        self.assertTrue(backups.verify_backup(oldest))
        unrelated = self.backup_root / "keep-unrelated.txt"
        unrelated.write_text("preserve", encoding="ascii")
        plan = backups.prune_plan(self.backup_root, 1)
        before = {p.name for p in self.backup_root.iterdir()}
        self.assertEqual(len(plan["remove"]), 2)
        self.assertEqual(before, {p.name for p in self.backup_root.iterdir()})
        result = backups.prune_backups(self.backup_root, 1, plan["plan_id"])
        self.assertEqual(result, plan)
        self.assertTrue((self.backup_root / plan["retain"][0]).is_file())
        self.assertEqual(len(backups.backup_inventory(self.backup_root)), 1)
        self.assertEqual(unrelated.read_text(), "preserve")
        for item in plan["remove"]:
            self.assertFalse((self.backup_root / item["name"]).exists())
            self.assertFalse((self.backup_root / (item["name"] + ".sha256")).exists())

    def test_changed_plan_corruption_and_unsafe_selection_cannot_delete_archives(self):
        archives = [backups.create_backup(self.root, self.backup_root) for _ in range(2)]
        plan = backups.prune_plan(self.backup_root, 1)
        archives.append(backups.create_backup(self.root, self.backup_root))
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            backups.prune_backups(self.backup_root, 1, plan["plan_id"])
        self.assertTrue(all(p.exists() for p in archives))
        with archives[0].open("ab") as handle:
            handle.write(b"corruption")
        self.assertIn("FAILED", [item["integrity"] for item in backups.backup_inventory(self.backup_root)])
        with self.assertRaisesRegex(ValueError, "verify failed"):
            backups.prune_plan(self.backup_root, 1)
        for name in ("../outside", str(archives[1]), "rclone.conf"):
            with self.assertRaises(ValueError):
                backups.selected_archive(self.backup_root, name)
        for keep in (0, 51, True):
            with self.assertRaises(ValueError):
                backups.prune_plan(self.backup_root, keep)
        self.assertTrue(all(p.exists() for p in archives))

    def test_signal_interrupt_removes_only_partial_new_archive(self):
        original = backups.create_backup(self.root, self.backup_root)
        before = {p.name for p in self.backup_root.iterdir()}
        with patch.object(backups, "snapshot", side_effect=[backups.snapshot(self.root), InterruptedError("TERM")]), self.assertRaises(InterruptedError):
            backups.create_backup(self.root, self.backup_root)
        self.assertTrue(original.is_file())
        self.assertEqual(before, {p.name for p in self.backup_root.iterdir()})


class RenewalTests(unittest.TestCase):
    def test_dry_run_is_current_edition_only_and_not_force_renewal(self):
        session = SimpleNamespace(hold_lock=lambda *_args, **_kwargs: nullcontext())
        manager = DomainProxyManager(session, OPENLIST_PRODUCT, {}, Mock())
        manager.read_state = Mock(return_value=state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com"))
        manager._run = Mock(return_value=(0, "TG2CLOUD_PROXY_TASK_CLEANUP=OK\n"))
        self.assertIn("没有替换正式证书", manager.maintenance("renew_dry_run"))
        command = shlex.split(manager._run.call_args.args[0])[-1]
        self.assertIn("--dry-run", command)
        self.assertIn("--cert-name ol.example.com", command)
        self.assertIn("--no-random-sleep-on-renew", command)
        self.assertIn("--no-directory-hooks", command)
        self.assertNotIn("--no-random-sleep-on-renew", render_certbot_loop())
        self.assertNotIn("--force-renewal", command)
        self.assertNotIn("--run-deploy-hooks", command)
        manager.read_state.return_value = empty_state()
        with self.assertRaisesRegex(RuntimeError, "尚未配置"):
            manager.maintenance("renew_dry_run")

    def test_failure_cleanup_is_exact_and_disconnect_preserves_original_error(self):
        session = SimpleNamespace(hold_lock=lambda *_args, **_kwargs: nullcontext())
        log = Mock()
        manager = DomainProxyManager(session, OPENLIST_PRODUCT, {}, log)
        manager.read_state = Mock(return_value=state_with_route(empty_state(), OPENLIST_PRODUCT, "ol.example.com"))
        manager._run = Mock(side_effect=[TimeoutError("lost SSH"), RuntimeError("still disconnected")])
        with self.assertRaisesRegex(TimeoutError, "lost SSH"):
            manager.maintenance("renew_dry_run")
        cleanup = manager._run.call_args_list[1].args[0]
        self.assertIn("com.tg2cloud.task", cleanup)
        self.assertIn("maintenance-dry-run", cleanup)
        self.assertNotIn("docker stop", cleanup)
        self.assertNotIn("tg2cloud-clouddrive2-bot", cleanup)
        self.assertTrue(any("9 分钟" in call.args[0] for call in log.call_args_list))

    def test_renewal_alerts_handle_legacy_failed_stale_and_future_records(self):
        now = dt.datetime(2026, 10, 8, tzinfo=dt.UTC)
        epoch = int(now.timestamp())
        self.assertEqual(renewal_warnings({}, now), ())
        self.assertEqual(renewal_warnings({"PROXY_RENEW_RESULT": "OK", "PROXY_RENEW_ATTEMPT": str(epoch - 3600)}, now), ())
        self.assertIn("失败", renewal_warnings({"PROXY_RENEW_RESULT": "FAILED"}, now)[0])
        self.assertIn("26 小时", renewal_warnings({"PROXY_RENEW_ATTEMPT": str(epoch - 27 * 3600)}, now)[0])
        self.assertIn("时间异常", renewal_warnings({"PROXY_RENEW_ATTEMPT": str(epoch + 600)}, now)[0])
        self.assertTrue(renewal_warnings({"PROXY_RENEW_ATTEMPT": "not-a-time"}, now))

    def test_backup_helper_deadline_and_selected_archive_are_scoped(self):
        session = Mock()
        session.run.return_value = (0, "")
        manager = DomainProxyManager(session, OPENLIST_PRODUCT, {}, Mock())
        manager._upload_files = Mock(return_value="/tmp/tg2cloud-proxy-" + "a" * 32)
        manager._run = Mock(return_value=(0, "TG2CLOUD_PROXY_BACKUP=CHECK_OK\n"))
        archive = "proxy-20261008T000000Z-" + "b" * 32 + ".tar.gz"
        manager._backup_helper("check", archive=archive)
        command = manager._run.call_args.args[0]
        self.assertIn("--kill-after=15s 150s python3", command)
        self.assertIn("--archive " + archive, command)
        self.assertEqual(manager._run.call_args.kwargs["timeout"], 190)
        self.assertEqual(session.run.call_args.args[0], "rm -rf -- /tmp/tg2cloud-proxy-" + "a" * 32)
        manager._upload_files.reset_mock()
        with self.assertRaises(ValueError):
            manager._backup_helper("check", archive="../rclone.conf")
        manager._upload_files.assert_not_called()

    def test_invalid_backup_plan_cannot_reach_ui(self):
        session = SimpleNamespace(hold_lock=lambda *_args, **_kwargs: nullcontext())
        manager = DomainProxyManager(session, OPENLIST_PRODUCT, {}, Mock())
        item = {"name": "proxy-20261008T000000Z-" + "a" * 32 + ".tar.gz", "created_utc": "2026-10-08 00:00:00 UTC", "size_bytes": 1, "integrity": "OK"}
        for retain in ([], [item["name"]]):
            with self.subTest(retain=retain):
                plan = {"keep": 5, "retain": retain, "remove": [item], "plan_id": "f" * 64}
                manager._backup_helper = Mock(return_value={"PROXY_BACKUP_PLAN": json.dumps(plan)})
                with self.assertRaisesRegex(RuntimeError, "保留有效备份"):
                    manager.manage_backups("prune-preview")

    @unittest.skipUnless(hasattr(installer, "InstallerWindow"), "Qt unavailable")
    def test_renewal_warning_keeps_https_gate_and_open_action_usable(self):
        installer.make_app()
        window = installer.InstallerWindow(preview=True)
        dialog = installer.DomainAccessDialog(window)
        report = ProxyReport("test.example.com", "healthy", "可用，续期待检查", (), warnings=("续期失败",))
        try:
            dialog._success("proxy_status", installer.OperationResult("检查状态", report.message, proxy_report=report))
            self.assertEqual(dialog.configured_state, "healthy")
            self.assertEqual(dialog.configured_domain, report.domain)
            self.assertIn("续期待检查", dialog.state_badge.text())
            self.assertEqual(dialog.state_badge.property("state"), "pending")
            self.assertIn("可用", window.footer_state.text())
        finally:
            dialog.close()
            window.close()

    @unittest.skipUnless(BASH, "Bash unavailable")
    def test_real_deadline_removes_only_owned_container_and_refuses_foreign_label(self):
        task_id = "a" * 32
        for owner in (task_id, "foreign-owner"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "docker").write_bytes((ROOT / "tests/maintenance_docker_stub.sh").read_bytes())
                (root / "docker").chmod(0o755)
                protected = root / "protected"
                protected.write_text("shared services", encoding="ascii")
                script = f"export PATH={shlex.quote(bash_path(root))}:$PATH\nexport TG2CLOUD_TEST_TASK_ROOT={shlex.quote(bash_path(root))}\nexport TG2CLOUD_TEST_TASK_OWNER={shlex.quote(owner)}\n" + renewal_dry_run_command("ol.example.com", task_id, seconds=1)
                result = subprocess.run([BASH, "-c", script], capture_output=True, timeout=15, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((root / "container").exists(), owner != task_id)
                self.assertEqual(protected.read_text(), "shared services")
                self.assertIn(b"CLEANUP=OK" if owner == task_id else b"CLEANUP=REFUSED", result.stdout)

    def test_history_is_optional_and_does_not_claim_real_renewal(self):
        text = renewal_summary({})
        self.assertIn("尚无记录", text)
        self.assertIn("不代表本次发生续签", text)
        text = renewal_summary({"PROXY_RENEW_RESULT": "FAILED", "PROXY_RENEW_ATTEMPT": "1791417600"})
        self.assertIn("失败", text)
        self.assertIn("UTC", text)

    @unittest.skipUnless(BASH, "Bash unavailable")
    def test_real_loop_records_success_failure_and_certificate_change_separately(self):
        for success, changed in ((True, False), (True, True), (False, False)):
            with self.subTest(success=success, changed=changed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "status").mkdir()
                (root / "live/test.example").mkdir(parents=True)
                cert = root / "live/test.example/fullchain.pem"
                cert.write_text("before", encoding="ascii")
                loop = render_certbot_loop().replace("/status/", bash_path(root / "status") + "/").replace("/etc/letsencrypt/live/", bash_path(root / "live") + "/").replace("/var/log/letsencrypt/renew-console.log", bash_path(root / "log"))
                stub = "certbot() { " + (f"printf after >{shlex.quote(bash_path(cert))}; " if changed else "") + ("return 0; }\n" if success else "return 1; }\n")
                script = stub + "TG2CLOUD_CERT_NAMES=test.example\nwait() { exit 0; }\nsleep() { return 0; }\n" + loop
                result = subprocess.run([BASH, "-c", script], capture_output=True, timeout=15, check=False)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                history = (root / "status/test.example.check").read_text(encoding="ascii")
                self.assertIn("RESULT=" + ("OK" if success else "FAILED"), history)
                self.assertEqual((root / "status/test.example.success").exists(), success)
                self.assertEqual((root / "status/test.example.renewed").exists(), changed and success)


class ProbeVisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_doctor_cooldown_time_is_actual_probe_not_message_refresh(self):
        from app.interfaces import DestinationProbe
        service = review.OpenListReviewTests.service(DestinationProbe(False, "root", "limited", "rate_limited"))
        service.settings.destination_label = "OpenList"
        service._sample_fresh = lambda: True
        service._destination_ready = lambda: service.destination_healthy
        service.download_window = service.upload_window = SimpleNamespace(value=1)
        await service._probe_destination_once()
        checked = service.destination_last_checked
        text = service._format_doctor()
        self.assertIn("限流等待", text)
        self.assertIn("刷新不会绕过冷却", text)
        self.assertIn("最近实际探测", text)
        await service._probe_destination_once()
        self.assertEqual(service.destination_last_checked, checked)
        self.assertEqual(service.rclone.probe.await_count, 1)
        service._destination_next_probe_at = time.monotonic() - 1
        service.rclone.probe = AsyncMock(return_value=DestinationProbe(True, "root", "ok"))
        await service._probe_destination_once()
        self.assertNotIn("限流等待", service._format_doctor())


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_tag_and_resources_match_one_version_source(self):
        self.assertEqual(release.source_version(ROOT), RELEASE_VERSION)
        metadata = release.release_metadata(ROOT, "v" + RELEASE_VERSION)
        self.assertEqual(metadata["is_prerelease"], "false")

    def test_invalid_and_mismatched_tags_are_rejected(self):
        for tag in ("main", "v9.0.0", "v01.1.1", "v1.1.1\nINJECT=1", "v1.1.1-rc.0", "v1.1.1;echo x"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.release_metadata(ROOT, tag)

    def test_rc_requires_exact_notes_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in ("payload_clouddrive2/app/version.py", "packaging/windows/TG2Cloud-CloudDrive2.version.txt", "packaging/windows/TG2Cloud-OpenList.version.txt", "CHANGELOG.md", "RELEASE_NOTES.md"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / path).read_bytes())
            tag = "v" + RELEASE_VERSION + "-rc.1"
            with self.assertRaisesRegex(ValueError, "exact release tag"):
                release.release_metadata(root, tag)
            (root / "RELEASE_NOTES.md").write_text(f"TG2Cloud {tag}\n", encoding="utf-8")
            metadata = release.release_metadata(root, tag)
            self.assertEqual(metadata["is_prerelease"], "true")
            self.assertTrue(metadata["release_title"].endswith("RC1"))

    def test_workflow_uses_validated_tag_and_reuses_one_build(self):
        text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertNotIn("RELEASE_TAG: v1.", text)
        self.assertIn('test "${GITHUB_REF_TYPE}" = tag', text)
        self.assertIn("needs.prepare.outputs.release_tag", text)
        self.assertEqual(text.count("./build.ps1"), 1)
        self.assertIn("needs.linux-validation.result == 'success'", text)


if __name__ == "__main__":
    unittest.main()
