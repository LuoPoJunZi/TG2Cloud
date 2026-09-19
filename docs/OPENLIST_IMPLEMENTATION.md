# TG115 OpenList 实施记录

> 状态：实施中  
> 首次审计：2026-09-18  
> 审计基线：`main@2529cdc` / TG115 v1.6.2  
> 需求来源：仓库根目录 `TG115-OpenList-Codex-Prompt-PySide6.md`

本文记录 OpenList 产品线的仓库审计、架构决定、实施顺序和验收状态。需求原文保留不改；
源码和测试仍是实现事实来源。

## 1. 产品边界

最终只发布两个相互独立的 Windows PySide6 部署器：

| 产品 | 正式文件名 | 默认安装目录 | 管理端口 | 默认 WebDAV 地址 |
| --- | --- | --- | --- | --- |
| CloudDrive2 | `TG115-CloudDrive2-Deployer.exe` | `/opt/tg115` | `19798` | `http://clouddrive2:19798/dav` |
| OpenList | `TG115-OpenList-Deployer.exe` | `/opt/tg115-openlist` | `5244` | `http://tg115-openlist:5244/dav/` |

硬边界：

- 两个 EXE 不提供运行时后端选择，名称、默认值、安装目录、容器、网络和 SSH 隧道均隔离。
- 两个 EXE 共用同一套 PySide6 界面组件、SSH 基础设施和校验框架，避免复制两套实现。
- Telegram 队列、SQLite 状态机、磁盘保护、普通／流式传输、失败保留和安全取消继续共用。
- OpenList 管理页只绑定 VPS 的 `127.0.0.1:5244`，Windows 端固定使用
  `127.0.0.1:5244` SSH 隧道；端口冲突必须明确失败，不能改用随机端口。
- 部署器不读取、保存或上传用户的 115 Cookie、Token 或登录信息。115 Open 存储由用户在
  OpenList 管理页自行添加。
- “部署基础环境成功”和“WebDAV 最终验收成功”是两个阶段。用户尚未配置 115/WebDAV 时，
  不得把已经成功的 OpenList 基础部署误报为失败。
- OpenList 版不改变 `completed` 与 `confirmed` 的数据库语义，也不得把 WebDAV 接收完成描述
  成 115 官方端已经入库。

## 2. 当前仓库审计

### 2.1 可以直接复用

- `installer.py` 的 PySide6 页面骨架、后台线程、日志脱敏、SSH 主机密钥核验、SFTP 上传、
  固定端口隧道、资源探测、配置预检和 EXE 自检。
- `vps_resources.py` 的只读探测协议、安装目录／Docker 文件系统空间核验和实例建议计算。
- `payload_clouddrive2/app/` 中的 Telegram Bot、SQLite 队列、原子额度预留、崩溃恢复、普通上传、流式
  上传、取消清理、远端复验、状态展示和健康检查。
- `payload_clouddrive2/app/rclone_client.py` 的标准 WebDAV `copyto`、`rcat`、`size`、`moveto`、
  `deletefile` 能力。
- `payload_clouddrive2/app/verify_destination.py` 的随机文件写入、大小检查、改名、复验和清理流程。
- `payload_clouddrive2/remote_install.sh` 已有的隔离预检、数据库一致性快照、配置／程序备份和失败回滚思路。

### 2.2 需要解耦

| 当前耦合 | 位置 | 处理方向 |
| --- | --- | --- |
| 产品标题、版本、默认值和 WebDAV 地址写死 | `installer.py` | 引入只读产品配置，由两个入口选择 |
| 页面和操作名称写死为 CloudDrive2 | `installer.py` | 共用页面组件，按产品配置显示差异内容 |
| 远端文件清单只有一套 payload | `installer.py` | 构建产品专属 payload，同时复用公共 `app/` |
| 环境变量只有 `CD2_*` | `payload_clouddrive2/app/config.py` | 增加中性 WebDAV 配置，保留 `CD2_*` 兼容读取 |
| rclone remote 固定名为 `cd2` | `payload_clouddrive2/app/rclone_client.py` | 改为受控产品配置，不接受任意命令片段 |
| 部署／运维脚本写死容器和目录 | `payload_clouddrive2/*.sh` | 抽出受控常量或提供 OpenList 专属脚本 |
| Compose 只包含 CloudDrive2 | `payload_clouddrive2/docker-compose.yml` | 新增独立 OpenList Compose，不混合两个后端 |
| FUSE 被视为所有受管部署的前提 | `vps_resources.py` | 只有 CloudDrive2 需要 FUSE；OpenList 不应误拦截 |
| 用户文案写死 CloudDrive2 | `payload_clouddrive2/app/*.py` | 使用安全的产品显示名，保留语义和布局 |
| 构建产物是 Modern／Classic | `build.ps1`、CI | 改成 CloudDrive2／OpenList 两个 PySide6 产物 |

