# 从 TG115 迁移到 TG2Cloud v1.0.2

TG2Cloud v1.0.2 默认按全新安装处理，**不提供自动原地迁移**。旧 TG115 目录或已停容器
单独存在时只提示，允许使用新的独立命名空间安装；不会接管、移动、覆盖、停止或删除旧资源。
若旧实例占用固定端口，或目标 TG2Cloud 目录/容器名已有不明归属，则停止并要求用户自行处理后
重新检测。检测到旧 Docker Network 时只提示，不会连接或修改该网络。

| Edition | 旧安装目录 | 新安装目录 | 新 Bot / 存储容器 / Network |
| --- | --- | --- | --- |
| CloudDrive2 | `/opt/tg115` | `/opt/tg2cloud-clouddrive2` | `tg2cloud-clouddrive2-bot` / `tg2cloud-clouddrive2` / `tg2cloud-clouddrive2-net` |
| OpenList | `/opt/tg115-openlist` | `/opt/tg2cloud-openlist` | `tg2cloud-openlist-bot` / `tg2cloud-openlist` / `tg2cloud-openlist-net` |

新备份目录分别为 `/opt/tg2cloud-clouddrive2-backups` 和
`/opt/tg2cloud-openlist-backups`。旧备份不会被新部署器读取、改名或清理。

## 迁移前

1. 在旧项目中确认队列已处理完毕，记录仍需保留的失败任务和下载文件。不要在同一 Bot Token
   上长期并行运行新旧实例，否则同一 Telegram 更新可能被两个 Bot 争抢。
2. 使用旧项目自己的备份流程，另行保存配置、SQLite 数据库、CloudDrive2/OpenList 状态和
   必要的下载文件，并验证备份可读取。备份必须留在用户控制的私有位置。
3. 记录 WebDAV 根目录、目标相对子目录和用户权限；网盘账号、OAuth、Token、Cookie 仍只在
   用户自己的 CloudDrive2 或 OpenList 后台管理，不要发给开发者或上传到 Issue。
4. 核对当前 VPS 的 `19798` 或 `5244` 固定管理端口。**同一 Edition 的新旧受管实例不能在
   同一 VPS 同时占用该端口**。不同 Edition 的端口、目录和网络彼此隔离，但仍须使用各自的
   Bot Token，或避免同时运行。

## 推荐做法

优先使用独立 VPS，按新目录重新部署 TG2Cloud，再由本人在 CloudDrive2/OpenList 中完成
云存储授权和 WebDAV 配置，执行真实 WebDAV 验收及小文件传输。验收完成前保留旧 VPS 和
完整备份，不要卸载旧项目。

如果必须复用同一 VPS，先在维护窗口内完成旧项目备份，并人工处理同 Edition 的固定端口
占用。旧目录和已停容器可保留，新部署器不会修改它们；运行中的旧容器若不占用所需端口，
也只提示而不接管。**端口 19798/5244 冲突会阻止对应 Edition 部署**，不会自动停掉旧容器或
改端口。不要仅仅把旧目录改名或手工移动数据库来欺骗检测。需要保留旧队列与状态时，
应先制定和验证逐项迁移及回滚步骤，再由操作者明确执行；这不属于 v1.0.2 自动部署流程。

TG2Cloud 的容器内 SQLite 文件名 `tg115.db` 及校验临时文件前缀暂时保留，属于稳定持久化/
清理边界，**不表示会自动导入旧数据库**。新机器状态只输出 `TG2CLOUD_*`，部署器解析器
优先读取它，并仅为旧脚本输出保留 `TG115_*` 兼容读取。新配置优先使用 `TG2CLOUD_*`
变量，同时保留必要的 `TG115_*` 环境别名，以免破坏已部署实例。不要把这些内部标记当作
安装目录或容器名称来手工替换。

新安装两版默认 `LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`，显式填写的值优先。
OpenList 新装默认 WebDAV 用户为 `tg2cloud`，旧实例的 `tg115` 用户只要凭据有效仍可使用；
不会自动改名或重设密码。目标子目录默认留空（即 WebDAV 用户根目录），也可由用户明确填写
`Telegram`、`Media/Telegram` 等相对路径；旧实例明确设置的路径不会被改写。

v1.0.2 不新增 restore 或 uninstall；请保留旧项目和独立备份，以便人工恢复。

TG2Cloud 的“重新部署”、`manage.sh update`、网络修复、状态和备份操作只面向当前
`/opt/tg2cloud-*` namespace。它们不会把 `/opt/tg115*` 原地升级为 TG2Cloud；只存在旧 TG115
而没有当前 TG2Cloud 时，状态会分别显示 “TG2Cloud 未安装” 与 “Legacy TG115 detected”。

本机 SSH 主机记录改存于 `%APPDATA%\TG2Cloud-Deployer\known_hosts`。旧
`%APPDATA%\TG115-Deployer\known_hosts` 不会自动导入或覆盖；第一次连接时应通过 VPS
服务商控制台重新核对主机指纹。

## 尚未验证的迁移路径

本仓库尚未在真实 VPS 上完成旧 TG115 到 TG2Cloud 的状态/队列迁移验收，也没有承诺可以
直接复制 `.env`、`rclone.conf`、SQLite 或存储服务数据目录。若这些数据需要延续，请保持
旧实例和备份可恢复，待有专门迁移方案及实测后再操作。
