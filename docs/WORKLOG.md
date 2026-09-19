# TG2Cloud 工作记录

本文件记录 TG2Cloud v1.0.0 整合过程中的实际操作、修改、测试和未测试边界。未执行的检查不得记录为“通过”。

## 2026-09-19 — 第一阶段：只读审计

### 已完成

- 阅读仓库根目录：
  - `AGENTS.md`
  - `TG2Cloud-Codex-Kickoff-Prompt.md`
  - `TG2Cloud-BRAND-GUIDE.md`
  - `TG2Cloud-v1.0.0-RELEASE-CHECKLIST.md`
- 读取 `assets/brand/README.md`，枚举并计算正式品牌资源 SHA256，视觉抽查：
  - `tg2cloud-logo-preview.png`
  - `tg2cloud-icon-256.png`
- 确认 `assets/brand/` 中已有完整 SVG、PNG 多尺寸和 ICO；没有生成、派生、修改或覆盖品牌资源。
- 检查根目录、Git 状态、跟踪文件、被忽略的 build/dist/spec、本地历史构建产物和 GitHub Actions。
- 定位两个 PySide6 入口、共享 UI/SSH/Tunnel 后端、Edition 配置与 VPS 资源探测。
- 检查 CloudDrive2/OpenList Compose、安装、管理、修复、备份、管理员密码和 WebDAV 配置保留脚本。
- 检查共享 Telegram/SQLite/队列/重启恢复/rclone/流式传输/磁盘保护/verify 核心及测试覆盖结构。
- 静态扫描 TG115 品牌、旧运行命名、115-only 用户文案、版本、构建和品牌资源引用。
- 静态检查遥测/第三方统计关键词、明显私钥和 Bot Token 形态；未发现生产凭据或遥测实现。
- 创建 `docs/AUDIT.md`，记录当前结构、问题、计划和风险。

### 本轮产生的文件变更

- 新增 `docs/AUDIT.md`。
- 新增 `docs/WORKLOG.md`。

除上述两份审计文档外，没有修改业务代码、构建脚本、测试、既有文档或品牌资源。

### 测试状态

- 自动化单元/场景测试：未执行（本阶段只进行审计）。
- Ruff：未执行。
- Bandit：未执行。
- 依赖审计：未执行。
- ShellCheck：未执行。
- Docker Compose 校验：未执行。
- PyInstaller 构建：未执行。
- 打包 EXE 自检：未执行。
- VPS 部署/升级/回滚：未执行。
- SSH Tunnel：未执行。
- CloudDrive2/OpenList WebDAV：未执行。
- Telegram 实际转存与 10MB～5GB 文件测试：未执行。

### 等待确认

- 用户已确认审计结果，并要求严格按阶段开发、测试和汇报。

## 2026-09-19 — Phase 1：v1.0.0、产品配置、构建体系

### 阶段范围

本阶段只处理：

- 两个 Edition 的 TG2Cloud v1.0.0 产品身份；
- 正式 EXE 名；
- PyInstaller 双产品构建；
- Windows EXE Icon 与版本资源；
- 构建后自检；
- CI 和相应回归测试。

本阶段没有迁移容器、Docker Network、VPS 安装目录、SQLite 文件名、Shell 协议标记或 WebDAV 默认值；这些仍保持已调试成功的 TG115 运行实现，等待后续独立阶段处理。

### 已修改

- `deployer_products.py`
  - 新增统一版本源 `RELEASE_VERSION = "1.0.0"`；
  - 两个 Edition 统一使用 v1.0.0；
  - 产品标题改为 `TG2Cloud · CloudDrive2` / `TG2Cloud · OpenList`；
  - 正式可执行文件名改为 `TG2Cloud-CloudDrive2-Deployer` / `TG2Cloud-OpenList-Deployer`；
  - 运行目录、容器、Network 和 WebDAV 配置暂未改动。
- `payload_clouddrive2/app/__init__.py`
  - 共享 Bot 核心版本从 `1.6.2` 更新为 `1.0.0`；
  - 更新模块说明，不改变传输逻辑。
- `installer.py`、`installer_clouddrive2.py`、`installer_openlist.py`
  - 更新 TG2Cloud 产品/模块身份；
  - Qt Application/Organization 名称改为 TG2Cloud；
  - 默认本地自检文件名改为 `tg2cloud-self-test.txt`；
  - 未调整现有 UI 布局、字段、SSH、Tunnel 或部署行为。
- `build.ps1`
  - 默认仍一次构建 CloudDrive2/OpenList 两个 PySide6 版本；
  - 构建目标改为两个正式 TG2Cloud EXE；
  - 使用 `assets/brand/tg2cloud.ico` 作为两个 EXE 的正式图标；
  - 把 `assets/brand/` 加入冻结资源，为后续 PySide6 品牌接入准备统一来源；
  - 使用独立 Windows 版本资源写入 FileVersion、ProductVersion、ProductName、描述和原始文件名；
  - spec 输出移动到 `build/spec/`，不再在仓库根目录产生新 spec；
  - payload、品牌和版本文件均使用绝对源路径，避免 spec 目录改变后解析错误；
  - 构建后自动启动两个 EXE 的 `--self-test`，核对产品、版本、GUI、后端和 payload；
  - 构建环境变量更新为 `TG2CLOUD_BUILD_PYTHON`；
  - 构建前清理 `dist/` 根目录的旧 TG115 Deployer EXE，不触碰历史 release 子目录。
- `packaging/windows/TG2Cloud-CloudDrive2.version.txt`
- `packaging/windows/TG2Cloud-OpenList.version.txt`
  - 新增两个 Windows EXE 版本资源定义；
  - 法律版权继续保留 `TG115 Contributors`，不抹去上游血缘。