### 2.3 CloudDrive2 兼容决定

现有部署已经使用 `/opt/tg115`、`tg115-bot`、`tg115-clouddrive2` 和 `tg115` 网络。
为了保证 v1.6.2 用户可以原位升级，CloudDrive2 产品线继续保留这些运行标识，不为了形式统一
而强制迁移。OpenList 产品线从首版开始严格使用独立标识：

- 安装目录：`/opt/tg115-openlist`
- OpenList 容器：`tg115-openlist`
- Bot 容器：`tg115-openlist-bot`
- Docker 网络：`tg115-openlist-net`
- 备份目录：`/opt/tg115-openlist-backups`

两版默认目录不同，可在同一台 VPS 共存；但同一个 Telegram Bot Token 不能同时由两套实例
长期运行。

## 3. 目标结构

```text
PySide6 公共部署器核心
├─ CloudDrive2 产品配置与入口
│  └─ CloudDrive2 专属 Compose／安装／网络修复
└─ OpenList 产品配置与入口
   └─ OpenList 专属 Compose／安装／初始化／管理

两条部署线共同复用
├─ SSH、主机密钥、隧道、资源探测、脱敏日志
├─ Telegram 配置与 TG115 Bot 应用代码
├─ SQLite 状态机和磁盘／并发保护
└─ 标准 WebDAV rclone 适配与最终写入验收
```

产品配置只能包含仓库维护者定义的常量；安装目录仍须经过现有严格校验和 shell 安全引用，
不能把任意界面文本直接拼接为远端命令。

## 4. OpenList 实施规则

### 4.1 容器与持久化

- 使用 OpenList 官方镜像，并在进入发布候选前锁定明确版本及多架构镜像摘要。
- 管理端口映射固定为 `127.0.0.1:5244:5244`，不默认开放公网。
- OpenList 数据目录持久化到安装目录中的独立子目录；Bot 数据、下载、日志和 rclone 配置也
  与 CloudDrive2 版完全分开。
- Bot 继续以非 root、只读根文件系统、丢弃 capabilities 和 `no-new-privileges` 运行。
- OpenList 镜像的运行用户、持久化目录和初始化命令必须以官方文档及实际镜像验证为准。

官方依据：

- OpenList Docker 安装文档：<https://pages.doc.oplist.org/guide/installation/docker>
- OpenList 官方发布页：<https://github.com/OpenListTeam/OpenList/releases>

### 4.2 管理员信息

- 首次安装只获取或生成一次管理员凭据，并通过专用结果字段返回界面；不得写入普通日志。
- 密码默认遮罩，提供显示和复制操作；界面关闭后不在 Windows 本地持久保存。
- 已存在 OpenList 数据时不得自动重置管理员密码。
- 密码恢复放在高级操作中，必须解释影响并二次确认，使用官方支持的管理命令。
- 在锁定实现前，必须验证目标 OpenList 版本的首次初始化输出和管理命令，不能只依赖某一条
  固定日志文本。

### 4.3 WebDAV 引导

- 本地用密码学安全随机数生成 WebDAV 密码，长度为 24～32 个字符；同一次界面会话中保持
  不变，只有用户明确点击“重新生成”才改变。
- 推荐用户名为 `tg115`，推荐基本路径为 `/115/Telegram`，均提供复制按钮。
- WebDAV URL 对普通用户只读，由产品配置固定为容器内网地址。
- 部署器只展示配置建议和步骤；用户在 OpenList 中自行创建 WebDAV 用户、设置权限和添加
  115 Open 存储。
