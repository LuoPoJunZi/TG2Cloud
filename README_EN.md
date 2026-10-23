<p align="center">
  <img src="assets/brand/tg2cloud-logo.svg" alt="TG2Cloud — From Telegram to Your Cloud" width="520">
</p>

<p align="center">
  <strong>Telegram file transfer · CloudDrive2 / OpenList · Linux one-line deployment</strong>
</p>

<p align="center">
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/LuoPoJunZi/TG2Cloud?style=flat-square&amp;label=release&amp;color=1677ff"></a>
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/actions/workflows/tests.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/LuoPoJunZi/TG2Cloud/tests.yml?branch=main&amp;style=flat-square&amp;label=tests"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/github/license/LuoPoJunZi/TG2Cloud?style=flat-square&amp;color=22a06b"></a>
</p>

<p align="center">
  <a href="docs/VPS-INSTALL.md"><strong>Installation</strong></a> ·
  <a href="docs/README.md">Repository docs</a> ·
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/releases">Releases</a> ·
  <a href="https://tg2cloud.pages.dev/">Documentation website</a> ·
  <a href="README.md">简体中文</a>
</p>

TG2Cloud is a self-hosted personal file transfer tool. Send or forward files to your own Telegram Bot; your Linux host queues, downloads and writes them to cloud storage mounted by you.

Telegram → TG2Cloud → rclone → CloudDrive2 / OpenList WebDAV → your cloud storage

## Features

- Two editions share one Bot core while keeping separate configuration, databases and Sessions.
- Persistent queues, deduplication, confirmed cancellation recovery, retained failed files and caption-based naming.
- Regular downloads and large-file streaming with adaptive concurrency and disk protection.
- Public HTTPS / trusted LAN deployment, storage recommendations and configuration-preserving upgrades.

v1.4.2 adds [reuse of an existing Docker Nginx](docs/DOCKER-NGINX.md) with explicit authorization, without stopping it or adding a second proxy. The default managed mode is unchanged; see the prerequisites, certificate responsibilities and untested live scenarios in the guide.

Current stable version: **v1.4.4**, maintained through Linux scripts with native AMD64 / ARM64 support. Source archives and checksums are available in the [stable Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.4). Explicitly upgrade running instances; updating documentation does not upgrade the Bot. Windows deployers remain at [v1.2.1](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1). See the [historical v1.3.3 CloudDrive2 upgrade and user-confirmed transfer record](docs/development/V133-ACCEPTANCE.md); it does not certify the current version or other deployment or recovery scenarios.

User-provided logs dated 2026-10-23 confirm a CloudDrive2 v1.4.2 → v1.4.3 upgrade on Debian 13 AMD64: basic upgrade, Bot health, code/configuration and on-host HTTPS checks passed. See the [redacted log review](docs/development/V143-ACCEPTANCE.md) for build warnings and unverified file transfers, external access and rollback; the [v1.4.2 manual record](docs/development/V142-ACCEPTANCE.md) remains historical.

## Getting started

1. Prepare your Telegram Bot, API information and server using the [information checklist](docs/填写信息清单.md). Never put real credentials in public documents.
2. Choose CloudDrive2 or OpenList and either the public VPS or trusted LAN entry. Review the wizard's installation plan before confirming.
3. Mount cloud storage in your own gateway, then configure and verify WebDAV as described in the installation guide. You manage cloud-account authorization yourself.
4. Send or forward files to the Bot and check its receipt. See [task usage and recovery](docs/RECOVERY.md) for commands, failed tasks and verification levels.

Both editions share transfer capabilities but have different gateway configuration and independent instance data. Upgrade an existing instance through its matching entry, preserving configuration; do not uninstall first.

## Quick start

