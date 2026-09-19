# TG115 项目记忆

> 最近复核：2026-09-19
> 复核基线：`main` / `2529cdc` / CloudDrive2 正式版 `v1.6.2`
> 当前工作树：OpenList 产品线开发中，尚未提交、推送或发布；用户提供的需求原文保持未跟踪
> 当前应用版本：CloudDrive2 `1.6.2`；OpenList 首版内部版本 `1.0.0`（未发布）
> GitHub 目标：`LuoPoJunZi/TG115`；原作者仓库：`whyhhh20/TG115`
> 用途：供后续 Codex/Agent 快速恢复项目上下文。源码、测试和当前用户要求优先于本文件。

## 1. 项目目标与边界

TG115 是个人自建的 Telegram 文件转存工具，由 Windows 图形化部署器把服务部署到 VPS。
当前开发方向提供两个彼此独立的 PySide6 产品入口，运行时链路为：

```text
Telegram 私聊 Bot
  -> Telethon
  -> SQLite 持久队列
  -> 普通文件落盘，或大文件直接流式传输
  -> rclone WebDAV
  -> CloudDrive2 或 OpenList
  -> 用户挂载的 115 网盘
```

仓库没有 115 官方 API/SDK 集成。Bot 只能证明所选 WebDAV 目的端接收了同样大小的文件，
不能证明内容哈希绝对一致，也不能证明 115 官方端已经入库。任务的 `completed` 表示 Bot
传输完成；历史 `confirmed` 状态和 `/confirm` 处理器为数据库兼容保留，但不再出现在菜单、
帮助、完成通知或任务展示中，用户界面将两者统一显示为“Bot 完成”。

当前支持对象是配置用户与 Bot 的一对一私聊。v1.6.x 同时校验允许用户 ID 和
`event.is_private`，群组和频道消息即使由本人发送也不会接收。

OpenList 版使用 `/opt/tg115-openlist`、`tg115-openlist`、`tg115-openlist-bot`、
`tg115-openlist-net` 和 5244 固定隧道，与 CloudDrive2 版完全隔离。115 Open 授权由用户在自己
的 OpenList 后台完成，部署器不读取 115 Cookie/Token。基础部署与最终 WebDAV 真写验收分开。

## 2. 两层架构

### Windows 部署层

- `installer.py`：共用 PySide6 GUI 与 Paramiko SSH/SFTP 后端；首次连接核对主机指纹；已记录
  密钥变化时显示当前目标及旧／新类型和 SHA-256 指纹，用户明确确认后只原子替换当前主机与
  端口记录并自动重试原操作一次；取消不修改记录；生成 Base64 配置；
  上传 payload；调用远端安装/修复/验收；通过固定本机 `127.0.0.1:19798` 的 SSH 隧道打开
  CloudDrive2 管理页。打开浏览器前必须通过隧道收到真实 HTTP 响应，旧隧道失效后自动重建；
  SSH 禁止转发或本机端口占用时明确失败，不回退随机端口。测试 SSH 和正式部署前都会读取
  当前 VPS 资源，建议值必须由用户主动应用。
- `installer_clouddrive2.py`、`installer_openlist.py`：两个对称的独立 PySide6 产品入口；
  `deployer_products.py` 固化两个产品的目录、容器、网络、端口、版本和 payload 清单，
  不在同一 EXE 内提供后端选择。
- `vps_resources.py`：生成经安装路径校验的只读 SSH 探测命令，严格解析版本化结果；结合
  CPU、内存、目标／Docker 文件系统、inode、既有占用和 FUSE 给出均衡／流式优先存储建议，
  并校验最终选择。优先使用 `docker info` 的实际数据目录，无权限时回退 `/var/lib/docker`
  估算；非 root 部署用户通过现有 sudo 凭据执行只读探测，目录统计失败不会当成 0。远端
  安装脚本在提权后再次权威复核。源码默认 20/20GB 不受实例探测影响。
- `build.ps1`：支持 `-Edition All|CloudDrive2|OpenList`，只生成
  `dist/TG115-CloudDrive2-Deployer.exe` 和／或 `dist/TG115-OpenList-Deployer.exe`；后者同时
  内嵌 `payload_clouddrive2/` 与专属 `payload_openlist/`。OpenList 构建复用前者中的中性 Bot
  运行代码，再用自己的 Compose 和运维脚本覆盖远端安装包。分析二进制依赖前临时隔离 `PATH`，避免
  构建机其他软件的同名 DLL 污染成品。
- 构建依赖：`paramiko==5.0.0`、`PySide6==6.11.2`、`pyinstaller==6.21.0`。

部署器不保存表单密码，只在 `%APPDATA%/TG115-Deployer/known_hosts` 持久化已确认的 SSH
主机密钥。Base64 和 rclone obscure 都只是编码/混淆，不是加密；VPS root 可读取 `.env`
与 rclone 配置。

### VPS 运行层

- `payload_clouddrive2/remote_install.sh`：Ubuntu/Debian 安装入口，准备 Docker、目录、备份、构建及启动。
- `payload_clouddrive2/docker-compose.yml`：运行 `tg115-bot` 与可选受管 `clouddrive2`。
- `payload_clouddrive2/Dockerfile`：Python 3.12 slim，安装 rclone/tini，入口 `python -m app.main`。
- `payload_clouddrive2/repair_clouddrive_network.sh`：兼容 CloudDrive2 bridge/host/container 网络模式并做
  真 WebDAV 验收；无法识别的 19798 端口占用会拒绝自动修改。
- `payload_clouddrive2/manage.sh`：`status|logs|restart|stop|start|update|verify|check|doctor|validate|ready|backups|prune-backups|apply-config`。
  `apply-config` 接收新配置，备份、预检、更新 Bot 并核对配置／代码／健康；失败或可捕获中断
  恢复旧配置，恢复失败明确报错。推荐输入配置放在安装目录外。`restart` 不应用配置变化。
- `payload_clouddrive2/backup_retention.sh`：只读盘点三类升级备份；显式清理时只删除匹配固定命名的普通
  文件，并按程序配置、数据库、环境配置和 OpenList 状态四类分别保留最近 N 份（N 为 1～50）。
- `payload_openlist/`：OpenList 独立 Compose、安装、管理与管理员恢复脚本；管理端口只映射
  `127.0.0.1:5244`，Bot 仍保持非 root、只读根文件系统和最小权限。PySide6 日常管理已接入
  状态、最近脱敏日志、分别重启 Bot／OpenList、手动一致性备份和带二次确认的管理员密码恢复；
  恢复密码不经过普通日志流，只写回当前窗口的遮罩字段。