- 最终验收必须从 Bot 容器按实际配置依次验证：认证／目录访问、写入、大小、改名、复验、
  删除；失败时输出稳定的机器可读状态和普通用户可理解的原因。

## 5. 分阶段清单

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 完整阅读需求、审计仓库、固化架构与兼容决定 | 已完成 |
| 2 | 建立产品配置和两个 PySide6 入口，确保 CloudDrive2 行为不回退 | 已完成并通过两个 EXE 自检 |
| 3 | 将 Classic/Tkinter 从正式构建、CI、启动器和发布说明中退役 | 已完成；旧源码与 CMD 启动器已清理 |
| 4 | 增加隔离的 OpenList Compose、安装、回滚、管理和备份脚本 | 本地实现完成，待真实 VPS 验收 |
| 5 | 增加 OpenList 五步式 PySide6 流程、固定 SSH 隧道和凭据 UX | 已完成；含二次确认的高级密码恢复 |
| 6 | 中性化 WebDAV 配置／文案并保留 `CD2_*` 升级兼容 | 已完成并通过兼容回归 |
| 7 | 分离基础部署与最终 WebDAV 验收，补齐机器可读状态 | 已完成；界面逐项展示验收状态 |
| 8 | 更新构建、CI、README、CHANGELOG、发布说明和操作教程 | 构建、CI 和开发期文档完成；正式 Release 文案待版本确定 |
| 9 | 完整自动化回归、两个 EXE 自检和本地 WebDAV 集成 | 194 项回归与两个 EXE 自检通过；本机 rclone 集成待补 |
| 10 | 真实 VPS、Telegram、OpenList、115 Open 和大文件人工验收 | 待实机验收 |

每一阶段都必须先补或更新测试，再运行与改动直接相关的回归。阶段 2～8 完成前不创建正式
OpenList Release。

## 6. 必须覆盖的回归

- CloudDrive2 v1.6.2 表单、配置生成、部署、固定 19798 隧道、网络修复和 WebDAV 验收不回退。
- OpenList 与 CloudDrive2 的目录、容器、网络、端口、备份和配置文件不会交叉覆盖。
- 两个 EXE 的标题、版本、字段、动作、payload 和自检结果与各自产品一致。
- OpenList 5244 本地端口被占用、SSH 转发被拒绝、隧道失效重建时均给出准确错误。
- 首次安装与已有数据能够区分；已有实例部署不会重置管理员密码。
- WebDAV 密码生成使用安全随机源，不出现在日志／异常／导出诊断中。
- 错误凭据、无写权限、目标目录不存在、改名失败和清理失败均失败关闭。
- 普通／流式任务、预算原子性、磁盘安全线、崩溃恢复、取消清理和远端临时命名保持现有测试。
- OpenList 基础部署在尚未配置 115/WebDAV 时仍可报告成功；最终验收单独报告未完成原因。
- `build.ps1` 和 Actions 最终只构建并自检两个 PySide6 成品，仓库不再要求 Tkinter 运行时。

## 7. 外部核验状态

已经按官方来源核对：

- OpenList v4.2.6 官方镜像多架构摘要为
  `sha256:c555c6e1c8af2aead38ed12ec761ac077fdf046d19cf033414be8e056aec6b64`，Compose
  已按摘要锁定；镜像清单包含 `linux/amd64` 与 `linux/arm64`。
- 官方 v4.2.6 源码显示：`OPENLIST_ADMIN_PASSWORD` 仅在管理员不存在时用于首次创建，不会
  自动重置已有管理员；显式恢复使用 `openlist admin random` 或 `openlist admin set`。

下列事项不能由源码审计代替，完成前必须明确标为待验收：

- 锁定的 OpenList 镜像在真实 `linux/amd64` 与 `linux/arm64` VPS 上能否正常拉取和启动。
- 目标 OpenList 版本的首次管理员初始化、已有数据升级和显式密码重置实机行为。
- 真实 VPS 上仅监听回环地址的 5244 管理页和 Windows SSH 隧道。
- 用户在 OpenList 中添加 115 Open 后的读取、写入、改名和删除权限。
- 真实 Telegram 文件、GB 级普通传输、超过预算的流式传输和中断恢复。
- 115 官方端最终可见性与可打开性；TG115 只对 WebDAV 链路负责。

## 8. 真实环境验收清单

