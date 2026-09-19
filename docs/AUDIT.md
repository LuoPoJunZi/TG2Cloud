# TG2Cloud v1.0.0 第一阶段审计

审计日期：2026-09-19

审计基线：`main@a037080`

审计范围：仓库静态结构、两个 Windows 部署器、两个 VPS payload、TG2Cloud 品牌资源、构建与 CI、运行时命名、传输核心、维护命令和现有文档。

阶段边界：本轮只审计并创建审计记录；未修改业务代码，未构建 EXE，未连接 VPS，未执行自动化或人工传输测试。

## 1. 结论摘要

当前仓库已经具备两套分别成型的产品路径，但实现方式不是两份完全独立代码，而是：

```text
installer_clouddrive2.py ─┐
                          ├─ installer.py（共享 PySide6 UI / SSH / Tunnel / 部署后端）
installer_openlist.py ────┘
                          │
                          ├─ deployer_products.py（Edition 配置）
                          ├─ payload_clouddrive2/（共享 Bot/传输核心 + CloudDrive2 运维）
                          └─ payload_openlist/（OpenList Compose 与专用运维脚本覆盖层）
```

现有稳定核心具备 SQLite 队列、重启恢复、rclone WebDAV、流式大文件、磁盘保护、目的端 verify、升级前备份和失败回滚等能力，不适合为品牌迁移而重写。

TG2Cloud v1.0.0 的主要工作不是重建核心，而是完成以下受控迁移：

1. TG115 用户可见品牌与 115-only 文案迁移；
2. 两个 Edition 的容器、网络、安装目录和备份目录迁移到独立 `tg2cloud-*` 命名空间；
3. 正式品牌资源接入 PySide6、PyInstaller、README 和 About；
4. 版本统一为 `1.0.0`，正式构建只输出两个 TG2Cloud PySide6 EXE；
5. 补齐或明确 update、backup/restore、uninstall 等正式运维入口；
6. 在不破坏稳定核心的前提下更新测试与兼容标记。

## 2. 当前仓库结构

### 2.1 Windows 部署器

| 文件 | 当前角色 | 审计结论 |
|---|---|---|
| `installer.py` | 共享 PySide6 主程序，包含 UI、验证、SSH、Tunnel、部署、repair、verify、日志脱敏和自检 | 两个 Edition 的稳定 UI/后端主体，应最小修改 |
| `installer_clouddrive2.py` | CloudDrive2 薄入口 | 正式 PySide6 入口之一 |
| `installer_openlist.py` | OpenList 薄入口 | 正式 PySide6 入口之一 |
| `deployer_products.py` | 两个 Edition 的标题、版本、路径、容器、网络、端口和 payload 清单 | 运行时命名迁移的中心配置，但 Shell/Compose 仍有硬编码，不能只改这里 |
| `vps_resources.py` | VPS CPU、内存、磁盘、inode、Docker 文件系统探测与容量建议 | 可共享；备份目录探测仍硬编码 `/opt/tg115-backups` |
| `build.ps1` | PyInstaller 一次构建 CloudDrive2/OpenList | 当前只构建两个 PySide6 入口，但产物名仍是 TG115，未接入正式 Icon/版本资源 |

### 2.2 VPS payload

| 目录 | 当前角色 | 审计结论 |
|---|---|---|
| `payload_clouddrive2/app/` | 两版共享的 Telegram Bot、SQLite、队列、恢复、rclone、流式传输、磁盘控制和 verify 核心 | 稳定核心，避免结构性重写 |
| `payload_clouddrive2/` | 共享 Dockerfile、依赖、备份工具；另含 CloudDrive2 Compose、安装、管理和网络修复 | CloudDrive2 完整 payload，同时是 OpenList Bot 核心来源 |
| `payload_openlist/` | OpenList Compose、安装、管理、管理员密码和 WebDAV 配置保留脚本 | 打包时覆盖共享 payload 中同名的后端专用文件 |

`InstallerBackend._add_payload_to_archive()` 对 CloudDrive2 直接打包整个 `payload_clouddrive2/`；对 OpenList 则按清单组合共享核心与 `payload_openlist/` 覆盖文件。这是当前两版共享稳定核心的关键边界。

### 2.3 测试与 CI

