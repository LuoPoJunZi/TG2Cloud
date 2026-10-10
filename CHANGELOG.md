# 更新记录

## TG2Cloud v1.1.5

版本日期：2026-10-10。修复共享 HTTPS 的取消回退、宿主 Python 3.10 兼容、VPS 向导续做凭据展示和精简系统依赖提示。两 Edition 正式 EXE 继续由 Actions 从不可变 Tag 构建一次，Release 复用已自检的 Windows artifact 与本次 SHA256。

- HTTPS 配置收到 Ctrl+C、TERM 或 HUP 时进入有限回退；状态提交和回退阶段延后处理重复信号，避免状态文件与实际路由不一致。已提交状态不会因随后收到取消信号而恢复成旧运行配置，另一 Edition 的路由继续保留。
- 共享代理备份改用分块 SHA256，证书及续期日期使用兼容的 UTC 接口，支持宿主 Python 3.10；备份核验和隔离恢复流程保持原范围。
- 首次安装基础服务成功但 HTTPS 失败后，续做成功再次提供已有凭据的逐项确认展示；新增独立 `--show-credentials`，仅在当前私有终端经确认显示，不安装、升级或改密。OpenList 初始化管理员密码明确提示可能已更改。
- HTTPS 预检明确列出缺少的宿主工具和 Debian/Ubuntu 安装命令；备份先检查宿主依赖，两 Edition 的已有 APT 清单补齐 `iproute2`、`python3`。
- 新增中断、提交一致性、备份兼容和凭据隐私回归；独立 Linux CI 的 Python 3.10/3.13 矩阵增加标准库维护测试。
- 同步源码、Bot、两 EXE Windows 资源及中英文文档版本。Telegram、SQLite、队列、rclone、WebDAV、streaming 和持久化兼容标识未改。
- 本地完整回归 470 passed、18 skipped、211 subtests passed；真实 VPS 的新中断/续做流程和 OpenList 脚本写入验收仍待完成。

## TG2Cloud v1.1.4

版本日期：2026-10-09。修复可选 VPS 向导的交互终端及候选镜像源码权限问题，并统一两 Edition 共用 Bot 镜像的有效内部名称。正式发布由 Actions 从新不可变 Tag 构建两个 EXE，Release 复用该次 Windows artifact 及实际 SHA256。

- 修复 `/dev/tty` 使用 `r+` 导致 `File or stream is not seekable`：分开管理读取和写入流、刷新提示、隐藏秘密输入并在中断时恢复终端；兼容 Python 3.10。
- 修复 CLI 私有归档源码复制到 Docker 后 UID 10001 无法读取 `app/__init__.py`：只对公开构建文件设置 0644、子目录设置 0755；上下文根仍为 0700，候选秘密配置保持 0600 且在上下文外。
- 共享 Dockerfile 对公开 `app/` 追加读取/目录遍历权限，源码仍归 root；Bot 继续以 `10001:10001` 运行，不改为 root、不使用 777。
- 两版 Bot 镜像内程序目录/PYTHONPATH 改为 `/opt/tg2cloud`，系统用户/组与 logger 改为 `tg2cloud`，新日志为 `tg2cloud.log`。
- 保留 `tg115.db`、`bot.session`、挂载、旧日志、环境兼容别名、verify 前缀和旧实例检测；不迁移或删除已有数据，不改 HTTPS、队列、rclone、WebDAV 或流式传输策略。
- 增加权限/隐私边界、日志和持久化路径回归；Linux 分支及 Release 检查实际以非 root 启动两 Edition 候选镜像，不再仅验证 Docker build。
- 同步版本源、两 EXE Windows 资源、中英文 README 和脚本/迁移指南；公开向导仍只固定通过 CI 的 commit，实际 payload 只来自正式稳定 Release。
- 本地回归不等于 Linux 镜像或 VPS 升级验收。首次安装、跨版本升级、回退与真实转存仍待专用测试 VPS 验收，OpenList 脚本实机验收暂缓。

## TG2Cloud v1.1.3

