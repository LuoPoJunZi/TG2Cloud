# TG2Cloud 文档站部署说明

本说明只部署网页文档，不运行 TG2Cloud Bot 或云盘服务。

## 方案一：GitHub + Cloudflare Pages（推荐长期维护）

### 1. 放置源码

解压 `TG2Cloud-Docs-source.zip`，得到 `TG2Cloud-Docs` 文件夹。

**独立文档仓库：** 在自己的 GitHub 中新建空仓库，例如 `TG2Cloud-Docs`，将解压目录“里面的文件”放在新仓库根目录。确保在仓库根目录能看到 `package.json`、`site.config.json`、`docs/`、`src/`、`public/`、`scripts/`。

**放进 TG2Cloud 原仓库：** 新建 `website/` 目录，把相同文件放进去，不要覆盖主项目已有文件。这时 `package.json` 应位于 `website/package.json`。

源代码包不包含 `dist/`；这是正常情况，构建时会生成。

### 2. 新建 Pages 项目

进入 Cloudflare 的 Workers & Pages，创建 **Pages** 项目，选择连接 Git / GitHub 仓库。不要误建成要求 Worker 入口的普通 Worker 应用。

授权需要的仓库，选择刚才保存文档源码的仓库，填写：

| 项目 | 独立文档仓库 | TG2Cloud 仓库内 website 子目录 |
| --- | --- | --- |
| 生产分支 | 实际分支，例如 `main` | 实际分支，例如 `main` |
| 框架预设 | None | None |
| 根目录 | 留空 | `website` |
| 构建命令 | `npm run build` | `npm run build` |
| 构建输出目录 | `dist` | `dist` |
| 环境变量 | `NODE_VERSION=22` | `NODE_VERSION=22` |

这里使用自定义构建器，所以即使框架预设为 None，仍然需要 `npm run build`，不要照搬纯 HTML 空构建或 VitePress 的 `.vitepress/dist`。

保存并部署。以 Cloudflare 实际分配的 `pages.dev` 地址为准；本次没有注册、预留或保证 `tg2cloud.pages.dev` 可用。

Cloudflare 对构建命令、根目录和输出目录的定义：
https://developers.cloudflare.com/pages/configuration/build-configuration/

### 3. 检查上线结果

打开首页，从侧栏访问 CloudDrive2 / OpenList 页面并刷新，确认深层路径仍可访问。

打开搜索输入 `401`、`SSH`、`备份`，测试主题切换、版本菜单、代码复制与手机导航。GitHub 下载链接指向项目正式 Release，不由文档站托管 EXE。

### 4. 补充真实站点地址

在 Pages 构建环境变量添加：

```text
SITE_URL=https://你的实际域名
```

必须是你的真实地址，只保留协议和域名，不带子路径。重新部署后会增加正确的 canonical 与 sitemap.xml。未设置时不影响访问和搜索，预构建包默认不带推测域名。

### 5. 后续维护

修改 Markdown，执行 `npm run build` 与 `npm test`，提交推送到生产分支；Pages Git 集成负责重新构建部署。

TG2Cloud 主仓库根目录的 `.github/workflows/website-docs.yml` 只做网站构建与链接检查，不是部署工作流。

放在原项目 `website/` 子目录时，该目录里的 `.github/` 不会自动被 GitHub 识别。需要 CI 时，应由维护者在主仓库根 `.github/workflows/` 中合并一份工作流，并将 `run` 步骤的 `working-directory` 与 `setup-node` 的 `cache-dependency-path` 调整为 `website` / `website/package-lock.json`；不要覆盖已有 CI。

## 方案二：直接上传静态包（快速预览）

使用 `TG2Cloud-Docs-Cloudflare-Pages.zip`，不是源码包。

进入 Pages 直接上传 / Drag and drop 流程，填写项目名称，上传该 ZIP 并部署。该 ZIP 根目录直接包含 `index.html`、`404.html`、`assets/` 与文章目录，不需要再套一层目录。

Cloudflare 拖放支持 ZIP 或单个文件夹；Wrangler CLI 不支持直接提交 ZIP，使用 CLI 时要先解压成目录。

**限制：Direct Upload 项目不能以后直接切换为 Git 集成。** 需要 Git 自动部署时要新建对应项目，因此长期维护更推荐方案一。

官方说明：
https://developers.cloudflare.com/pages/get-started/direct-upload/

## Windows 本地预览

在源码目录空白处打开 PowerShell，确认已安装 Node.js 22：

```powershell
node --version
npm ci --ignore-scripts
npm run build
npm test
npm run preview
```

浏览器打开 `http://127.0.0.1:4173`。不要双击 `dist/index.html` 预览，因为站点采用根路径资源和 HTTP 加载搜索索引。

如果 PowerShell 的策略阻止运行 `npm.ps1`，可将命令中的 `npm` 换成 `npm.cmd`，无需关闭系统安全策略。

开发时用 `npm run dev`：文件保存后自动构建，浏览器手动刷新。

## 常见部署问题

**根目录 404：** 检查上传的是静态产物而非源码；ZIP 最外层必须能看到 `index.html`。Git 部署检查输出目录是否为 `dist`，不要填 `docs` 或 `public`。

**Cannot find package.json：** 检查根目录与文件位置；根目录必须指向包含本站 `package.json` 的位置。

**搜索无结果 / JSON 404：** 检查 `/search-index.json` 是否上传；整包更新，不要仅复制首页。未检索到时先减少关键词。

**直接上传后没有自动更新：** Direct Upload 不监听 GitHub。每次修改都要重新构建并上传完整 `dist/`。

**没有 sitemap.xml：** 首次包没有配置真实 `SITE_URL`，这是刻意设计，避免使用虚构域名。

**新版产品发布，网站还是旧版：** 网站版本和正文是经过核对后手动维护，不会自动改写。修改 `site.config.json`、下载页、更新日志与相应教程后再部署。