- `tests/test_core.py`：部署器、SSH、Tunnel、配置、SQLite、磁盘预算、恢复、rclone、verify 与 payload 结构。
- `tests/test_openlist.py`：OpenList 产品隔离、凭据 UX、5244 Tunnel、管理操作与 payload。
- `tests/test_deployment.py`：Shell 故障、回滚、备份保留和 Windows 构建结构。
- `tests/test_optimizations.py`、`tests/test_scenarios.py`：队列、状态机、流式传输、失败恢复与规模化模拟。
- `tests/test_webdav_integration.py`：本机真实 rclone/WebDAV 协议测试；缺少 rclone 时会跳过。
- `.github/workflows/tests.yml`：Windows 单元测试、Ruff、Bandit、依赖审计、双 EXE 构建/自检；Linux ShellCheck、Compose 校验、运行时测试和 Bot 镜像构建。

本轮没有执行这些测试，不能把已有历史产物或历史文档中的结果当作 TG2Cloud v1.0.0 的通过结论。

## 3. 两个 Edition 的当前差异

| 项目 | CloudDrive2 当前实现 | OpenList 当前实现 |
|---|---|---|
| PySide6 入口 | `installer_clouddrive2.py` | `installer_openlist.py` |
| 安装目录 | `/opt/tg115` | `/opt/tg115-openlist` |
| 备份目录 | `/opt/tg115-backups` | `/opt/tg115-openlist-backups` |
| Bot 容器 | `tg115-bot` | `tg115-openlist-bot` |
| Gateway 容器 | `tg115-clouddrive2` | `tg115-openlist` |
| Docker Network | `tg115` | `tg115-openlist-net` |
| Gateway 服务名 | `clouddrive2` | `openlist` |
| Bot Compose 服务名 | `tg115-bot` | `tg115-bot` |
| 固定管理端口 | `127.0.0.1:19798` | `127.0.0.1:5244` |
| 容器内 WebDAV | `http://clouddrive2:19798/dav` | `http://tg115-openlist:5244/dav/` |
| 当前 WebDAV 默认用户 | 空 | `tg115` |
| 当前 WebDAV 默认目标 | 空 | `/115/Telegram` |
| Gateway 要求 | FUSE、可选择部署/使用外部 WebDAV | 始终部署受管 OpenList，不要求 FUSE |
| 管理操作 | UI 提供网络修复；Shell 有 status/logs/restart/update/verify 等 | UI 提供状态、脱敏日志、Bot/OpenList 重启、手动备份、管理员密码恢复 |

目标运行命名必须迁移为：

```text
CloudDrive2:
  tg2cloud-clouddrive2-bot
  tg2cloud-clouddrive2
  tg2cloud-clouddrive2-net
  /opt/tg2cloud-clouddrive2

OpenList:
  tg2cloud-openlist-bot
  tg2cloud-openlist
  tg2cloud-openlist-net
  /opt/tg2cloud-openlist
```

默认新装路径与旧 TG115 路径不同，因此可以实现共存；不得把旧目录或容器当作同名升级目标静默覆盖。

## 4. PySide6、Tkinter 与现有构建入口

### 4.1 两个正式 PySide6 入口

- `installer_clouddrive2.py` 调用共享 `main(product=CLOUDDRIVE2_PRODUCT)`。
- `installer_openlist.py` 调用共享 `main(product=OPENLIST_PRODUCT)`。
- 两者使用相同主题、导航、卡片、表单、日志、进度、对话框、SSH、Tunnel 和内嵌线性图标系统，符合“同一产品系列”的技术基础。

### 4.2 Tkinter 遗留

仓库已没有 `installer_classic.py`，当前 `build.ps1` 也没有 Tkinter 构建目标。工作目录仍存在以下被 `.gitignore` 忽略的旧 spec/产物：

- `TG115-Deployer-Classic.spec`：指向已经不存在的 `installer_classic.py` 和 `payload/`；是失效旧入口。
- `TG115-Deployer-Modern.spec`：指向 `installer.py` 和旧 `payload/`；不属于当前双产品正式构建。
- `dist/release-v1.6.2/TG115-Deployer-Classic-v1.6.2.exe`：历史本地产物，不是当前 `build.ps1` 的输出。

另有 `TG115-CloudDrive2-Deployer.spec`、`TG115-OpenList-Deployer.spec`，它们是 PyInstaller 生成/遗留的 TG115 规格文件，同样被忽略，且都未配置正式品牌 icon。

结论：Tkinter 已退出当前源码和正式构建逻辑，但旧 spec 与 `dist/` 历史产物会干扰发布验收；正式发布准备阶段需清理发布工作区并增加“只允许两个目标 EXE”的断言。删除本地历史产物应在用户确认后进行。

