# TG2Cloud 文档目录

当前正式版本为 **v1.5.2**，以 Linux Python + Bash 一键脚本维护；Windows PySide6 部署器停留在 v1.2.1。本文档目录面向仓库读者，不要求跳到网站源码中阅读教程。升级前备份，业务 schema 2 → 3 迁移与回退见[监听指南](LISTENING.md)；公网 NAT 的执行条件见[VPS 指南](VPS-INSTALL.md)。

当前版本的发布证据与待执行的实机清单见 [v1.5.2 记录](development/V152-ACCEPTANCE.md)。历史记录统一列在下方，按对应版本与实际测试范围理解。

## 按你的情况开始

| 你的目标 | 推荐阅读顺序 |
| --- | --- |
| 第一次公网安装 | 填写信息清单 → VPS 安装 → 存储网关 → Bot 使用。 |
| 家里 Linux／NAS 没有公网域名 | 填写信息清单 → LAN 安装 → 存储网关；不要把内网 HTTP 暴露公网。 |
| 已有实例升级 | 先备份 → 对应 VPS／LAN 指南的只读预检 → 确认升级 → 实际转存验收。 |
| 家人转存、手机看电影 | 家庭共享 → 独立外部 WebDAV；提交和读取是两套授权。 |
| 任务失败或名字不理想 | 先看 FAQ → 任务恢复或命名专题，不先卸载。 |
| 停止使用 | 备份需保留的数据 → 解除附加功能依赖 → 卸载预检和确认。 |

下面各专题提供实际命令；示例路径、域名和任务编号需替换为自己的值。

## 开始使用与安装

- [管理员监听与转存计划](LISTENING.md)：个人账号、筛选规则、审批、来源目录与迁移。
- [项目说明与下载](../README.md)
- [English README](../README_EN.md)
- [填写信息清单](填写信息清单.md)：部署前需要准备的信息，不在文档中保存秘密。
- [Linux 部署与兼容性](ARCHITECTURES.md)：原生支持、镜像和依赖证据、CI／发布结果及已确认的实机范围。
- [VPS 一键安装与升级](VPS-INSTALL.md)：公网服务器、强制 HTTPS、保留配置升级。
- [Docker Compose 部署](COMPOSE.md)：从下载到首次转存的逐步操作、两版网关配置、常用命令及备份升级排查；包含 v1.5.3 的可选 HTTPS 向导及其适用范围。
- [局域网 / NAS 安装](LAN-INSTALL.md)：独立内网入口、支持平台与安全边界。
- [存储网关配置与 WebDAV 验收](STORAGE.md)：两版后台配置、专用用户权限、根目录／子目录及真实写入验收。
- [外部 WebDAV](external-webdav.md)：v1.3.1 起提供，v1.3.2 优化向导；独立 HTTPS 只读附加入口、独立账号、目录和生命周期，不加入主安装，原生权限需按指南验收。
- [Bot 使用与命令](BOT-USAGE.md)：首次提交、任务状态、完整命令、首页与资源页、原生命令菜单。
- [文件命名与媒体组](NAMING.md)：文字来源、多语言评分、原名优先、图片说明、一图一视频同标题、多成员编号及识别限制。
- [家庭共享](FAMILY-SHARING.md)：管理员与家人授权、各自任务、共同目录及独立的外部只读账号；新版可用性以正式 Release 为准。

## 运维、故障排查与迁移

- [运行状态与维护](OPERATIONS.md)：管理命令、配置变更、实际版本、日志、HTTPS、备份管理与排查索引。
- [四项可选增强（v1.4.3）](FEATURE-ENHANCEMENTS.md)：分类、主动通知、成员配额和诊断报告，含默认值、schema2迁移与验收边界。
- [复用已有 Docker Nginx](DOCKER-NGINX.md)：v1.4.2 显式接入、持久化网络／挂载、证书责任与续期、事务恢复、迁移和卸载保护；原 managed 默认模式不变，真实 VPS 仍需验收。
- [常见问题](FAQ.md)：安装／升级、账号／目录、状态计数、命名、限流及卸载的快速排查入口。
- [任务恢复与验证](RECOVERY.md)：重新转存、远端冲突、验证等级、遗留扫描、容量保护及旧链接兼容。
- [配置与运行目录参考](CONFIGURATION.md)：环境字段、默认值、账号边界、实际数据位置及安全修改方法。
- [备份与恢复预检](BACKUP-RESTORE.md)：备份范围、数据库／Session 一致性、离线快照命令与隔离恢复边界。
- [卸载指南](UNINSTALL.md)：先只读核对，区分完整清理与保留数据；卸载不是升级步骤。
- [从 TG115 迁移](MIGRATION_FROM_TG115.md)：旧实例识别、数据保护与迁移边界。

## 开发、品牌与许可

- [参与贡献](../.github/CONTRIBUTING.md)：本地检查、CI 与正式发布规则。
- [仓库结构与维护规范](development/REPOSITORY.md)：源码职责、文档同步与本地产物处理。
- [Linux Python + Bash 重构（v1.3.0）](development/LINUX-REFACTOR.md)：新入口、模块映射、运行兼容、指纹协议和 helper 发布门槛。
- [脚本优先与桌面版冻结](development/SCRIPT-FIRST.md)：磁盘推荐、源码发布、备份和分阶段清理边界。
- [品牌规范](development/BRAND-GUIDE.md)：正式 Logo / Icon 的唯一来源与使用规则。
- [第三方组件说明](第三方组件说明.md)
- [安全政策](../.github/SECURITY.md)
- [许可证](../LICENSE)
- [全版本更新记录](../CHANGELOG.md)：v1.0.0 至今的逐版功能、修复、兼容与验收边界，包含已移除 Release／Tag 的历史版本；页首提供速查表，不随下载版本精简而删减历史。
- [当前发布说明](../RELEASE_NOTES.md)：当前维护版本的改动与发布边界，不代替全版本记录。