- `.github/workflows/tests.yml`
  - Windows 构建改用 TG2Cloud 环境变量和两个正式 EXE 名；
  - 构建脚本自身负责双 EXE 自检；CI 额外断言 TG2Cloud Deployer 产物集合恰好为两个；
  - Linux 测试镜像标签改为 `tg2cloud-bot:test`，不改变运行时 Compose。
- `tests/test_core.py`、`tests/test_deployment.py`、`tests/test_openlist.py`
  - 更新 v1.0.0、产品名、构建资源、版本资源和双 EXE 断言；
  - 继续断言 Tkinter 入口不存在、正式构建只有两个 PySide6 产品；
  - 继续保留旧运行命名断言，防止 Phase 1 意外改动稳定运行链路。

### 实际构建产物

```text
dist/TG2Cloud-CloudDrive2-Deployer.exe
  大小：54,442,583 bytes
  SHA256：067545CA3E9AD711D99C15C5CBCBDCD9C3AF3FD307BBF84923E57E093CBF3AC2

dist/TG2Cloud-OpenList-Deployer.exe
  大小：54,452,385 bytes
  SHA256：7A57B0E224A3C338D271EF40953F73DF7029950149FAB5DA2B01431B3BF3FB49
```

`dist/` 根目录检查：

- TG2Cloud Deployer EXE：2；
- TG115 Deployer EXE：0；
- Tkinter EXE：0。

两个 EXE 的 Windows 元数据均已读取确认：

- FileVersion：`1.0.0`；
- ProductVersion：`1.0.0`；
- ProductName 分别为两个 TG2Cloud Edition；
- OriginalFilename 与正式文件名一致。

### 自动测试结果

- Phase 1 针对性回归：27 项通过。
- 完整 `unittest`：203 项通过，4 项跳过。
  - 跳过项均为需要本机 `rclone` 的真实 WebDAV 集成测试；本机未安装 rclone。
  - 首次完整测试在只读沙箱中因没有可写临时目录失败；随后在 `build/test-temp` 可写临时目录中对同一代码重新执行并通过。
- Ruff：通过，`All checks passed!`。
- Python `compileall`：通过。
- PyInstaller 双 EXE 实际构建：通过。
- CloudDrive2 打包 EXE 自检：通过。
- OpenList 打包 EXE 自检：通过。
- `git diff --check`：通过。

PyInstaller warning 文件只包含 Windows 构建中常见的 POSIX/可选模块缺失项；两个冻结 EXE 的 GUI、后端导入和 payload 自检均通过。

### 构建中发现并修复的问题

首次实际构建发现：把 spec 输出移动到 `build/spec/` 后，PyInstaller 会相对 spec 目录解析相对 `--add-data` 路径，导致找不到 payload。已将脚本入口、payload、品牌资源和版本资源源路径统一转换为绝对路径；重新构建和双 EXE 自检均通过。

### 尚未测试

- Windows 用户可见 UI 的人工点击与视觉验收；
- 正式 Logo 在 PySide6 页头/About 中的显示（属于 Phase 2）；
- VPS SSH、实际部署、重复部署和升级回滚；
- 19798/5244 实际 SSH Tunnel；
- CloudDrive2/OpenList 真实 WebDAV；
- Telegram 实际转存和 10MB～5GB 文件；
- GitHub Actions 远端运行结果。

### 对稳定功能的影响

- CloudDrive2/OpenList 的 Compose、Shell、容器、Network、安装目录和 WebDAV 配置未修改。
- Telegram 下载、SQLite、队列、重启恢复、rclone、流式传输、磁盘保护和 verify 逻辑未修改。
- 本阶段影响集中在版本身份、构建产物和构建验证；完整回归通过，未发现稳定核心回退。

### 下一阶段计划（尚未开始）

Phase 2 计划接入 `assets/brand/` 到两个 PySide6 窗口、页头和 About，并处理 TG115/115-only 用户可见文案。开始前等待用户确认 Phase 1 结果。

## 2026-09-19 — Phase 2：TG2Cloud 品牌资源接入与用户可见文案迁移

### 阶段范围

本阶段只处理：

- `assets/brand/` 正式资源在两个 PySide6 Edition 中的运行时加载；
- 主窗口图标、页头和 About；
- README 首屏、Edition、构建产物名和多云定位；
- 部署器与 Bot 的用户可见 TG115/115-only 文案；
- 品牌资源缺失检测和相应自动测试。

本阶段没有修改 Compose、容器、Network、VPS 安装目录、内部 WebDAV 主机名、SQLite 文件名、Shell 成功标记或 verify 协议。OpenList 的 `tg115` 用户、`/115/Telegram` 默认路径以及远程脚本中的 TG115 兼容标记仍属于运行时配置，随 Phase 3 一并迁移，避免品牌改字阶段改变已调试部署行为。

### 已修改

- `installer.py`
  - 新增正式品牌资源清单，统一通过现有 `resource_path()` 同时支持源码目录和 PyInstaller `_MEIPASS`；
  - 主窗口和 QApplication 使用 `assets/brand/tg2cloud-icon-256.png`；
  - 页头使用正式 Icon、`TG2Cloud` 和 `From Telegram to Your Cloud`，并按 Edition 显示 CloudDrive2/OpenList；
  - About 使用 `assets/brand/tg2cloud-logo.svg`，显示 Edition、v1.0.0、界面版本和隐私边界；
  - `dependency_report()` 与打包自检新增 `brand_missing`，品牌资源缺失时不再报告 ready；
  - 导出日志默认名更新为 `tg2cloud-时间.log`；
  - 将 WebDAV、验收、OpenList 引导、备份结果和下一步提示迁移为多云文案，115 只作为示例；
  - 保留所有 `TG115_*` Shell/verify 解析标记，未改变远程行为。
