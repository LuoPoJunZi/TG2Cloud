# 更新记录

## TG2Cloud v1.0.0

GitHub Release 标签为 `v1.0.0`；程序内部版本为 `1.0.0`。两个 Windows EXE 由 GitHub
Actions 从该标签源码构建，并以本次构建实际文件生成 SHA256 校验值。真实 VPS、WebDAV 与
Telegram 端到端验收仍待用户下载 Release 资产后完成。

- 新安装按 Edition 使用独立的 `tg2cloud-*` 安装目录、备份目录、容器和 Docker Network；
  CloudDrive2 与 OpenList 的内网 WebDAV 主机名同步更新。
- 识别同 Edition 的旧 TG115 安装目录和已停容器后提示并继续；固定端口或目标新资源
  冲突时明确停止，不自动覆盖或迁移。手动迁移边界见 `docs/MIGRATION_FROM_TG115.md`。
- 新输出使用 `TG2CLOUD_*` 状态标记，解析器兼容旧 `TG115_*`；保留 SQLite 文件名及
  必要的兼容环境变量别名。固定 Tunnel 端口和传输核心未改动。
- 既有 TG2Cloud 重复部署默认在 VPS 内保留完整 `.env`，仅在用户明确勾选时应用本次表单；
  SQLite、rclone 配置及两种网关的持久化目录继续原位保留。
- 两版增加只读运行状态区分（运行中、已停、未安装、独立 legacy 提示），`manage.sh update`
  仅在全部健康核验通过后输出 `TG2CLOUD_UPDATE=OK`；明确 v1.0.0 不新增 Restore/Uninstall。
- 正式 Windows 版本仅构建两个 PySide6 Edition，统一使用 `assets/brand/` Logo/Icon、固定
  19798/5244 SSH Tunnel、20GB 任务预算与 8GB 安全空闲线。
- 坚持无遥测、无第三方统计、无开发者侧凭据收集；部署和诊断日志对密码、Token、API Hash、
  OpenList 管理员凭据及 URL userinfo 脱敏。

### 双 Edition 与 OpenList

- 在现有 PySide6 部署器上增加独立的 CloudDrive2／OpenList 产品配置与入口；最终构建产物改为
  `TG2Cloud-CloudDrive2-Deployer.exe` 和 `TG2Cloud-OpenList-Deployer.exe`，Classic/Tkinter 不再参与
  当前构建和 CI。
- OpenList 使用独立的 `/opt/tg2cloud-openlist`、容器、网络、备份目录和固定 5244 SSH 隧道；
  管理端口只绑定 VPS 回环地址。
- 增加 OpenList 首次管理员与 WebDAV 会话级随机凭据、复制／重新生成交互，并明确已有实例不
  自动重置管理员密码；已有实例可在 VPS 内复用旧 WebDAV 配置，凭据不回传或写入日志；
  115 Open 授权继续由用户在自己的后台完成。
- 增加 OpenList Compose、部署、回滚、管理和备份脚本；基础部署不依赖 WebDAV 已配置，最终
  认证／写入／大小／改名／删除验收单独执行。
- OpenList 部署器增加运行状态、脱敏日志、分别重启服务、一致性手动备份和带二次确认的管理员
  密码恢复；恢复出的新密码不进入普通日志。最终 WebDAV 验收改为逐阶段显示通过／失败／未执行。
- 已有 OpenList 实例部署后隐藏无效的首次密码区域并提示使用原凭据；最终验收新增独立的
  OpenList 服务阶段，并为认证、目录、写入、大小、改名和清理失败提供面向普通用户的主提示。
- Bot 配置和目的端文案改为受控产品配置，同时兼容已部署 CloudDrive2 的 `CD2_*` 环境变量及
  运行标识；任务状态机、流式传输和磁盘保护语义保持不变。
- 增加 OpenList 产品隔离、界面、凭据、配置、资源、Compose、安装和打包结构回归。
- 源码部署目录统一为 `payload_clouddrive2/` 与 `payload_openlist/`；远端安装包内部仍使用中性
  `payload/`，不改变 VPS 协议。新增对称的 `installer_clouddrive2.py` 产品入口，删除两个
  CMD 启动器和已退役的 `installer_classic.py`。
- Windows 部署器检测到 SSH 主机密钥变化时，显示当前目标以及旧／新密钥类型和 SHA-256
  指纹；用户确认后仅原子替换当前主机与端口的记录，并自动重试原操作一次。取消不会修改记录，
  身份认证、端口不可达、超时、解析和协议错误会分别提示；首次连接仍保持严格人工核验。
- CloudDrive2 版的导航、配置卡片和文档模块标题统一使用 `CloudDrive2`，不再把 `115` 与产品名
  并列为模块名称；115 挂载、路径、验收和配置示例继续保留，实际部署与 WebDAV 逻辑不变。

## 上游 TG115 历史记录（保留用于代码血缘）

以下条目属于 TG115 上游历史，不是 TG2Cloud 的版本号或当前发布说明。

### TG115 v1.6.2（2026-09-16）

- Windows 部署器界面迁移到 PySide6，保留 SSH 主机密钥确认、VPS 资源建议、部署前容量复检、
  固定本机隧道、CloudDrive2 网络修复和 WebDAV 真写验收；新增离线预览、依赖诊断、脱敏日志
  导出和 Qt 打包自检，并同步构建依赖与回归测试；构建时隔离 DLL 搜索路径，避免环境中其他
  软件的 ICU 运行库被误打包后导致 QtCore 无法启动。
- Windows 构建新增 Modern／Classic 双版本：Modern 使用 PySide6 新界面，Classic 保留原
  Tkinter 界面；`build.ps1 -Edition All|Modern|Classic` 可选择构建范围，CI 分别自检两个成品。
