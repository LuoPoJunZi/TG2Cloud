# 文档来源与维护

本次内容核对日期为 **2026 年 10 月 20 日**，对应 TG2Cloud **v1.4.0**（待发布）。本轮准备原生 AMD64 / ARM64 兼容，镜像索引和 wheel 元数据已核验，本地回归已执行；原生双架构 CI、helper A／固定入口 B 和同标签发布仍按实际结果更新。现有正式下载保留 v1.3.4；Oracle／真实 VPS、Telegram、网盘、ACME 和手机验收由用户发布后执行。

## 主要来源

| 来源 | 用于核对 |
| --- | --- |
| [项目 README](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/README.md) | 部署、命令、路径、状态、常见问题 |
| [已发布 v1.3.4 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.3.4) | 同标签源码包与实际 SHA256；说明正文、污染原名、图片与媒体组命名增强 |
| [已发布 v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) | 同一次 Actions 构建的实际资产与 SHA256；不是实机验收结论 |
| [运行维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md) | 实际版本、阶段提示、续期记录、代理备份与清理边界 |
| [HTTPS 验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/DOMAIN-HTTPS-ACCEPTANCE.md) | 各次实机检查与尚未完成的验收 |
| [VPS 一键脚本](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md) | 单行入口、正式稳定 payload、配置保留与未验收范围 |
| [v1.3.0 升级验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md) | CloudDrive2 人工迁移的实际检查、用户确认及未执行项；不扩大为 OpenList 或全部自动升级验证 |
| [内网安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/LAN-INSTALL.md) | 独立内网入口、固定端口、用户提供验收与未验收范围 |
| [独立卸载](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md) | 主分支完整清理与保留模式、归属/外部引用保护及部分失败；原 Tag 行为另行区分 |
| [CHANGELOG](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md) | TG2Cloud 更新与上游历史边界 |
| [产品定义](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/src/tg2cloud/deployment/profiles.py) | 当前工作树两版默认路径、容器、端口及 FUSE 要求 |
| [迁移说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/MIGRATION_FROM_TG115.md) | TG115 到 TG2Cloud 的操作与未验证范围 |
| [安全政策](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/SECURITY.md) | 凭据保护与第三方边界 |
| [贡献指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/.github/CONTRIBUTING.md) | 测试和构建入口 |

本网站区分当前工作树和正式发布行为。Linux 版本源为 `src/tg2cloud/version.py`，当前正式版本为 1.3.4；在线 helper 已按先验证辅助 A、后固定入口 B 的流程更新，不用 moving main 替代。业务代码仍只取正式稳定 Release。历史验收按原版本和日期理解，不作为当前全链路通过的承诺。

## 文档与软件版本分别维护

`site.config.json` 的 `version` 表示网站讲解的软件源码版本；`publishedVersion` 表示实际可下载的正式版本，`releaseStatus` 区分 `unreleased` 与 `released`。`package.json` 和 lockfile 的文档包版本本轮统一为 1.4.0；依赖和历史版本不机械替换。

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

本网站采用独立仓库时，根目录保持仓库根，构建命令 `npm run build`，输出目录 `dist`，Node 版本 `22`。

每个文章都生成独立 HTML，不需要 SPA 全站回退。首次部署前尚未确定正式域名时，不写虚构 canonical 地址。确定后设置环境变量 `SITE_URL`，重新构建生成 canonical、站点地图与 robots 的站点地图入口。

## 图片与隐私

页面不依赖外部字体、CDN 图片或第三方统计。首页为流程示意，而非部署器截图；没有用占位截图冒充实际运行结果。

后续补充界面截图时，把真实脱敏图片放入 `public/images/`，在 Markdown 中引用，并标注 Edition 与版本。不要提交真实 Token、IP、密码、二维码或私人文件名。