发布日期：2026-10-09。产品版本、两个部署器与 Bot 的共享版本源、Windows 版本资源及文档站版本统一为 1.1.3；正式 EXE 由 GitHub Actions 从同一不可变 Tag 构建、自检并生成实际 SHA256，发布 Job 复用同一次构建产物，不替换历史 Release。

- 新增可选 Linux VPS 单行安装／保留配置升级入口：先收集信息、预检、展示计划，最终确认后才执行；两个 PySide6 部署器仍是主力。
- 独立引导固定已验证的向导源码 commit，实际部署 payload 始终来自最新正式稳定 Release；不安装 main/RC 未发布业务代码，不要求旧稳定 Tag 包含新增脚本。
- 已有完整实例核对 Compose 身份、持久化挂载、官方源码与运行指纹后复用配置；TG115、部分实例、手改程序、目录冲突和云网关镜像迁移安全停止。
- 复用现有 Docker 安装、备份/有限回退和强制 HTTPS；不隐式切换健康域名，不重启未选中的 Bot；WebDAV 写入验收另行确认。
- 增加独立 Linux 脚本 CI 与单行引导离线回归；分支 CI 根据实际 EXE 输入决定是否打包，正式 Tag 发布仍复用一次 Windows 构建的 artifact。
- 同步中英文 README、脚本指南与文档站；保留历史版本与真实已发布下载链接，明确只读预检、部署及转存验收的区别。
- 已合入 Telethon 1.45.0 和 PyInstaller 6.22.3 的限定兼容验证；实际新版 EXE、Telegram 登录和真实转存仍待对应验收。
- CloudDrive2 专用 VPS 仅通过脚本只读预检，未执行首次安装、跨版本升级或回退；OpenList 脚本实机验收暂缓，不将这些场景写成通过。

## TG2Cloud v1.1.2

发布日期：2026-10-08。维护与故障可见性更新；两个正式 EXE 由 GitHub Actions 从同一不可变标签构建、验证并生成实际 SHA256，Release 不重复构建、不上传本机产物。

- 运行状态区分本机部署器与 VPS Bot 实际版本；旧版本不可获取时明确提示，不自动升级或降级。
- 在现有进度/日志与错误弹窗中显示真实部署、HTTPS 阶段及核对建议，不虚构百分比或根因。
- HTTPS 对话框新增维护菜单：VPS 私密共享代理备份、完整性检查、隔离解包演练及当前域名续期 dry-run；不提供在线覆盖恢复。
- 续期记录区分检查成功与证书实际变更，补充到期提示；修正已失效的 Let's Encrypt 邮件提醒描述。
- 一次性续期演练和私密备份增加远端执行时限与精确任务清理；连接中断时明确提示清理尚未确认，不停止共享代理或 Bot。
- 续期失败、记录过期与临近到期使用黄色提醒；当前严格 HTTPS 自检通过时仍保持管理页与验收可用。
- 历史代理备份支持选择、完整性核验和隔离演练；旧备份清理必须先预览再确认，清单变化拒绝执行，至少保留一份有效备份。
- OpenList 运行诊断显示实际探测时间、401/429 冷却状态；保持原有退避策略和简洁主页。
- 部署器和 Bot 共用唯一版本源，构建校验 Windows 资源；Release Workflow 从严格校验的不可变 Tag 获取版本，继续复用一次构建的 artifact。
- 修复 PyInstaller 在 build/spec 下解析备份助手相对路径导致的打包失败，增加资源与备份对话框自检。
- 本地完整回归通过；专用 VPS 的 OpenList 续期演练、历史备份核验/隔离解包与无删除清理预览通过，CloudDrive2 配置和容器保持不变。真实转存/限流恢复、独立网络后端端口隔离和长期续期仍待验收。

## TG2Cloud v1.1.1

发布日期：2026-10-01。两个正式 EXE 继续由 GitHub Actions 从同一不可变标签构建；Release Job 复用已通过自检的 Windows artifact，不重复构建。

