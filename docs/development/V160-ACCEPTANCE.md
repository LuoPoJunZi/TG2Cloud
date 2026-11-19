<a id="v160-发布准备与兼容记录"></a>

# v1.6.0 发布与兼容记录

记录日期：2026-11-19。状态：**已正式发布，源码／镜像／Compose 资源已核验**。[v1.6.0 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.6.0)非草稿、非预发布，真实用户 VPS 验收尚未执行；本轮未连接或升级 VPS。

## 本版范围

- 定位为稳定维护与文档整合版。安装、使用和维护教程按当前功能说明，清理逐版累积的介绍与旧菜单；README 保持简洁，详细内容留在 docs 与网站。
- 保留全部版本记录、历史验收、许可证与上游致谢；改名章节保留旧锚点，网站使用现有 legacy 映射。最低依赖版本、包格式、协议和升级回退条件继续明确。
- 唯一版本源、安装入口版本标识与网站源码元数据同步为 1.6.0；网站 publishedVersion、正式下载与实际摘要同步为已核验的 v1.6.0；未替换旧版资产。
- 补充 v1.5.9 不可变提交的两 Edition 可信升级基线；下载、上传、命名、监听、任务队列、去重、恢复及资源保护的业务实现没有修改。网关和基础镜像、运行依赖、部署模板不作无关更新。

## 提交 A／入口 B 与真实 pin

本地准备基于 main 的 `63ebaa37d042c3cb76d006df8e7b4d447cd8ef73`。下列真实身份构成本次已完成的 A／B 与 Tag 版本链：

| 身份 | 真实提交 | 本轮处理 |
| --- | --- | --- |
| 前版 helper A | `16a51c86dd948fe897ace17e464e3ab2828ca953` | 属于原 v1.5.9，保留历史对象 |
| v1.5.9 入口 B／Tag 指向 | `0bd9ec6c6c5a829a2f98c060c1d9f42a7486bff3` | 用于计算可信升级基线，原 Tag 与资产不变 |
| v1.6.0 helper A | `dde1faa6d0ef750e9b3e3a99d99697d0ef56c6e6` | 五组 CI 通过；80 个 helper 远端对象及匿名样本已核验 |
| v1.6.0 入口 B／Tag 提交 | `24961f68bc49253a987916d8f121ba7349fd0f51` | 两个公开入口固定 A，五组 CI 通过 |

新增基线按原工具从 v1.5.9 的不可变提交计算：CloudDrive2 载荷 `eaaf4f59c5c8751ab70d05eb37d07c70178b6612afc713b23e7b699afc708420`，OpenList 载荷 `25588861e67863132b41bb3bc2cd3febdc3f8dd4bfd123411da77989874162d5`。它们是升级比对指纹，不是新发布包的 SHA256。

本批次的 helper A、入口 B 和发布文档提交主题统一为：

```text
release: TG2Cloud v1.6.0
```

各提交正文说明各自职责。GitHub 文件列表显示每条路径最近一次真实修改的提交，未修改路径继续显示原说明；不重写历史，不为统一这一列触碰无关文件。A 已公开并通过 CI，B 固定同一真实 A；正式安装仍以通过同标签检查的已核验 Release 资产为准，源码版本标识不能代替发布结果。

## 自动化验证

以下为 2026-11-19 本地真实结果，不代表已在 GitHub 或真实 VPS 执行：

| 检查 | 实际结果 |
| --- | --- |
| `python -B .github/scripts/check_python.py all` | 1665 项：1630 通过、35 项条件跳过、0 失败；公开输入、Ruff、compileall 通过 |
| Python 3.10 标准库专项 | 215 项：206 通过、9 项条件跳过、0 失败；覆盖一键脚本、Compose、离线管理和诊断 |
| 文档与网站 | 仓库文档回归 55 项、网站回归 38 项通过；构建 33 篇文章、首页及 404，站内链接与资源检查通过 |
| 保留性审阅 | 50 篇原指南的 613 个章节锚点全部可定位；7 份原验收文件及两个更新日志的历史内容保留，品牌与许可证未改 |
| 两 Edition 离线组装 | 干净公开副本的脚本载荷各 143 个 Bot 文件且一致；两份 format 3 Compose 候选包及 21 项无第三方依赖 CLI 帮助检查通过，未构建或运行 Docker |
| Bash／ShellCheck、Bandit | 现有检查范围通过；没有更改规则或新增跳过 |
| 版本与发布预检 | 版本、清单、既有可信基线、发布说明格式与在线 helper 字节一致性均通过；B 远端 CI、同标签发布与正式资源核验现已完成 |

条件跳过包括缺少本机 rclone、真实 Linux 权限／终端条件和未启用的 Docker 集成；不计作通过，不新增无依据 skip。候选组装使用合成镜像引用，不产生正式资产或真实 digest。下载链接继续指向已发布资源。

辅助 A 五组 GitHub Actions 已通过：[原生双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44451281574)、[宿主 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44451282244)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44451281590)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44451281748)、[公共仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44451279590)。入口 B 与同标签原生双架构发布检查均已通过。尚未启动本地 Linux Docker 或真实网关。历史 CI 与测试不作为本版结果，已发布基线的真实实机范围见 [v1.5.9 记录](V159-ACCEPTANCE.md)。

## 实际发布资源与安装入口

正式 Tag 对象为 `bd83556e838ccf207f09750c1e5e0a38c54b4a43`，固定入口 B 提交；未移动旧 Tag。下载实际五个资产，逐个核对 GitHub asset digest、校验清单和字节内容。源码 410 个文件与 Tag Git 对象一致；两版 Compose 包按 Tag 源码及真实镜像重新组装，逐文件一致。