## 历史发布与验收

这些文件保留当时的变更、测试和未验证范围，不作为当前操作步骤。已发布版本的开发阶段记录不代表功能仍待发布。

### 按版本查阅验收

- [v1.5.2 Compose 与监听恢复](development/V152-ACCEPTANCE.md)：真实进度、兼容边界与发布后清单。

- [v1.5.1 性能维护与用户验收](development/V151-ACCEPTANCE.md)：发布资产、CloudDrive2 升级与 WebDAV 验收。
- [v1.5.0 管理工具同步](development/V150-ACCEPTANCE.md)：Bot／CLI 版本、监听稳定性与发布核验。
- [v1.4.11 来源归档与导航](development/V1411-ACCEPTANCE.md)：来源目录、恢复与界面返回。
- [v1.4.10 交互维护发布与验收](development/V1410-ACCEPTANCE.md)：监听表单、终端菜单、外部维护恢复、升级与发布后检查。
- [v1.4.9 监听发布与验收](development/V149-ACCEPTANCE.md)：schema 3、独立 Session 与发布后验收。
- [v1.4.5 用户验收记录](development/V145-ACCEPTANCE.md)：Ubuntu ARM64 CloudDrive2 升级及单独 WebDAV 写入验收，按实际日志限定结论。
- [v1.4.4 CloudDrive2 双架构升级验收](development/V144-ACCEPTANCE.md)：用户确认 Ubuntu ARM64 与 Debian AMD64 的 v1.4.3 → v1.4.4 升级通过，记录新摘要、最近业务观察和容量提醒，明确 WebDAV 写入／真实转存／外网／回退等边界。
- [v1.4.3 CloudDrive2 在线升级日志核验](development/V143-ACCEPTANCE.md)：用户日志确认 v1.4.2 → v1.4.3、Bot healthy 和本机 HTTPS；解释构建 WARNING，真实转存／公网访问及回退尚未确认。
- [v1.4.2 CloudDrive2 人工升级验收](development/V142-ACCEPTANCE.md)：Debian AMD64、核验原 v1.3.4 提交后保留配置升级；备份、数据保留、只读 WebDAV、外部 HTTPS，以及旧 Release 缺失的自动升级限制。
- [v1.4.1 CloudDrive2 ARM64 首次安装验收](development/V141-ACCEPTANCE.md)：Ubuntu 26.04.1 公网 NAT、原生构建、Bot 健康、本机 HTTPS 与 WebDAV 操作；APT 问题及未验证范围单列。
- [v1.3.3 CloudDrive2 升级与转存验收](development/V133-ACCEPTANCE.md)：正式 v1.3.2 → v1.3.3 升级、配置／Session 保留及用户实际转存确认，其他场景不外推。
- [v1.3.0 CloudDrive2 升级验收](development/V130-ACCEPTANCE.md)：本次人工迁移、配置与历史数据保留、用户确认及尚未验证范围。

### 开发历史与验收规范

- [v1.4.6～v1.5.1 维护开发记录](development/LOCAL-MAINTENANCE.md)：本地 WebDAV 页面、发布候选工具、测试分类和共享 CI。
- [v1.4.5 维护、页面与发布核验](development/MAINTENANCE-NEXT.md)：诊断建议、隔离数据库恢复演练、可信升级基线与发布预检，以及 OpenList／内网／已有代理／家庭共享的独立实机补测清单。
- [v1.4.3 维护增强](development/MAINTENANCE-IMPROVEMENTS.md)：受支持旧版基线、实例快照、业务就绪、Nginx 生命周期与命名预览；区分开发记录、正式发布和实机验收。
- [HTTPS 人工验收范围](development/DOMAIN-HTTPS-ACCEPTANCE.md)：按版本理解实机证据，不等于当前所有流程均已验收。
- [可靠性维护版本验收](development/RELIABILITY-ACCEPTANCE.md)：主分支与正式版差异、自动与人工发布门槛。

## 历史图形部署器

- [历史 Windows 部署说明](README-小白使用说明.md)：冻结的图形界面与部署步骤，不随 Linux 版本更新；Windows 部署器停更于 v1.2.1，当前 Linux 用户请使用上面的安装、网关与 Bot 指南。

## 文档维护边界

`docs/` 是仓库阅读入口，不以网站源码或网站文章代替必要说明；README 导航指向本目录。`website/` 是独立的网站内容，两边可以包含相同主题，不为消除跨入口重复而删减任一侧。仓库内部同一主题尽量集中在对应指南，并用相互链接连接安装、使用、恢复与维护；命令、安全边界和版本事实仍应一致。

历史教程与验收记录继续保留原路径和链接。当前操作以用户指南为准；过去某一版本、某个 Edition 的验收结果不外推到全部功能或其他实例。

- [v1.5.3 发布准备与兼容说明](development/V153-ACCEPTANCE.md)：新安装命名、Compose HTTPS、脚本隔离及发布前门槛。