- `README.md`
  - 首屏接入 `assets/brand/tg2cloud-logo.svg`；
  - 新增正式标语和 `Telegram → TG2Cloud → CloudDrive2/OpenList → Your Cloud` 架构；
  - 版本统一为 `TG2Cloud v1.0.0`，列出两个正式 Edition 和 EXE；
  - 仓库与 Release 链接更新为 TG2Cloud；
  - 改为用户自有云存储定位，115 明确为主要测试/文档示例之一；
  - 保留 TG115 上游来源、兼容运行路径和兼容验收标记，并明确这些不代表 115-only。
- `payload_clouddrive2/app/main.py`、`bot_commands.py`、`states.py`
  - Bot 启动通知和帮助标题更新为 TG2Cloud；
  - 历史人工确认展示改为中性的“云存储官方端”，不修改数据库状态和方法；
  - 传输、队列、SQLite 和 rclone 行为未改动。
- `payload_clouddrive2/app/config.py`、`backup_database.py`
  - 仅更新面向用户的错误/帮助文案；环境变量名与脚本成功标记保持兼容。
- `tests/test_core.py`、`tests/test_openlist.py`、`tests/test_deployment.py`、`tests/test_optimizations.py`、`tests/test_scenarios.py`
  - 增加正式品牌资源、两个 Edition 页头/窗口图标、About Logo、README 和 Bot 文案断言；
  - 打包自检 mock 同步包含 `brand_missing`；
  - 原有运行命名断言继续保留，防止 Phase 2 越界。

`assets/brand/` 中没有新增、覆盖或重新生成任何图片；本阶段只读取并接入现有正式资源。

### 自动测试结果

- Phase 2 定向 pytest：9 项通过。
- 完整 pytest：200 项通过、4 项跳过、2 个 subtests 通过。
  - 4 项跳过均为需要本机 `rclone` 的真实 WebDAV 集成测试；本机未安装 rclone。
- Ruff：通过，`All checks passed!`。
- Python `compileall`：通过。
- `git diff --check`：通过。
- CloudDrive2 离屏 UI 预览：4 个页面截图生成成功。
- OpenList 离屏 UI 预览：5 个页面截图生成成功。
- OpenList About 离屏截图：生成成功。
- 人工查看上述截图：正式 Icon、TG2Cloud 页头、Edition 区分和横版 About Logo 均正常；未发现拉伸、空白资源或旧 TG115 页头。

本轮按用户指定的快速验证策略执行，没有重新打包 PyInstaller EXE。Phase 1 已确认 `assets/brand/` 会进入两个冻结包；Phase 2 新增的 `brand_missing` 会在下次正式构建自检中直接校验冻结资源。

### 尚未测试

- Windows 桌面上的实际任务栏图标、Alt-Tab 图标和高 DPI 多显示器效果；
- 本阶段代码重新打包后的两个 EXE（按快速验证策略未重复构建）；
- GitHub README 对内嵌 SVG 的线上渲染；
- VPS SSH、实际部署、重复部署和升级回滚；
- 19798/5244 实际 SSH Tunnel；
- CloudDrive2/OpenList 真实 WebDAV；
- Telegram 实际转存和 10MB～5GB 文件。

### 对稳定功能的影响

- 没有修改 Compose、Shell、容器、Network、安装目录、内部 WebDAV 地址或 Tunnel 端口。
- 没有修改 Telegram 下载、SQLite schema/状态值、队列、重启恢复、rclone、流式传输、磁盘保护或 verify 逻辑。
- Bot 变更仅限通知、帮助和历史确认状态的显示文本。
- 完整 pytest、Ruff 和 compileall 均通过，未发现 CloudDrive2/OpenList 稳定核心回退。

### 下一阶段计划（尚未开始）

Phase 3 将单独处理运行时命名迁移：按 Edition 更新 `/opt/tg2cloud-*`、容器、Network、内部 WebDAV 主机、OpenList 推荐用户/中性目标目录、日志/数据库兼容策略、Shell 与 verify 标记，并明确检测但不静默覆盖旧 TG115。开始前等待用户确认 Phase 2 结果。

## 2026-09-19 — Phase 3：运行时命名空间与兼容迁移

### 本阶段修改

- `deployer_products.py`：为两个 Edition 指定 TG2Cloud 安装目录、备份目录、Bot/存储容器、
  Compose 服务、Docker Network 和内网 WebDAV 地址；OpenList 推荐用户改为 `tg2cloud`、
  目标路径改为 `/Telegram`；显式列出对应旧 TG115 资源供识别。
- `payload_clouddrive2/docker-compose.yml`、`payload_openlist/docker-compose.yml`：新部署
  使用各自的 `tg2cloud-*` 容器和 Network。保留指向新服务名的旧 Compose 环境变量别名。
- `payload_clouddrive2/remote_install.sh`、`payload_openlist/remote_install.sh`、两版
  `manage.sh`、CloudDrive2 `repair_clouddrive_network.sh`、`backup_retention.sh` 及
  OpenList `openlist_admin.sh`、`preserve_webdav_config.sh`：切换外部运行路径和服务名；
  在软件安装、目录创建和旧容器操作之前识别同 Edition 旧目录/容器并明确拒绝隐式迁移。
  旧 Network 只提示，不连接或删除。CloudDrive2 网络修复只操作新 Network；host 网络修复
  同步更新 `WEBDAV_URL_B64` 与 `CD2_WEBDAV_URL_B64`。
- `installer.py`、`vps_resources.py`、`payload_clouddrive2/app/config.py`、
  `deployment_check.py`：拒绝用户手填旧安装目录；本机 SSH 主机记录使用新的 TG2Cloud
  目录，检测旧记录时要求重新核对指纹而非自动导入；资源探测按 Edition 统计新备份目录；
  新配置写入 `TG2CLOUD_*` 并保留必要的旧变量别名；验收网络错误识别新旧 DNS 名。