VPS 预期为 Ubuntu/Debian、x86_64/ARM64、root 或 sudo、Docker Compose v2；受管
CloudDrive2 必须有 `/dev/fuse`。安装脚本硬检查约 1.8GB 内存和安装文件系统 8GB 可用空间，
50GB 总盘只是推荐值。现在空间检查针对实际安装目录所在文件系统；Windows 部署器会在任何
远端写入前按最终预算／保留线执行更严格的实例容量复检。部署会修改 APT/Docker 状态，且
依赖 Docker/PyPI/Telegram 网络。

持久数据默认位置：

| 数据 | 容器路径 | 宿主安装目录 |
| --- | --- | --- |
| SQLite、Telethon 会话、heartbeat | `/data` | `data/` |
| 普通下载和临时文件 | `/downloads` | `downloads/` |
| 轮转日志 | `/logs` | `logs/` |
| rclone 配置 | `/config/rclone/rclone.conf` | `config/rclone/` |
| CloudDrive2 配置/挂载 | `/Config`、`/CloudNAS` | `clouddrive/` |

重新部署先在隔离目录构建镜像并预检配置，再备份旧配置代码到
`/opt/tg115-backups/config-*.tar.gz`；通过 SQLite Backup API 另存完整性已校验的
`database-*.db` 一致性快照。新 Bot 的健康、CloudDrive2 网络或运行配置／代码核验失败时，
自动恢复旧程序、配置、数据库和旧镜像。downloads、logs 和 clouddrive 不复制进升级备份，
配置更新备份为 `env-*.env`。部署只统计备份占用，超过 5GB 时提示，不自动删除；用户核对后
可运行 `manage.sh prune-backups N`，按三类各保留最近 N 份。`manage.sh update` 只重建已部署
的本地 payload，不会执行 Git 拉取。

## 3. 服务端模块职责

- `payload_clouddrive2/app/main.py`：`TransferService` 的 Telegram 入站、资源／调度循环、普通／流式传输、
  通知和生命周期；通过 mixin 组合命令能力，仍是传输状态机的主要改造热点。
- `payload_clouddrive2/app/bot_commands.py`：Bot 命令路由、任务／系统状态展示、重试／取消及带二次确认的
  远端遗留临时文件清理。清理计划只在进程内保留 5 分钟，一次最多 100 项。
- `payload_clouddrive2/app/db.py`：SQLite tasks 表、旧库字段迁移、消息/媒体去重、原子预算预留、查询、
  更新、人工确认和重启恢复。使用 WAL、`synchronous=FULL`、`BEGIN IMMEDIATE`。
  当前 `PRAGMA user_version=1`；增加 `service_meta`（暂停）、`task_events`（状态历史），
  任务有 `remote_temp_path`、`remote_final_path`、`cancel_requested`，保留旧 `remote_path` 兼容字段。
- `payload_clouddrive2/app/rclone_client.py`：创建/更新受控 WebDAV remote，封装 `copyto`、`rcat`、
  `size`、`lsjson`、`moveto`、`deletefile`；流对象用异步 `drain()` 向 Telethon 提供背压。
- `payload_clouddrive2/app/resources.py`：采集 CPU、可用内存、swap、磁盘和容器可见的汇总网络速率；
  并发反馈使用阶段吞吐和活动数量，包含增长冷却、收益试探与下载积压抑制。
- `payload_clouddrive2/app/config.py`：环境变量解码、类型/阈值校验和目录创建。
- `payload_clouddrive2/app/naming.py`：清理危险文件名；后缀最多 24 UTF-8 bytes，总名控制在约 180 bytes。
- `payload_clouddrive2/app/verify_destination.py`：真写 256B 随机文件，检查大小、改名、复验并清理。
- `payload_clouddrive2/app/healthcheck.py`：资源和调度双心跳均须小于 90 秒，且不早于当前容器 PID 1
  的启动时间；不代表 WebDAV 或 115 健康。
- `payload_clouddrive2/app/states.py`：集中状态文案与本地额度归属；DB update 拒绝未知状态／模式。
- `payload_clouddrive2/app/interfaces.py`：媒体来源、目的端与上传流协议；服务可注入适配器，默认仍为
  Telethon Bot 与 CloudDrive2 WebDAV，不代表已内置多来源监听。
- `payload_clouddrive2/app/deployment_check.py`：不输出配置值地校验环境与应用代码指纹；预检不创建目录。
- `payload_clouddrive2/app/backup_database.py`：用 SQLite 在线 Backup API 创建一致性快照并执行
  `PRAGMA quick_check`，升级脚本在停止旧 Bot 后用它保存回退点。

## 4. 任务状态机与数据一致性

主路径：

```text
queued -> reserved
  -> downloading -> downloaded -> waiting_upload -> uploading
  -> streaming
  -> verifying -> finalizing -> cleanup_pending -> completed -> confirmed
```

失败/终止状态：`download_failed`、`upload_failed_retained`、
`verification_failed_retained`、`cancelled`。

关键行为：

1. 新媒体先持久化为 `queued`；`UNIQUE(chat_id, message_id)` 和条件唯一索引
   `UNIQUE(sender_id, media_key)` 避免重复任务。
2. 调度器每秒分页扫描队列；资源独立每 3 秒采样，远端独立每 30 秒探测（总超时 30 秒）。
   采样过期、目的端失败或暂停时不启动新传输；普通上传和流式任务共享上传窗口。
3. `TaskDB.reserve()` 用 `BEGIN IMMEDIATE` 原子检查本地预算和真实磁盘安全线。前方大文件
   暂时受阻时仍继续扫描后方小文件。
4. 普通模式下载到 `<task-id>.part`，校验本地大小，先把确定的最终路径写进 DB，再
   `os.replace()`，以便在改名后崩溃时恢复。
5. 普通上传先 `copyto` 到 `.uploading-*`，检查大小，加锁选择不冲突的正式名，并同时持久化
   临时与正式路径意图，`moveto` 后再查大小。排除其他任务已预留的正式路径。
   然后先记录 `cleanup_pending`，再删本地副本并记 `completed`。
6. 单文件大于本地预算时自动设为 `transfer_mode=stream`；Telethon 直接写入
   `rclone rcat --size`。流式模式不保留完整本地副本、不占完整本地任务额度，失败通常从头
   重传；若重启后记录的远端文件存在且大小正确，则继续收尾。
7. 普通上传失败保留本地完整文件；`/retry` 优先重试上传，本地文件丢失时回到下载队列。
8. 磁盘触线会停止活动下载、删除不完整文件并重新排队；已有完整本地文件的上传仍可继续，
   以释放空间。
9. `/cancel` 采用 fail-closed：先持久化取消意图阻止调度，停止协程，删除并复查临时与正式
   远端路径，再删本地/part，最后写 `cancelled`。远端清理失败时保留路径、本地数据和取消
   意图；重启不会自动恢复这些任务。清理进行中不能 /retry 抢占；失败后可单独 /retry 撤销意图。

