# TG2Cloud 文档目录

后续以 Linux 一键脚本为主要维护入口，Windows PySide6 部署器停留在 v1.2.1。请按部署环境选择教程，不把内网 HTTP 管理方式用于公网；旧图形界面教程用于 v1.2.1。

## 开始使用与安装

- [项目说明与下载](../README.md)
- [English README](../README_EN.md)
- [小白使用说明](README-小白使用说明.md)：图形化部署、网关配置与首次转存。
- [填写信息清单](填写信息清单.md)：部署前需要准备的信息，不在文档中保存秘密。
- [VPS 一键安装与升级](VPS-INSTALL.md)：公网服务器、强制 HTTPS、保留配置升级。
- [局域网 / NAS 安装](LAN-INSTALL.md)：独立内网入口、支持平台与安全边界。

## 运维、故障排查与迁移

- [运行状态与维护](OPERATIONS.md)：实际版本、日志、HTTPS 续期、备份与故障提示。
- [任务恢复与离线备份（v1.2.1）](RECOVERY.md)：重新转存、远端冲突、验证等级、容量保护和备份边界。
- [卸载指南](UNINSTALL.md)：先只读核对，区分完整清理与保留数据；卸载不是升级步骤。
- [从 TG115 迁移](MIGRATION_FROM_TG115.md)：旧实例识别、数据保护与迁移边界。

## 开发、品牌与许可

- [参与贡献](../.github/CONTRIBUTING.md)：本地检查、CI 与正式发布规则。
- [仓库结构与维护规范](development/REPOSITORY.md)：源码职责、文档同步与本地产物处理。
- [脚本优先与桌面版冻结](development/SCRIPT-FIRST.md)：磁盘推荐、源码发布、备份和分阶段清理边界。
- [品牌规范](development/BRAND-GUIDE.md)：正式 Logo / Icon 的唯一来源与使用规则。
- [HTTPS 人工验收范围](development/DOMAIN-HTTPS-ACCEPTANCE.md)：按版本理解实机证据，不等于当前所有流程均已验收。
- [可靠性维护版本验收](development/RELIABILITY-ACCEPTANCE.md)：主分支与正式版差异、自动与人工发布门槛。
- [第三方组件说明](第三方组件说明.md)
- [安全政策](../.github/SECURITY.md)
- [许可证](../LICENSE)
- [版本历史](../CHANGELOG.md)与[发布说明](../RELEASE_NOTES.md)

## 网页文档

[文档站源码与维护说明](../website/README.md)介绍构建和检查方式；网站文章位于 `website/docs/`。网站与仓库文档针对不同阅读入口维护，操作命令、删除边界和版本事实必须保持一致，不能以网站摘要替代完整安全说明。
