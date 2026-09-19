"""Immutable product definitions shared by the two PySide6 deployer entries."""

from __future__ import annotations

from dataclasses import dataclass

SHARED_PAYLOAD_FILES = (
    "payload_clouddrive2/backup_retention.sh",
    "payload_clouddrive2/.dockerignore",
    "payload_clouddrive2/Dockerfile",
    "payload_clouddrive2/requirements.txt",
    "payload_clouddrive2/app/__init__.py",
    "payload_clouddrive2/app/config.py",
    "payload_clouddrive2/app/main.py",
    "payload_clouddrive2/app/bot_commands.py",
    "payload_clouddrive2/app/interfaces.py",
    "payload_clouddrive2/app/states.py",
    "payload_clouddrive2/app/deployment_check.py",
    "payload_clouddrive2/app/backup_database.py",
    "payload_clouddrive2/app/naming.py",
    "payload_clouddrive2/app/db.py",
    "payload_clouddrive2/app/resources.py",
    "payload_clouddrive2/app/rclone_client.py",
    "payload_clouddrive2/app/healthcheck.py",
    "payload_clouddrive2/app/verify_destination.py",
)


@dataclass(frozen=True)
class ProductProfile:
    key: str
    display_name: str
    app_title: str
    app_version: str
    executable_name: str
    install_dir: str
    backup_dir: str
    webdav_url: str
    webdav_username: str
    webdav_target: str
    management_port: int
    bot_service: str
    bot_container: str
    storage_container: str
    docker_network: str
    requires_fuse: bool
    managed_toggle: bool
    payload_variant: str
    required_payload: tuple[str, ...]

    @property
    def is_openlist(self) -> bool:
        return self.key == "openlist"


CLOUDDRIVE2_PRODUCT = ProductProfile(
    key="clouddrive2",
    display_name="CloudDrive2",
    app_title="Telegram → 115 CloudDrive2 部署器",
    app_version="1.6.2",
    executable_name="TG115-CloudDrive2-Deployer",
    install_dir="/opt/tg115",
    backup_dir="/opt/tg115-backups",
    webdav_url="http://clouddrive2:19798/dav",
    webdav_username="",
    webdav_target="",
    management_port=19798,
    bot_service="tg115-bot",
    bot_container="tg115-bot",
    storage_container="tg115-clouddrive2",
    docker_network="tg115",
    requires_fuse=True,
    managed_toggle=True,
    payload_variant="payload_clouddrive2",
    required_payload=SHARED_PAYLOAD_FILES
    + (
        "payload_clouddrive2/remote_install.sh",
        "payload_clouddrive2/manage.sh",
        "payload_clouddrive2/repair_clouddrive_network.sh",
        "payload_clouddrive2/docker-compose.yml",
    ),
)


OPENLIST_PRODUCT = ProductProfile(
    key="openlist",
    display_name="OpenList",
    app_title="Telegram → 115 OpenList 部署器",
    app_version="1.0.0",
    executable_name="TG115-OpenList-Deployer",
    install_dir="/opt/tg115-openlist",
    backup_dir="/opt/tg115-openlist-backups",
    webdav_url="http://tg115-openlist:5244/dav/",
    webdav_username="tg115",
    webdav_target="/115/Telegram",
    management_port=5244,
    bot_service="tg115-bot",
    bot_container="tg115-openlist-bot",
    storage_container="tg115-openlist",
    docker_network="tg115-openlist-net",
    requires_fuse=False,
    managed_toggle=False,
    payload_variant="payload_openlist",
    required_payload=SHARED_PAYLOAD_FILES
    + (
        "payload_openlist/remote_install.sh",
        "payload_openlist/manage.sh",
        "payload_openlist/openlist_admin.sh",
        "payload_openlist/preserve_webdav_config.sh",
        "payload_openlist/docker-compose.yml",
    ),
)


PRODUCTS = {
    CLOUDDRIVE2_PRODUCT.key: CLOUDDRIVE2_PRODUCT,
    OPENLIST_PRODUCT.key: OPENLIST_PRODUCT,
}