### 4.3 当前正式构建方式

`build.ps1 -Edition All|CloudDrive2|OpenList` 使用 `uv` 或指定/系统 Python 调用 PyInstaller：

```text
--onefile --windowed --collect-all paramiko
--add-data payload...
--name TG115-CloudDrive2-Deployer|TG115-OpenList-Deployer
```

当前问题：

1. 产物仍名为 `TG115-CloudDrive2-Deployer.exe`、`TG115-OpenList-Deployer.exe`；
2. 构建函数和环境变量仍是 `Tg115` / `TG115_BUILD_PYTHON`；
3. 没有 `--icon assets/brand/tg2cloud.ico`；
4. 没有把 `assets/brand/` 加入冻结包，PySide6 运行时无法读取正式 Logo/Icon；
5. 没有 Windows `FileVersion`、`ProductVersion`、`ProductName` 等版本资源配置；
6. CI 的 EXE 路径、自检结果名和 Linux 镜像测试标签仍是 TG115；
7. 当前工作目录 `dist/` 中有多个旧 TG115、Classic 和历史 release 产物，虽然它们未被 Git 跟踪，但正式 Release 必须隔离输出。

## 5. 品牌资源审计

`assets/brand/` 已实际读取并抽查预览，包含品牌说明和 10 个正式图形资源：

```text
tg2cloud-logo.svg
tg2cloud-icon.svg
tg2cloud-icon.png
tg2cloud-icon-32.png
tg2cloud-icon-64.png
tg2cloud-icon-128.png
tg2cloud-icon-256.png
tg2cloud-icon-512.png
tg2cloud.ico
tg2cloud-logo-preview.png
```

资源内容与 Brand Guide 描述一致：云朵、纸飞机、环绕/上行轨迹，主色为蓝/青色，横版包含 `TG2Cloud` 和 `From Telegram to Your Cloud`。本轮未生成、修改或覆盖任何品牌文件。

### 5.1 当前接入状态

- PySide6：尚未接入。`installer.py` 的 Window Icon 与页头图标使用代码内嵌的通用 `plane` SVG。
- PyInstaller：尚未接入。`build.ps1` 和现有 spec 均没有正式 ICO 配置。
- README：尚未接入，首屏仍为 `# TG115`。
- About/诊断：尚未展示正式 TG2Cloud Logo。
- 冻结资源：当前 build 只打包 payload，不打包 `assets/brand/`。

### 5.2 建议接入方式

1. 保留 `assets/brand/` 为唯一来源，不复制多套品牌资源。
2. PySide6 通过现有 `resource_path()` 读取冻结包中的 `assets/brand/tg2cloud-icon-256.png` 或 SVG，设置 Window Icon、页头和 About。
3. `build.ps1` 对两个目标统一使用 `assets/brand/tg2cloud.ico`，并以 `--add-data` 打包 UI 实际使用的品牌文件。
4. README 使用 `assets/brand/tg2cloud-logo.svg`；必要兼容场景使用现有 preview PNG。
5. 当前资源尺寸完整，审计阶段未发现需要派生的新尺寸。

## 6. 稳定核心审计

### 6.1 Telegram / Queue / SQLite / Restart Recovery

- 使用 Telethon Bot，只接收配置的 `ALLOWED_USER_ID`，并包含 `/start`、`/help`、`/queue`、`/status`、`/performance`、`/task`、`/confirm`、`/retry`、`/cancel` 等命令及扩展运维命令。
- `app/db.py` 维护 SQLite schema、状态转换、预算预留和任务历史。
- `TransferService.start()` 调用数据库恢复逻辑，处理完整文件、截断文件、已移动远端文件和清理待完成状态。
- 当前数据库文件名为 `tg115.db`，日志名为 `tg115.log`；这些是内部稳定标识，迁移时需单独决策和兼容，不能机械替换。

### 6.2 rclone / WebDAV / 大文件

- `app/rclone_client.py` 生成/校准 rclone WebDAV 配置，并执行上传、stat、move、delete 和健康探测。
- 普通文件先下载到本地再上传；超过本地任务预算的文件可通过 rclone `rcat` 流式写入，并带精确大小、背压、失败清理与恢复逻辑。
- rclone 命令日志会对 WebDAV 密码做替换；配置通过 Base64 环境字段传递，Base64 只是编码，不是加密，但传输路径为用户电脑到用户 VPS 的 SSH。

