from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from payload_fixture import payload

import tg2cloud.deployment.configuration as tgdep_configuration
import tg2cloud.deployment.payload as tgdep_payload

SOURCE = Path(__file__).resolve().parents[1]
PAYLOAD = payload("clouddrive2")
OPENLIST_PAYLOAD = payload("openlist")
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(PAYLOAD))

from tg2cloud.config import Settings
from tg2cloud.deployment.profiles import (
    CLOUDDRIVE2_PRODUCT,
    OPENLIST_PRODUCT,
    RELEASE_VERSION,
)
from tg2cloud.deployment.resources import GIB, VpsResources, recommend_storage


def encoded(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


class OpenListProductTests(unittest.TestCase):

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
        self.assertEqual(CLOUDDRIVE2_PRODUCT.app_version, RELEASE_VERSION)
        self.assertEqual(OPENLIST_PRODUCT.app_version, RELEASE_VERSION)
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


    def test_openlist_config_contains_neutral_keys_and_no_115_credentials(self) -> None:
        values = {
            "api_id": "12345", "api_hash": "a" * 32, "bot_token": "123456:FAKE_LOCAL_TEST_TOKEN_ONLY",
            "user_id": "987654321", "webdav_user": "tg2cloud", "webdav_password": "FAKE_WEBDAV",
            "target": "", "budget": "20", "reserve": "8", "timezone": "Asia/Shanghai",
            "admin_password": "FAKE_ADMIN_PASSWORD",
        }
        pairs = tgdep_configuration.new_config(OPENLIST_PRODUCT, values)
        config = "\n".join(f"{key}={value}" for key, value in pairs.items())
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
            pairs["OPENLIST_ADMIN_PASSWORD"], values["admin_password"]
        )
        self.assertEqual(pairs["TG2CLOUD_PRESERVE_WEBDAV"], "false")
        self.assertEqual(pairs["TG115_PRESERVE_WEBDAV"], "false")
        self.assertNotRegex(config, r"(?i)(115_cookie|115_token|cookie_115)")


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
        with tempfile.TemporaryDirectory() as temp:
            payload = Path(temp) / "payload"
            tgdep_payload.build_payload(SOURCE, OPENLIST_PRODUCT, payload)
            names = {"payload/" + path.relative_to(payload).as_posix()
                     for path in payload.rglob("*") if path.is_file()}
            compose_text = (payload / "docker-compose.yml").read_text(encoding="utf-8")

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
