# 更新日志

v1.4.3 新增可选分类、管理员通知、家庭成员配额和白名单诊断报告。分类／通知默认关闭，成员默认不限额；涉及业务 schema 2，升级前备份。见[转存](/usage/first-transfer/)、[个人配额](/usage/commands/)、[维护](/operations/maintenance/)和[备份](/operations/backup/)。

这里记录 TG2Cloud **全部历史版本**做了什么，而非仅列出目前还能下载的 Release。v1.0.0 至 v1.4.3 共 22 个版本，逐版说明如下；更细的修复与兼容记录见[仓库完整更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

截至 **2026-10-21**，GitHub 保留 [v1.4.2](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.2)、[v1.4.1](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.1)、[v1.2.1](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) 三个 Release／Tag。v1.0.2 及其他版本虽已移除发布页和标签，历史说明仍保留；下面的发布与测试结论按当时记录理解，不表示今日仍能下载，也不替代当前环境验收。当前安装与下载见[下载与校验](/download/)。

| 版本 | 这一版主要做了什么 |
| --- | --- |
| [v1.4.3](#tg2cloud-v1-4-3) | 维护与备份增强、可选分类／通知／成员配额及脱敏报告、传输测速与编号菜单修复。 |
| [v1.4.2](#tg2cloud-v1-4-2) | 显式复用已有 Docker Nginx，单层代理、事务恢复、Webroot 证书与续期、附加路由及卸载保护。 |
| [v1.4.1](#tg2cloud-v1-4-1) | 修复公网 IPv4 NAT 的 HTTPS 预检；增加映射人工确认与执行前复核，补充 CloudDrive2 ARM64 首装验收。 |
| [v1.4.0](#tg2cloud-v1-4-0) | 原生支持 AMD64／ARM64；统一平台与镜像检查，接入双架构 CI 和发布验证。 |
| [v1.3.4](#tg2cloud-v1-3-4) | 增强长说明、图片和媒体组命名，处理网址污染名、斜杠说明与后缀；补全使用文档。 |
| [v1.3.3](#tg2cloud-v1-3-3) | 新增 Bot 家庭共享、外部 WebDAV 多只读账号；增强多语言命名，精简资源页。 |
| [v1.3.2](#tg2cloud-v1-3-2) | 中文编号安装与管理向导；新增离线 `tg2cloud` 管理命令，完善所选实例卸载及工具清理。 |
| [v1.3.1](#tg2cloud-v1-3-1) | 新增独立外部 WebDAV：独立账号与 HTTPS，只读访问既有目录；扩展共享代理与依赖保护。 |
| [v1.3.0](#tg2cloud-v1-3-0) | 转为 Linux Python + Bash 维护；冻结 Windows 版，整理共享源码、构建与指纹，完善磁盘推荐。 |
| [v1.2.1](#tg2cloud-v1-2-1) | 修复取消重传、远端冲突和遗留扫描；完善验证、备份、磁盘保护、说明命名与每周失败统计；最后一个 Windows 版。 |
| [v1.2.0](#tg2cloud-v1-2-0) | 增加独立内网／NAS 安装与卸载入口，显示内网 IP 和端口；当时默认保留数据。 |
| [v1.1.5](#tg2cloud-v1-1-5) | 修复 HTTPS 中断回退、Python 3.10 兼容；完善失败续做凭据展示与系统依赖提示。 |
| [v1.1.4](#tg2cloud-v1-1-4) | 修复终端不可 seek 与非 root 镜像源码读取权限；统一内部命名，保留旧数据位置。 |
| [v1.1.3](#tg2cloud-v1-1-3) | 新增公网 VPS 单行安装／保留配置升级；稳定 Release 引导和依赖兼容更新。 |
| [v1.1.2](#tg2cloud-v1-1-2) | 完善版本和故障提示、HTTPS 备份核验与续期演练、OpenList 冷却诊断。 |
| [v1.1.1](#tg2cloud-v1-1-1) | 共享 HTTPS 事务锁、状态原子提交与回退；OpenList 大目录和 401／429 探测修复。 |
| [v1.1.0](#tg2cloud-v1-1-0) | 受管部署必须完成 HTTPS 验收；日常管理不再使用 SSH 隧道按钮，后端保持回环监听。 |
| [v1.0.4](#tg2cloud-v1-0-4) | 紧凑 Bot 状态首页、动态 Edition 名称、独立 VPS 资源页及原消息刷新。 |
| [v1.0.3](#tg2cloud-v1-0-3) | 可选共享 Nginx／Certbot 域名 HTTPS、证书续期、失败回退及公开 `/dav` 阻断。 |
| [v1.0.2](#tg2cloud-v1-0-2) | 修复 OpenList MOVE 假成功，改为预留正式路径直接上传；CloudDrive2 策略不变。 |
| [v1.0.1](#tg2cloud-v1-0-1) | 修复 CloudDrive2 首装将 Bot 容器误判成额外网关的问题。 |
| [v1.0.0](#tg2cloud-v1-0-0) | 建立双 Edition 和独立实例身份，提供两个 PySide6 部署器，保留稳定转存核心与旧数据兼容。 |

v1.2.1 是最后一个 Windows 版，v1.0.2 仅保留历史变更记录，不再提供 Release 下载；新安装使用最新稳定版，不用旧 EXE 覆盖新实例。上游 TG115 的版本单独记录，不计入上述 22 个 TG2Cloud 版本。

## TG2Cloud v1.4.3

2026-10-23，[v1.4.3 已正式发布](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.3)。辅助 A `cace622ffbbcecd28db7b00a29c26901e8fa139d`、入口 B／Tag `5aaf6a9b158d785ffa2fee52750c022fb8654810` 各五项 CI 与[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39901152742)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要核验通过。 新增可选分类、管理员通知、成员配额及脱敏报告，修复测速、保留简洁首页，统一编号菜单和外部 WebDAV 默认值。业务数据库迁移到 schema 2，升级前备份；范围见[仓库更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。本版真实 VPS／网盘验收未执行。

本版还包括四个旧版可信基线、实例快照／隔离预检、业务就绪观察、Nginx 生命周期回归与命名预览；延续实例身份、历史路径、命名优先级与冷却保护，不增加生产覆盖恢复。开发阶段记录与发布核验见[维护增强](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-IMPROVEMENTS.md)，不回写旧版已发布资产。

## TG2Cloud v1.4.2

2026-10-21，[v1.4.2 已正式发布](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.2)。辅助 A、固定入口 B 各五项 CI 及[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39592291162)全部成功，实际源码资产、SHA256 和 GitHub 摘要核验通过。完整范围见[仓库变更](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)，不将 CI 扩大为 VPS、ACME 或迁移实机验收。

发布后同日另完成 CloudDrive2 v1.3.4 → v1.4.2 的授权人工升级：原 Release／Tag 已删除，先核验原提交并备份，再调用正式升级核心。数据保留、Bot 健康、只读 WebDAV、外部电脑 HTTPS 与升级后在线复检通过，继续使用 managed。自动缺失基线处理尚未改进，真实转存和新代理模式未验收，详见[本次记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md)。这只是发布后文档补充，不改写正式资产。

- 新增显式授权的 external_docker 模式，不关闭外部 Nginx，不增加第二层代理，不修改外部 Compose；默认 managed 模式与 Bot 流程不变。
- 核验端口真实归属、持久化配置和稳定网络别名；使用逐文件事务、私密备份、nginx -t、reload 和实际 TLS／后端检查。
- Webroot 签发及宿主离线续期，复用证书仍由原工具负责；共享 schema 3 保留独立外部 WebDAV，卸载不停止外部代理且默认保留证书与恢复材料。
- 标准目录、普通 Nginx 和已运行的 cron 等支持条件见[域名 HTTPS](/deploy/domain-https/)。external_docker 的真实 VPS 接入、ACME、长期续期、代理迁移和现有网站业务仍待实机验收；不改变 Bot 依赖、镜像或数据库。

## TG2Cloud v1.4.1

发布审计发现的开发依赖漏洞通过更新 uv 0.13.4、certifi 2026.10.19 并统一重生成哈希锁修复；Bot 运行依赖和网关镜像不变，保留安全审计。

版本日期：2026-10-21，[v1.4.1 已正式发布](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.1)。单一公网 A、已核对本机 AAAA 且端口归属安全的 NAT 场景增加云控制台公网 IPv4 人工确认，确认仅本次有效，执行前重新比对。错误记录、端口占用和拒绝确认仍会停止；ACME、TLS 和失败回退继续执行。新增 DNS／80／443 分项错误提示和回环地址保护。辅助 A／固定入口 B 各五项 CI、[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39525213331)及实际资产校验通过。发布后用户确认Ubuntu26.04.1／ARM64／公网NAT的CloudDrive2首装、本机HTTPS与WebDAV通过，见[验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md)；OpenList、外网手机、升级回退与长期续期不外推。此为文档证据补充，不改已发布资产。完整改动见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)，环境要求见[部署前准备](/guide/prerequisites/)。

## TG2Cloud v1.4.0

完整改动见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

统一主安装、LAN、维护、卸载与外部 WebDAV 的架构检查，核对内核、64 位用户态、Docker daemon 和镜像原生平台，不自动设置 QEMU。两 Edition、依赖、镜像版本、配置与数据路径不变；新增原生双架构 CI、隔离网关与扩展依赖检查。版本日期：2026-10-20，[v1.4.0 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v140)；A／B 各五项 CI 与[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39426176679)成功，实际源码包、SHA256 清单与 GitHub 资产摘要已核验。Oracle／真实 VPS、云盘与手机仍由用户发布后验收，不能用 CI 代替。见[部署前准备](/guide/prerequisites/)。

TG2Cloud 与上游 TG115 分别记录版本。以下是仓库 CHANGELOG 和发布说明的整理，不把历史 TG115 的版本号当成 TG2Cloud 发布版本。

## TG2Cloud v1.3.4

版本与资料核对日期：2026-10-19。[v1.3.4 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v134) 已正式发布；辅助 A 与入口 B 各五项 CI、[同标签发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39204327020)全部成功，实际源码包、SHA256 清单与 GitHub 资产摘要已核验。详见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

### 待发布边界修复

以下规则已随 v1.3.4 发布，旧标题仅用于保留链接锚点，不表示仍待发布。

- 媒体斜杠说明正常接收；改善表情标题、正常作品名与推广／凭据区分、相邻作品名／集数、斜杠文字、中文旁域名及尾部画质过滤。
- 网址、账号或处理前缀污染的视频原名可使用实际可靠正文；无原名、数字／默认／污染名的单图片可使用自身说明，不借用无关消息。
- 同组恰好一图一视频、真实后缀可区分时共用无编号标题；多成员、同类或后缀不明确继续编号。真实后缀和正常 MKV 格式保留，明显错误的视频后缀保守修正。
- 保留正常原名、隐藏实体、鉴权、去重、无说明兜底、原名记录与远端冲突保护；不改历史任务，不增依赖、数据库迁移或传输流程，不抓评论／频道，不做 OCR。
- 补全仓库命名、配置、备份恢复和 FAQ 文档，网站独立同步，README 保留简短入口和原致谢许可。

新规则示例和限制见[第一次转存](/usage/first-transfer/)。本地全量 864 项（838 成功、26 既有环境跳过）、Python 3.10 CLI 393 项（382 成功、11 环境跳过），Node.js 22 构建与网站 19 项测试通过。真实 VPS、Telegram、两版网关、手机或升级尚未验收；用户确认的 CloudDrive2 v1.3.3 转存不扩大为本版结论。

## TG2Cloud v1.3.3

版本日期：2026-10-18。[v1.3.3 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v133) 已正式发布；辅助提交、入口提交与同标签 Actions 均通过，实际源码包与 SHA256 已下载核对。详见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

新增家庭共享：Bot 安装后授权成员、各自任务与通知、共用保存目录；外部 WebDAV 支持多个独立只读账号，授权和目录由网关后台确认。未增加个人目录，也未完成本轮真实网关／手机验收；详见[Bot 使用](/usage/commands/)与[外部 WebDAV](/deploy/external-webdav/)。

视频命名增量增强 Unicode 多语言、混合随机 ID、广告域名与元数据过滤，同条消息及本组说明共用候选评分；可靠原名、扩展名、媒体组指定名称、无说明回退及既有去重保留。识别异常不阻止接收，不抓评论／频道，不增依赖。示例与限制见[第一次转存](/usage/first-transfer/)；真实 Telegram 或网关验收仍需独立完成。

资源页移除文件系统容量清单，后台磁盘采样与安全保护不变。新增回归与既有恢复、权限、转存检查共同运行；自动检查不代替[历史实机记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)之外的新验收。

发布后补充（2026-10-19）：用户确认 CloudDrive2 v1.3.3 升级后的实际转存验收完成；不扩大为 OpenList、家庭共享或所有异常路径的验收。

## TG2Cloud v1.3.2

版本与资料核对日期：2026-10-18。[v1.3.2 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v132) 已正式发布；辅助提交、入口提交和同标签发布检查全部通过，下载的源码包、实际 SHA256 与公开资产摘要已核对。详见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

- 公网／内网默认入口采用中文编号向导，未安装的 Edition 确认后进入安装，已有实例进入管理；新装 WebDAV 密码回车生成 8 位，升级保留原配置。
- 新增离线 `tg2cloud`：安装升级、状态、日志、启停、WebDAV 验收、HTTPS、备份、凭据与“卸载当前实例”；危险操作保留确认，状态／日志不下载代码。
- 最后一套完整卸载后，仅在无依赖且归属核验通过时清理管理代码和命令；另一 Edition、云端文件、系统软件与防并发锁不删除。
- 外部 WebDAV 使用独立中文编号菜单、实际目录确认及简洁手机参数；不加入主安装或 Bot 菜单。

不新增 Bot 依赖、数据库迁移、网关镜像或环境变量。新安装／升级／卸载、真实手机与原生账号权限仍需单独验收，自动测试不等于 VPS 验收。

## TG2Cloud v1.3.1

发布日期与资料核对日期：2026-10-18。[v1.3.1 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v131) 已从同一不可变 Tag 验证并发布源码包/实际 SHA256，下载及公开资产摘要已核对。本轮改动见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

- 独立 `install-webdav.sh` 和离线维护命令；主安装不询问或默认启用，不改 Bot 配置与菜单。
- 原生独立只读账号、最终目录确认、专用 HTTPS 域名单账号门禁和 Range 读取；不复用 Bot/管理员密码。
- 共享代理 schema 2、认证文件轮换、管理路由保留、证书续期与卸载依赖保护。
- 修正只读方法检查与编码反斜杠拦截，隔离 Nginx 覆盖两版认证、中文/编码、写方法拒绝、密码轮换和视频 Range。

不新增数据库迁移、Bot 配置或依赖，不升级网关镜像。原生网关账号/目录、手机、公网 ACME 和 ARM64 尚未实机验收；历史 v1.3.0 CloudDrive2 记录不作为本版附加功能验收。

## TG2Cloud v1.3.0

版本与资料核对日期：2026-10-17。本版以 Linux 一键脚本维护 CloudDrive2 和 OpenList；Windows EXE 停留在 v1.2.1。该版发布与兼容信息见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v130)；v1.3.0 Release／Tag 现已移除，不再作为下载入口。

- VPS 与内网首次安装提供流式优先、均衡和手动磁盘预算，复用现有资源算法；升级保留原配置。
- 执行前在锁内重新检查容量，磁盘条件变化则停止；任务预算不是分区，也不覆盖所有网关缓存。
- Linux／Docker／WebDAV 回归后生成一次源码包及实际 SHA256，发布任务复用同一 artifact；三个在线入口固定到匹配的辅助源码。
- 共享核心模块化到 `src/tg2cloud/`，保留既有配置、数据库、Session 和后端提交策略，不新增数据库结构迁移或配置项。
- 视频命名优先有效长描述与引用块，过滤链接、话题和推广；CI 工具与已验证依赖更新，网关镜像不变。

新布局已通过 Linux 全量回归、宿主 Python 3.10/3.13、两 Edition 非 root 镜像和隔离 LAN 网关检查。[发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/workflows/release.yml) 已从同一 Tag 验证、打包并发布源码包与实际 SHA256。

发布后补充（2026-10-17）：CloudDrive2 旧测试候选经授权备份、人工核对后，使用正式 v1.3.0 原生流程迁移成功，用户确认升级后使用验收完成。历史任务、配置与 Session 授权保留，健康、指纹、HTTPS、只读 WebDAV 和在线入口复检通过；OpenList 与共享代理容器未重启。这不是任意候选代码可被自动覆盖的证明，也不替代首次安装、故障回退、NAS 及全部异常传输验证，见[验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。

## TG2Cloud v1.2.1

本节对应 v1.2.1 正式版本，详见[源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.1/CHANGELOG.md)与 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)。

- 视频数字/默认名称从同条说明提取标题，过滤链接、话题与常见推广；不获取评论区资源。
- 整组图片/视频可共用本组说明标题并分别编号；没有说明的单个视频保留原名，不回查频道。
- 失败数字每周一按容器时区切换统计范围，首页仍显示 `❌ 数字`，不删除失败历史或文件。

- 已取消任务确认后重新转存，保留去重、编号与历史；新增归属受限的查询和状态分页。
- 远端文件不完整或结果不确定时保留数据，允许确认换名重传；OpenList 不恢复使用不可靠的 MOVE。
- 遗留扫描增量读取并显示完整性，删除范围和数量保护不变。
- 大小验证记录、CloudDrive2 安全回退、离线备份预检、多文件系统容量诊断与错误脱敏。

发布日期与内容核对日期：2026-10-15。两个 EXE 已由同标签 Actions 构建、自检和发布，实际 SHA256SUMS 已核对。包含主分支此前的 OpenList DB 快照/digest 回退修复。CloudDrive2 候选已完成保留历史任务的迁移、健康启动与只读 WebDAV 检查，真实 Telegram 转存、完整安装升级、OpenList 实机和灾难恢复仍待验收；正式下载为 v1.2.1。见[源码验收清单](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/RELIABILITY-ACCEPTANCE.md)。

## TG2Cloud v1.2.0

发布日期与内容核对日期：2026-10-11。两个 Windows EXE 已由 GitHub Actions 从同一 v1.2.0 Tag 测试、构建和自检；Release 复用该次 Windows artifact，实际 SHA256SUMS 与资产摘要已核对。

- 增加独立内网向导，人工输入私有 IPv4，不申请域名证书、不改变原 EXE / 公网 VPS 的强制 HTTPS；验收前再次显示内网 IP 和 Edition 固定端口。
- 增加独立卸载入口，先预检并确认所选 Edition / all，默认保留业务数据、历史备份和证书，不卸载系统 Docker/Nginx；未知归属、外部引用、FUSE 或使用中的网络均停止。
- 分支 CI 检查 Python 3.10/3.13；发布验证覆盖三个 Shell 入口、两版候选镜像与隔离 LAN 网关，两个部署器仍是主力。

用户提供的 CloudDrive2 内网 Debian 日志显示首次部署和 WebDAV 验收通过；OpenList 内网、其他 NAS、跨版本升级/回退、真实卸载及本轮 Telegram 转存仍未验收。

[查看 v1.2.0 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v120) · [下载与安装入口](/download/)。

## TG2Cloud v1.1.5

发布日期与内容核对日期：2026-10-10。两个 Windows EXE 已由 GitHub Actions 从同一 v1.1.5 Tag 测试、构建和自检；Release 复用该次 Windows artifact，实际 SHA256SUMS 与资产摘要已核对。

- HTTPS 配置在 Ctrl+C、TERM 或 HUP 时执行有限回退；提交与回退期间延后重复信号，已提交状态不会恢复成旧运行配置，另一 Edition 路由继续保留。
- 共享代理备份改为分块 SHA256，证书与续期日期使用兼容 UTC 接口，宿主 Python 3.10 纳入维护兼容检查。
- 首次基础安装成功但 HTTPS 失败后，续做成功再次提供凭据逐项确认；新增独立 `--show-credentials`，不安装、升级或改密，保存的 OpenList 初始化密码可能已更改。
- HTTPS 预检列出缺少的工具和安装命令；基础部署补齐 `iproute2`、`python3`，预检本身不自动安装软件。
- 补充中断、提交一致性、备份兼容和凭据隐私回归；Telegram、SQLite、队列、rclone、WebDAV、streaming 和持久化兼容标识未改。

本地回归 470 passed、18 skipped、211 subtests passed；同标签发布检查通过。真实 VPS 的新中断/续做流程、首次安装、跨版本升级、回退与 Telegram/云盘转存仍待验收，OpenList 脚本实机验收暂缓。

[查看 v1.1.5 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v115) · [下载与 VPS 单行入口](/download/)。

## TG2Cloud v1.1.4

发布日期与内容核对日期：2026-10-09。两个 Windows EXE 已由 GitHub Actions 从同一 v1.1.4 Tag 测试、构建和自检，Release 复用该次 Windows artifact；实际 SHA256SUMS 与资产摘要已核对。

- 修复 `/dev/tty` 输入流打开失败，以及 CLI 私有源码导致非 root 候选镜像无法读取 `app/__init__.py` 的问题；两 Edition 共用修复。
- 公开构建文件为 0644、子目录为 0755，私有外层目录与秘密仍分别保持 0700/0600，秘密不进入 Docker 上下文。
- 两版 Bot 镜像内部程序目录改为 `/opt/tg2cloud`，用户/组与 logger 改为 `tg2cloud`，新日志使用 `tg2cloud.log`；UID/GID 仍为 `10001:10001`。
- 保留 `tg115.db`、`bot.session`、旧日志、兼容变量与 verify 前缀；不迁移数据、不重写 Telegram、SQLite、rclone、WebDAV 或 HTTPS 业务流程。
- 新增 Linux 真实候选镜像启动门槛；正式两个 EXE 仍由 Windows Actions 构建，Release 复用该次 artifact 与实际 SHA256。

真实首次安装、跨版本升级、回退和 Telegram/云盘转存仍待修复后的实机验收，OpenList 脚本实机验收暂缓。

[查看 v1.1.4 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v114) · [下载与 VPS 单行入口](/download/)。

## TG2Cloud v1.1.3

发布日期与内容核对日期：2026-10-09。两个 Windows EXE 已由 GitHub Actions 从同一 v1.1.3 Tag 重新测试、构建和自检；Release 复用该次产物及实际 SHA256，不使用本机旧构建。

- 新增可选 VPS 单行安装/保留配置升级向导；先收集信息、预检及确认，两个 PySide6 部署器仍是主力。
- 向导模块固定已验证的 commit，实际 payload 始终来自最新正式稳定 Release，不安装 main/RC 未发布业务代码。
- 已有完整实例复用配置，核对官方源码、运行指纹与挂载；TG115、部分实例、手改代码、目录冲突和网关数据库迁移安全停止。
- 复用现有 Docker、备份/有限回退与强制 HTTPS；健康域名不隐式切换，WebDAV 写入验收另行确认。
- 同步 Bot、两个部署器、Windows 资源和文档版本；正式发布后同步下载链接与网站发布状态，保留历史验收记录，不把发布成功当作实机验收。
- 合入 Telethon 1.45.0、PyInstaller 6.22.3 的限定兼容验证及 CI 工具升级；新版 EXE 的真实 VPS 部署、Telegram 登录和转存仍需对应验收。

CloudDrive2 脚本仅通过真实 VPS 只读预检，未执行首次安装、跨版本升级或回退；OpenList 脚本实机验收暂缓。

该历史版本的 Tag/Release 后来已移除，不再作为下载入口。[查看历史源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/9ef61daffe4e62a5177dfcc50e78aa4df70f1af6/CHANGELOG.md) · [下载与 VPS 单行入口](/download/) · [脚本完整指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。

## TG2Cloud v1.1.2

发布日期：2026-10-08。本次聚焦运行状态、故障提示与 HTTPS 维护，两个 Windows EXE 继续由 Actions 从同一不可变标签构建一次，并以该次实际产物生成 SHA-256。

**实际版本与阶段。** 运行状态分别显示本机部署器和 VPS Bot 实际版本；未知不当作最新版，不自动升级或降级。既有进度、日志与弹窗显示实际执行阶段和核对建议，不虚构百分比或根因。

**共享代理维护。** 两版 HTTPS 对话框新增私密代理备份、完整性检查、隔离解包和当前域名续期 dry-run。历史备份可选择核验；清理须先预览再确认，默认取消、至少保留一份，清单变化或校验失败拒绝执行。维护增加远端时限与精确任务清理，断连时不冒充清理已完成。

**续期与限流诊断。** 区分续期检查成功与证书实际变更；续期失败、已有记录超过 26 小时未更新或证书临近到期显示黄色警告，当前 HTTPS 自检通过时入口仍可用。OpenList `/doctor` 显示真实探测时间、401/429 分类和剩余冷却，原有退避与转存逻辑不变。

**构建与发布。** 部署器与 Bot 共用版本源，校验 Tag、源码、Windows 资源和发布文档一致性；修复打包备份助手的相对路径问题，增加备份对话框自检。Release 等待同标签 Windows/Linux 检查成功，复用已构建的 artifact，拒绝替换已有 Release。

本地回归与标签 CI 通过。专用 Debian 13 VPS 的代理备份/核验/隔离解包、OpenList 路由移除后恢复和续期 dry-run 通过；两版各 11 项 HTTPS 自检通过，CloudDrive2 既有配置与容器保持不变。历史备份清理只做无删除预览。

真实 Bot/网盘转存、401/429 实际恢复、长期自动续期、完整灾难恢复、独立网络的后端端口隔离及真实 Windows 桌面交互仍待验收，不把隔离解包或本机 HTTPS 自检当作全链路通过。

[查看该版历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v112) · [维护与诊断说明](/operations/maintenance/) · [备份与恢复边界](/operations/backup/)。

## TG2Cloud v1.1.1

**共享 HTTPS 事务保护。** 配置/移除使用 VPS 级事务锁，状态原子提交；移除路由同步 Certbot 活动域名，并检查保留 Edition，失败回退旧配置。

**OpenList 探测与路径保护。** 大目录检查不再截断至 10,000 项；只读探测区分 401/429，合并短时间刷新并增加冷却与限流退避。CloudDrive2 上传、改名命令与探测策略不变。

**发布门禁。** 同一标签的 Linux 验证和 Windows 构建均成功后，才发布一次构建生成的两个 EXE 与实际 SHA-256。

本轮双网关 HTTPS 共存、外部访问/跳转/公开 WebDAV 阻断及真实 SSH 锁互斥/断锁释放通过。OpenList Bot/WebDAV/限流恢复、路由移除和长期续期尚未重新实测；沿用旧版转存验收基线，不宣称本版全链路重新验收。

[查看该版历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v111)。

## TG2Cloud v1.1.0

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**强制 HTTPS 管理入口。** 受管 CloudDrive2/OpenList 基础容器健康后自动进入域名配置；证书、HTTPS、HTTP 跳转、公开 `/dav` 阻断和后端回环监听全部通过后才显示“部署完成”。

**收紧公网边界。** CloudDrive2 19798 与 OpenList 5244 继续只监听 VPS 回环地址，只有共享 Nginx 使用公网 80/443。普通工作台不再显示固定端口 SSH 隧道按钮，底层隧道代码仅保留兼容和故障恢复能力。

**验收门禁。** 受管网关在 WebDAV 最终验收前再次检查当前 Edition 的 HTTPS 状态；外部 WebDAV 模式不要求为不存在的本地管理容器配置域名。

CloudDrive2 与 OpenList 已在真实 VPS 完成受管部署、证书签发/复用、HTTPS 自检和 WebDAV 全流程验收。

[查看该版历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v110)。

## TG2Cloud v1.0.4

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**Bot 状态首页。** 使用紧凑的任务与实时速度面板，根据实际 Edition 显示 CloudDrive2 或 OpenList，并以数字时间标记本次状态生成时间。

**按钮与资源页。** 首页按钮精简为任务、VPS 资源和原地刷新；CPU、可用内存、可用磁盘与 TG2Cloud 本地额度进入独立资源页，按钮结果继续编辑原消息。

**兼容与边界。** 目的端状态、任务统计、分阶段速度与 `ResourceMonitor` 均复用现有实现，旧 `menu:status` 回调继续兼容；Telegram 下载、SQLite 队列、rclone、WebDAV、streaming 和既有部署流程未被重写。

新 Bot 界面已通过自动回归测试；v1.0.3 已完成的共享域名 HTTPS 验收，以及两版既有基础部署和 WebDAV 真实 VPS 验收结果继续作为回归基线。

[查看该版历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v104)。

## TG2Cloud v1.0.3

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**域名 HTTPS。** 新增两个 Edition 共用的 Dockerized Nginx/Certbot 网关，可为 CloudDrive2 与 OpenList 管理界面分别配置 HTTPS 域名；原 SSH 隧道和 Docker 内网 WebDAV 保持不变。

**安全与回退。** 增加 DNS、端口归属、证书、HTTPS、跳转、公开 `/dav` 阻断和后端回环监听检查；配置失败保留旧路由，不停止或覆盖外部 Web 服务。

**可靠性与界面。** 修复证书复用、失败清理、续期筛选、状态脚本和 NAT 回环误报，域名状态结果改为固定高度、可滚动和可复制的小型日志框。

共享域名 HTTPS 功能已完成验收，适用于 CloudDrive2 与 OpenList。两版原有基础部署和 WebDAV 真实 VPS 验收结果继续作为回归基线。

[查看该版历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v103)。

## TG2Cloud v1.0.2

该版本的两个 Windows EXE 从同一标签源码构建，并使用实际产物计算 SHA-256。

**OpenList 写入兼容性。** 针对部分 OpenList/115 Open 对 MOVE 返回成功但目标文件未生成的情况，改成预留无冲突最终路径后直接写入，保留大小复验、失败保护和安全清理。

**CloudDrive2 稳定流程。** 继续使用临时上传、改名和大小复验；OpenList 新逻辑按后端隔离。

**部署界面与错误提示。** 修复 OpenList 工作台窄侧栏裁切，区分 401 凭据错误和 429 限流。

发布说明记载两版已完成真实 VPS 基础部署与 WebDAV 验收；Telegram 和不同文件规模仍应在用户实际环境继续验证。

该版 Release／Tag 已移除，[查看 v1.0.2 历史记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md#tg2cloud-v102)。

## TG2Cloud v1.0.1

修复 CloudDrive2 首次部署时，网络修复发现逻辑把当前 Bot 容器误判为第二个网关的问题。

仅从网关发现中排除当前 Edition 的 Bot，保留多个真实网关和旧 TG115/固定端口冲突的保护，增加对应回归测试。该历史条目的验证说明按当时记录理解，不当作当前全链路验收承诺。

## TG2Cloud v1.0.0

建立两个 PySide6 正式 Edition，使用独立安装目录、容器、Docker 网络和固定管理隧道端口。

加入新命名空间与必要旧标记兼容，既有 TG2Cloud 重新部署默认保留 `.env`，明确旧 TG115 不会被自动接管。OpenList 增加管理、脱敏日志、一致性备份等专属操作。

正式构建不再包含 Classic/Tkinter 部署器。

## 与上游 TG115 的关系

TG115 v1.6.2 等记录属于代码演进历史，并不是 TG2Cloud 自身的版本。历史入口可查看 [仓库完整 CHANGELOG](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

本导航中的历史版本条目是更新日志入口，不是各旧版文档的完整快照。下载历史产物前，应自行核对对应 Release 是否存在及其具体资产。

## 当前仍然存在的限制

没有正式自动 Restore；独立卸载仅针对可核验的标准受管资源，实机卸载待验收；CloudDrive2 没有手动业务备份 UI，但两版都有共享 HTTPS 代理备份工具；没有旧 TG115 状态/队列的自动原地迁移；没有跨实例 Token 分布式锁；Windows EXE 未提供商业代码签名。

使用前查看 [备份边界](/operations/backup/) 与 [迁移说明](/operations/migration/)。