### 6.3 磁盘保护

- `LOCAL_TEMP_BUDGET_GB` 的核心默认值是 20GB，UI 两版也为 20GB。
- `MIN_FREE_DISK_GB` 的运行时 fallback 仍是 20GB；UI 当前 CloudDrive2 为 20GB、OpenList 为 8GB。
- TG2Cloud v1.0.0 要求两版统一默认 `LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`，因此 CloudDrive2 UI、运行时 fallback、测试和旧文档均需同步调整。
- 20GB 是任务预算而非分区，现有代码按并发任务占用和真实磁盘安全线分别控制，逻辑应保留。

### 6.4 verify

`app/verify_destination.py` 当前执行完整协议验收：

```text
认证
→ 准备/列目录
→ 上传 256 字节随机测试文件
→ 读取远端大小
→ 改名
→ 再次检查大小并确认旧名消失
→ 删除
→ 确认已删除
→ 失败时尽力清理临时对象
```

现有机器标记全部使用 `TG115_*`，`installer.py` 和测试又依赖这些标记。迁移到要求的 `TG2CLOUD_*` 时必须同步生产端、解析端和测试；为了降低回归风险，可在过渡期同时接受旧/新标记，但正式输出以 TG2Cloud 为准。

当前友好错误已经覆盖认证、目录、写入、大小、改名、删除、SSH 转发和固定端口占用等场景，但有一处产品耦合：共享 `verify()` 的认证/目录错误文案硬编码为 OpenList、`tg115` 用户和 `/115/Telegram`，CloudDrive2 失败时也可能显示 OpenList 文案。应改为按 ProductProfile 生成。

## 7. Tunnel 审计

- CloudDrive2 使用产品端口 19798，本地绑定 `127.0.0.1:19798` 并转发到 VPS `127.0.0.1:19798`。
- OpenList 使用产品端口 5244，本地绑定 `127.0.0.1:5244` 并转发到 VPS `127.0.0.1:5244`。
- `TunnelServer` 绑定固定端口；端口占用时直接给出明确错误，不会回退到随机端口。
- 打开浏览器前会发送真实 HTTP 探测；旧 Tunnel 失效时会关闭并按相同固定端口重建。
- 部署器关闭时 Tunnel 随窗口关闭。
- VPS Compose 的两个管理端口均只绑定回环地址，没有默认公网暴露。

“重新检测”当前体现为再次点击打开管理页/重试操作，没有单独命名为“重新检测端口”的按钮；后续 UI 验收时应确认是否需要更明确的按钮或错误对话框动作。

## 8. OpenList 特殊 UX 审计

现有实现已经具备：

- 使用 `secrets.choice()` 本地生成 28 字符管理员密码和 WebDAV 密码；
- 密码字段默认隐藏，支持显示/隐藏、复制和重新生成；
- 以 `openlist/data/data.db` 是否存在判断新实例/已有实例；
- 新实例把当前窗口生成的 `OPENLIST_ADMIN_PASSWORD` 交给 OpenList 容器初始化；
- 已有实例不会自动重置管理员密码，并可选择只在 VPS 内保留现有 WebDAV 配置；
- 管理员密码恢复需要二次确认，命令输出不进入普通日志；
- OpenList 日常日志经过 Shell 与 UI 两层脱敏；
- WebDAV 地址、用户名、密码、目标路径均提供复制，密码可重新生成。

需要改造或确认：

1. 当前首次密码是“部署器本地生成后注入”，不是“部署后从 OpenList 初始化输出自动获取”；需根据当前 OpenList 官方行为确认 v1.0.0 最终采用哪种受支持方式，但不能让用户 SSH 查日志。
2. 当前默认 WebDAV 用户是 `tg115`，应改为推荐的 `tg2cloud`。
3. 当前默认目标 `/115/Telegram` 和多处“115 Open”引导过度绑定 115；应改为多云中性默认/说明，同时把 115 保留为示例。
4. “恢复管理员密码”会真实重置现有密码，现有二次确认应保留。

## 9. update / repair / backup / restore / uninstall

### update

- 两版 `manage.sh` 都有 `update` 分支。
- 桌面“再次部署”路径对已有实例执行候选镜像预检、配置/数据库备份、替换、健康检查和失败回滚，实质上承担安全升级能力。
- PySide6 UI 没有独立“更新”按钮，OpenList 桌面允许动作白名单也不包含 `update`。