以下项目必须在用户自己的测试 VPS、Telegram Bot、OpenList 和 115 Open 环境中执行。自动化
回归、1KB WebDAV 探针和 EXE 自检都不能替代本节；任何一项未执行时，OpenList v1.0.0 都应
继续标记为候选版本。

### 8.1 环境与部署

- 分别在干净 VPS 和已有 `/opt/tg115-openlist` 数据的 VPS 上部署，记录 CPU、内存、磁盘、
  架构和 Docker 版本；若条件允许，至少各覆盖一台 `linux/amd64` 与 `linux/arm64`。
- 同机已安装 CloudDrive2 版时再次部署 OpenList，确认安装目录、容器、网络、数据库、下载目录、
  rclone 配置和备份目录互不覆盖。
- 全新实例应显示首次管理员凭据；已有实例只提示使用原凭据，且部署前后的管理员密码保持不变。
- 确认 VPS 公网接口没有监听 5244；Windows 本地固定使用 `127.0.0.1:5244` 隧道。另用一个本地
  程序占用 5244，确认部署器明确报错且不会改用随机端口。
- VPS 和两个容器分别重启后，确认 OpenList、Bot、队列、SQLite 数据及 SSH 隧道重建流程正常。

### 8.2 OpenList、WebDAV 与备份

- 用户本人在 OpenList 后台完成 115 Open 授权、目标目录和 `tg115` 普通用户配置；部署器不得
  读取或显示任何 115 Token、Cookie 或登录信息。
- 分别验证正确凭据、错误密码、权限不足、错误基本路径和 OpenList 停止五种情况；主提示应易懂，
  原始 rclone/HTTP 细节只出现在脱敏日志中。
- 最终验收必须依次通过 Bot、OpenList 服务、认证、列目录、写入、大小、改名和清理八个阶段；
  随后在 115 官方客户端确认测试文件已清理。
- 创建一次一致性备份，核对程序配置、TG115 SQLite 和 OpenList 状态备份可读；在测试副本或一次性
  VPS 上执行恢复，确认不包含 `downloads/`、日志、临时目录或大型缓存。不要用生产实例做首次恢复
  演练。
- 检查 `.env`、rclone 配置、数据库与备份权限，并搜索导出日志，确认没有 SSH、Telegram、
  WebDAV、OpenList 管理员或 115 凭据明文。

### 8.3 真实文件矩阵

每个文件都记录 Telegram 文件大小、传输模式、下载耗时、WebDAV 耗时、重试次数、VPS 峰值
占用、OpenList 返回状态、115 官方端大小与可打开性、本地清理结果。不能只记录 Bot 显示的
“完成”。

| 文件大小 | 预期模式 | 必查项目 | 结果 |
|---|---|---|---|
| 10～100MB | 普通落盘 | 基础下载、上传、改名、官方端打开、本地清理 | 待执行 |
| 500MB | 普通落盘 | 持续速度、磁盘占用、同名文件处理、官方端大小 | 待执行 |
| 1GB | 普通落盘 | 长时连接、OpenList 返回完成后的官方端可见性 | 待执行 |
| 2GB | 按当前预算决定 | Telegram 限制、WebDAV 稳定性、失败重试无错误副本 | 待执行 |
| 5GB | 流式或普通落盘 | 背压、峰值磁盘、临时远端文件、最终清理与官方端打开 | 待执行 |

至少另选一个大于当前 `LOCAL_TEMP_BUDGET_GB` 的文件确认流式模式：VPS 不应保存完整本地副本；
网络中断后应清理远端临时文件并从头安全重试。再分别在 Telegram 下载、普通上传、流式上传和
远端改名前后重启 Bot，核对恢复结果、数据库状态和重复文件情况。

### 8.4 发布门槛

只有上述记录全部填写且没有未解释的数据丢失、凭据泄露、跨产品覆盖或错误成功提示，才可把
OpenList v1.0.0 标为正式可发布。TG115 的自动验收终点仍是 WebDAV 文件大小与操作正确；115
官方端最终可见、大小一致和可打开必须由测试人员单独确认。

## 9. 变更记录

- 2026-09-18：完成需求全文阅读和 v1.6.2 仓库审计；确定共用 PySide6 核心、两个独立入口、
  OpenList 完全隔离、CloudDrive2 原位升级兼容以及分阶段实施顺序。尚未改变运行时行为。