- `README.md`、`CHANGELOG.md`、`docs/README-小白使用说明.md`、`docs/填写信息清单.md`：
  更新新安装的路径、命令和运行名称。新增 `docs/MIGRATION_FROM_TG115.md`，说明备份、
  固定端口冲突、手动迁移边界及敏感配置处理。
- `tests/test_core.py`、`tests/test_openlist.py`、`tests/test_deployment.py`、
  `tests/manage_harness.sh`：更新外部命名契约，覆盖旧路径拒绝、兼容变量、脚本预检顺序、
  新旧 DNS 错误提示和修复脚本的双 WebDAV URL 字段。

### 有意保留的兼容标记

- 容器内 `tg115.db`、`tg115.log`、Linux UID/GID 10001 对应的内部工作目录/用户名、
  verify 临时文件前缀暂不改名；没有自动复制或迁移旧数据库。
- `TG115_*` Shell/verify 结果标记及部分内部辅助函数名保持与当前 PySide6 解析器一致。
  新配置优先读 `TG2CLOUD_*`，仍能读取旧配置变量，避免为品牌清零破坏稳定协议。
- 固定 Tunnel 端口 19798/5244、Telegram/SQLite 队列、rclone、WebDAV 数据传输、
  流式大文件、磁盘保护与 verify 操作语义均未重写。

### 自动验证结果

- Phase 3 定向 pytest：134 passed，2 subtests passed。
- 完整 pytest：205 passed、4 skipped、2 subtests passed。4 个跳过项需要本机 `rclone`
  真实 WebDAV 集成环境；不能视为通过。
- Ruff：`All checks passed!`。
- Python `compileall`：通过。
- Bash `-n`：两版安装/管理、CloudDrive2 修复/备份、OpenList 管理员/配置保留脚本通过。
- `git diff --check`：通过；Git 仅提示工作区 LF/CRLF 换行符转换，不是差异错误。

本阶段按快速验证策略没有重新构建两个 EXE。

### 尚未测试与风险

- 无本机 Docker CLI/真实 VPS：未运行 `docker compose config`、实际新装、旧 TG115
  资源共存检测、重复部署、升级回滚、网络修复和 OpenList 管理员首次初始化。
- 未执行真实 SSH Tunnel、WebDAV 写入、Telegram 转存和 10MB～5GB 文件传输；
  这些结果不能从源码测试推断为已通过。
- 同一 Edition 的新旧受管实例使用相同固定管理端口；同 VPS 并行运行不受支持。
  当前部署器遇到同 Edition 旧目录/容器会拒绝，而不会自动迁移或停止旧服务。
- 仓库现有 CloudDrive2 `MIN_FREE_DISK_GB` 默认值仍为 20，与 `AGENTS.md` 的 8GB
  约束不一致；Phase 3 未修改磁盘保护默认值，须在后续独立阶段审定并测试。

### 对已有稳定功能的影响

外部安装目录、Compose 服务、容器、Network、内网 WebDAV 主机名和 OpenList 新装默认
WebDAV 用户/路径发生变化；因此源码回归通过不等于 VPS 运行验证通过。现有 TG115 运行
资源不被新部署器接管或覆盖。两套已调试的 Telegram/SQLite/rclone/streaming/verify 核心
未重构，兼容状态标记和数据库文件名保留。

### 下一阶段计划（尚未开始）

等待用户确认 Phase 3 后再进入 Phase 4：分别核对 update、手动 backup、保守 restore 与
带二次确认的 uninstall；优先延续现有安全升级/回滚，并将任何删除范围限定为当前 Edition
的新 TG2Cloud 资源。

## 2026-09-19 — Phase 3.1：Runtime Migration 收尾修正

### 对 Phase 3 记录的校正

Phase 3 记录中的 CloudDrive2 20GB 磁盘安全线、旧目录/旧容器一律阻断、OpenList 目标
`/Telegram`、`TG115_*` 作为现行输出协议，以及 Phase 4 新增 restore/uninstall，均由本节
覆盖；以上是历史阶段快照，不再代表 v1.0.0 最终规格。**本阶段未进入 Phase 4。**

### 实施结果与文件

- 默认配置：`installer.py`、`deployer_products.py`、`payload_clouddrive2/app/config.py`
  将两版新装统一为 `LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`；OpenList 新装
  WebDAV 用户为 `tg2cloud`、目标子目录为空。`.env` 生成沿用用户输入值；Compose 通过
  `env_file` 透传，无需改 Compose 或磁盘算法。旧实例显式配置不自动重置。
- 正式状态协议：`installer.py`、`vps_resources.py`、
  `payload_clouddrive2/app/{verify_destination,deployment_check,backup_database}.py`、
  `payload_clouddrive2/{remote_install,repair_clouddrive_network,manage,backup_retention}.sh`、
  `payload_openlist/{remote_install,manage,openlist_admin,preserve_webdav_config}.sh`。
  新输出为 `TG2CLOUD_*`；解析器优先新前缀，仅兼容读取旧 `TG115_*`；VPS probe
  新旧边界也采用同样优先级。verify 的认证、列目录、上传、大小、改名、复验、清理操作
  顺序没有变。
- 根路径：`payload_clouddrive2/app/rclone_client.py` 仅在目标非空时执行 `mkdir`；
  空目标直接访问 WebDAV 根目录，`remote:filename` 不会产生重复斜杠。
- 旧实例识别：两版 `remote_install.sh` 对旧目录、已停容器和未占端口的运行容器只告警；
  对 19798/5244 端口冲突、目标新目录无法识别或新容器名被别的部署占用明确停止。
  CloudDrive2 安装/网络修复排除旧 `tg115-*` 容器，不连接、不停用、不删除旧资源；
  端口占用提示用户自行处理并重新检测。