- OpenList 父目录回退查询检查完整文件清单，避免超过 10,000 项时把已有同名文件误判为空闲路径；CloudDrive2 上传和改名命令保持不变。
- 共享 HTTPS 配置与移除使用 VPS 级事务锁，锁覆盖读状态、安装、自检、提交和回滚；状态文件通过同目录原子替换提交。
- 移除一个 Edition 后同步更新 Certbot 活动域名，并在提交前检查剩余 Edition；失败时回退旧路由与续期配置。
- OpenList 健康探测区分 401 与 429，限制探测重试，合并短时间刷新，并为认证失败与限流增加冷却；CloudDrive2 健康探测策略保持不变。
- Release 必须等待同一不可变标签的 Windows 构建和 Linux 运行、Shell、Docker、真实本地 WebDAV 检查成功，继续发布 Windows Build Job 已生成的 artifact。
- 明确 VPS 本机 HTTPS 自检不等于公网连通验收，并补充共享代理的独立备份与恢复边界。
- 本轮已在真实 VPS 验证双管理网关 HTTPS 共存、外部 HTTPS/HTTP 跳转/公开 WebDAV 阻断，以及双 SSH 通道锁互斥与断锁释放；原 CloudDrive2 域名、已核对配置和容器保持不变。OpenList Bot/WebDAV/401/429 恢复、路由移除与长期续期没有重新完成实机验收；既有转存结果继续以 v1.1.0 等历史验收为基线。

## TG2Cloud v1.1.0

- 受管 CloudDrive2 与 OpenList 基础容器部署后，部署器自动进入 HTTPS 管理入口配置；证书、HTTPS、跳转、公开 `/dav` 阻断及回环监听检查全部通过后，才显示“部署完成”。
- 部署工作台移除普通“打开管理页”SSH 隧道按钮，改以“配置 HTTPS 管理入口”为主操作；底层固定端口隧道代码暂时仅作为兼容和故障恢复能力保留，不作为日常入口。
- WebDAV 最终验收在后端再次检查当前 Edition 的 HTTPS 状态，未配置或运行异常时明确停止；外部 WebDAV 模式没有本地管理容器，因此不强制配置本地 HTTPS 入口。
- CloudDrive2/OpenList 管理端继续只绑定 VPS 回环地址，只有共享 Nginx 占用公网 80/443；不会把 19798/5244 改为 `0.0.0.0`，公网 `/dav` 继续被拒绝。
- 本改造已加入自动回归与双 Edition 离屏界面检查，并在真实 VPS 完成受管部署、证书签发、HTTPS 自检及 WebDAV 全流程验收。

## TG2Cloud v1.0.4

GitHub Release 标签和程序内部版本均为 `v1.0.4`。两个 Windows EXE 继续由 GitHub Actions 从同一个不可变标签统一测试、构建和自检，并按本次实际产物生成 SHA256。

- 重新设计 Telegram Bot 状态首页：使用紧凑的任务与实时速度面板，并根据当前 Edition 动态显示 CloudDrive2 或 OpenList。
- 首页 Inline Keyboard 精简为任务、VPS 资源和原地刷新三个 Emoji 按钮；VPS CPU、可用内存、可用磁盘与 TG2Cloud 本地额度移入独立资源页。
- 首页刷新复用现有目的端探测、任务统计和分阶段速度数据；VPS 资源刷新复用现有 `ResourceMonitor`，旧 `menu:status` 回调继续兼容。
- `/start`、`/status` 与 `/performance` 统一进入新状态首页；按钮操作通过编辑原消息更新，减少 Bot 对话中的重复消息。
- CloudDrive2 与 OpenList 共用同一套实现，Edition 名称按实际部署动态显示；Telegram 下载、SQLite 队列、rclone、WebDAV、streaming 和既有部署流程未被重写。

## TG2Cloud v1.0.3

GitHub Release 标签和程序内部版本均为 `v1.0.3`。两个 Windows EXE 继续由 GitHub Actions 从同一个不可变标签统一测试、构建和自检，并按本次实际产物生成 SHA256。