修改状态时必须同步核对 `states.py` 的 `STATE_LABELS`、`LOCAL_STATES`、`GROWING_STATES`，
`main.py` 的调度/通知、`bot_commands.py` 的命令与展示、`db.py` 的额度计算/恢复/迁移，
以及相关回归和集成测试。
`states.py::LEGAL_TRANSITIONS` 是持久状态合法边的唯一事实来源；运行主路径通过
`TaskDB.transition()` 在同一 `BEGIN IMMEDIATE` 事务内检查旧状态并写入新状态。DB 内部的
额度预留、恢复和人工确认仍使用各自的原子事务。

## 5. 用户命令与主要流程

Bot 对外命令：`/start`、`/help`、`/queue [page]`、`/status`、`/performance`、`/task <id>`、
`/retry <id|all>`、`/cancel <id>`、`/pause`、`/resume`、`/doctor`、
`/watch <id>`、`/stream <id>`、`/orphans`、`/orphans clean [一次性确认码]`。
暂停跨重启保存，活动任务继续，已校验任务仍可清理。批量重试最多 100 个且排除未完成的取消。
旧 `/confirm <id|all>` 处理器仅为已部署实例和历史数据库兼容保留，不在帮助和日常流程中宣传；
`/stream` 可将排队或下载失败任务改为流式模式；`/orphans` 只读列出疑似遗留临时文件的任务号，
不显示原文件名。`/orphans clean` 生成 5 分钟有效的一次性确认码，携码二次确认时重新巡检，
保护活动任务编号和已记录路径，逐项删除后复查；一次最多 100 项。`/watch` 每 5 秒尝试编辑
同一条消息，重启需重新订阅。进度与速度不是 115 入库进度。

`/start`、`/help`、`/status`、`/queue`、`/task` 和 `/doctor` 使用四字字段名的单页界面。
未发布改动把主页快捷按钮迁移到 Telegram 输入框左侧原生命令菜单，菜单包含 `status`、
`queue`、`pause`、`resume`、`doctor`、`orphans`、`help`，说明统一为 6 个中文字符。新的 Bot
回复不附加 Inline Keyboard；`/queue` 使用页码参数翻页，任务查看／重试／流式／取消继续使用
带编号文字命令。旧消息按钮的回调实现为兼容保留，仍执行原有私聊与用户鉴权。快捷临时巡检
只读，清理仍使用一次性确认码。

首次部署：填写 VPS/Telegram/WebDAV -> 测试 SSH 并查看实例建议 -> 按需主动应用建议 ->
一键部署前重新探测和容量校验 -> 用 SSH 隧道打开
CloudDrive2 -> 用户登录并挂载 115、开启 WebDAV -> 执行真写入验收。

日常使用：发送或转发文件 -> 获得任务号 -> 自动传输 -> Bot 报告 CloudDrive2 接收完成。
是否再到 115 官方客户端检查由用户自行决定，Bot 不再要求逐个或批量人工确认。

### 已知使用方式全景

项目实践中存在多种使用和部署方式。后续讨论需求时，先确认用户指的是哪一种：

1. **Windows 图形化一键部署**：直接运行对应产品的 EXE，由 `installer.py` 通过 SSH/SFTP 把
   产品 payload 部署到 VPS。这是面向普通用户的主部署入口。
2. **VPS 手工源码部署**：直接下载固定版本源码，手工生成配置文件，再调用
   `payload_clouddrive2/remote_install.sh`。博客中的真实 TG115 实例采用此方式；它仍然运行当前仓库的
   `tg115-bot` 与 CloudDrive2，只是绕过了 Windows GUI。
3. **手动选择、自动转存**：用户在 Telegram 频道或聊天中挑选文件，手动转发给私人 Bot；
   TG115 负责鉴权、持久排队、下载或流式写入、WebDAV 校验、重试、清理和状态查询。这是
   当前仓库原生、正式支持的日常用法。
4. **普通落盘模式**：文件不超过本地预算时，先完整下载到 VPS，上传失败可保留本地副本。
   这是 TG115 内部自动选择的传输方式，不需要用户手工切换。
5. **大文件流式模式**：单文件超过本地预算时，Telethon 通过 `rclone rcat` 边读边写，避免
   保存完整本地副本；中断通常要从头重传。这同样是 TG115 原生传输方式。
6. **频道自动监听组合方案**：在同一 TG115 使用场景和服务器部署体系中，保留 TG115 Bot
   处理手动选择文件，同时使用 `tg-rclone` + Telethon 用户 Session 自动监听指定频道；上传
   端可实验 OpenList WebDAV 或 115cli。用户将其视为 TG115 项目的一种组合使用方法，应予以
   记录，不能简单说成“与 TG115 无关”。但自动监听、用户 Session、OpenList 和 115cli 当前
   尚未实现于本仓库源码，不能误写成 `tg115-bot` 已内置功能。
7. **历史频道批量归档**：使用 `tg-archiver` 等工具批量下载历史媒体，再通过 rclone/115cli
   分批上传；适合一次性搬运，不是当前 TG115 队列的原生入口。可与 TG115 日常转存并存。
8. **双节点转存**：Telegram 下载节点与 115 上传节点分离，中间通过 rsync/SFTP/rclone SFTP
   传递。适合单台 VPS 无法同时获得良好 Telegram 与 115 线路的情况，代价是部署和恢复更复杂。
9. **管理入口方式**：CloudDrive2 默认通过 Windows 部署器建立的 SSH 隧道访问；也可在 VPS
   外加 Nginx + HTTPS。后者只保护管理入口，TG115 数据链仍走 Docker 内网 WebDAV。

其中第 1-5 项是当前仓库直接提供的能力；第 6-9 项是围绕当前 TG115 实例形成的组合、扩展
或运维方法。未来可以选择把部分扩展正式纳入代码，但在实施前必须明确产品范围和兼容策略。

## 6. 配置联动

核心配置由 `installer.py::_build_config()` 生成，`Settings.from_env()` 消费。必填项包括
Telegram API ID/Hash、Bot Token、允许用户 ID、WebDAV URL/用户名/密码；目标相对子目录
可空。重要默认值：

| 设置 | 默认值 |
| --- | ---: |
| 本地任务预算 | 20 GB |
| 磁盘最少保留 | 20 GB |
| 控制循环 | 3 秒 |
| CPU low/high/pressure | 60/80/90% |
| 内存 soft/hard | 1024/512 MB |
| 最大重试 | 3 |
| 远端健康检查 | 30 秒 |
| 时区 | Asia/Shanghai |