### repair

- CloudDrive2 有独立 `repair_clouddrive_network.sh` 和 PySide6“修复 CloudDrive2 网络”操作，包含旧环境识别、网络/别名修复、WebDAV 凭据恢复与 verify。
- OpenList 的同位置按钮实际映射为只读状态检查；另有独立重启 Bot/OpenList 操作，不是通用 repair。
- CloudDrive2 修复脚本高度硬编码旧容器、网络、目录和 `TG115_*` 标记，是运行命名迁移的高风险文件。

### backup / restore

- 两版远程安装都会在升级前自动备份程序配置和 SQLite，并在失败时自动回滚。
- OpenList 还备份 OpenList `data.db` 状态，PySide6 有“创建安全备份”按钮。
- CloudDrive2 只有备份库存/保留工具和升级时备份，没有对称的手动完整备份 UI。
- 当前没有用户可调用的手动 restore 命令/UI；只有安装失败自动回滚。

### uninstall

- 业务源码、Shell 和 PySide6 中均未发现卸载实现；`uninstall` 只出现在规划/检查清单文档。
- 正式 v1.0.0 若要求验收 uninstall，必须新增受控卸载：二次确认、明确删除范围、默认保留 Gateway 持久化数据，并确保绝不触碰旧 TG115 路径。

## 10. TG115 品牌与 115-only 残留

排除上游说明和 TG2Cloud 约束文档后，跟踪文件中仍有大量 `TG115` 引用（静态扫描约 585 行）。主要分为五类：

1. 用户可见品牌：PySide6 页头、应用/组织名、窗口标题、Bot 启动消息、README、CHANGELOG、Release Notes、运维日志。
2. 正式构建：EXE 名、CI 路径、构建环境变量、自检文件名和 Docker 测试标签。
3. 运行命名：容器、Compose 服务、Network、安装/备份目录、内部 WebDAV 主机名。
4. 内部兼容协议：`TG115_*` 环境变量、健康/verify 标记、VPS 探测标记。
5. 持久化/临时数据：`tg115.db`、`tg115.log`、`.tg115-verify-*`、`.uploading-*` 相关描述、临时部署前缀和 known_hosts 目录。

明确的 115-only 用户文案包括但不限于：

- 应用标题 `Telegram → 115 ... 部署器`；
- 页头 `TG115` / `Telegram → 115`；
- CloudDrive2/OpenList 页面要求“挂载 115”或“添加 115 Open”；
- verify 成功后要求只到“115 官方客户端”确认；
- Bot 启动信息 `Telegram → 115 服务已启动`；
- 默认 OpenList 目标 `/115/Telegram`；
- README 首屏与绝大部分教程仍以 TG115/115 为唯一定位。

允许保留 TG115 的位置：LICENSE 原版权、上游致谢、历史版本记录、迁移文档、必要兼容代码和兼容标记说明。不得为了表面统一删除这些血缘信息。

## 11. 隐私、安全与上游信息

静态审计观察：

- 未发现遥测、第三方统计或 Sentry/PostHog/Segment 等埋点实现/依赖。
- 未发现提交到源码的真实私钥或明显 Telegram Bot Token；扫描命中均为测试占位值或读取/脱敏逻辑。
- PySide6 `Redactor` 会记录当前敏感字段并清洗日志；OpenList 日志还有 Shell 脱敏层。
- OpenList 管理员重置的原始输出不进入普通日志。
- `.gitignore` 排除了 `.env`、私钥、session、`rclone.conf`、数据库和日志。
- `LICENSE` 存在，版权为 `TG115 Contributors`；README 已有原项目链接和二次开发致谢。
- 仓库没有 `NOTICE`。是否需要新增应依据上游/第三方许可证审查，不能凭空抹去或改写版权。

以上是静态检查，不等同于完整安全审计或历史 Git 秘密扫描，也未验证 VPS 上的实际文件权限。

## 12. 主要问题清单与优先级

### P0：发布阻塞

1. 两个正式 EXE、窗口标题、页头、应用组织名仍是 TG115/115。
2. CloudDrive2 仍为 v1.6.2；两版没有统一 TG2Cloud `1.0.0` 版本源。
3. 两版运行目录、容器和 Network 均未迁移到要求的 `tg2cloud-*` 命名。
4. 正式 TG2Cloud Icon/Logo 尚未接入 PySide6、PyInstaller、README、About。
5. `build.ps1` 未输出规定的两个 TG2Cloud EXE，也没有 EXE 版本资源。
6. CloudDrive2 的 `MIN_FREE_DISK_GB` 默认仍为 20，不符合 8GB 要求。
7. README/Release/CHANGELOG 仍是 TG115 历史体系，尚无 TG2Cloud v1.0.0 正式文档。