The public/LAN entries offer setup for a missing Edition or its maintenance menu for an existing instance. After confirming manager installation, run `tg2cloud` locally. Uninstall stays Edition-scoped; the standalone URL remains available for recovery. Menu, update and cleanup boundaries are in the [operations guide](docs/OPERATIONS.md#本地管理菜单).

Requires Debian / Ubuntu with native 64-bit userspace, root, Python 3.10+, curl and an interactive terminal, with access to GitHub, Telegram, container registries and the destination. CloudDrive2 also requires `/dev/fuse`.

Native AMD64 / ARM64 (`linux/amd64` / `linux/arm64`) are supported without QEMU. v1.4.1 fixes HTTPS preflight on public IPv4 NAT hosts; explicit mapping confirmation, certificate and HTTPS checks remain mandatory. The user completed a CloudDrive2 first install on Ubuntu 26.04.1 ARM64 behind public NAT, including on-host HTTPS and WebDAV verification. See the [acceptance record](docs/development/V141-ACCEPTANCE.md); it does not certify OpenList, upgrade rollback, external phone access or long-term renewal. See the [installation guide](docs/VPS-INSTALL.md) and [architecture evidence](docs/ARCHITECTURES.md).

### Public VPS

Prepare a domain pointing to the VPS and allow inbound TCP 80/443. Select CloudDrive2 or OpenList in the wizard:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

The wizard collects information, checks the environment and asks for confirmation. Business code comes only from official stable Releases. For an existing instance, first append `--edition clouddrive2 --check` (use `openlist` for OpenList). This check does not upgrade. Then rerun the entry without arguments, choose the Edition and installation/upgrade, and confirm to also install the offline manager. Explicit flags remain compatible. See the [VPS guide](docs/VPS-INSTALL.md).

### Trusted LAN / NAS

Without a public domain, use the separate LAN entry and enter the host's private IPv4. The Linux requirements above still apply; not every NAS OS is supported:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

LAN HTTP is unencrypted: do not expose it through public port forwarding or use it to bypass public HTTPS. See the [LAN guide](docs/LAN-INSTALL.md).

### Uninstall preview

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

This command only previews; it does not uninstall. Actual complete removal deletes the selected instance's data and recognized backups. To preserve data, use `--keep-data`; save independent backups outside the removal paths first. See the [uninstall guide](docs/UNINSTALL.md).

## Documentation

v1.4.4 adds classified installation logs, evidence-based upgrade/acceptance summaries and a shallower management menu. No new dependencies or database migrations. v1.4.3 introduced optional features and schema 2. Back up before the schema 2 migration; rollback requires matching old code and a verified old database snapshot. See [release notes](RELEASE_NOTES.md). The logs above concern v1.4.3 only; v1.4.4 live upgrades, transfers and rollback remain unverified.

See the [v1.4.3 maintenance improvements](docs/development/MAINTENANCE-IMPROVEMENTS.md) for trusted historical baselines, instance snapshots, readiness checks and naming previews. Explicitly upgrade the Bot and offline management tools.

[Optional enhancements](docs/FEATURE-ENHANCEMENTS.md) in v1.4.3 add classification, administrator alerts, member quotas and redacted reports. Classification/alerts default off; members default unlimited. Back up before the schema 2 database migration.

Optional add-on: [External WebDAV](docs/external-webdav.md). Available since v1.3.1: separately installed, read-only HTTPS access to an existing upload directory with an independent native account, an online installer and offline maintenance commands.

Browse the repository guides by topic below. Most are in Chinese; see the [full documentation index](docs/README.md) or the [documentation website](https://tg2cloud.pages.dev/).

Since v1.3.3, [family sharing](docs/FAMILY-SHARING.md) provides post-install Bot grants and independent read-only WebDAV accounts for the same shared directory. Installation still takes one administrator ID. Version 1.3.4 improves URL-polluted names, individual image captions and shared stems for a cover/video pair. See the [naming guide](docs/NAMING.md) for priorities and limits. Existing instances and offline managers require an explicit upgrade.

| Topic | Repository documents |
| --- | --- |
| Installation and configuration | [Public VPS installation / upgrade](docs/VPS-INSTALL.md) · [LAN / NAS installation](docs/LAN-INSTALL.md) · [Information checklist](docs/填写信息清单.md) |
| Gateway and first transfer | [CloudDrive2 / OpenList configuration and verification](docs/STORAGE.md) · [Bot usage, menus and commands](docs/BOT-USAGE.md) |
| Naming and common questions | [Video, caption and album naming](docs/NAMING.md) · [FAQ](docs/FAQ.md) |
| Configuration and backups | [Configuration fields and runtime paths](docs/CONFIGURATION.md) · [Backup scope and restore preflight](docs/BACKUP-RESTORE.md) |
| Family and mobile reading | [Bot family grants](docs/FAMILY-SHARING.md) · [Read-only external WebDAV](docs/external-webdav.md) |
| Operation and troubleshooting | [Management commands, logs and HTTPS maintenance](docs/OPERATIONS.md) · [Task recovery, verification and backup](docs/RECOVERY.md) |
| Upgrade acceptance | [v1.4.2 manual upgrade and verification limits](docs/development/V142-ACCEPTANCE.md) · [v1.3.3 official upgrade and transfer confirmation](docs/development/V133-ACCEPTANCE.md) · [v1.3.0 historical migration](docs/development/V130-ACCEPTANCE.md) |
| Uninstall and migration | [Uninstall guide](docs/UNINSTALL.md) · [Migration from TG115](docs/MIGRATION_FROM_TG115.md) |
| Development and tests | [Contributing](.github/CONTRIBUTING.md) · [Repository structure](docs/development/REPOSITORY.md) · [Linux architecture and compatibility](docs/development/LINUX-REFACTOR.md) |
| Versions and releases | [Complete version history](CHANGELOG.md) · [Current release notes](RELEASE_NOTES.md) |
| Historical Windows edition | [v1.2.1 GUI deployment guide](docs/README-小白使用说明.md) · [Script-first maintenance and desktop freeze](docs/development/SCRIPT-FIRST.md) |
| Branding and components | [Brand guide](docs/development/BRAND-GUIDE.md) · [Third-party components](docs/第三方组件说明.md) |

## Boundaries

- Transfer only content you are authorized to save. No automatic channel monitoring or protection bypass. 115 is an example, not the only destination.
- Cloud authentication stays in your own CloudDrive2 / OpenList instance. TG2Cloud has no telemetry or credential callback.
- WebDAV size verification is not a content hash or an official cloud-provider completion result. Verify important files independently.
- Never publish tokens, passwords, Sessions, databases, configuration or backups. Back up before upgrading; never overwrite a newer instance with an old EXE. See [Security](.github/SECURITY.md).

## Acknowledgements and Project Origin

<table>
  <tr>
    <td align="center" width="50%">
      <a href="https://github.com/LuoPoJunZi">
        <img src="https://github.com/LuoPoJunZi.png?size=96" width="72" alt="LuoPoJunZi"><br>
        <strong>LuoPoJunZi</strong>
      </a><br>
      <sub>TG2Cloud maintainer</sub>
    </td>
    <td align="center" width="50%">
      <a href="https://github.com/whyhhh20">
        <img src="https://github.com/whyhhh20.png?size=96" width="72" alt="whyhhh20"><br>
        <strong>whyhhh20</strong>
      </a><br>
      <sub>Original author of upstream TG115</sub>
    </td>
  </tr>
</table>

Thanks to **whyhhh20** for creating and publishing the upstream [TG115 project](https://github.com/whyhhh20/TG115).

TG2Cloud evolved from that project, retains the MIT license, original copyright, and required attribution, and continues to improve the reliability, deployment safety, and operational experience of the Telegram → rclone → CloudDrive2/OpenList → user-owned-cloud path.

Thanks also to Telethon, rclone, Docker, Paramiko, and the other open-source projects involved, and to CloudDrive2 for its WebDAV and cloud-mount features. Each third-party component remains subject to its own license and terms.

## License and Disclaimer

This project is licensed under the [MIT License](LICENSE).

TG2Cloud is not affiliated with, authorized by, or officially partnered with Telegram, CloudDrive2, OpenList, any cloud-storage provider, or their operators. Users are responsible for evaluating account, data, network, VPS privilege, and third-party closed-source component risks.
