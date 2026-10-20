# 从 TG115 迁移到当前 TG2Cloud

适用于当前 Linux v1.4.0，**不提供 TG115 自动原地迁移**。当所选 Edition 尚无完整 TG2Cloud 实例、但发现对应旧 TG115 容器或目录时，当前 CLI 会停止，不再按早期 EXE 的“只提示后继续安装”解释。它不会接管、移动、覆盖、停止或删除旧资源；部分实例和未知身份也会停止。

旧项目和当前 TG2Cloud 的升级不是同一件事。已经是完整官方 TG2Cloud 的实例按 [VPS](VPS-INSTALL.md#已有实例升级)／[LAN](LAN-INSTALL.md#已有实例与升级)升级，不套用本页迁移方案。

| Edition | 旧安装目录 | 新安装目录 | 新 Bot / 存储容器 / Network |
| --- | --- | --- | --- |
| CloudDrive2 | `/opt/tg115` | `/opt/tg2cloud-clouddrive2` | `tg2cloud-clouddrive2-bot` / `tg2cloud-clouddrive2` / `tg2cloud-clouddrive2-net` |
| OpenList | `/opt/tg115-openlist` | `/opt/tg2cloud-openlist` | `tg2cloud-openlist-bot` / `tg2cloud-openlist` / `tg2cloud-openlist-net` |

新备份目录分别为 `/opt/tg2cloud-clouddrive2-backups` 和 `/opt/tg2cloud-openlist-backups`。旧备份不会被新部署器读取、改名或清理。

## 迁移前

1. 在旧项目中确认队列已处理完毕，记录仍需保留的失败任务和下载文件。不要在同一 Bot Token 上长期并行运行新旧实例，否则同一 Telegram 更新可能被两个 Bot 争抢。
2. 使用旧项目自己的备份流程，另行保存配置、SQLite 数据库、CloudDrive2/OpenList 状态和必要的下载文件，并验证备份可读取。备份必须留在用户控制的私有位置。
3. 记录 WebDAV 根目录、目标相对子目录和用户权限；网盘账号、OAuth、Token、Cookie 仍只在用户自己的 CloudDrive2 或 OpenList 后台管理，不要发给开发者或上传到 Issue。
4. 核对当前 VPS 的 `19798` 或 `5244` 固定管理端口。**同一 Edition 的新旧受管实例不能在同一 VPS 同时占用该端口**。不同 Edition 的端口、目录和网络彼此隔离，但仍须使用各自的 Bot Token，或避免同时运行。

## 推荐做法

优先使用独立 VPS，按新目录重新部署 TG2Cloud，再由本人在 CloudDrive2/OpenList 中完成云存储授权和 WebDAV 配置，执行真实 WebDAV 验收及小文件传输。验收完成前保留旧 VPS 和完整备份，不要卸载旧项目。

必须复用同一 VPS 时，先在维护窗口完成可验证的旧项目备份，制定人工迁移和回退计划。当前脚本发现对应旧身份会停止；不要仅改旧目录名或搬 DB 来骗过检查。**端口 19798/5244 冲突也会阻止部署**，不会自动停止旧容器或改端口。需要延续队列、Session 或授权时，应在隔离环境先验证逐项转换，不直接复制覆盖新实例。优先选择独立主机，避免同时处理旧任务和新路径。

TG2Cloud 的容器内 SQLite 文件名 `tg115.db` 及校验临时文件前缀暂时保留，属于稳定持久化/清理边界，**不表示会自动导入旧数据库**。新机器状态只输出 `TG2CLOUD_*`，部署器解析器优先读取它，并仅为旧脚本输出保留 `TG115_*` 兼容读取。新配置优先使用 `TG2CLOUD_*` 变量，同时保留必要的 `TG115_*` 环境别名，以免破坏已部署实例。不要把这些内部标记当作安装目录或容器名称来手工替换。

新安装先选择资源方案：手动默认 `LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`，推荐值依实际资源。两版用户名提示默认 `tg2cloud`；旧受管实例显式账号不自动改名或重置。目标子目录默认留空，根目录由后台设置；字段和历史别名见[配置参考](CONFIGURATION.md)。

当前有[受管 TG2Cloud 卸载](UNINSTALL.md)，但不清理旧 TG115，也不提供自动生产 Restore。请另存[完整备份](BACKUP-RESTORE.md)，不要将“新项目能运行”当作“旧历史已迁移”。

当前管理和维护操作面向核验通过的 TG2Cloud namespace，不把 `/opt/tg115*` 原地升级。只有旧项目时按明确错误停止；早期界面中的 “Legacy TG115 detected” 是历史展示，不是当前 CLI 承诺的固定文本。

当前 Linux 脚本直接在目标主机运行，不内置 SSH 客户端；SSH 由你用于登录服务器，并按服务商控制台核对主机指纹。Windows `%APPDATA%` 主机记录仅属于[历史 EXE](README-小白使用说明.md)，不是 Linux 配置路径。

## v1.1.4 容器内部程序名称

v1.1.4 源码将两 Edition 共用 Bot 镜像的程序目录从 `/opt/tg115` 改为 `/opt/tg2cloud`，容器用户/组改为 `tg2cloud`，新日志使用 `tg2cloud` / `tg2cloud.log`。这只修改镜像内的公开程序与日志名称，不是宿主机 TG115 数据迁移，也不改已有宿主机安装目录、容器或网络名称。较早版本源码仍使用旧内部名称；下载新版部署器或更新入口不会自动更改 VPS。

容器 UID/GID 保持 `10001:10001`，继续使用原来的 `/data`、`/downloads`、`/logs`、`/config` 挂载。数据库 `/data/tg115.db` 和 Telegram `/data/bot.session` 不改名、不搬移；旧日志不删除。必要的 `TG115_*` 兼容变量、旧实例识别和校验临时文件前缀继续保留，避免丢失队列、登录状态或破坏回退。不要手工替换这些持久化标识。

## 尚未验证的迁移路径

本仓库尚未在真实 VPS 上完成旧 TG115 到 TG2Cloud 的状态/队列迁移验收，也没有承诺可以直接复制 `.env`、`rclone.conf`、SQLite 或存储服务数据目录。若这些数据需要延续，请保持旧实例和备份可恢复，待有专门迁移方案及实测后再操作。