- 新增可选的 Dockerized Domain HTTPS Gateway：两个 Edition 共用一套固定版本 Nginx/Certbot，并保留原 SSH 隧道、Docker 内网 WebDAV 与回环后端绑定。
- 增加域名与 DNS 检查、80/443 端口归属保护、公开 `/dav` 阻断、未知 Host/SNI 拒绝、证书自动续期、事务提交和按 Edition 回退/移除；不会停止或覆盖用户已有的 Web 服务。
- 修复已有证书复用、首次签发失败回退、最后路由移除、续期域名筛选、状态脚本初始化与 Bash 条件表达式问题；状态自检使用本机回环解析，避免 VPS 不支持公网 NAT 回环时误报失败。
- 域名状态结果改为固定高度、可滚动和可复制的小型日志框，避免长检查结果撑高对话框。
- 共享域名 HTTPS 功能已完成真实 VPS 验收，适用于 CloudDrive2 与 OpenList：证书复用、HTTPS 管理页、HTTP 跳转、公开 `/dav` 阻断、回环监听和证书有效期自检均通过。
- Telegram、SQLite 队列、rclone、streaming 与既有 WebDAV 落盘流程未重写；CloudDrive2 v1.0.1 与 OpenList v1.0.2 已通过的基础部署及 WebDAV 结果继续作为回归基线。

## TG2Cloud v1.0.2

GitHub Release 标签和程序内部版本均为 `v1.0.2`。两个 Windows EXE 由 GitHub Actions 从同一个不可变标签统一测试、构建和自检，并按本次实际产物生成 SHA256。

- 修复部分 OpenList／115 Open 挂载对 WebDAV `MOVE` 返回 201、但目标文件没有实际生成的后端兼容问题；OpenList 改为预留无冲突路径后直接写入最终文件名。
- 保留远端大小复验、失败现场保护、重启恢复和安全清理；旧版遗留临时文件不会被隐式改名或覆盖。
- 修复 OpenList 部署工作台窄侧栏裁切，并区分 401 凭据错误与 429 限流提示。
- 已在真实 VPS、OpenList 与 115 Open 环境通过部署和 WebDAV 最终验收。
- CloudDrive2 继续使用已经在真实 VPS 验收通过的临时上传、改名与大小复验流程；新增逻辑均由 OpenList 后端门控，并有 CloudDrive2 专项回归测试保护。

## TG2Cloud v1.0.1

GitHub Release 标签为 `v1.0.1`；程序内部版本为 `1.0.1`。Windows EXE 继续由 GitHub Actions 从标签源码构建，并对本次实际生成的文件计算 SHA256。

- 修复 CloudDrive2 首次部署启动 Bot 后，网络修复阶段把 `tg2cloud-clouddrive2-bot` 误判为第二个 CloudDrive2 网关容器，导致基础部署失败的问题。
- 仅从 CloudDrive2 网关发现结果中排除当前 Edition 的 Bot；存在多个真实网关时仍拒绝自动修改，旧 TG115 容器和固定端口冲突保护保持不变。
- 增加两处容器发现逻辑的 Bash 回归测试；OpenList 业务流程、Telegram、SQLite、rclone、streaming、Tunnel 和 verify 未改动。真实 VPS 端到端结果仍待用户验收。

## TG2Cloud v1.0.0

GitHub Release 标签为 `v1.0.0`；程序内部版本为 `1.0.0`。两个 Windows EXE 由 GitHub Actions 从该标签源码构建，并以本次构建实际文件生成 SHA256 校验值。真实 VPS、WebDAV 与 Telegram 端到端验收仍待用户下载 Release 资产后完成。