### P1：高风险一致性问题

1. 运行命名散落在 ProductProfile、Compose、Dockerfile、Shell、Python、CI 和测试中，不能全局替换。
2. CloudDrive2 修复脚本对旧网络/容器/备份目录有大量硬编码。
3. `vps_resources.py` 固定统计 `/opt/tg115-backups`，OpenList/新 TG2Cloud 备份空间可能统计错误。
4. verify 机器标记和解析器强耦合 `TG115_*`；改名必须同步并考虑兼容期。
5. 数据库、日志、临时文件和 known_hosts 路径仍使用 TG115，需明确“新命名”与“兼容旧数据”的边界。
6. 当前共享 verify 的友好错误文案硬编码 OpenList/115，存在跨 Edition 错误提示。
7. 历史 `dist/` 中有 Classic/TG115 EXE，发布打包若直接收集目录会混入禁发产物。

### P2：功能/交付缺口

1. uninstall 未实现。
2. 手动 backup UI 只在 OpenList 存在；手动 restore 两版均不存在。
3. update 存在 Shell/重复部署路径，但缺少清晰的桌面入口与发布说明。
4. 固定端口占用已有明确错误，但“重新检测”动作不够显式。
5. OpenList 首次管理员密码现为本地注入，需要确认是否满足最终“自动获取”定义。
6. `NOTICE` 缺失，第三方/上游要求尚需判定。

## 13. 不应重构的模块

以下模块已有明确实现与较丰富回归测试，品牌迁移期间只做必要命名/兼容改动：

- Telegram Bot 收件与 Allowed User 限制；
- Telegram 下载与重试；
- SQLite schema、状态机、队列和重启恢复；
- rclone WebDAV 封装；
- 大文件流式写入与背压；
- 磁盘预算、真实安全线和资源自适应窗口；
- verify 的实际写入/大小/改名/删除流程；
- SSH 主机密钥确认与 known_hosts；
- 固定 SSH Tunnel；
- 远端安装预检、升级备份、失败回滚和清理守卫；
- OpenList 已有实例不自动重置、WebDAV 配置仅在 VPS 内保留、管理员恢复不写普通日志。

## 14. 正式改造计划（等待确认后执行）

### 阶段 A：建立 TG2Cloud 命名与构建基线

1. 在 `deployer_products.py` 统一两个 Edition 的 `1.0.0`、正式标题、EXE 名和目标运行命名。
2. 把 `build.ps1` 改为只输出两个规定的 PySide6 EXE，并增加正式 ICO、版本资源、品牌 add-data 和严格产物检查。
3. 更新 CI 的构建、自检路径和断言；保留“Tkinter 源码/目标不存在”的测试。
4. 不复用或发布旧 Classic/Modern spec；正式构建以统一 `build.ps1` 为唯一入口。

### 阶段 B：品牌和多云文案

1. PySide6 Window Icon、页头、About 使用 `assets/brand/` 正式资源。
2. 把共享 UI 和 Bot 的用户可见 TG115/115-only 文案迁移为 TG2Cloud/用户自有云存储。
3. 115 只保留在示例、FAQ、人工验收示例和上游说明中。
4. OpenList 默认 WebDAV 用户和目标路径会影响新部署配置，已从纯文案阶段移至阶段 C，与运行命名和兼容策略一起修改。

### 阶段 C：运行命名迁移

1. 按 Edition 分别更新 Compose、ProductProfile、Shell 常量、Dockerfile、内部 WebDAV 主机名和测试。
2. 新 TG2Cloud 默认只写新目录/容器/Network，不自动接管旧 TG115。
3. 对环境变量、verify 标记、数据库/日志名采用明确迁移表；必要时短期双读或双标记，避免一次替换破坏解析器。
4. 把 VPS 资源探测中的备份目录改为产品参数，而不是固定 TG115 路径。

### 阶段 D：运维能力补齐

1. 保留现有安全升级/回滚，明确 update 的 UI 和文档入口。
2. 为两版建立对称、可验证的手动 backup；设计保守 restore。
3. 实现带二次确认的 uninstall，默认保留 Gateway 持久化数据，并严格限制删除目标为当前 Edition 的新路径。
4. 保留 CloudDrive2 专用网络修复和 OpenList 专用状态/管理员 UX，不强行抽象成同一后端动作。