Windows 部署器的实例建议不是新配置项，也不改变这些源码默认值。均衡模式的本地预算上限
20GB；流式优先上限 8GB；磁盘保留线按目标文件系统总量的 20% 计算并限制在 8～20GB。
建议会给现有 downloads 保留额度，并预留 3GB 升级空间或新装受管 CloudDrive2 的 6GB 空间。
正式部署仍按用户最终输入和当时实际可用空间复检。

新增配置必须同步 GUI 字段、输入验证、`_build_config()`、`Settings`、Compose/脚本、文档和
测试；新增 payload 模块还要同步打包自检文件清单。

## 7. 安全与第三方边界

- `tg115-bot` 以 UID/GID 10001 运行，根文件系统只读，drop 全部 capabilities，启用
  `no-new-privileges`。
- CloudDrive2 是闭源组件，为 FUSE 使用 `privileged: true`、`pid: host` 和 `/dev/fuse`；
  推荐使用独立 VPS，不与钱包、数据库等重要工作负载共用。
- 19798 只绑定宿主机 `127.0.0.1`，管理页通过 SSH 隧道打开。
- 20GB 预算只约束 Bot 普通落盘任务，不约束 CloudDrive2 内部缓存；真实磁盘安全线是兜底。
- 远端只做大小校验，没有内容 hash；大文件流式模式不能断点续传。
- Python 顶层依赖固定了版本但没有哈希/完整传递锁；apt 包未锁版本，因此重建并非完全可复现。

## 8. 测试与交付基线

仓库当前共有 202 个 `unittest` 测试方法；覆盖核心、场景、优化、部署脚本、VPS 实例建议、
备份保留和 WebDAV 集成。
完整命令：

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

CI 还执行 Ruff 0.16.0、Bandit 1.9.4、pip-audit 2.10.1、两个 PySide6 Windows EXE 打包自检、Linux
ShellCheck、Compose 校验和 Bot 镜像构建。生产级改变最终还要在真实 VPS/Telegram/
CloudDrive2/115 环境验收。

2026-09-13 在项目隔离 `.venv` 中补齐锁定依赖：原始 HEAD 导出后的 75 项测试通过；
第一阶段 120 项测试全部通过，无跳过，包括 Git Bash 模拟故障回退、真实本地 rclone 1.75.1／
回环 WebDAV 及子进程取消／超时。Ruff、Bandit、ShellCheck、两份 requirements 的 pip-audit
通过。Windows EXE 已构建并通过 payload 和隐藏 GUI 运行时自检。
2026-09-14 增加 VPS 资源／存储建议、Docker 分盘校验和显式备份保留后，154 项测试全部
通过且无跳过，包含 4 项真实本地
rclone 回环 WebDAV；EXE 自检现在会完整构造部署器界面，不再只创建空白 Tk 根窗口。
本机 Python 的 Tcl/Tk 路径发现异常，构建时仅以进程级环境变量指向现有库，没有更改系统安装；
build.ps1 现有预检可阻止再次生成缺少 GUI 运行时的产物。
本机缺少 Docker 和 Linux 环境，Compose 校验、镜像构建及 Linux Python 3.12 实跑尚未完成；
CI 已补 Linux 3.12 全量回归。真实 VPS／Telegram／CloudDrive2／115 验收仍待用户环境完成。

2026-09-18 OpenList 第一批实现后，187 项完整回归通过，其中 4 项真实本地 rclone WebDAV
因当前机器缺少 rclone 明确跳过；Ruff、Bandit、ShellCheck、Bash 语法和工作流 YAML 检查通过。
两个 PySide6 EXE 已本地构建并通过 GUI／后端／payload 自检：CloudDrive2 为 51,953,986 bytes，
SHA-256 `F7BBE381E4D3F8069EF6B8EDC2A2D3A169D8A21D9DDDD76899E39BCFC764E11E`；OpenList 为
51,965,305 bytes，SHA-256 `87E047AB9C58EA470F5A641E73EDB9AD63C08875163CA3E57DBFEB767BAD7925`。
这些是未提交工作树的本地候选，不是正式发布附件；真实 VPS/OpenList/115 验收仍待完成。

2026-09-18 OpenList 第二阶段管理闭环完成后，完整回归为 193 项通过、4 项因本机缺少 rclone
明确跳过；Ruff、Bandit、ShellCheck 和 Bash 语法检查通过。最终 WebDAV 验收在界面按 Bot、
认证、目录、写入、大小、改名和清理七项展示“通过／失败／未执行”。手动备份会短暂停止两个
服务以复制一致的 OpenList 状态，之后自动启动并执行 OpenList HTTP 与 Bot 健康检查。
本阶段两个 EXE 已重建并自检：CloudDrive2 为 51,963,362 bytes，SHA-256
`014DD7B242712DF2830FF8441C47F4BFB0BBD6DD05F56CFA854E4575A32EB8FD`；OpenList 为
51,973,948 bytes，SHA-256 `65B8DFE154D1BAE40FF5D8AA0C851313F290E6FFE48FD4BFC5727A48A5790339`。

2026-09-19 OpenList 第三阶段补齐已有实例与最终验收体验：已有实例部署后隐藏无效的首次
管理员凭据，显式恢复后只在当前遮罩输入框显示新密码；最终验收增加 OpenList 服务阶段，
并按认证、目录、写入、大小、改名和清理失败给出不泄露远端原始响应的友好主提示。完整回归为
194 项通过、4 项因本机缺少 rclone 明确跳过，Ruff、Bandit 和 ShellCheck 通过。两个 EXE
已重建并自检：CloudDrive2 为 51,962,051 bytes，SHA-256
`D922E0918F05CCB93169A04996E107A4D0D1B779377E04D9B03C626DA5663B2A`；OpenList 为
51,972,722 bytes，SHA-256 `EA8D941F6D9CA3243584FE9FA0A4C3010E94F48D45759FD3F31F681EE4D6756C`。

## 9. 已知问题与后续候选方向

当前边界和待办：

- 已修复私聊限制、旧测试数量文档、监控耦合、过期采样放行与取消意图缺失。
- 已拆分远端路径，但保留 `remote_path` 兼容旧记录；新扩展应使用显式字段，不再增加前缀推断。
- 定时健康探测仅 lsd（子目录不存在时可检查 WebDAV 根），结构化区分目标目录与根目录，
  不写远端；真写、改名、删除仍在主动验收流程完成。状态文字不把目录访问成功说成“可写”。
- 命令与状态展示已经从 `main.py` 拆到 `bot_commands.py`；`main.py` 仍集中调度、通知和两种
  传输状态机，后续重构宜继续小步进行，不应一次性重写。