- Linux CI 显式使用 Qt offscreen 平台运行 Modern 界面回归，避免无头 Runner 中残留的显示环境
  变量触发不可用的桌面平台插件。
- Windows 构建预检不再创建真实 GUI 窗口，打包后 Modern／Classic 自检分别设定超时，避免
  非交互 Runner 因窗口初始化永久占用作业。
- Windows CI 构建显式使用 `setup-python` 提供的 Python 3.13，避免 `uv` 自动选用 Python
  3.14 后触发 Tcl/Tk zipfs 打包异常，导致 Classic 成品自检挂起。
- Bot 改用 Telegram 输入框左侧的原生命令菜单，7 项菜单说明统一为 6 个中文字符；新回复不再
  附带消息下方快捷按钮，队列翻页和带参数任务操作继续使用文字命令；菜单注册失败不阻止服务启动。
- 系统状态的目的端可访问文案移除“只读检查”和检查时间后缀，后台探测与过期保护逻辑不变。

### TG115 v1.6.1（2026-09-15）

- Windows 部署器固定使用本机 `127.0.0.1:19798` 打开 CloudDrive2 管理页；端口被占用时
  明确停止并提示释放，不再生成随机端口；
- 打开浏览器前通过 SSH 隧道执行真实 HTTP 验收，旧隧道失效时自动关闭并重建；SSH 服务拒绝
  TCP 转发时显示 `AllowTcpForwarding`／`PermitOpen` 排查提示，不再吞掉异常后误报成功。
- Bot `/status` 改为单页对齐布局，使用四字字段名集中展示目的端、调度、并发、空间、资源、
  分阶段速度和任务统计；日常界面不再提示人工确认，历史 `confirmed` 兼容状态并入“Bot 完成”。
- Bot 帮助、队列、任务详情、诊断和操作结果统一为四字标签单页布局；新增私聊鉴权的快捷按钮、
  每页 5 项的任务翻页和按状态展示的任务操作。按钮取消采用 5 分钟二次确认，文字命令保持兼容；
  快捷临时巡检仍为只读，远端遗留文件清理继续要求一次性确认码。

### TG115 v1.6.0（2026-09-15）

- Windows 部署器新增 VPS CPU、内存、目标文件系统、inode、已有占用和 FUSE 的只读探测，
  提供“均衡／流式优先”实例建议；Phase 3.1 将源码默认统一为 20GB 任务预算／8GB 安全线，应用建议必须由用户主动点击；
- 正式部署前重新探测并校验所选预算，空间或运行门槛不足时在上传安装文件前停止；远端安装
  脚本改为检查实际安装目录所在文件系统，不再固定检查根分区；
- 识别 Docker 实际数据目录；与安装目录分盘时独立检查 Docker 空间和 inode，并在 Docker
  启动后、构建镜像前再次复核两个文件系统；
- 新增只读 `manage.sh backups` 和显式 `prune-backups [1-50]`；部署只报告备份占用，超过
  5GB 时提示人工整理，不自动删除任何回退点；
- 拆分资源采样、远端目录探测和调度心跳；采样过期不启动新传输；
- 增加仅私聊限制、跨重启暂停／恢复、只读 `/doctor`／`/orphans`、`/watch`、`/retry all`、
  手动 `/stream` 和批量 `/confirm all`；
- 增加 `/orphans clean` 一次性确认码、清理前重新扫描和删除后复查，并保护活动任务路径；
- 将 Bot 命令路由、运维动作和状态展示从传输主模块拆分到 `bot_commands.py`；
- 用 rclone JSON 统计展示阶段进度，流式上传与普通上传共享上传窗口；
- 并发增长增加冷却和吞吐收益评估，并考虑本地积压；
- 增加数据库版本、合法状态迁移图、事务化迁移、状态变更历史和取消意图；
- 分开持久化远端临时／正式路径，覆盖改名前后恢复与取消失败关闭；
- 增加隔离构建／配置预检、运行环境／代码指纹核验、一致性数据库快照及失败自动回退；
- Shell 不再执行 `.env`，安装与管理入口加强路径验证；
- 预留媒体来源／目的端协议接口，不引入频道用户会话或新的上传依赖；
- 增加故障回归、真实本地 WebDAV 集成测试和 Linux Python 3.12 CI 测试。

### TG115 v1.5.0

- 单文件超过本地任务预算时自动切换为带背压的流式传输，不再永久排队；
- 使用 `rclone rcat --size` 直接从 Telegram 写入 CloudDrive2，并继续执行大小校验和安全改名；
- 修复远端改名与 `/cancel` 竞态导致的远端孤儿文件；
- 修复本地下载完成改名与数据库提交之间崩溃导致的本地孤儿文件；
- 修复不存在的保留文件仍占用本地任务额度；
- CloudDrive2 修复脚本不再把任意占用 19798 端口的容器当作 CloudDrive2；
- SQLite 旧数据库自动新增传输模式字段；
- CI 新增 Linux ShellCheck、Compose 校验、Bot 镜像构建、依赖审计和 Windows EXE 自检；
- 自动化测试增加到 75 项。

### TG115 v1.0.0

首个正式版本。

- 提供 Windows 图形化部署器；
- 支持 Telegram 私聊文件自动排队与任务恢复；
- 支持 CloudDrive2 WebDAV 扁平目录写入和远端大小校验；
- 支持 CPU、内存、磁盘和错误率动态并发控制；
- 支持 20GB 本地任务预算和磁盘安全线；
- 区分 Bot 传输完成与 115 官方客户端人工确认；
- 提供 `/confirm <任务编号>`、`/status`、`/task`、`/retry` 和 `/cancel`；
- 通过自动化模拟、静态检查、依赖审计和打包自检。

此前本地构建均为内部测试版本，不作为公开发行版本。