### 阶段 E：文档、测试与发布验收

1. 更新 README、CHANGELOG、RELEASE_NOTES，新增 `docs/MIGRATION_FROM_TG115.md`，保留 LICENSE/上游致谢并判定 NOTICE。
2. 先运行静态/单元/场景/Shell/Compose 测试，再构建两个 EXE 并分别执行打包自检。
3. 在可用环境执行 VPS、Tunnel、WebDAV 和不同体积文件测试；不能实测的项目明确写“未测试”。
4. 用干净的发布目录生成恰好两个 EXE、SHA256 和最终验收报告。

## 15. 风险与控制措施

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 全局替换 TG115 | Compose/脚本/解析器不一致，部署或回滚失败 | 按 ProductProfile → Compose → Shell → Python → tests 顺序逐组迁移 |
| 新旧目录混用 | 静默覆盖旧 TG115 或读错备份 | 新装只使用 `tg2cloud-*`，旧路径只用于显式迁移检测/文档 |
| SQLite 文件名直接更换 | 队列和恢复数据丢失 | 决定保留内部名或实现原子迁移与回滚测试后再改 |
| verify 标记直接更换 | GUI 将成功误判为失败 | 生产/解析/测试同步，必要时先双读再移除旧标记 |
| 品牌文件未打包 | 源码运行正常、冻结 EXE 丢图标 | 自检同时检查外部品牌资源和 PyInstaller `_MEIPASS` 资源 |
| 旧 dist 混入 Release | 发布含 Classic/TG115 EXE | 构建到干净 TG2Cloud staging，执行白名单和数量断言 |
| 运维删除范围过宽 | 卸载误删用户数据或旧项目 | 路径实值校验、容器白名单、二次确认、默认保留 Gateway 数据 |
| 文案去 115 过度 | 丢失主要测试场景和上游血缘 | 只移除“唯一目标”暗示，保留示例、迁移和致谢 |
| 未经实测宣称通过 | 发布判断失真 | WORKLOG/验收表区分自动、人工、未测试 |

## 16. 第一阶段状态

- [x] 阅读四份项目约束文档。
- [x] 检查 `assets/brand/` 实际文件与预览。
- [x] 识别 CloudDrive2/OpenList 代码结构和两个 PySide6 入口。
- [x] 定位 Tkinter 旧 spec/历史产物及其当前非正式构建状态。
- [x] 定位 Docker、rclone、SQLite、Tunnel、verify、update、repair、backup、restore/rollback、uninstall 状态。
- [x] 检查 TG115 品牌、旧容器/路径、多云文案和构建残留。
- [x] 形成改造计划与风险控制。
- [x] 用户已确认审计结果并授权分阶段实施。
- [x] Phase 1：v1.0.0、产品配置与构建体系。
- [x] Phase 2：正式品牌资源与多云文案接入。
- [x] Phase 3：运行时命名迁移（源码阶段完成，真实 VPS 验收待做）。
- [x] Phase 4：现有运维能力边界、重复部署保护、状态与诊断收尾。
- [x] Phase 5：文档、自动测试、正式构建与 frozen 验收（真实 VPS 人工验收待完成）。
- [x] TG2Cloud v1.0.0 自动化测试。
- [ ] 两个正式 EXE 的真实环境/交互式人工验收（构建与 frozen 资源验收已完成）。

## Phase 3.1 审计校正（2026-09-19）

此前第 14 节阶段 D 中新增 restore/uninstall 的计划，以及第 15 节对应删除风险，属于历史审计
草案，**不再是 v1.0.0 实施范围**。Phase 4 只整理已有 update、repair、backup、重复部署、
诊断和状态能力；restore/uninstall 未形成成熟实现，作为已知限制/后续工作，不阻断本版发布。

最终新装默认值：`LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`，用户显式配置优先。
OpenList 新装 WebDAV 用户为 `tg2cloud`；两版目标子目录默认空，表示用户 WebDAV 根目录。
旧 OpenList `tg115` 用户和显式路径仍可使用，不执行自动用户/数据迁移。

`TG2CLOUD_*` 为当前正式机器状态协议。新 producer 只输出该前缀；桌面解析器优先读取新
前缀，仅为旧脚本输出兼容读取 `TG115_*`。容器内 `tg115.db`、校验临时文件名和内部
稳定标识保留，防止 SQLite 队列、重启恢复、清理及已部署数据产生非必要迁移风险。

