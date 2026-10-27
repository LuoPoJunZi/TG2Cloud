# 文档来源与维护

当前源码 **v1.5.0**（待发布）；核对日期 **2026 年 10 月 27 日**。正式下载基线仍为 [v1.4.11](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.11)，新版本进度见[发布与验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V150-ACCEPTANCE.md)。


上一正式版本 **v1.4.10**；核对日期 **2026 年 10 月 26 日**。[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.10)、[同标签双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40287434283)与实际资产已核验，真实环境验收单独记录。

历史资料：当时源码与正式版本 **v1.4.9**；资料核对日期 **2026 年 10 月 26 日**。A／B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40268795680)及实际源码资产、SHA256 清单和 GitHub 摘要已核验。真实 VPS、Telegram 与两网关转存尚待用户验收。

历史版本为 [**v1.4.8**](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.8)；资料核对日期 **2026 年 10 月 25 日**。A／B、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175950235)和实际源码资产核验通过，原生 Linux PTY 与隔离网关由 CI 验证，真实 VPS 及账号目录仍须人工验收。

历史资料（2026-10-25）：当时正式稳定版本为 [**v1.4.7**](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.7)；资料核对日期 **2026 年 10 月 25 日**。A／B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160704507)及实际源码资产核验通过；本版未执行真实 VPS、手机、公网 ACME 或灾难恢复验收。

历史资料（2026-10-24）：当时源码与正式版本为 [**v1.4.6**](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.6)；资料核对日期 **2026 年 10 月 24 日**。A／B、[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089991036)及实际源码资产核验通过，下方旧版记录按历史范围保留；本版维护细节见[源码说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LOCAL-MAINTENANCE.md)。