- 测试：`tests/test_core.py`、`tests/test_openlist.py`、`tests/test_deployment.py` 新增
  默认值/显式覆盖、两版 `.env`、machine marker 新旧优先级、根路径及上传目标、
  旧/运行容器和端口冲突模拟；保留旧协议兼容测试。
- 文档：`README.md`、`CHANGELOG.md`、`RELEASE_NOTES.md`、
  `TG2Cloud-v1.0.0-RELEASE-CHECKLIST.md`、`docs/AUDIT.md`、
  `docs/MIGRATION_FROM_TG115.md`、`docs/README-小白使用说明.md`、
  `docs/填写信息清单.md`。明确新默认、共存边界、正式协议和 Phase 4 限定范围。

### 兼容边界与剩余 TG115 引用分类

1. Legacy machine parser：`installer.py` 的 `machine_markers()` 与
   `vps_resources.py` 的旧 probe 边界，仅在新标记缺席时读取旧输出。
2. SQLite/稳定内部标识：`tg115.db`、`tg115.log`、容器内 `/opt/tg115` 与 Linux
   用户名、verify 临时文件前缀、备份辅助函数名、日志 logger 名；避免队列恢复、持久化和
   清理行为变化。未改 schema、队列模型或重启恢复。
3. 迁移/历史文档：`docs/MIGRATION_FROM_TG115.md`、旧版验收报告、旧 prompt、
   `AGENTS_old.md` 等为历史事实，不作为新装命名。
4. 许可证/上游：`LICENSE` 中 TG115 Contributors、README 上游致谢保留；仓库目前无
   独立 `NOTICE` 文件，不能虚构一个。
5. 兼容环境别名及旧资源检测：`TG115_*` 环境变量、旧容器/目录/网络名仅用于读取旧
   配置、回滚兼容或冲突识别；`build.ps1` 的旧 EXE 名只用于正式发布排除清单。
6. 兼容测试：旧 marker、旧环境键、SQLite 文件名及旧容器名的测试保留。
7. 新 TG2Cloud 运行时错误引用：复查源码未发现旧 `/opt/tg115-*` 或 `tg115-*`
   被用作新安装目标；容器内历史 `/opt/tg115` 与主机安装目录不是同一命名空间。

### 验证与未测

- Phase 3.1 定向 pytest：140 passed、18 subtests passed。
- 完整 pytest：211 passed、4 skipped、18 subtests passed；收集到 215 个顶层测试。
  Phase 3 收集项为 209（205 passed + 4 skipped），本阶段新增 6 项顶层测试；
  subtests 由 2 增至 18，主要来自四种路径、两版旧资源与端口情境。Phase 1 的 203/4、
  Phase 2 的 200/4/2 是各阶段测试集合快照，不能只比较 passed 数字。
- Ruff：全仓 `check . --no-cache` 通过。Python `compileall` 通过。
- Bash `-n`：两版安装/管理、CloudDrive2 修复/备份、OpenList 管理员/配置保留脚本通过。
  Git Bash 在受限沙箱内无法创建信号管道，改用批准的执行权限后只读检查通过。
- `git diff --check`：通过；仅有 Git LF/CRLF 未来转换警告。
- Docker CLI 当前不可用，且本阶段未改 Compose；`docker compose config` 未执行。
- 真实 VPS、旧 TG115 共存/端口占用、实际升级回滚、WebDAV 和 Telegram 转存均未测试；
  不能把脚本模拟当作 VPS 验收。本阶段没有重新构建 EXE。

### 对稳定功能的影响和下一阶段边界

未修改 Telegram 下载/Bot 业务、SQLite schema/队列/重启恢复、流式决策、磁盘保护算法、
固定 Tunnel 或 verify 操作流程。rclone 只修空目标时避免对远端根目录执行 `mkdir`，
其余传输架构未动。Phase 4 如获用户确认，仅整理已有 update、repair、backup、重复部署、
诊断及状态能力；**不新增 restore/uninstall**，两者是 v1.0.0 已知限制而非发布阻断项。

## Phase 4：现有运维能力子审计（代码修改前）

本轮先核对了两版部署器、`manage.sh`、`remote_install.sh`、CloudDrive2 网络修复、
OpenList 配置保留及备份清理脚本。以下为实施前现状，不代表下述问题已修复。

- Update：两版 `manage.sh update` 已存在，分别构建 Bot、拉取/启动对应服务并等待健康；
  当前 PySide6 没有独立 Update 按钮。该命令在既有目录内运行，不主动替换 `.env` 或
  bind mount 数据，但必须在真实 VPS 上验证结果。
- Redeploy：PySide6 的“一键部署基础环境”再次运行时会重新生成候选 `.env`；两版
  `remote_install.sh` 均把候选文件复制到已安装目录。若用户只使用本次表单默认值，
  旧 Telegram/WebDAV/磁盘预算等设置可能被覆盖；这是本阶段优先修复的风险。
  OpenList 的可选 `preserve_webdav` 仅保护部分 WebDAV/管理员字段，不覆盖全部配置。
- Repair：CloudDrive2 有现成网络修复入口、固定 19798 端口和当前 Edition 网络范围；
  OpenList 没有对称的网络修复，现有“检查”是只读状态核验，不应伪装成修复。
- Backup：OpenList 已有手动备份入口；暂停服务后保存配置归档、SQLite 快照和已初始化
  OpenList 状态，失败时清理本次产物并尝试重启。CloudDrive2 仅有重部署前自动配置/
  数据库快照及备份列举、清理，没有手动备份 UI。两版备份位于各自 TG2Cloud 目录，
  清理脚本以该目录为边界；归档包含 `.env`/可能包含 `rclone.conf`，须保持本机权限
  并避免在日志中泄露。没有正式 Restore 或 Uninstall 功能。
