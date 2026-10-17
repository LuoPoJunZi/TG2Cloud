"""Immutable Edition identities and payload manifests for Linux deployment."""

from __future__ import annotations

from dataclasses import dataclass

from tg2cloud.version import VERSION as RELEASE_VERSION

SHARED_PAYLOAD_FILES = (
    "packaging/hooks/clouddrive2/backup_retention.sh",
    "packaging/hooks/clouddrive2/preserve_runtime_config.sh",
    "packaging/.dockerignore", "packaging/Dockerfile", "requirements/bot.lock.txt",
    "packaging/compat/app/__init__.py", "packaging/compat/app/main.py",
    "packaging/compat/app/deployment_check.py", "packaging/compat/app/healthcheck.py",
    "packaging/compat/app/backup_database.py", "packaging/compat/app/backup_bundle.py",
    "packaging/compat/app/verify_destination.py",
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
    legacy_install_dirs: tuple[str, ...]
    legacy_containers: tuple[str, ...]
    legacy_networks: tuple[str, ...]
    required_payload: tuple[str, ...]

    @property
    def is_openlist(self) -> bool:
        return self.key == "openlist"


CLOUDDRIVE2_PRODUCT = ProductProfile(
    key="clouddrive2",
    display_name="CloudDrive2",
    app_title="TG2Cloud · CloudDrive2",
    app_version=RELEASE_VERSION,
    executable_name="TG2Cloud-CloudDrive2-Deployer",
    install_dir="/opt/tg2cloud-clouddrive2",
    backup_dir="/opt/tg2cloud-clouddrive2-backups",
    webdav_url="http://tg2cloud-clouddrive2:19798/dav",
    webdav_username="",
    webdav_target="",
    management_port=19798,
    bot_service="tg2cloud-clouddrive2-bot",
    bot_container="tg2cloud-clouddrive2-bot",
    storage_container="tg2cloud-clouddrive2",
    docker_network="tg2cloud-clouddrive2-net",
    requires_fuse=True,
    managed_toggle=True,
    payload_variant="packaging/hooks/clouddrive2",
    legacy_install_dirs=("/opt/tg115",),
    legacy_containers=("tg115-bot", "tg115-clouddrive2"),
    legacy_networks=("tg115",),
    required_payload=SHARED_PAYLOAD_FILES
    + (
        "packaging/hooks/clouddrive2/remote_install.sh",
        "packaging/hooks/clouddrive2/manage.sh",
        "packaging/hooks/clouddrive2/repair_clouddrive_network.sh",
        "packaging/compose/clouddrive2.yml",
    ),
)


OPENLIST_PRODUCT = ProductProfile(
    key="openlist",
    display_name="OpenList",
    app_title="TG2Cloud · OpenList",
    app_version=RELEASE_VERSION,
    executable_name="TG2Cloud-OpenList-Deployer",
    install_dir="/opt/tg2cloud-openlist",
    backup_dir="/opt/tg2cloud-openlist-backups",
    webdav_url="http://tg2cloud-openlist:5244/dav/",
    webdav_username="tg2cloud",
    webdav_target="",
    management_port=5244,
    bot_service="tg2cloud-openlist-bot",
    bot_container="tg2cloud-openlist-bot",
    storage_container="tg2cloud-openlist",
    docker_network="tg2cloud-openlist-net",
    requires_fuse=False,
    managed_toggle=False,
    payload_variant="packaging/hooks/openlist",
    legacy_install_dirs=("/opt/tg115-openlist",),
    legacy_containers=("tg115-openlist-bot", "tg115-openlist"),
    legacy_networks=("tg115-openlist-net",),
    required_payload=SHARED_PAYLOAD_FILES
    + (
        "packaging/hooks/openlist/remote_install.sh",
        "packaging/hooks/openlist/manage.sh",
        "packaging/hooks/openlist/openlist_admin.sh",
        "packaging/hooks/openlist/preserve_webdav_config.sh",
        "packaging/compose/openlist.yml",
    ),
)


PRODUCTS = {
    CLOUDDRIVE2_PRODUCT.key: CLOUDDRIVE2_PRODUCT,
    OPENLIST_PRODUCT.key: OPENLIST_PRODUCT,
}