- 博客记录过旧凭据现象且 force-recreate 后恢复，但不能单凭没有该标志认定脚本根因；
  Compose up 原本就支持配置变化时重建。本轮新增运行环境和代码指纹核验以及配置失败回退。
- VPS 建议不会发现、格式化、挂载或迁移到独立数据盘；Docker 数据目录优先从当前 Docker
  读取，SSH 用户无访问权限时界面按默认 `/var/lib/docker` 估算，但正式部署会在提权并启动
  Docker 后读取实际目录、复查两个文件系统。需要迁移独立盘时仍须用户明确挂载和确认目标。
- 未实现内置频道用户会话、完整多来源游标、无人值守自动删除远端遗留临时文件
  或内容哈希验证。已有显式二次确认的遗留临时文件清理和显式备份保留；磁盘长期不足时已有人工
  `/stream`，但没有基于等待时长的自动回退。
  不要把协议注入或本机集成测试表述成这些功能已完成。

可选演进方向：在现有接口上接入频道来源、继续拆分传输状态机、结构化日志/metrics、
目标路由与更强校验。任何抽象
都必须先保住现有的事务额度、崩溃恢复、取消清理和 `completed`/`confirmed` 语义。

## 10. 外部部署实录与运维经验

2026-09-13 阅读并核对以下两篇公开、已脱敏的实际记录：

- `https://blog.luopojunzi.com/p/tg115-1/`：TG115 v1.5.0 + CloudDrive2 直接部署。
- `https://blog.luopojunzi.com/p/tg115/`：频道自动监听、OpenList/115cli 和线路诊断的替代方案。

### TG115 直接部署记录

- 已验证环境为 Ubuntu 24.04 x86_64、2 核、约 2.4 GiB 内存、约 1.2 GiB Swap、39 GB
  系统盘。它低于推荐规格但可以保守运行；文章部署时使用 8 GB 本地预算和 8 GB 磁盘安全线。
  这些是某一实例的初始值，不应覆盖项目默认的 20/20 GB，也不能当作所有小 VPS 的保证。
- 该实例走“VPS 手工执行 payload”路径：源码位于 `/root/TG115-src`，原始配置为
  `/root/tg115-config.env`，安装目录为 `/opt/tg115`。官方 Windows GUI 是另一层封装；排查
  该实例时要同时区分原始配置文件、已安装 `.env` 和容器当前实际环境。
- CloudDrive2 中将专用 WebDAV 用户根路径设为 `/115open/Telegram`，同时让
  `CD2_TARGET_PATH_B64` 为空，可避免生成 `Telegram/115open/Telegram/...` 套娃目录。
  WebDAV 用户必须具有读取、写入、改名和删除权限，不能是只读用户。
- 实际发生过 `tg115-bot healthy` 且 Telegram 登录成功，但目的端每约 30 秒报
  `401 Unauthorized`。宿主机使用相同凭据执行 `PROPFIND` 返回 207 后，可把问题缩小为
  TG115 保存的凭据不一致或容器仍使用旧环境。更新配置、强制重建 Bot、查看最新日志并运行
  `manage.sh verify` 后恢复，最终以 `TG115_DESTINATION=OK` 为成功标准。
- 排查当前问题应优先使用 `docker logs --since ...` 或 `--tail ...`，避免把容器历史日志中的
  已解决错误误判成当前故障。没有最近日志也不等于故障，可能只是近期没有事件。
- `healthy` 只证明 heartbeat/进程存活；宿主机 `PROPFIND 207` 只证明一组手工凭据可用；
  `manage.sh verify` 才会从 Bot 容器内按实际配置完成写入、大小检查、改名和删除。115 官方端
  仍需人工检查文件存在、大小及可打开性。
- CloudDrive2 管理入口可以通过 SSH 隧道访问。文章还给出 Nginx + HTTPS 的可选外层方案，
  但 TG115 的数据链路仍应走 Docker 内网 `http://clouddrive2:19798/dav`；Nginx、证书和
  防火墙当前不由本仓库自动管理。
- 迁移时需处理 `/opt/tg115`、原始配置和源码；如果排除 `downloads/`，必须先确认没有需要
  恢复的本地任务。新旧实例不能同时使用同一个 Bot Token 长期运行。

### 自动监听频道的组合扩展记录

- 第一篇文章同样属于当前 TG115 项目的实际使用背景：TG115 用于“手动挑选并转发给 Bot”，
  `tg-rclone` + Telethon 用户 Session + OpenList/115cli 则补充自动监听和上传链路实验。
  应把它视为围绕 TG115 的组合使用方案，而不是与项目无关的材料。
- 同时必须保持代码事实边界：当前未发布工作树已开始内置 OpenList 目的端，但 115cli、频道
  用户 Session、多频道容器和自动历史回填仍不是本仓库功能；不要把 OpenList 目的端适配写成
  Bot 已经能够自动监听频道或直连 115 官方 API。
- 该实验再次验证了“逐段验收”的价值：Telegram 登录、实体解析、下载、本地完整性、上传
  客户端、目的端、远端确认和本地清理应分别检查。
- 一个约 1.04 GiB 文件经 OpenList WebDAV 出现多轮读取/PUT 与卡住；绕过 OpenList 后，
  115cli 直传仍只有约 18 kB/s。这个样本更支持 VPS 到 115 上传线路差，而不是单纯的
  WebDAV 或程序并发问题。普通公网 Speedtest 不能替代真实目的端文件测试。
- `--transfers` 主要增加同时传输的文件数，不能把一个大文件自动拆成多路；单文件瓶颈时
  盲目提高并发可能只会增加重试、资源占用和风控风险。
- 后续若扩展自动频道监听或新目的端，应沿用 SourceAdapter/DestinationAdapter 思路，并继续
  保留任务持久化、磁盘预算、失败保留、远端复验和清理顺序。

## 11. 记忆更新日志

- 2026-09-19：Windows 共用 SSH 层补齐主机密钥变化闭环。首次连接仍需人工核验；旧密钥与
  本次密钥不一致时，界面同时显示服务器、旧／新密钥类型及 SHA-256 指纹，并说明重装、快照、
  密钥重生、IP 重分配和中间人风险。用户取消时保持原文件并按“已取消”结束；明确确认后仅原子
  替换 `%APPDATA%/TG115-Deployer/known_hosts` 中当前主机／端口的对应条目，保留其他服务器，
  自动重试原操作一次。认证、端口、解析、超时、协议和网络错误分类提示；默认／非默认端口、
  IPv4／IPv6／域名及中文空格私钥路径已有回归。完整测试现为 202 项通过、4 项因缺少 rclone
  明确跳过，Ruff 与 Bandit 通过；最终两个 EXE 已重建并通过离线自检：CloudDrive2 为
  51,973,204 bytes，SHA-256 `045B7AB2205E090EACBC353AA1D50F402F85CCF851457F89923F91C46150FE83`；
  OpenList 为 51,982,894 bytes，SHA-256
  `C3B3B24FDA4E697D4EC2E5D44DBD8C29612D550A4DCD3326B27A82F620713467`。尚未在真实 VPS 上复核
  新旧指纹弹窗。
