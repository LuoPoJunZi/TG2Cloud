# 来源、致谢与素材说明

TG2Cloud v1.5.1 准备发布（2026-10-28）；不新增第三方依赖、品牌素材或许可，历史记录保留。

TG2Cloud v1.5.0 已正式发布，资料核对日期 2026-10-27；本版不增加第三方运行依赖、品牌资源或许可证，下面历史来源与原许可保留。


TG2Cloud v1.4.10 已正式发布；资料核对日期：2026-10-26。A／B、main、同标签双架构和实际源码资产核验通过；新增监听交互与维护恢复，不新增依赖或品牌资源。真实 Telegram／VPS 验收尚未执行，下面历史结果保持原范围。
TG2Cloud v1.4.9 已正式发布；资料核对日期：2026-10-26。A／B、同标签 AMD64／ARM64 CI 和实际资产核验通过；真实 VPS／Telegram／两网关转存尚待验收。本版不新增运行依赖、品牌资源或许可证。

TG2Cloud v1.4.7 资料核对日期：2026-10-25，已正式发布。同标签双架构与实际源码资产核验通过；本轮不新增运行依赖或变更品牌、上游及许可，历史来源记录保留。

TG2Cloud v1.4.6 资料核对日期：2026-10-24，已正式发布；同标签双架构及实际源码资产核验通过。本文保留下面的历史来源与许可；本版不新增第三方依赖，不更换品牌资源或许可证。

TG2Cloud v1.4.5 资料核对日期：2026-10-24。本版已正式发布，A／B 和同标签原生双架构门禁均通过，实际源码资产与校验清单已核验。本次不新增运行依赖，开发审计依赖 filelock 安全更新至 4.2.1；不改变固定镜像、品牌或上游许可，不借用历史实机结论。

2026-10-23 另收到[用户升级日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)：仅证明 CloudDrive2 AMD64 的 v1.4.2 → v1.4.3 基础升级、Bot 健康与本机 HTTPS；实际转存、外网与回退未确认。以脱敏记录区分用户反馈与开发者／CI 测试，不发布私人部署信息或原始日志。

2026-10-23 另收到两份 [v1.4.4 双架构升级日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)，用户确认 CloudDrive2 在 Ubuntu ARM64 与 Debian AMD64 的 v1.4.3 → v1.4.4 升级验收通过。只记录用户日志证据；WebDAV 写入、真实转存、外网、回退和其他 Edition 不由本次结论覆盖，不发布原始日志或私人部署信息。

## 主项目与上游

本网站为 LuoPoJunZi/TG2Cloud 整理中文使用与维护文档，保留项目与上游作者致谢：
- https://github.com/LuoPoJunZi/TG2Cloud
- https://github.com/whyhhh20/TG115

TG2Cloud 的公开 LICENSE 为 MIT，版权行为 `Copyright (c) 2026 TG115 Contributors`。完整许可保留在根目录 LICENSE 与静态产物 LICENSE.txt 中。
- https://github.com/LuoPoJunZi/TG2Cloud/blob/main/LICENSE

主要技术资料：
- README：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/README.md
- v1.2.0 Release：https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.0
- 运行维护：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md
- VPS 单行脚本：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md
- CHANGELOG：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md
- 产品参数：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/src/tg2cloud/deployment/profiles.py
- 迁移说明：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/MIGRATION_FROM_TG115.md
- 安全说明：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/SECURITY.md
- 贡献说明：https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/CONTRIBUTING.md

README 与 main 分支可能在之后更新。正式 Release 的确定行为应以对应标签、发布说明及用户实际验收为准。

## 界面与素材

页面的栏目、文档导航和首页组织参考 https://tg115.pages.dev/ 的文档站思路；没有下载其整站代码或第三方图片。

本站 HTML/CSS 模板、轻量云图标、流程示意和交互代码随源码提供。没有加入商业素材、部署器虚构截图或字体文件。字体使用操作系统已有字体。

CloudDrive2、OpenList、Telegram、GitHub、Cloudflare 等名称仅用于描述兼容组件、资料来源与部署平台，不表示这些平台对本网站的背书。

TG2Cloud v1.0.3 的可选域名 HTTPS 功能使用 Nginx 与 Certbot 容器。Nginx 开源版采用 BSD-2-Clause 许可，Certbot 采用 Apache-2.0 许可；具体版本与其他第三方组件说明见主仓库的 `docs/第三方组件说明.md`。

## 构建实现

自包含 Node.js 标准库静态生成器，无第三方 npm 运行或构建依赖。并非 VitePress、Vue 或 React 项目，不声称提供这些框架的完整能力。

Cloudflare 部署说明参考官方文档：
- https://developers.cloudflare.com/pages/configuration/build-configuration/
- https://developers.cloudflare.com/pages/get-started/direct-upload/