- 新安装按 Edition 使用独立的 `tg2cloud-*` 安装目录、备份目录、容器和 Docker Network；CloudDrive2 与 OpenList 的内网 WebDAV 主机名同步更新。
- 识别同 Edition 的旧 TG115 安装目录和已停容器后提示并继续；固定端口或目标新资源冲突时明确停止，不自动覆盖或迁移。手动迁移边界见 `docs/MIGRATION_FROM_TG115.md`。
- 新输出使用 `TG2CLOUD_*` 状态标记，解析器兼容旧 `TG115_*`；保留 SQLite 文件名及必要的兼容环境变量别名。固定 Tunnel 端口和传输核心未改动。
- 既有 TG2Cloud 重复部署默认在 VPS 内保留完整 `.env`，仅在用户明确勾选时应用本次表单；SQLite、rclone 配置及两种网关的持久化目录继续原位保留。
- 两版增加只读运行状态区分（运行中、已停、未安装、独立 legacy 提示），`manage.sh update` 仅在全部健康核验通过后输出 `TG2CLOUD_UPDATE=OK`；明确 v1.0.0 不新增 Restore/Uninstall。
- 正式 Windows 版本仅构建两个 PySide6 Edition，统一使用 `assets/brand/` Logo/Icon、固定 19798/5244 SSH Tunnel、20GB 任务预算与 8GB 安全空闲线。
- 坚持无遥测、无第三方统计、无开发者侧凭据收集；部署和诊断日志对密码、Token、API Hash、OpenList 管理员凭据及 URL userinfo 脱敏。

### 双 Edition 与 OpenList

- 在现有 PySide6 部署器上增加独立的 CloudDrive2／OpenList 产品配置与入口；最终构建产物改为 `TG2Cloud-CloudDrive2-Deployer.exe` 和 `TG2Cloud-OpenList-Deployer.exe`，Classic/Tkinter 不再参与当前构建和 CI。
- OpenList 使用独立的 `/opt/tg2cloud-openlist`、容器、网络、备份目录和固定 5244 SSH 隧道；管理端口只绑定 VPS 回环地址。
- 增加 OpenList 首次管理员与 WebDAV 会话级随机凭据、复制／重新生成交互，并明确已有实例不自动重置管理员密码；已有实例可在 VPS 内复用旧 WebDAV 配置，凭据不回传或写入日志；115 Open 授权继续由用户在自己的后台完成。
- 增加 OpenList Compose、部署、回滚、管理和备份脚本；基础部署不依赖 WebDAV 已配置，最终认证／写入／大小／改名／删除验收单独执行。
- OpenList 部署器增加运行状态、脱敏日志、分别重启服务、一致性手动备份和带二次确认的管理员密码恢复；恢复出的新密码不进入普通日志。最终 WebDAV 验收改为逐阶段显示通过／失败／未执行。
- 已有 OpenList 实例部署后隐藏无效的首次密码区域并提示使用原凭据；最终验收新增独立的 OpenList 服务阶段，并为认证、目录、写入、大小、改名和清理失败提供面向普通用户的主提示。
- Bot 配置和目的端文案改为受控产品配置，同时兼容已部署 CloudDrive2 的 `CD2_*` 环境变量及运行标识；任务状态机、流式传输和磁盘保护语义保持不变。
- 增加 OpenList 产品隔离、界面、凭据、配置、资源、Compose、安装和打包结构回归。
- 源码部署目录统一为 `payload_clouddrive2/` 与 `payload_openlist/`；远端安装包内部仍使用中性 `payload/`，不改变 VPS 协议。新增对称的 `installer_clouddrive2.py` 产品入口，删除两个 CMD 启动器和已退役的 `installer_classic.py`。
- Windows 部署器检测到 SSH 主机密钥变化时，显示当前目标以及旧／新密钥类型和 SHA-256 指纹；用户确认后仅原子替换当前主机与端口的记录，并自动重试原操作一次。取消不会修改记录，身份认证、端口不可达、超时、解析和协议错误会分别提示；首次连接仍保持严格人工核验。
- CloudDrive2 版的导航、配置卡片和文档模块标题统一使用 `CloudDrive2`，不再把 `115` 与产品名并列为模块名称；115 挂载、路径、验收和配置示例继续保留，实际部署与 WebDAV 逻辑不变。

## 上游 TG115 历史记录（保留用于代码血缘）

以下条目属于 TG115 上游历史，不是 TG2Cloud 的版本号或当前发布说明。

