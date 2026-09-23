# 文档来源与维护

本次内容核对日期为 **2026 年 9 月 23 日**，对应 TG2Cloud **v1.0.3**。网站不会通过后台自动证明新的软件版本已经发布或测试完成。

## 主要来源

| 来源 | 用于核对 |
| --- | --- |
| [项目 README](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/README.md) | 部署、命令、路径、状态、常见问题 |
| [v1.0.3 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.0.3) | 当前发布行为、资产名称和已知限制 |
| [CHANGELOG](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md) | TG2Cloud 更新与上游历史边界 |
| [产品定义](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/deployer_products.py) | 两版默认路径、容器、端口及 FUSE 要求 |
| [迁移说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/MIGRATION_FROM_TG115.md) | TG115 到 TG2Cloud 的操作与未验证范围 |
| [安全政策](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/SECURITY.md) | 凭据保护与第三方边界 |
| [贡献指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CONTRIBUTING.md) | 测试和构建入口 |

README 中部分日常状态文字沿用 CloudDrive2 描述时，本网站以 v1.0.3 Release 和产品定义区分两个后端，不把旧段落机械套到 OpenList。

## 文档与软件版本分别维护

`site.config.json` 的 `version` 表示网站当前讲解的软件版本；`package.json` 的版本表示文档站源码包自身版本，二者不必相同。

导航“最新 Release”只是跳转到 GitHub，不代表站内内容自动跟随最新。发布新软件后，应同时审核下载链接、更新日志和教程，再修改网站版本号。

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