| 已发布资产 | 实际 SHA256 |
| --- | --- |
| `COMPOSE-SHA256SUMS.txt` | `0b04aab568ea080b726a3da740e62efa33032b4d3eb644848f031c793fb9370a` |
| `SHA256SUMS.txt` | `f3992f3d25f27bd5f95835882bff321f718736bbe14ed2f2ccc1c47134ca0aff` |
| `TG2Cloud-v1.6.0-compose-clouddrive2.tar.gz` | `46fe04edcef865d4feddff8cc751d4c3372eaa88fd3a4b4d8c0cfb8dab189a6b` |
| `TG2Cloud-v1.6.0-compose-openlist.tar.gz` | `1bf0892788b81d7956fda2a8a2663ed8a135fbc5bd540646e05072d5f1bdb02a` |
| `TG2Cloud-v1.6.0-source.tar.gz` | `9cb0dec06fe9de12ab58e3644f63d2bfd9fd7ab8e674e0256d466444944f6c87` |

共享镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:4ef0b2a4b44c7ef869e4e90da7a2f74b8a434ce895568882a54d6be84101d64d`。匿名拉取核验通过，两个 Linux 子镜像及其配置内容的摘要、版本 1.6.0 和 revision 与 Tag 提交一致：

| 平台 | 实际镜像摘要 |
| --- | --- |
| `linux/amd64` | `sha256:eea9e19207889449f76379d816902e60a1c632ee0cc88e2887de536d3d3199fd` |
| `linux/arm64` | `sha256:e75ee1b6e5436641e9062a5f57ecbed4dfa2b525f0ebfe873bb14017764ab920` |

一键脚本继续使用原[VPS 入口](../VPS-INSTALL.md)或[内网入口](../LAN-INSTALL.md)，固定已公开 A 并从正式 Release 读取业务源码。独立 Compose 使用[同版完整部署包](../COMPOSE.md)，源码和 Compose 均为 v1.6.0；按原方式升级，不混用目录。

入口 B 的五组 CI：[原生双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44452615735)、[宿主 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44452615790)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44452615861)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44452615604)、[公共仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44452615628)，均成功。

同标签原生双架构及官方源码发布：[release](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44453089754)，成功；同标签共享镜像和两版部署包：[Compose images and bundles](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/44453992612)，成功。公开主分支仅保留 main，本次已合并辅助分支已清理，提交主题全部为 `release: TG2Cloud v1.6.0`。

历史 v1.5.9 的用户实机结果保留在对应记录中，不扩展为本版已经完成真实 Telegram、两网关或 VPS 验收。源码 Tag 中的网站待发布元数据是发布时快照，资产核验后只更新 main 的文档，不回写 Tag 或替换源码／镜像／部署包。

## 数据、部署与回退

业务 schema 3 不变，本版没有数据库迁移。保留受支持的旧 schema 事务迁移与升级前备份；新装 `data/tg2cloud.db`，已有唯一 `data/tg115.db` 按原名继续使用，双库等不明确情况停止。Bot Session、个人监听 Session、配置、任务和下载文件保留。

一键脚本与独立 Compose 分别按原部署方式升级，不相互接管。升级前保存私密配置、匹配代码／模板和数据库、Session 的一致性快照，备份记录不能包含公开凭据。恢复先保护当前数据并停止新 Bot，再按匹配代码与快照操作；不能只降低镜像版本，不自动覆盖可能已经写入的新数据库，不同时启动使用同一 Bot Token 的两个实例。详见[备份与恢复](../BACKUP-RESTORE.md)。

## 发布后验收清单

真实用户 VPS 验收尚未执行，安排在发布资源可安装并获相应授权后。优先使用独立测试实例和测试 Bot，不复用同时在线的 Token。

| 项目 | 操作与通过标准 | 失败时保留的安全信息 |
| --- | --- | --- |
| 两种部署的升级与新装 | 按原方式使用同版完整资源；CLI、Bot 实际版本均为目标，健康、配置和数据保留 | 版本、阶段标记、退出码及脱敏摘要，不发 .env／Session |
| 公网与内网入口 | 核对管理模式、监听地址和实际访问；HTTPS 从外部网络单独验证 | 模式、检查分类与证书有效期，不公开私有拓扑 |
| CloudDrive2／OpenList | 各做自有小文件手动转存和监听，核对目标目录、名称和大小，再在云端官方客户端确认 | 任务编号、脱敏失败分类和聚合诊断，不公开文件内容 |
| 监听与家庭共享 | 普通用户保持原权限；管理员规则、来源目录、审批、暂停与恢复正常，两个 Session 隔离 | 计数、状态、规则摘要与错误分类，不提供个人账号信息 |
| 排队与资源保护 | 就绪／诊断反映实际等待原因；磁盘保护、有限冷却与恢复不丢任务 | 聚合窗口、等待原因、资源余量及时间 |
| 备份与故障回退 | 隔离目录校验匹配快照，核对库完整性及任务；不覆盖生产库演练 | 校验结果、schema、工具版本，不发送备份本体 |

若失败，先暂停相关新增任务、保护现场与一致性备份，按错误分类处理；不批量删除云端文件、数据库或授权来掩盖问题。WebDAV 接收和大小复验不等于内容哈希验证或云存储官方最终入库。既有版本验收也不证明本版已经通过长期负载、真实 ACME／续期或全部平台测试。