### TG115 v1.6.2（2026-09-16）

- Windows 部署器界面迁移到 PySide6，保留 SSH 主机密钥确认、VPS 资源建议、部署前容量复检、固定本机隧道、CloudDrive2 网络修复和 WebDAV 真写验收；新增离线预览、依赖诊断、脱敏日志导出和 Qt 打包自检，并同步构建依赖与回归测试；构建时隔离 DLL 搜索路径，避免环境中其他软件的 ICU 运行库被误打包后导致 QtCore 无法启动。
- Windows 构建新增 Modern／Classic 双版本：Modern 使用 PySide6 新界面，Classic 保留原 Tkinter 界面；`build.ps1 -Edition All|Modern|Classic` 可选择构建范围，CI 分别自检两个成品。
- Linux CI 显式使用 Qt offscreen 平台运行 Modern 界面回归，避免无头 Runner 中残留的显示环境变量触发不可用的桌面平台插件。
- Windows 构建预检不再创建真实 GUI 窗口，打包后 Modern／Classic 自检分别设定超时，避免非交互 Runner 因窗口初始化永久占用作业。
- Windows CI 构建显式使用 `setup-python` 提供的 Python 3.13，避免 `uv` 自动选用 Python 3.14 后触发 Tcl/Tk zipfs 打包异常，导致 Classic 成品自检挂起。
- Bot 改用 Telegram 输入框左侧的原生命令菜单，7 项菜单说明统一为 6 个中文字符；新回复不再附带消息下方快捷按钮，队列翻页和带参数任务操作继续使用文字命令；菜单注册失败不阻止服务启动。
- 系统状态的目的端可访问文案移除“只读检查”和检查时间后缀，后台探测与过期保护逻辑不变。

### TG115 v1.6.1（2026-09-15）

- Windows 部署器固定使用本机 `127.0.0.1:19798` 打开 CloudDrive2 管理页；端口被占用时明确停止并提示释放，不再生成随机端口；
- 打开浏览器前通过 SSH 隧道执行真实 HTTP 验收，旧隧道失效时自动关闭并重建；SSH 服务拒绝 TCP 转发时显示 `AllowTcpForwarding`／`PermitOpen` 排查提示，不再吞掉异常后误报成功。
- Bot `/status` 改为单页对齐布局，使用四字字段名集中展示目的端、调度、并发、空间、资源、分阶段速度和任务统计；日常界面不再提示人工确认，历史 `confirmed` 兼容状态并入“Bot 完成”。
- Bot 帮助、队列、任务详情、诊断和操作结果统一为四字标签单页布局；新增私聊鉴权的快捷按钮、每页 5 项的任务翻页和按状态展示的任务操作。按钮取消采用 5 分钟二次确认，文字命令保持兼容；快捷临时巡检仍为只读，远端遗留文件清理继续要求一次性确认码。

### TG115 v1.6.0（2026-09-15）

- Windows 部署器新增 VPS CPU、内存、目标文件系统、inode、已有占用和 FUSE 的只读探测，提供“均衡／流式优先”实例建议；Phase 3.1 将源码默认统一为 20GB 任务预算／8GB 安全线，应用建议必须由用户主动点击；
- 正式部署前重新探测并校验所选预算，空间或运行门槛不足时在上传安装文件前停止；远端安装脚本改为检查实际安装目录所在文件系统，不再固定检查根分区；
- 识别 Docker 实际数据目录；与安装目录分盘时独立检查 Docker 空间和 inode，并在 Docker 启动后、构建镜像前再次复核两个文件系统；
- 新增只读 `manage.sh backups` 和显式 `prune-backups [1-50]`；部署只报告备份占用，超过 5GB 时提示人工整理，不自动删除任何回退点；
- 拆分资源采样、远端目录探测和调度心跳；采样过期不启动新传输；
- 增加仅私聊限制、跨重启暂停／恢复、只读 `/doctor`／`/orphans`、`/watch`、`/retry all`、手动 `/stream` 和批量 `/confirm all`；
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
