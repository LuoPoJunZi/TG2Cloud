# TG2Cloud 文档目录

当前正式版本为 **v1.4.2**，以 Linux Python + Bash 一键脚本维护，原生支持 AMD64／ARM64；Windows PySide6 部署器停留在 v1.2.1。本文档目录面向仓库读者，不要求跳到网站源码中阅读教程。公网 NAT 的 HTTPS 修复及执行条件见[VPS 指南](VPS-INSTALL.md)。

v1.3.4 已发布说明命名与图片／媒体组增强，完整规则见[命名指南](NAMING.md)。旧“待发布”章节标题仅保留链接兼容，正文已明确实际版本；升级实例才会启用新代码，更新文档不更新 Bot。

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

- [项目说明与下载](../README.md)
- [English README](../README_EN.md)
- [填写信息清单](填写信息清单.md)：部署前需要准备的信息，不在文档中保存秘密。
- [AMD64 / ARM64 与 Oracle Cloud](ARCHITECTURES.md)：原生支持、镜像和依赖证据、CI／发布结果及已确认的实机范围。
- [VPS 一键安装与升级](VPS-INSTALL.md)：公网服务器、强制 HTTPS、保留配置升级。
- [局域网 / NAS 安装](LAN-INSTALL.md)：独立内网入口、支持平台与安全边界。
- [存储网关配置与 WebDAV 验收](STORAGE.md)：两版后台配置、专用用户权限、根目录／子目录及真实写入验收。
- [外部 WebDAV](external-webdav.md)：v1.3.1 起提供，v1.3.2 优化向导；独立 HTTPS 只读附加入口、独立账号、目录和生命周期，不加入主安装，原生权限需按指南验收。
- [Bot 使用与命令](BOT-USAGE.md)：首次提交、任务状态、完整命令、首页与资源页、原生命令菜单。
- [文件命名与媒体组](NAMING.md)：文字来源、多语言评分、原名优先、图片说明、一图一视频同标题、多成员编号及识别限制。
- [家庭共享（v1.3.3）](FAMILY-SHARING.md)：管理员与家人授权、各自任务、共同目录及独立的外部只读账号；新版可用性以正式 Release 为准。

## 运维、故障排查与迁移

- [运行状态与维护](OPERATIONS.md)：管理命令、配置变更、实际版本、日志、HTTPS、备份管理与排查索引。
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
- [HTTPS 人工验收范围](development/DOMAIN-HTTPS-ACCEPTANCE.md)：按版本理解实机证据，不等于当前所有流程均已验收。
- [可靠性维护版本验收](development/RELIABILITY-ACCEPTANCE.md)：主分支与正式版差异、自动与人工发布门槛。
- [v1.3.0 CloudDrive2 升级验收](development/V130-ACCEPTANCE.md)：本次人工迁移、配置与历史数据保留、用户确认及尚未验证范围。
- [v1.3.3 CloudDrive2 升级与转存验收](development/V133-ACCEPTANCE.md)：正式 v1.3.2 → v1.3.3 升级、配置／Session 保留及用户实际转存确认，其他场景不外推。
- [v1.4.1 CloudDrive2 ARM64 首次安装验收](development/V141-ACCEPTANCE.md)：Ubuntu 26.04.1 公网 NAT、原生构建、Bot 健康、本机 HTTPS 与 WebDAV 操作；APT 问题及未验证范围单列。
- [v1.4.2 CloudDrive2 人工升级验收](development/V142-ACCEPTANCE.md)：Debian AMD64、核验原 v1.3.4 提交后保留配置升级；备份、数据保留、只读 WebDAV、外部 HTTPS，以及旧 Release 缺失的自动升级限制。
- [第三方组件说明](第三方组件说明.md)
- [安全政策](../.github/SECURITY.md)
- [许可证](../LICENSE)
- [全版本更新记录](../CHANGELOG.md)：v1.0.0 至今的逐版功能、修复、兼容与验收边界，包含已移除 Release／Tag 的历史版本；页首提供速查表，不随下载版本精简而删减历史。
- [当前发布说明](../RELEASE_NOTES.md)：当前维护版本的改动与发布边界，不代替全版本记录。

## 历史图形部署器

- [小白使用说明](README-小白使用说明.md)：历史 Windows 界面与部署步骤；当前 Linux 用户先按本目录的安装、网关与 Bot 指南操作。

## 文档维护边界

`docs/` 是仓库阅读入口，不以网站源码或网站文章代替必要说明；README 导航指向本目录。`website/` 是独立的网站内容，两边可以包含相同主题，不为消除跨入口重复而删减任一侧。仓库内部同一主题尽量集中在对应指南，并用相互链接连接安装、使用、恢复与维护；命令、安全边界和版本事实仍应一致。

历史图形教程、历史验收记录与当前操作指南承担不同职责，不能用旧截图代替 Linux 界面，也不能将过去的测试结论扩展到当前全部功能。2026-10-19 用户确认 CloudDrive2 v1.3.3 升级后实际转存完成；2026-10-21 提供 v1.4.1 CloudDrive2 ARM64 公网 NAT 首装验收结果。两次分别记录，不代表 OpenList、家庭共享、升级回退或灾难恢复均已通过。

同日另完成 CloudDrive2 v1.3.4 → v1.4.2 的人工升级及只读检查，见上述独立记录；未执行本版真实文件转存或 `external_docker` 实机接入，不与其他版本结果混写。