- Status/diagnostics：OpenList 管理脚本能输出健康标记；CloudDrive2 的 `status` 目前
  主要是 `docker compose ps`，缺少统一可解析状态。未安装、已停、旧 TG115 与运行中
  的区分在桌面端也不完整。现有本机诊断/日志导出做脱敏，无远程诊断包。
- 危险命令：安装脚本的 `rm -rf` 用于限定在本 Edition 安装目录内的程序文件和带
  TG2Cloud 前缀的暂存目录；部署器 SSH 暂存目录删除有路径校验。未发现维护脚本
  执行 `docker compose down -v`、`docker volume rm` 或 `chmod 777`。备份清理
  使用目录、文件名和符号链接校验后的 `rm -f`。这些路径保护需随修改回归复查。
- Legacy 边界：旧 `/opt/tg115-*`、旧容器仅用于识别/告警及必要解析兼容；
  Phase 4 的 update、repair、backup、status 不得把它们当作操作目标。

实施范围：优先补重复部署的显式配置保留/覆盖语义和必要的状态、结果核验；只为
既有能力增补测试与说明，不扩大为 Restore/Uninstall 或重写稳定传输核心。

### Phase 4 实施结果

- Repeated deployment：新增共享 `preserve_runtime_config.sh`。只有在安装脚本已确认当前
  Edition 的 TG2Cloud Compose 后才启用；默认用 `install -m 600` 在 VPS 内把现有 `.env`
  复制到候选配置，不读取回 Windows、不打印内容。现有配置缺失或为符号链接时失败关闭。
  PySide6 增加明确的“使用本页配置覆盖 VPS 当前 `.env`”勾选项，默认关闭；用户明确勾选
  后才应用表单配置。OpenList 还可选择在显式覆盖时仅保留现有 WebDAV 与管理员字段。
- 持久化保护：两版 `remote_install.sh` 仍只替换程序清单内文件；SQLite、下载、日志、
  `config/rclone/rclone.conf`、CloudDrive2 `clouddrive/`、OpenList `openlist/data/` 不进入
  `remove_program_files`。没有加入 `compose down -v`、volume 删除或网关数据清空。
- Update：保留两版现有 `manage.sh update` 入口。CloudDrive2 构建并核验 Bot；OpenList
  拉取固定 OpenList 镜像、构建 Bot 并核验两个服务。二者只有全部命令和健康检查成功后才
  输出 `TG2CLOUD_UPDATE=OK`；不替换 `.env`，不读取旧 TG115 目录。
- Status：两个 PySide6 Edition 均使用只读 probe 区分 `RUNNING`、`STOPPED`、
  `NOT_INSTALLED`；当前 TG2Cloud 的 install path、Bot、网关和 Network 必须匹配，OpenList
  还检查 5244 回环 HTTP。旧 TG115 只输出独立 `TG2CLOUD_LEGACY=DETECTED` 提示，不能
  使 TG2Cloud 状态变成运行中。CloudDrive2 `manage.sh status` 也补充正式状态标记；
  OpenList 已停状态统一为 `TG2CLOUD_STATUS=STOPPED`。
- Repair：CloudDrive2 保持既有网络修复职责和新 TG2Cloud namespace；未扩为系统/Docker
  万能修复。OpenList 没有新增网络 repair，其已有“检查”继续执行服务健康核验。
- Backup：CloudDrive2 没有新增手动备份 UI，保留重部署前配置/SQLite 快照和只读盘点、
  显式 retention。OpenList 手动备份仍保存程序配置（含 `.env`、`rclone.conf`）、可用时的
  SQLite 快照与已初始化 OpenList 状态（排除 temp/log）；不含 downloads、TG2Cloud logs
  或云端文件。备份目录为对应 `/opt/tg2cloud-*-backups`，目录 `700`、敏感文件 `600`；
  retention 只识别目录内 `config-*`、`database-*`、`env-*`、`openlist-state-*` 普通文件。
- Diagnostics：未新增诊断包。保留本机依赖诊断/脱敏日志导出；OpenList 的远程近期日志继续
  经过密码、Token、API Hash、Secret 和 URL userinfo 脱敏；CloudDrive2 的 SSH 日志入口
  本阶段补齐相同脱敏管道及测试。不会复制完整 `.env` 或
  `rclone.conf` 到公开诊断。
- Restore/Uninstall：没有新增正式功能。安装失败时原有内部回退仍只用于本次升级失败；
  不包装为用户可调用 Restore。Uninstall 继续作为已知限制。
- 文档：README 明确重新部署默认配置保护、状态、Update 与精确备份边界；迁移文档明确
  TG2Cloud 运维不会原地升级 TG115；CHANGELOG/Release Notes 同步真实能力。

### Dangerous command 最终审计

- `rm -rf`：两版安装脚本只删除 `${INSTALL_DIR:?}` 下固定 `PROGRAM_PATHS`，以及严格匹配
  `/opt/tg2cloud-<edition>-release-*` 的暂存目录；部署器只删除通过
  `re_safe_remote_stage()` 校验的 `/tmp/tg2cloud-deploy-<hex>`。Dockerfile 只清理镜像层
  `/var/lib/apt/lists/*`。未发现空变量或用户任意路径直接进入 `rm -rf`。
- `docker compose rm -sf`：仅在本次安装失败的原有内部回退中移除当前 Edition Bot 服务，
  随后恢复升级前程序/配置；不带 `-v`，不操作网关数据卷。
- 未发现维护路径使用 `docker rm`、`docker network rm`、`docker volume rm`、
  `docker compose down`/`down -v` 或 `chmod 777`。
- retention 仅对已验证物理备份目录内、受控命名且非符号链接的普通文件执行 `rm -f`；
  不触及 TG115 备份或其他文件。

### Phase 4 验证

