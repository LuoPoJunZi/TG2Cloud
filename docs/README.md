# TG2Cloud 文档目录

后续以 Linux 一键脚本为主要维护入口，Windows PySide6 部署器停留在 v1.2.1。请按部署环境选择教程，不把内网 HTTP 管理方式用于公网；旧图形界面教程用于 v1.2.1。

## 开始使用与安装

- [项目说明与下载](../README.md)
- [English README](../README_EN.md)
- [填写信息清单](填写信息清单.md)：部署前需要准备的信息，不在文档中保存秘密。
- [VPS 一键安装与升级](VPS-INSTALL.md)：公网服务器、强制 HTTPS、保留配置升级。
- [局域网 / NAS 安装](LAN-INSTALL.md)：独立内网入口、支持平台与安全边界。
- [存储网关配置与 WebDAV 验收](STORAGE.md)：两版后台配置、专用用户权限、根目录／子目录及真实写入验收。
- [外部 WebDAV](external-webdav.md)：v1.3.1 起提供，v1.3.2 优化向导；独立 HTTPS 只读附加入口、独立账号、目录和生命周期，不加入主安装，原生权限需按指南验收。
- [Bot 使用与命令](BOT-USAGE.md)：首次提交、任务状态、完整命令、首页与资源页、原生命令菜单。
- [家庭共享（v1.3.3）](FAMILY-SHARING.md)：管理员与家人授权、各自任务、共同目录及独立的外部只读账号；新版可用性以正式 Release 为准。

## 运维、故障排查与迁移

- [运行状态与维护](OPERATIONS.md)：管理命令、配置变更、实际版本、日志、HTTPS、备份管理与排查索引。
- [任务恢复与离线备份](RECOVERY.md)：重新转存、远端冲突、验证等级、命名规则、容量保护和备份边界。
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
- [第三方组件说明](第三方组件说明.md)
- [安全政策](../.github/SECURITY.md)
- [许可证](../LICENSE)
- [版本历史](../CHANGELOG.md)与[发布说明](../RELEASE_NOTES.md)

## 历史图形部署器

- [小白使用说明](README-小白使用说明.md)：历史 Windows 界面与部署步骤；当前 Linux 用户先按本目录的安装、网关与 Bot 指南操作。

## 文档维护边界

`docs/` 是仓库阅读入口，不以网站源码或网站文章代替必要说明；README 导航指向本目录。`website/` 是独立的网站内容，两边可以包含相同主题，不为消除跨入口重复而删减任一侧。仓库内部同一主题尽量集中在对应指南，并用相互链接连接安装、使用、恢复与维护；命令、安全边界和版本事实仍应一致。