- 2026-09-19：CloudDrive2 版导航页、配置卡片以及 README／小白说明／填写清单的模块名称统一
  为 `CloudDrive2`，不再使用 `CloudDrive2 / 115` 或 `CloudDrive2/115`。教程中的 115 挂载、
  WebDAV 路径、账号准备、官方端核验和链路示例均保留；没有改动产品名 TG115、配置键、部署、
  WebDAV 或 115 业务逻辑。
- 2026-09-18：完整阅读 `TG115-OpenList-Codex-Prompt-PySide6.md` 并建立
  `docs/OPENLIST_IMPLEMENTATION.md`。新增不可变产品配置、OpenList PySide6 入口、固定 5244
  隧道、会话级管理员/WebDAV 凭据、独立 Compose／安装／管理／备份脚本，以及中性 WebDAV
  配置和目的端文案；保留 CloudDrive2 `CD2_*`、目录和容器标识兼容。活动构建与 CI 已从
  Modern/Classic 切换为 CloudDrive2/OpenList 两个 PySide6 成品；Classic 源码仅作历史参考。
  本轮尚未提交、推送、发布或部署真实 VPS。
- 2026-09-18：完成第二阶段日常管理与验收状态 UI。`payload_openlist/manage.sh` 增加结构化
  状态、非跟随脱敏日志、独立重启和一致性手动备份；部署器增加固定动作白名单与高级管理员
  密码恢复，重置输出不进入日志。完整回归 193 项通过、4 项 rclone 集成明确跳过；尚未实机
  验证 OpenList 数据备份／恢复和管理员命令输出。
- 2026-09-19：完成第三阶段已有实例凭据 UX、OpenList 服务验收和常见 WebDAV 失败友好提示。
  最终验收扩展为八个阶段，完整回归 194 项通过、4 项 rclone 集成明确跳过；两个产品 EXE
  已重建并通过离线自检。`docs/OPENLIST_IMPLEMENTATION.md` 已补充干净／已有实例、同机共存、
  固定 5244、备份恢复、安全检查，以及 10～100MB、500MB、1GB、2GB、5GB 和超预算流式文件
  的实机验收矩阵。真实 VPS／Telegram／OpenList／115 Open 和 GB 级传输仍待人工验收。
- 2026-09-19：按用户要求统一源码目录命名：原 `payload/` 改为 `payload_clouddrive2/`，与
  `payload_openlist/` 对称；远端压缩包内部仍使用中性 `payload/`，因此不改变已部署 VPS 的
  安装和回滚协议。新增与 OpenList 对称的 `installer_clouddrive2.py` 产品入口；删除
  CloudDrive2、OpenList 两个 CMD 启动器和 `installer_classic.py`。当前用户入口只保留两个
  PySide6 EXE，历史 Release／CHANGELOG 中的 Classic 记录保留事实。194 项完整回归通过、
  4 项因本机缺少 rclone 明确跳过，Ruff、Bandit、ShellCheck 通过。标准化后两个 EXE 已重建
  并自检：CloudDrive2 为 51,963,588 bytes，SHA-256
  `1700088A15C739A23853E993DB55A060486FD429D897B08C3EAFE5930DB0ED9E`；OpenList 为
  51,972,876 bytes，SHA-256 `8A87662B7F91C4001EA25A759DEB6BA57D781DABC64D9347F22D9B168D25F049`。

- 2026-09-16：源码版本升级到 `v1.6.2`，最终基线提交
  `2529cdcb7cdbac691d98835ebaaa476207db4e50` 已推送到用户 Fork `main`。首个发布提交只包含
  18 个必要源码、测试和文档文件；随后仅追加必要 CI 修复，未提交 EXE、build、spec、虚拟
  环境、项目记忆或本机运行数据。174 项回归通过；带 rclone 的发布验证包含 4 项真实本地
  WebDAV，Ruff、Bandit、两份 pip-audit、工作流 YAML、差异空白和敏感信息检查通过。
  Modern／Classic 成品均报告 `app_version=1.6.2`、`result=OK`；Modern 为 51,941,421 bytes，
  SHA-256 `AFB273D9534B231862598DB7F2C448DEF4237174023DE31FE520917735B44CF7`；Classic 为
  17,332,165 bytes，SHA-256 `4F5BCDAA0075102BD513C2D6647B6CC374D0184A332479808DC56FFEDA82CC6B`。
  Actions 运行 `35097592539` 的 Windows 与 Linux 作业全绿；Windows CI 显式复用
  `setup-python` 的 Python 3.13，避免 uv 选择 Python 3.14 后引发 Tcl/Tk zipfs 打包异常。
  `v1.6.2` 标签指向该提交，GitHub Release ID 为 `389923259`。正式附件为
  `TG115-Deployer-Modern-v1.6.2.exe`（51,941,421 bytes，SHA-256
  `AFB273D9534B231862598DB7F2C448DEF4237174023DE31FE520917735B44CF7`）、
  `TG115-Deployer-Classic-v1.6.2.exe`（17,332,165 bytes，SHA-256
  `4F5BCDAA0075102BD513C2D6647B6CC374D0184A332479808DC56FFEDA82CC6B`）、
  `TG115-Source-v1.6.2.zip`（194,087 bytes，SHA-256
  `A8D5B66F7C1CA22C27FC17C8E00D7E32FC5CED70DD20DAAD98F6F32DB7914805`）和
  `SHA256SUMS.txt`（SHA-256
  `E53D006D2F90B26CFF9226C30C3D2C0202B1F50745235F1F308031CEC801E467`）；远端附件摘要与
  本地一致。源码 ZIP 由标签直接生成，共 51 个跟踪文件，不含本地记忆、AGENTS、构建目录、
  配置、数据库、会话或密钥文件。真实 VPS／Telegram／CloudDrive2／115 升级验收仍待完成。