- 定向 pytest（deployment + OpenList）：44 passed、32 subtests passed。
- 完整 pytest：收集 219 个顶层测试，215 passed、4 skipped、36 subtests passed。
  Phase 3.1 为 215 collected / 211 passed / 4 skipped / 18 subtests；本阶段新增 4 个顶层
  测试，覆盖运行/停止/未安装/legacy 状态、默认保留与显式覆盖配置、两版 update 成败、
  `.env`/SQLite/`rclone.conf` 不变和 CloudDrive2 日志脱敏；新增场景使 subtests 增至 36。
- Ruff：`check . --no-cache` 通过。Python `compileall` 通过。
- Bash `-n`：两版安装/管理、配置保留、CloudDrive2 修复、备份 retention 和测试 harness
  全部通过。
- `git diff --check`：通过；仅显示工作树未来 LF/CRLF 转换警告。
- Docker CLI 当前不可用，`docker compose config` 未执行。本阶段没有修改 Compose 文件。
- 未连接真实 VPS；真实重复部署、Update、Repair、Backup、Docker/OpenList HTTP、Telegram
  与 WebDAV 端到端均未实测。没有重新构建 EXE。

### 稳定核心与 Phase 5 边界

本阶段未修改 Telegram Bot/下载、SQLite schema/队列/重启恢复、rclone 传输核心、流式策略、
Tunnel 或 verify 操作流程；没有触碰 `assets/brand/`、版本、构建脚本或 PyInstaller 元数据。
Phase 5 前主要风险仍是真实 VPS 上两版首次安装/重复部署/失败回退/备份、固定 Tunnel、真实
WebDAV/rclone/Telegram 链路和最终双 EXE frozen 验收尚未完成。

## 2026-09-19 — Phase 5：Final Validation / Release Candidate

### 最终源码与文档收尾

- 最终静态审计按“legacy compatibility / internal stable identifier / upstream attribution /
  migration/history / compatibility tests / genuine omission”分类剩余 `TG115/tg115`。没有为了
  清零字符串删除 legacy parser、旧实例检测、`tg115.db` 或容器内稳定路径。
- `installer.py` 的截图验收模式补充 About 对话框抓图，使 frozen 验收可以直接验证 About
  Logo、Edition、版本、依赖和资源状态；没有修改正常交互流程、SSH、Tunnel 或部署逻辑。
- `README.md`、`CHANGELOG.md`、`RELEASE_NOTES.md` 和小白说明完成 v1.0.0 RC 文案收尾；
  CloudDrive2 网盘准备改为多云表述，重复部署说明与 Phase 4 的默认保留 `.env` 行为一致。
- 新增 `docs/MANUAL_ACCEPTANCE.md`，用无真实秘密的占位符列出 CloudDrive2/OpenList
  Fresh Install、Tunnel、WebDAV、Telegram、重复部署、Update、Repair/Check、Backup、
  文件规模、磁盘/Streaming、Legacy 冲突和发布决策步骤。
- Release Checklist 按真实证据更新；自动化与真实 VPS 测试明确分开，未测试项未勾选。

### v1.0.0 Release Candidate 自动测试基线

- Phase 5 定向 pytest（core + deployment + OpenList）：144 passed、36 subtests passed。
- 完整 pytest：收集 219 个顶层测试，215 passed、4 skipped、36 subtests passed；4 个 skip
  仍需要真实 `rclone`/WebDAV 集成环境，不视为通过。
- Ruff：通过（`All checks passed!`）。
- Python `compileall`：通过。
- Bash `-n`：10 个 Shell 脚本通过。
- `git diff --check`：通过；仅有 Git 的 LF/CRLF 未来转换提示。
- Docker CLI：当前机器不可用，`docker compose config` 未执行。

### 唯一一次正式 Final Build 与 frozen 验证

- 在验证 `dist` 为工作区直接子目录后，仅清理该输出目录；旧 TG115/Classic 历史产物未进入
  新 `dist`。随后只执行一次 `build.ps1 -Edition All`，两个 PyInstaller 构建均成功。
- 构建脚本的两个 frozen self-test 均为 `result=OK`：`app_version=1.0.0`、PySide6 6.11.2、
  Paramiko 5.0.0、payload/brand 无缺失、GUI runtime 与 backend import 均为 OK，remote test
  明确为 `NOT_RUN`。
- 两个 frozen EXE 分别在 Qt scale factor 1.00、1.25、1.50 启动截图模式。CloudDrive2 每个
  比例 5 张、OpenList 每个比例 6 张，共 33 张；页头、正式 Logo、Edition、v1.0.0、表单、
  按钮、日志区和 About 资源均成功生成并抽样目视检查。窗口模式 EXE 启动后异步返回，验收
  脚本等待 PNG 写入完成后判定；这不是产品错误。
- 从两个 EXE 提取的 Windows 关联图标均为 TG2Cloud 正式图标。版本资源中的 Product Name、
  Product/File Version、File Description 与 Original Filename 均符合各自 Edition。
- Taskbar、Alt-Tab、Explorer 图标缓存、交互式窗口操作和 Windows 干净机未测试；离屏截图
  与资源自检不能替代这些人工项目。两个 EXE 均为 `NotSigned`，作为已知限制记录。

### 最终 Release artifacts

本地 Phase 5 构建时，`dist/` 仅包含以下三个验证文件；它们是本机冻结验证证据，
不是 GitHub Release 上传来源：

- `TG2Cloud-CloudDrive2-Deployer.exe`：54,454,325 bytes；SHA256
  `ee1619185e9ecf39573f017fe4a0c818b63ecfd14b73d2f0fc815f8bda656ec7`。
- `TG2Cloud-OpenList-Deployer.exe`：54,463,903 bytes；SHA256
  `c486e51a0a2d54b6d768ef3f892784386760263723f23aa342e715de192db172`。
- `SHA256SUMS.txt`：仅列出上述两个 EXE；逐项重算验证通过。

