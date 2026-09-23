from __future__ import annotations

import base64
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1]
PAYLOAD = SOURCE / "payload_clouddrive2"
OPENLIST_PAYLOAD = SOURCE / "payload_openlist"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(PAYLOAD))

from app.config import Settings

import installer
from deployer_products import CLOUDDRIVE2_PRODUCT, OPENLIST_PRODUCT
from installer import (
    InstallerBackend,
    OperationError,
    defaults_for,
    make_app,
    secure_password,
    verification_statuses,
)
from vps_resources import GIB, VpsResources, recommend_storage


def encoded(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def openlist_values() -> dict[str, str]:
    values = defaults_for(OPENLIST_PRODUCT)
    values.update(
        {
            "vps_host": "203.0.113.10",
            "vps_port": "22",
            "vps_user": "root",
            "vps_password": "test-vps-password",  # pragma: allowlist secret
            "bot_token": "123456:" + "a" * 30,
            "telegram_api_id": "12345",
            "telegram_api_hash": "a" * 32,
            "allowed_user_id": "987654321",
        }
    )
    return values


class OpenListProductTests(unittest.TestCase):
    def backend(self, **kwargs: object) -> InstallerBackend:
        return InstallerBackend(
            log=kwargs.pop("log", Mock()),
            confirm_host_key=Mock(return_value=True),
            publish_resources=Mock(),
            product=OPENLIST_PRODUCT,
            **kwargs,
        )

    def test_product_runtime_identities_are_isolated(self) -> None:
        self.assertEqual(OPENLIST_PRODUCT.install_dir, "/opt/tg2cloud-openlist")
        self.assertEqual(OPENLIST_PRODUCT.storage_container, "tg2cloud-openlist")
        self.assertEqual(OPENLIST_PRODUCT.bot_container, "tg2cloud-openlist-bot")
        self.assertEqual(OPENLIST_PRODUCT.docker_network, "tg2cloud-openlist-net")
        self.assertEqual(OPENLIST_PRODUCT.management_port, 5244)
        self.assertEqual(
            OPENLIST_PRODUCT.webdav_url, "http://tg2cloud-openlist:5244/dav/"
        )
        self.assertEqual(OPENLIST_PRODUCT.webdav_username, "tg2cloud")
        self.assertEqual(OPENLIST_PRODUCT.webdav_target, "")
        self.assertNotEqual(OPENLIST_PRODUCT.install_dir, CLOUDDRIVE2_PRODUCT.install_dir)
        self.assertNotEqual(
            OPENLIST_PRODUCT.docker_network, CLOUDDRIVE2_PRODUCT.docker_network
        )

    def test_product_release_identity_is_tg2cloud_v1(self) -> None:
        self.assertEqual(CLOUDDRIVE2_PRODUCT.app_version, "1.0.3")
        self.assertEqual(OPENLIST_PRODUCT.app_version, "1.0.3")
        self.assertEqual(
            CLOUDDRIVE2_PRODUCT.executable_name,
            "TG2Cloud-CloudDrive2-Deployer",
        )
        self.assertEqual(
            OPENLIST_PRODUCT.executable_name,
            "TG2Cloud-OpenList-Deployer",
        )
        self.assertEqual(CLOUDDRIVE2_PRODUCT.app_title, "TG2Cloud · CloudDrive2")
        self.assertEqual(OPENLIST_PRODUCT.app_title, "TG2Cloud · OpenList")

    def test_generated_credentials_are_secure_and_session_scoped(self) -> None:
        first = secure_password()
        second = secure_password()
        self.assertRegex(first, r"^[A-Za-z0-9_-]{28}$")
        self.assertRegex(second, r"^[A-Za-z0-9_-]{28}$")
        self.assertNotEqual(first, second)
        defaults = defaults_for(OPENLIST_PRODUCT)
        self.assertEqual(defaults["cd2_username"], "tg2cloud")
        self.assertEqual(defaults["cd2_target"], "")
        self.assertEqual(defaults["local_budget_gb"], "20")
        self.assertEqual(defaults["min_free_disk_gb"], "8")
        self.assertRegex(defaults["cd2_password"], r"^[A-Za-z0-9_-]{28}$")
        self.assertRegex(
            defaults["openlist_admin_password"], r"^[A-Za-z0-9_-]{28}$"
        )
        self.assertEqual(defaults["preserve_webdav"], "false")

    def test_legacy_openlist_install_dir_is_rejected_before_deploy(self) -> None:
        values = openlist_values()
        values["install_dir"] = "/opt/tg115-openlist"
        with self.assertRaisesRegex(ValueError, "不会静默覆盖"):
            self.backend()._validate(values)

    @unittest.skipUnless(
        getattr(installer, "InstallerWindow", None) is not None,
        "Qt runtime unavailable",
    )
    def test_openlist_preview_uses_five_step_shared_pyside_ui(self) -> None:
        app = make_app()
        window = installer.InstallerWindow(preview=True, product=OPENLIST_PRODUCT)
        try:
            snapshot = window.snapshot()
            self.assertEqual(set(snapshot), set(defaults_for(OPENLIST_PRODUCT)))
            self.assertEqual(window.pages.count(), 5)
            self.assertEqual(window.edits["cd2_url"].text(), OPENLIST_PRODUCT.webdav_url)
            self.assertTrue(window.edits["cd2_url"].isReadOnly())
            self.assertFalse(window.managed.isEnabled())
            self.assertFalse(window.preserve_webdav.isChecked())
            window.preserve_webdav.setChecked(True)
            app.processEvents()
            self.assertEqual(window.snapshot()["preserve_webdav"], "true")
            self.assertFalse(window.field_boxes["cd2_password"].isEnabled())
            self.assertIn("OpenList", window.windowTitle())
            self.assertEqual(window.brand_name_label.text(), "TG2Cloud")
            self.assertIn("OpenList Edition", window.brand_subtitle_label.text())
            self.assertFalse(window.windowIcon().isNull())
            self.assertFalse(window.brand_icon_label.pixmap().isNull())
            self.assertTrue(hasattr(window, "verification_summary"))
            for operation in (
                "openlist_status",
                "openlist_logs",
                "restart_bot",
                "restart_openlist",
                "backup_openlist",
                "reset_openlist_admin",
            ):
                self.assertIn(operation, window.action_buttons)
            window._set_openlist_instance_state("existing")
            self.assertTrue(window.openlist_credentials_row.isHidden())
            self.assertIn("已初始化", window.openlist_instance_notice.text())
            window._set_openlist_instance_state("new")
            self.assertFalse(window.openlist_credentials_row.isHidden())
            self.assertFalse(window.openlist_regenerate_admin.isHidden())
            window._set_openlist_instance_state("recovered")
            self.assertFalse(window.openlist_credentials_row.isHidden())
            self.assertTrue(window.openlist_regenerate_admin.isHidden())
        finally:
            window.close()
            app.processEvents()

    @unittest.skipUnless(
        getattr(installer, "InstallerWindow", None) is not None,
        "Qt runtime unavailable",
    )
    def test_openlist_management_actions_fit_sidebar_viewport(self) -> None:
        app = make_app()
        window = installer.InstallerWindow(preview=True, product=OPENLIST_PRODUCT)
        try:
            window.resize(1280, 800)
            window.show()
            app.processEvents()
            sidebar = window.action_scroll
            content = sidebar.widget()
            self.assertLessEqual(content.minimumSizeHint().width(), sidebar.viewport().width())
            for operation in (
                "openlist_status",
                "openlist_logs",
                "restart_bot",
                "restart_openlist",
                "backup_openlist",
                "reset_openlist_admin",
            ):
                button = window.action_buttons[operation]
                with self.subTest(operation=operation):
                    right = button.mapTo(content, button.rect().topRight()).x()
                    self.assertLessEqual(right, sidebar.viewport().width())
        finally:
            window.close()
            app.processEvents()

    def test_verification_markers_become_safe_stage_statuses(self) -> None:
        statuses = dict(
            verification_statuses(
                """BOT_HEALTH=healthy
TG115_OPENLIST=OK
TG115_WEBDAV_AUTH=OK
TG115_WEBDAV_LIST=OK
TG115_WEBDAV_WRITE=OK
TG115_WEBDAV_SIZE=FAILED
"""
            )
        )
        self.assertEqual(statuses["Bot 容器"], "通过")
        self.assertEqual(statuses["OpenList 服务"], "通过")
        self.assertEqual(statuses["WebDAV 认证"], "通过")
        self.assertEqual(statuses["测试写入"], "通过")
        self.assertEqual(statuses["大小校验"], "失败")
        self.assertEqual(statuses["临时改名"], "未执行")
        current = dict(verification_statuses("TG2CLOUD_BOT_HEALTH=healthy\nTG2CLOUD_WEBDAV_AUTH=OK\nTG115_WEBDAV_AUTH=FAILED\nTG2CLOUD_UPLOAD=OK\n"))
        self.assertEqual(current["Bot 容器"], "通过")
        self.assertEqual(current["WebDAV 认证"], "通过")
        direct = dict(verification_statuses(
            "TG2CLOUD_WEBDAV_FINALIZE_MODE=DIRECT\n"
            "TG2CLOUD_WEBDAV_MOVE=NOT_REQUIRED\n"
        ))
        self.assertEqual(direct["最终落盘"], "无需执行")

    def test_openlist_verification_uses_manage_script_and_friendly_auth_error(
        self,
    ) -> None:
        values = openlist_values()
        session = Mock()
        session.run.side_effect = [
            (0, "0\n"),
            (
                1,
                """TG115_OPENLIST=OK
BOT_HEALTH=healthy
older unrelated log: 429 Too Many Requests
TG115_WEBDAV_AUTH=FAILED
401 Unauthorized
""",
            ),
        ]
        backend = self.backend(session_factory=Mock(return_value=session))

        with self.assertRaises(OperationError) as raised:
            backend.verify(values)

        self.assertIn("无法登录 OpenList WebDAV", str(raised.exception))
        self.assertNotIn("401", str(raised.exception))
        self.assertEqual(dict(raised.exception.statuses)["WebDAV 认证"], "失败")
        command = session.run.call_args_list[1].args[0]
        self.assertIn("bash ./manage.sh verify", command)

    def test_openlist_webdav_rate_limit_is_not_reported_as_bad_credentials(self) -> None:
        session = Mock()
        session.run.side_effect = [
            (0, "0\n"),
            (
                1,
                (
                    "TG2CLOUD_OPENLIST=OK\n"
                    "TG2CLOUD_BOT_HEALTH=healthy\n"
                    "TG2CLOUD_WEBDAV_AUTH=FAILED\n"
                    "TG2CLOUD_DESTINATION=FAILED: read metadata failed: 429 Too Many Requests\n"
                ),
            ),
        ]
        backend = self.backend(session_factory=Mock(return_value=session))

        with self.assertRaises(OperationError) as raised:
            backend.verify(openlist_values())

        message = str(raised.exception)
        self.assertIn("429", message)
        self.assertIn("稍后重试", message)
        self.assertNotIn("用户名", message)
        self.assertNotIn("密码", message)

    def test_openlist_unknown_move_is_not_misreported_as_permission_failure(self) -> None:
        session = Mock()
        session.run.side_effect = [
            (0, "0\n"),
            (1, (
                "TG2CLOUD_WEBDAV_MOVE=FAILED\n"
                "TG2CLOUD_DESTINATION=FAILED: MOVE_UNCERTAIN: rename unknown\n"
            )),
        ]
        backend = self.backend(session_factory=Mock(return_value=session))
        with self.assertRaises(OperationError) as raised:
            backend.verify(openlist_values())
        message = str(raised.exception)
        self.assertIn("状态暂时无法确认", message)
        self.assertIn("不要重复点击", message)
        self.assertNotIn("权限", message)

    def test_openlist_management_uses_only_fixed_manage_action(self) -> None:
        values = openlist_values()
        session = Mock()
        session.run.side_effect = [
            (0, "0\n"),
            (
                0,
                (
                    "TG2CLOUD_STATUS=RUNNING\nTG2CLOUD_LEGACY=DETECTED\n"
                    "TG2CLOUD_BOT_HEALTH=healthy\nTG2CLOUD_GATEWAY=RUNNING\n"
                    "TG2CLOUD_NETWORK=PRESENT\n"
                ),
            ),
        ]
        backend = self.backend(session_factory=Mock(return_value=session))

        result = backend.openlist_status(values)

        self.assertEqual(result.title, "运行状态")
        session.connect.assert_called_once_with()
        command = session.run.call_args_list[1].args[0]
        self.assertIn("bash -c", command)
        self.assertIn("tg2cloud-openlist-bot", command)
        self.assertNotIn("docker compose", command)
        self.assertNotIn(values["vps_password"], command)
        session.close.assert_called_once_with()

    def test_admin_password_reset_never_streams_or_returns_secret_in_message(self) -> None:
        values = openlist_values()
        new_password = "ResetOnly_23456789"
        session = Mock()
        session.run.side_effect = [
            (0, "0\n"),
            (
                0,
                f"""TG115_OPENLIST_ADMIN_RESET=OK
TG115_OPENLIST_ADMIN_USERNAME=admin
TG115_OPENLIST_ADMIN_PASSWORD={new_password}
""",
            ),
        ]
        log = Mock()
        backend = self.backend(
            log=log, session_factory=Mock(return_value=session)
        )

        result = backend.reset_openlist_admin(values)

        self.assertEqual(result.secret_field, "openlist_admin_password")
        self.assertEqual(result.secret_value, new_password)
        self.assertNotIn(new_password, result.message)
        self.assertNotIn(new_password, repr(result))
        self.assertIsNone(session.run.call_args_list[1].kwargs["stream"])
        log.assert_not_called()

    def test_openlist_config_contains_neutral_keys_and_no_115_credentials(self) -> None:
        values = openlist_values()
        config = self.backend()._build_config(values)
        pairs = dict(line.split("=", 1) for line in config.splitlines())
        self.assertEqual(pairs["TG2CLOUD_STORAGE_BACKEND"], "openlist")
        self.assertEqual(pairs["TG2CLOUD_RCLONE_REMOTE_NAME"], "openlist")
        self.assertEqual(pairs["TG115_STORAGE_BACKEND"], "openlist")
        self.assertEqual(pairs["TG115_RCLONE_REMOTE_NAME"], "openlist")
        self.assertEqual(pairs["LOCAL_TEMP_BUDGET_GB"], "20")
        self.assertEqual(pairs["MIN_FREE_DISK_GB"], "8")
        self.assertEqual(pairs["WEBDAV_TARGET_PATH_B64"], "")
        self.assertEqual(pairs["CD2_TARGET_PATH_B64"], "")
        self.assertEqual(
            base64.b64decode(pairs["WEBDAV_URL_B64"]).decode(),
            OPENLIST_PRODUCT.webdav_url,
        )
        self.assertEqual(
            pairs["OPENLIST_ADMIN_PASSWORD"], values["openlist_admin_password"]
        )
        self.assertEqual(pairs["TG2CLOUD_PRESERVE_WEBDAV"], "false")
        self.assertEqual(pairs["TG115_PRESERVE_WEBDAV"], "false")
        self.assertNotRegex(config, r"(?i)(115_cookie|115_token|cookie_115)")

    def test_openlist_management_uses_fixed_5244_tunnel(self) -> None:
        values = openlist_values()
        session = Mock()
        session.run.return_value = (0, "")
        tunnel = Mock()
        tunnel.url = "http://127.0.0.1:5244"
        factory = Mock(return_value=tunnel)
        browser = Mock()
        backend = self.backend(
            session_factory=Mock(return_value=session),
            tunnel_factory=factory,
            browser_open=browser,
        )

        backend.open_clouddrive(values)

        self.assertIn("127.0.0.1:5244", session.run.call_args.args[0])
        factory.assert_called_once_with(
            session,
            local_port=5244,
            remote_port=5244,
            product_name="OpenList",
        )
        browser.assert_called_once_with("http://127.0.0.1:5244")

    def test_openlist_resource_advice_does_not_require_fuse(self) -> None:
        resources = VpsResources(
            architecture="x86_64",
            cpu_cores=1,
            memory_total_bytes=GIB,
            memory_available_bytes=int(0.75 * GIB),
            swap_total_bytes=GIB,
            storage_total_bytes=30 * GIB,
            storage_available_bytes=24 * GIB,
            filesystem_type="ext4",
            inodes_total=1_000_000,
            inodes_available=900_000,
            install_present=False,
            install_used_bytes=0,
            downloads_used_bytes=0,
            backups_used_bytes=0,
            docker_same_filesystem=True,
            docker_root_detected=True,
            docker_storage_total_bytes=30 * GIB,
            docker_storage_available_bytes=24 * GIB,
            docker_inodes_total=1_000_000,
            docker_inodes_available=900_000,
            fuse_available=False,
        )
        advice = recommend_storage(
            resources,
            managed_clouddrive=False,
            managed_storage=True,
            requires_fuse=False,
            minimum_memory_mb=900,
        )
        self.assertTrue(advice.stream_first.safe)
        self.assertNotIn("FUSE", advice.stream_first.reason.upper())


class OpenListPayloadTests(unittest.TestCase):
    def test_openlist_archive_replaces_only_backend_specific_payload(self) -> None:
        backend = InstallerBackend(
            log=Mock(),
            confirm_host_key=Mock(return_value=True),
            publish_resources=Mock(),
            product=OPENLIST_PRODUCT,
        )
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "openlist-payload.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                backend._add_payload_to_archive(archive)
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
                compose = archive.extractfile("payload/docker-compose.yml")
                self.assertIsNotNone(compose)
                compose_text = compose.read().decode()  # type: ignore[union-attr]

        self.assertIn("payload/app/main.py", names)
        self.assertIn("payload/openlist_admin.sh", names)
        self.assertNotIn("payload/repair_clouddrive_network.sh", names)
        self.assertIn("container_name: tg2cloud-openlist", compose_text)

    def test_openlist_compose_is_private_pinned_and_restricted(self) -> None:
        compose = (OPENLIST_PAYLOAD / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            compose, r"openlistteam/openlist@sha256:[0-9a-f]{64}"
        )
        self.assertNotIn(":latest", compose)
        self.assertIn('"127.0.0.1:5244:5244"', compose)
        self.assertNotRegex(compose, r'(?m)^\s*-\s*"?5244:5244')
        self.assertIn("container_name: tg2cloud-openlist", compose)
        self.assertIn("container_name: tg2cloud-openlist-bot", compose)
        self.assertIn("name: tg2cloud-openlist-net", compose)
        self.assertIn('user: "10001:10001"', compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)

    def test_openlist_install_separates_deploy_from_destination_verification(self) -> None:
        script = (OPENLIST_PAYLOAD / "remote_install.sh").read_text(encoding="utf-8")
        self.assertIn("TG2CLOUD_OPENLIST_INITIALIZED=NEW", script)
        self.assertIn("TG2CLOUD_OPENLIST_INITIALIZED=EXISTING", script)
        self.assertIn("TG2CLOUD_DESTINATION=PENDING_USER_CONFIGURATION", script)
        self.assertNotIn("app.verify_destination", script)
        self.assertIn("chmod 600 \"$INSTALL_DIR/.env\"", script)
        self.assertIn("/opt/tg2cloud-openlist-backups", script)
        self.assertIn("openlist-state-", script)
        self.assertIn("tg115_preserve_existing_webdav_config", script)
        helper = (OPENLIST_PAYLOAD / "preserve_webdav_config.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("(TG2CLOUD|TG115)_PRESERVE_WEBDAV=true", helper)
        self.assertIn("WEBDAV_PASSWORD_B64 CD2_WEBDAV_PASSWORD_B64", helper)
        self.assertNotIn('source "$INSTALL_DIR/.env"', script)

    def test_openlist_legacy_detection_precedes_mutation(self) -> None:
        script = (OPENLIST_PAYLOAD / "remote_install.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("/opt/tg115-openlist", script)
        self.assertIn("tg115-openlist-bot", script)
        self.assertIn("tg115-openlist", script)
        self.assertIn("保留不动", script)
        self.assertIn("固定端口 5244", script)
        self.assertLess(script.index("检测到旧目录"), script.index("apt-get"))
        self.assertLess(script.index("目标容器名"), script.index('mkdir -p \\'))
        self.assertNotIn("docker network disconnect tg115-openlist-net", script)

    def test_openlist_admin_reset_requires_explicit_confirmation(self) -> None:
        script = (OPENLIST_PAYLOAD / "openlist_admin.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD", script)
        self.assertIn("./openlist admin random", script)
        self.assertNotIn("admin set admin", script)

    def test_openlist_manage_supports_safe_desktop_operations(self) -> None:
        script = (OPENLIST_PAYLOAD / "manage.sh").read_text(encoding="utf-8")
        for marker in (
            "TG2CLOUD_STATUS=OK",
            "TG2CLOUD_LOGS=OK",
            "TG2CLOUD_BOT_RESTART=OK",
            "TG2CLOUD_OPENLIST_RESTART=OK",
            "TG2CLOUD_BACKUP=OK",
        ):
            self.assertIn(marker, script)
        self.assertIn("create_backup", script)
        self.assertIn("python -m app.backup_database", script)
        self.assertIn("docker compose stop", script)
        self.assertIn("redact_runtime_logs", script)
        self.assertNotIn("OPENLIST_ADMIN_PASSWORD=$OPENLIST_ADMIN_PASSWORD", script)


class OpenListSettingsTests(unittest.TestCase):
    def test_neutral_webdav_environment_loads_openlist_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {
                "TELEGRAM_API_ID": "12345",
                "TELEGRAM_API_HASH_B64": encoded("a" * 32),
                "BOT_TOKEN_B64": encoded("123456:" + "a" * 30),
                "ALLOWED_USER_ID": "987654321",
                "WEBDAV_URL_B64": encoded(OPENLIST_PRODUCT.webdav_url),
                "WEBDAV_USERNAME_B64": encoded("tg2cloud"),
                "WEBDAV_PASSWORD_B64": encoded("safe-webdav-password"),
                "WEBDAV_TARGET_PATH_B64": encoded("Telegram"),
                "TG2CLOUD_STORAGE_BACKEND": "openlist",
                "TG2CLOUD_RCLONE_REMOTE_NAME": "openlist",
                "DATA_DIR": str(root / "data"),
                "DOWNLOAD_DIR": str(root / "downloads"),
                "LOG_DIR": str(root / "logs"),
                "RCLONE_CONFIG_PATH": str(root / "config" / "rclone.conf"),
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()
            self.assertEqual(settings.storage_backend, "openlist")
            self.assertEqual(settings.destination_label, "OpenList")
            self.assertEqual(settings.rclone_remote_name, "openlist")
            self.assertEqual(settings.cd2_target, "Telegram")

    def test_legacy_tg115_environment_keys_remain_supported(self) -> None:
        env = {
            "TELEGRAM_API_ID": "12345",
            "TELEGRAM_API_HASH_B64": encoded("a" * 32),
            "BOT_TOKEN_B64": encoded("123456:" + "a" * 30),
            "ALLOWED_USER_ID": "987654321",
            "WEBDAV_URL_B64": encoded(OPENLIST_PRODUCT.webdav_url),
            "WEBDAV_USERNAME_B64": encoded("tg2cloud"),
            "WEBDAV_PASSWORD_B64": encoded("safe-webdav-password"),
            "TG115_STORAGE_BACKEND": "openlist",
            "TG115_RCLONE_REMOTE_NAME": "openlist",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env(create_directories=False)
        self.assertEqual(settings.storage_backend, "openlist")
        self.assertEqual(settings.rclone_remote_name, "openlist")

    def test_remote_name_cannot_be_injected(self) -> None:
        env = {
            "TELEGRAM_API_ID": "12345",
            "TELEGRAM_API_HASH_B64": encoded("a" * 32),
            "BOT_TOKEN_B64": encoded("123456:" + "a" * 30),
            "ALLOWED_USER_ID": "987654321",
            "WEBDAV_URL_B64": encoded(OPENLIST_PRODUCT.webdav_url),
            "WEBDAV_USERNAME_B64": encoded("tg2cloud"),
            "WEBDAV_PASSWORD_B64": encoded("safe-webdav-password"),
            "TG2CLOUD_STORAGE_BACKEND": "openlist",
            "TG2CLOUD_RCLONE_REMOTE_NAME": "openlist;touch-pwned",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(RuntimeError, "存储后端不匹配"),
        ):
            Settings.from_env(create_directories=False)


if __name__ == "__main__":
    unittest.main()