旧 TG115 目录或已停容器是 legacy presence：告警并保留，可继续在新命名空间安装。旧容器
运行但未占固定端口时也不自动接管；19798/5244 被占用、目标新容器名冲突或目标目录无法
安全识别才是 runtime conflict，必须停止、提示人工处理后重新检测。不会停用或删除旧资源，
也不会自动换端口。真实 VPS 共存/升级仍待人工验证。

## Phase 5 最终审计状态（2026-09-19）

本节是 v1.0.0 当前结论，覆盖第 12～15 节的初始问题/计划快照；早期 P0/P1 列表保留用于
追溯，不再代表尚未修复的现状。

### 最终架构与命名空间

架构保持为 `Telegram → Private Bot → TG2Cloud → rclone → CloudDrive2/OpenList WebDAV
→ 用户云存储`。正式 Windows 应用只有 CloudDrive2/OpenList 两个 PySide6 Edition，版本
均为 1.0.0，共用 `assets/brand/` 主品牌。

CloudDrive2 新装使用 `/opt/tg2cloud-clouddrive2`、`tg2cloud-clouddrive2`、
`tg2cloud-clouddrive2-bot`、`tg2cloud-clouddrive2-net` 和固定回环端口 19798。OpenList
新装使用 `/opt/tg2cloud-openlist`、`tg2cloud-openlist`、`tg2cloud-openlist-bot`、
`tg2cloud-openlist-net` 和固定回环端口 5244。正式机器协议为 `TG2CLOUD_*`；默认磁盘值
为 20GB 任务预算和 8GB 安全空闲线，`TARGET_PATH` 默认空，OpenList 新装推荐用户为
`tg2cloud`。

### Legacy compatibility boundary

旧 `/opt/tg115-*`、`tg115-*` 容器/网络和 `TG115_*` 解析仅用于检测、告警及兼容读取。
legacy presence 与端口/新资源名 runtime conflict 分开处理；TG2Cloud 不自动停止、删除、
覆盖或原地迁移旧 TG115，也不在固定端口冲突时随机换端口。`tg115.db`、容器内 `/opt/tg115`
等内部稳定标识有意保留，避免破坏 SQLite 队列、恢复和现有数据。许可证与 TG115 上游归属
保留；MIT/当前仓库材料没有要求虚构独立 NOTICE。

### 实际验证覆盖

- 完整 pytest：219 collected，215 passed，4 skipped，36 subtests passed；4 个 skip 需要真实
  rclone/WebDAV 环境。Ruff、compileall、10 个 Shell 语法检查和 `git diff --check` 通过。
- 最终双 EXE 构建和各自 frozen self-test 通过；brand/payload 无缺失，GUI runtime、backend
  imports、产品 profile 和 v1.0.0 正确。
- 两个 frozen EXE 在 100%/125%/150% 下共生成 33 张页面/About 截图并抽样目视核对；
  Windows 版本资源、关联图标、SHA256 和正式 artifact 白名单验证通过。
- `dist/` 最终只有两个 PySide6 EXE 和 `SHA256SUMS.txt`。无 Tkinter、Classic、TG115、
  debug/test EXE。源码/产物扫描未发现真实凭据、私钥、本机路径、遥测或第三方统计。
- 当前机器没有 Docker CLI，也没有用户授权测试 VPS/Bot/云存储；真实 Compose、Fresh
  Install、Tunnel、WebDAV、Telegram、文件规模/Streaming、重复部署、Update、Repair、
  Backup、Legacy 共存以及容器实际环境变量均未测试。

### 最终风险与结论

当前未发现自动测试、构建、冻结资源、版本/品牌或 artifact 层面的 Release Blocker。剩余
主要风险来自真实基础设施组合尚未验收，以及 EXE 未签名、未在干净 Windows 环境验证；
Taskbar、Alt-Tab、Explorer 缓存、SmartScreen/Defender 也未测试。Restore、Uninstall 和
CloudDrive2 手动 Backup UI 未提供，是已文档化的 v1.0.0 限制。

最终状态为 **RELEASE CANDIDATE — MANUAL ACCEPTANCE PENDING**。必须按
`docs/MANUAL_ACCEPTANCE.md` 完成关键真实环境验收后，才可重新判断是否达到 READY。