- 2026-09-18：完成第一批本地实现：增加不可变产品配置与 OpenList PySide6 入口、五步界面、
  固定 5244 SSH 隧道、会话级管理员／WebDAV 凭据、独立 Compose 与安装／管理／备份脚本，
  并将 Bot WebDAV 配置和状态文案中性化；保留 `CD2_*` 与 CloudDrive2 运行标识兼容。
- 2026-09-18：新增 12 项 OpenList 回归及 1 项升级凭据保护回归；完整 Python 回归 187 项通过、4 项因本机缺少 rclone
  跳过，Ruff、Bandit、ShellCheck 和 Bash 语法检查通过。
- 2026-09-18：活动构建与 CI 已切换为两个 PySide6 成品，Classic/Tkinter 退出活动产品线。
  本机构建后的 CloudDrive2（51,953,986 bytes，SHA-256
  `F7BBE381E4D3F8069EF6B8EDC2A2D3A169D8A21D9DDDD76899E39BCFC764E11E`）与 OpenList
  （51,965,305 bytes，SHA-256
  `87E047AB9C58EA470F5A641E73EDB9AD63C08875163CA3E57DBFEB767BAD7925`）均通过 GUI、后端导入、
  产品标识和内嵌 payload 自检。正式 Release 和真实 VPS／115 验收仍未完成。
- 2026-09-18：完成 OpenList 日常管理闭环：运行状态、脱敏日志、分别重启 Bot／OpenList、
  程序配置＋TG115 SQLite＋OpenList 状态一致性备份，以及需要确认文字的管理员密码恢复。
  新密码只通过专用结果字段写回遮罩输入框；最终 WebDAV 验收按八个阶段显示结果。
- 2026-09-18：第二阶段候选 EXE 重建并通过离线自检。CloudDrive2 为 51,963,362 bytes，
  SHA-256 `014DD7B242712DF2830FF8441C47F4BFB0BBD6DD05F56CFA854E4575A32EB8FD`；OpenList 为
  51,973,948 bytes，SHA-256 `65B8DFE154D1BAE40FF5D8AA0C851313F290E6FFE48FD4BFC5727A48A5790339`。
  产物位于本地忽略目录，未提交或发布。
- 2026-09-19：源码部署目录统一为 `payload_clouddrive2/` 与 `payload_openlist/`；远端压缩包内
  继续使用中性的 `payload/`，不改变 VPS 安装和回滚协议。删除两个 CMD 启动器及
  `installer_classic.py`；增加与 `installer_openlist.py` 对称的 `installer_clouddrive2.py`
  产品入口，共用界面和部署后端继续放在 `installer.py`。当前用户入口只保留两个 PySide6 EXE。
- 2026-09-19：已有实例部署后不再显示无效的首次密码；恢复密码后只重新显示当前新密码。
  最终验收新增 OpenList 服务阶段，错误主提示按认证、目录、写入、大小、改名、删除分流，
  原始远端细节留在脱敏日志。完整回归增至 194 项通过、4 项 rclone 集成明确跳过。
- 2026-09-19：第三阶段候选 EXE 重建并通过离线自检。CloudDrive2 为 51,962,051 bytes，
  SHA-256 `D922E0918F05CCB93169A04996E107A4D0D1B779377E04D9B03C626DA5663B2A`；OpenList 为
  51,972,722 bytes，SHA-256 `EA8D941F6D9CA3243584FE9FA0A4C3010E94F48D45759FD3F31F681EE4D6756C`。
  产物位于本地忽略目录，未提交或发布。
- 2026-09-19：完成源码目录和产品入口标准化后再次重建并自检。CloudDrive2 为
  51,963,588 bytes，SHA-256
  `1700088A15C739A23853E993DB55A060486FD429D897B08C3EAFE5930DB0ED9E`；OpenList 为
  51,972,876 bytes，SHA-256
  `8A87662B7F91C4001EA25A759DEB6BA57D781DABC64D9347F22D9B168D25F049`。两个成品均确认产品
  标识、Qt GUI、后端导入和内嵌 payload 正常；构建目录与 EXE 继续由 Git 忽略。