- 2026-09-16：按用户决定提供双 Windows 部署器。新增 `installer_classic.py`，保留替换前的
  Tkinter 界面并标记为 Classic 兼容版；当前 PySide6 版本命名为 Modern。`build.ps1` 支持
  `-Edition All|Modern|Classic`，默认同时生成两个文件；启动 CMD 优先 Modern，再回退 Classic
  和旧文件名。构建脚本会分别预检 Qt/Tk，并自动处理本机 Python 可用但未自动发现 Tcl/Tk
  目录的问题，相关环境变量只在构建子进程中生效。CI、README、小白说明、贡献指南和测试已
  同步。Modern 成品 51,940,709 bytes，SHA-256
  `3BA1FD1173735E410018F29AC0AB92E73DFF0FC1024AA510934889669C069780`；Classic 成品
  17,332,460 bytes，SHA-256 `001AF4BF84068DCED756529846684F1FBA12945562BBE23AAC64A31B8399CB23`；
  两者打包后 GUI/payload 自检通过。173 项完整回归无跳过，Ruff、Bandit、两份依赖审计和
  GitHub Actions YAML 解析通过。当前改动尚未提交、推送、发布或部署 VPS。

- 2026-09-16：用户提供的 `tg115_deployer_single.py` 经核查、修复后已替换正式 `installer.py`，
  Windows 部署器由 Tkinter 迁移到 PySide6，保留主机密钥、资源建议、部署、固定 SSH 隧道、
  CloudDrive2 修复和 WebDAV 验收能力，并增加离线预览、依赖诊断和脱敏日志导出。构建依赖、
  README、CHANGELOG 与部署器测试已同步。打包验证发现构建环境 `PATH` 中另一套 Poppler ICU
  会被 PyInstaller 误收集并覆盖 Windows 系统 ICU，导致成品 `QtCore` 加载失败；`build.ps1`
  现会在 Qt 预检和 PyInstaller 分析期间隔离 DLL 搜索路径。最终 EXE 未包含该冲突 ICU，大小
  51,939,849 bytes，打包后自检通过。172 项回归全部通过且无跳过（含 4 项本地 rclone WebDAV），
  Ruff、Bandit 和两份依赖审计通过；当前改动尚未提交、推送、发布或部署 VPS。

- 2026-09-16：按用户决定将 Bot 导航迁移到 Telegram 输入框左侧原生命令菜单，7 项菜单说明
  均为 6 个中文字符：查看系统状态、查看最近任务、暂停任务调度、恢复任务调度、运行系统诊断、
  检查临时文件、查看使用帮助。Bot 登录后通过 Telethon 注册默认命令列表和 Commands 菜单；
  Telegram 菜单设置失败只记录日志，不阻断传输服务。所有新命令回复不再附加消息下方按钮；
  队列使用 `/queue 2` 等页码翻页，任务操作继续使用带编号文字命令，旧消息按钮回调仅作兼容。
  同时将系统状态的可访问文案简化为“目的状态：目标目录可访问”，不改变远端探测和过期保护。
  README、小白说明和 CHANGELOG 已同步；168 项完整回归无跳过（含 4 项真实本地 rclone WebDAV）
  全部通过，Ruff、Bandit 和差异检查通过。当前改动尚未提交、推送、发布或部署 VPS。

- 2026-09-15：正式发布 `v1.6.1`，标签指向 `14a60b39437f3a82dbb6af9bbb31ca452e57c1eb`，
  Release ID `389052738`。发布前本地 166 项 Python 回归（含 4 项真实本地 rclone WebDAV
  集成）、Ruff、Bandit、两份依赖审计、EXE 构建及最终附件 `--self-test` 全部通过；Actions
  运行 `34957682544` 的 Windows 与 Linux 作业全绿。附件为 `TG115-Deployer-v1.6.1.exe`
  （SHA-256 `43321D4E9BA14A324863D7086135F3A0759FD751A464091F94B667C05C384A4C`）、
  `TG115-Source-v1.6.1.zip`（SHA-256
  `9AE37CA1B4F75DF89542D4253E30ED7F9574C7774372E93B68208FACCFC79B3C`）和
  `SHA256SUMS.txt`；GitHub 返回的附件摘要与本地一致。源码 ZIP 由标签直接生成，共 55 个
  已跟踪条目，不含 `.codex`、构建目录、配置、数据库、会话或密钥文件。真实 VPS、Telegram、
  CloudDrive2 与 115 官方端升级验收仍待用户环境完成。

- 2026-09-15：用户选择 Bot 菜单方案 C。帮助、队列、任务详情、诊断和操作结果统一采用四字
  标签单页布局；主页增加状态、队列、调度、诊断和只读临时巡检按钮，队列改为每页 5 项并可
  按钮翻页，任务详情按状态提供刷新、重试、流式和取消操作。按钮回调同时校验允许用户 ID 和
  私聊 chat ID；按钮取消先展示影响，再用 5 分钟内存令牌二次确认，失效按钮不能改变任务；
  文字命令和原有失败关闭清理顺序不变。新增 7 项回归后共 166 项测试（含 4 项真实本地 rclone
  WebDAV 集成）全部通过，Ruff、Bandit、差异检查、EXE 重建与 `--self-test` 通过；README、
  CHANGELOG 与小白说明已同步。提交 `b21573b` 已推送到用户 Fork `main`，Actions 运行
  `34955982721` 的 Linux 与 Windows 作业全绿；尚未另行发布或在真实 Telegram/VPS 上点击验收。

- 2026-09-15：Bot `/status` 与 `/performance` 按方案 2 合并为同一张单页状态卡片，所有字段名
  采用四个汉字后接全角冒号，对齐展示目的端只读检查、调度、实际传输、并发窗口、额度、磁盘、
  CPU/内存、分项速率和任务统计；零速率简写为 `0B/s`。菜单、帮助、任务详情、完成通知和
  `/doctor` 不再显示 115 人工确认提示，历史 `confirmed` 在界面与统计中并入“Bot 完成”；
  底层状态与旧 `/confirm` 处理器仅为兼容保留。当时共 159 项测试（含 4 项真实本地 rclone
  WebDAV 集成）全部通过，Ruff、Bandit、EXE 重建与 `--self-test` 通过；尚未提交、推送、
  发布或在真实 VPS 上复验。

- 2026-09-15：真实 Windows 部署器访问 CloudDrive2 时，旧版随机本地端口显示
  `ERR_EMPTY_RESPONSE`，且端口转发异常被处理器吞掉后仍误报打开成功。当前未提交源码改为
  固定绑定 `127.0.0.1:19798`，打开浏览器前通过同一隧道执行真实 HTTP 验收，重复点击先检查
  并自动重建失效隧道；SSH administratively prohibited 与本机端口占用分别给出明确提示，
  不回退随机端口。README、CHANGELOG 和小白说明已同步；新增 4 项隧道回归后共 158 项测试
  均已覆盖通过（4 项 rclone 回环集成单独补跑），Ruff、Bandit、EXE 重建及打包自检通过。
  尚未提交、推送、发布或在真实 VPS 上复验，未记录真实 VPS 地址。