正式 EXE 数量：PySide6 2；Tkinter 0；TG115 0；Classic 0；Debug/Test 0。二进制静态扫描
未发现私钥头、Bot Token 形态或本机仓库绝对路径。源码扫描的唯一 Bot Token 形态命中是
`tests/test_deployment.py` 中明确的假测试 fixture；跟踪文件中无 `.env`、`rclone.conf`、
私钥、数据库或日志。未发现 telemetry、第三方 analytics、`chmod 777`、正常维护路径中的
`compose down -v` 或对根目录/用户目录的无限制 `rm -rf`。

### 验证分类与最终状态

- A. 已自动测试：pytest、Ruff、compileall、Shell 语法、diff、命名空间/固定端口/协议/
  配置保护/Update 成败/Status/Repair/Backup 边界、双 EXE 构建、自检、冻结资源、元数据、
  SHA256 和 artifact 白名单。
- B. 已本机视觉检查：从最终 frozen EXE 生成的 100%/125%/150% 页面与 About 截图、两个
  EXE 提取图标；没有把离屏检查描述成交互式人工操作。
- C. 已真实 VPS 测试：无。当前没有用户明确授权并配置的测试 VPS/Bot/云存储。
- D. 未测试：真实 Fresh Install、Docker/容器环境、Tunnel、Gateway 登录、WebDAV 全操作、
  Telegram 端到端、10MB～5GB 文件、Streaming、真实重复部署/Update/Repair/Backup、
  Legacy 共存冲突、Taskbar/Alt-Tab/Explorer、SmartScreen/Defender、代码签名和干净机。

当前结论：**RELEASE CANDIDATE — MANUAL ACCEPTANCE PENDING**。没有自动测试或构建
Release Blocker；在 `docs/MANUAL_ACCEPTANCE.md` 的关键真实环境项目完成前不得写 READY。
按要求未创建 tag、未创建 GitHub Release、未 push，也未开始 v1.0.1。

## 2026-09-19 — v1.0.0-rc.1 GitHub 发布准备

- 发布策略调整为先发布 GitHub Pre-release `v1.0.0-rc.1`，再从 GitHub Release 页面下载
  同一组二进制执行 Phase 5.1 人工验收；程序内部版本继续为 `1.0.0`。
- RC 标题准备为 `TG2Cloud v1.0.0 RC1`，明确不是 Stable/Latest；正式 `v1.0.0` tag 与
  Release 均不在本阶段创建。
- 本阶段只整理 README、CHANGELOG、RELEASE_NOTES、Checklist 和 WORKLOG；不修改运行源码、
  Logo、版本或构建配置，也不重新运行 PyInstaller。
- Release 资产限定为两个 PySide6 EXE 和 `SHA256SUMS.txt`。本地 Phase 5 的旧 EXE 与哈希
  只作为本机验证记录，不提交、不手工上传，也不要求与 GitHub Runner 的重现构建一致；
  Release 校验值必须由 Windows Build Job 对本次实际生成的两个 EXE 计算。
- Phase 5.1 真实 VPS、WebDAV、Telegram、重复部署、Update、Repair/Backup 和文件规模验收
  继续保持 Pending；RC1 资产发布后不得同名覆盖，发现阻断问题应进入新的 RC。
- GitHub 发布结果、tag 指向和 source commit 以本阶段最终命令结果及 Release 页面为准；
  不在仓库中记录凭据或尝试让 commit 内容自引用其自身 SHA。

## 2026-09-19 — RC1 GitHub Actions 构建发布修正

- 首次推送 `v1.0.0-rc.1` 后，GitHub Actions Windows Job 通过，但 Linux Job 因
  ShellCheck `SC1091`/`SC2015` 失败，因此没有创建 GitHub Release，也没有上传 Release assets。
- 两版 `remote_install.sh` 只做等价的 ShellCheck 收尾：为动态加载的受控 helper 增加 source
  提示，并把 `A && B || fail` 改为显式 `if`；没有修改 Tunnel、Telegram、SQLite、rclone、
  streaming、verify 或部署语义。
- `tests.yml` 以 `shellcheck -x` 校验全部 10 个当前 Shell 脚本，补齐配置保护 helper 和测试
  harness，避免新脚本遗漏静态检查。
- 新增 `release.yml`：只响应 `v1.0.0-rc.1` Tag（或显式手动调度），Windows Build Job 在
  固定 Tag 上执行测试、Ruff 和一次 `build.ps1 -Edition All`；它白名单核对两个 EXE，按本次
  实际文件生成 `SHA256SUMS.txt`，再上传一个 Actions artifact。
- Release Job 不运行 `build.ps1`，只下载上述 artifact，重新核验 SHA256 和精确三文件集合，
  然后创建标题为 `TG2Cloud v1.0.0 RC1` 的 Pre-release 并上传同一组文件。若同名 Release
  已存在则拒绝覆盖。
- `.gitignore` 增加全局 `*.exe` 防护；`build/`、`dist/` 继续忽略。本地工具、EXE、dist 和
  build 不进入提交。
- 本轮提交前验证：完整 pytest 215 passed、4 skipped、36 subtests passed；Ruff、compileall、
  官方 ShellCheck 0.9.0/0.11.0、10 个 Bash `-n`、actionlint 1.7.12 和 `git diff --check`
  均通过。首次修正提交的远端 Ubuntu ShellCheck 0.9.0 还报告 trap 间接调用的 `SC2317`；
  已与现有新版 `SC2329` 注释一起做版本兼容抑制，不改变 backup trap 行为。
- 由于 RC1 Tag 曾在失败 CI 后提前推送且尚无 Release，本轮将在 `main` Branch CI 全绿后，
  仅删除并重新创建同名 RC1 Tag，使其准确指向包含发布 Workflow 的已验证提交；不会创建
  Stable `v1.0.0`。实际 Actions 构建、Release 资产与远端 SHA256 结果仍待远端运行完成。