历史资料核对日期为 **2026 年 10 月 24 日**，对应正式 [**v1.4.5**](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.5)。辅助 A、入口 B 与[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40073091331)全部通过，实际源码包、SHA256 清单及 GitHub 资产摘要已核验；完整证据见[维护发布记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-NEXT.md#7-v145-发布核验2026-10-24)。本版未连接真实 VPS，不借用下面历史记录声明实机验收。

历史资料核对（2026-10-23，对应 v1.4.4）：辅助 A `ea93c95eda0fa68c807b56c41871e09b7a19634b`、入口 B／Tag `6164a237108786c01a7a958ab56e16023df04d79` 各五项 CI 及[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39920070111)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要已核验。 本版补充安装反馈与管理菜单精简，不改变 Bot 核心或新增数据库迁移；须显式升级离线工具。历史用户日志不外推本版实机验收。

2026-10-23 已另收到两份 v1.4.4 用户升级日志并确认验收通过，分别覆盖 CloudDrive2／Ubuntu ARM64 和 Debian AMD64。日志证据与用户确认、自动 CI 以及仍未执行的 WebDAV 写入／真实转存／外网／回退分别记录，不因发布成功而推断业务全部通过。

## 主要来源

| 来源 | 用于核对 |
| --- | --- |
| [v1.4.9 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.9) | 管理员监听、转存计划、schema 3；A／B、同标签双架构及实际资产核验，实机未验收 |
| [v1.4.8 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.8) | 外部 WebDAV 安装、终端输入、实际目录和管理地址；A／B、同标签双架构及实际资产核验 |
| [v1.4.7 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.7) | 外部 WebDAV 统一管理、独立脚本退役、Certbot 挂载与失败恢复；A／B、同标签双架构和实际资产核验 |
| [v1.4.5 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.5) | 管理页面、诊断、隔离数据库演练与开发依赖安全补丁；A／B、同标签双架构和实际资产核验 |
| [v1.4.4 双架构用户升级验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md) | 用户确认两台 CloudDrive2 的 v1.4.3 → v1.4.4 升级；配置／备份／healthy／本机 HTTPS／最近业务就绪观察，以及写入未执行和其他未覆盖范围 |
| [已发布 v1.4.4 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.4) | 日志分级、证据型升级摘要与浅层菜单；同标签原生双架构及实际资产核验，不等同真实 VPS 验收 |
| [v1.4.3 用户在线升级日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md) | 用户日志中的 CloudDrive2 AMD64 基础升级、healthy、本机 HTTPS 与 WARNING；转存、外网、数据库回退及可选功能尚未确认 |
| [已发布 v1.4.3 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.3) | 维护、可选分类／通知／配额、脱敏报告、测速及菜单；schema 2 迁移与原生双架构发布核验 |
| [项目 README](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/README.md) | 部署、命令、路径、状态、常见问题 |
| [已发布 v1.4.2 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.2) | Docker Nginx 显式复用、事务恢复、Webroot 与宿主续期、schema 3 及卸载保护；同标签双架构验证和实际资产校验 |
| [已发布 v1.4.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.1) | NAT 预检修复、同标签双架构验证、源码包与实际 SHA256；保留命名、家庭共享及外部只读功能 |
| [已发布 v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) | 同一次 Actions 构建的实际资产与 SHA256；不是实机验收结论 |
| [运行维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md) | 实际版本、阶段提示、续期记录、代理备份与清理边界 |
| [v1.4.3 维护增强](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-IMPROVEMENTS.md) | 旧版基线目录、实例快照、就绪观察、命名预览、本地记录及正式发布核验 |
| [HTTPS 验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/DOMAIN-HTTPS-ACCEPTANCE.md) | 各次实机检查与尚未完成的验收 |
| [VPS 一键脚本](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md) | 单行入口、正式稳定 payload、配置保留与未验收范围 |
| [v1.3.0 升级验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md) | CloudDrive2 人工迁移的实际检查、用户确认及未执行项；不扩大为 OpenList 或全部自动升级验证 |
| [v1.4.1 ARM64 首装验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md) | 用户提供的Ubuntu26.04.1公网NAT／CloudDrive2首装、本机HTTPS与WebDAV结果；APT错误、未覆盖项及脱敏边界 |
| [v1.4.2 人工升级验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md) | 原 v1.3.4 提交核验、备份、正式核心升级、数据保留、只读 WebDAV 与外部 HTTPS；旧 Release 缺失限制和未执行范围 |
| [内网安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/LAN-INSTALL.md) | 独立内网入口、固定端口、用户提供验收与未验收范围 |
| [独立卸载](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md) | 主分支完整清理与保留模式、归属/外部引用保护及部分失败；原 Tag 行为另行区分 |
| [CHANGELOG](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md) | TG2Cloud 更新与上游历史边界 |
| [产品定义](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/src/tg2cloud/deployment/profiles.py) | 当前工作树两版默认路径、容器、端口及 FUSE 要求 |
| [迁移说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/MIGRATION_FROM_TG115.md) | TG115 到 TG2Cloud 的操作与未验证范围 |
| [安全政策](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/SECURITY.md) | 凭据保护与第三方边界 |
| [贡献指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/CONTRIBUTING.md) | 测试和构建入口 |

本网站区分当前工作树和正式发布行为。Linux 唯一版本源为 `src/tg2cloud/version.py`，源码与正式版本均为 1.4.9。发布 helper 必须先验证辅助 A、再由入口 B 固定 A，不以 moving main 替代；业务代码仍只取正式稳定 Release。历史验收按原版本和日期理解。

## 文档与软件版本分别维护

`site.config.json` 的 `version` 表示网站讲解的软件源码版本；`publishedVersion` 表示实际可下载的正式版本，`releaseStatus` 区分 `unreleased` 与 `released`。`package.json` 和 lockfile 的文档包版本本轮统一为 1.4.8；依赖和历史版本不机械替换。

导航“最新 Release”只是跳转到 GitHub，不代表站内内容自动跟随最新。未发布的源码更新可以先更新文档版本，但必须说明待发布，并保留真实下载链接。正式发布完成后再同步下载链接、`publishedVersion`、状态、更新日志和教程。

## Markdown 内容在哪里

文章位于 `docs/`。导航分类、文章标题与路径位于 `site.config.json`。新增文章后，把它加入相应导航，再执行构建与校验。

本静态引擎支持标题、段落、单层有序/无序列表、表格、代码块、链接、粗体、图片与提示块。不执行 Markdown 中的任意 HTML 或脚本；不是 VitePress/Vue 插件运行环境。

## 本地查看与构建

文档站只需要 Node.js 22 或更高版本，没有第三方 npm 依赖。

```bash
npm run build
npm test
npm run preview
```

浏览器打开命令输出的本地地址，不要双击 `dist/index.html`；本地搜索和根路径资源需要 HTTP 服务。

开发时可使用 `npm run dev`，它会监测内容变化并重新构建；刷新浏览器查看修改。

## Cloudflare Pages 配置

当前网站源码位于 TG2Cloud 仓库的 `website/`，Pages 根目录应设为 `website`；构建命令 `npm run build`，输出目录 `dist`，Node 版本 `22`。部署成独立文档仓库时才将根目录留空。

每个文章都生成独立 HTML，不需要 SPA 全站回退。正式地址已确认是 `https://tg2cloud.pages.dev/`，配置据此生成 canonical、站点地图及 robots 入口。自行部署副本时必须改成自己的 `SITE_URL`；未知域名不猜测。

## 图片与隐私

页面不依赖外部字体、CDN 图片或第三方统计。首页为流程示意，而非部署器截图；没有用占位截图冒充实际运行结果。

后续补充界面截图时，把真实脱敏图片放入 `public/images/`，在 Markdown 中引用，并标注 Edition 与版本。不要提交真实 Token、IP、密码、二维码或私人文件名。