- 2026-09-15：真实 Windows 部署器使用中出现 SSH `Host key ... does not match`，用户确认关闭
  部署器、打开 `%APPDATA%/TG115-Deployer/known_hosts` 并只删除目标 VPS 对应记录后恢复。
  主 README 和小白说明已补充安全处理顺序：先从服务商控制台核对当前 ED25519/RSA SHA-256
  指纹，确认重装／换机／密钥重生等合理原因后只移除单条记录，再在新弹窗复核指纹；原因不明
  不得直接接受或清空整个文件。未记录真实 IP 或公钥。文档提交 `6a6f5dd` 已推送，Actions
  运行 `34943616714` 全绿。

- 2026-09-15：主 README 的 Windows 图形化部署章节补充第 3、4 页逐项填写规则、受管与外部
  CloudDrive2 的区别、2 核约 2GB／33GB VPS 使用 8GB/8GB 流式优先值示例、部署中等待提示
  以及完整按钮顺序。文档提交 `4d826f4` 已推送，Actions 运行 `34941943298` 全绿；不移动
  `v1.6.0` 标签，不替换已发布附件。

- 2026-09-15：`v1.6.0` 已在用户 Fork 正式发布，标签指向 `0ef55da`，Release ID
  `388823941`，最终 Actions 运行 `34919814371` 的 Windows 与 Linux jobs 全绿。发布附件为
  `TG115-Deployer-v1.6.0.exe`、`TG115-Source-v1.6.0.zip` 和 `SHA256SUMS.txt`；远端附件摘要、
  大小及公开下载均已复核。发布准备过程发现 Windows Runner 扫描 200 个受阻任务时可能让
  测试内静态资源快照超过 10 秒；公平性测试现隔离资源新鲜度条件并在失败时可靠关闭数据库，
  生产资源过期保护未放宽。真实 VPS／Telegram／CloudDrive2／115 验收仍待部署环境完成。

- 2026-09-15：用户首次手动运行 Fork Actions 时，Linux job 全绿，Windows job 因 Git Bash
  将 Runner 临时目录表示为 `RUNNER~1` 8.3 短路径，备份测试夹具传入的路径与 `pwd -P` 字符串
  不同而误报失败。生产 `backup_retention.sh` 的严格目录校验没有放宽；只在跨平台测试调用前
  规范化为物理路径。修复提交 `274dda9` 已推送；Actions 运行 `34918947379` 的 Windows 和
  Linux jobs 全部通过，包括 154 项回归、Ruff、Bandit、两份依赖审计、EXE 打包自检、
  ShellCheck、Compose 校验、真实 WebDAV 集成和 Docker 镜像构建。

- 2026-09-15：二次开发版已推送到用户 Fork `LuoPoJunZi/TG115` 的 `main@f32424b`，原作者
  `whyhhh20/TG115` 保留为本地 `upstream` 且禁用 push URL。README 已扩展为完整部署、验收、
  运维和排错教程，并在开头及致谢章节链接原作者仓库。公开提交共包含 34 个改动文件；本地
  `AGENTS.md` 与 `.codex/PROJECT_MEMORY.md` 通过 `.git/info/exclude` 保留，已从改写后的公开
  历史中移除。用户 Fork 默认未运行 Actions，工作流已增加 `workflow_dispatch`，仍需用户在
  GitHub Actions 页面首次启用后手动运行。正式标签和 Release 继续等待真实 VPS 验收。

- 2026-09-14：1.6.0 候选版固化前重新扫描 36 个待提交文件，未发现私钥、Bot Token、凭据 URL
  或敏感配置赋值；使用项目隔离的 rclone 1.75.1 重跑 154 项测试，全部通过且无跳过。候选版
  固化在 `codex/v1.6.0-rc`，正式标签和发布继续等待真实 VPS／Telegram／CloudDrive2／115
  分层验收。

- 2026-09-14：继续存储安全优化：资源探测协议升级，优先识别 Docker 实际数据目录，分盘时
  独立校验空间／inode；远端在 Docker 启动后、构建候选镜像前权威复查。新增备份只读盘点、
  超过 5GB 提示及显式 `prune-backups 1-50`，部署不自动删除。154 项完整测试无跳过，含
  真实 Git Bash 保留测试和 4 项 rclone 回环 WebDAV；静态检查与 EXE 自检通过。未部署 VPS。

- 2026-09-14：Windows 部署器新增版本化只读 VPS 资源探测、均衡／流式优先实例建议和部署前
  复检，保持源码默认 20/20GB、运行时动态并发和磁盘不自动变更；远端脚本改为核对安装目录
  所在文件系统。149 项完整测试无跳过，含 4 项真实本地 rclone 回环 WebDAV；Ruff、Bandit、
  ShellCheck、依赖审计和重建 EXE 自检通过。未在真实 VPS 部署。

- 2026-09-14：第三阶段将命令路由、运维动作和用户状态展示从 `main.py` 拆到
  `bot_commands.py`；`/orphans` 保持只读，新增 `/orphans clean` 的 5 分钟一次性确认码、
  清理前重新巡检、活动任务保护、逐项删除复查和 100 项上限。新增文件已纳入 EXE payload
  自检；136 项完整测试（含 4 项真实本地 rclone 回环 WebDAV）、Ruff、Bandit、两份依赖审计、
  EXE 重建和打包后自检通过。真实 VPS 调优和验收仍待部署环境。

- 2026-09-13：按用户授权完成现有 Bot 的 v1.6.0 本地优化，保持默认预算、依赖、镜像和容器
  权限；新增持久暂停、诊断、进度、状态记录、取消保护、路径恢复、配置核验和测试。
  120 项测试与 EXE 自检通过；未提交／发布／部署。详细边界见 `docs/v1.6.0-优化与验收.md`。

- 2026-09-13：继续第二阶段可靠性优化：新增合法状态迁移图与事务化迁移、隔离升级预检、
  SQLite 一致性快照和失败自动回退；目的端探测区分目标／根目录；增加只读 `/orphans`、
  手动 `/stream` 与可选批量 `/confirm all`，完成状态不再显示为待办。131 项完整测试通过，
  含 4 项真实本地 rclone 回环 WebDAV 集成；Ruff、Bandit、Bash 语法检查、EXE 构建和
  打包后自检通过。仍未部署 VPS。

- 2026-09-13：阅读两篇公开部署文章；记录真实 TG115 部署环境、401 凭据/旧容器修复链路、
  逐层验收方法、管理入口边界和线路诊断经验；将配置变化未保证重建 Bot 标为修复候选；
  补充 Windows/手工部署、Bot 手动转存、普通/流式传输、频道自动监听组合、历史归档、双节点
  和管理入口等多种使用方式，并区分仓库原生能力与组合扩展能力。
- 2026-09-12：基于 `main@a524fac` 首次建立；完成架构、业务流、运行部署、状态机、测试和
  风险复核，未改动产品代码。
