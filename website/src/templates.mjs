import {escapeHtml as e, slugify} from '../scripts/markdown.mjs';
import {icon} from './icons.mjs';

const link = (slug) => `/${slug}/`;
const ext = 'target="_blank" rel="noopener noreferrer"';
const brandIcon = '<img class="brand-mark" src="/assets/tg2cloud-icon-64.png" width="64" height="64" alt="">';
export function renderPage({config:c, page, body='', headings=[], previous, next, home=false, notFound=false, hashes}) {
  const fullTitle = home ? 'TG2Cloud · 从 Telegram，到你的云存储' : `${page.title} | TG2Cloud Docs`;
  const slug = page.slug || '';
  const description = page.description || c.description;
  const url = c.siteUrl ? c.siteUrl.replace(/\/$/,'') + (home ? '/' : notFound ? '/404.html' : link(slug)) : '';
  const section = c.navigation.find(g=>g.items.some(p=>p.slug===slug))?.title || '文档';
  const navLinks = `<a href="/guide/introduction/" ${slug.startsWith('guide/')?'class="active"':''}>指南</a><a href="/guide/quick-start/">从零部署</a><a href="/faq/" ${slug==='faq'?'class="active"':''}>常见问题</a><a href="/changelog/" ${slug==='changelog'?'class="active"':''}>更新日志</a>`;
  const brand=`<a href="/" class="brand" aria-label="TG2Cloud 文档首页"><span class="brand-icon">${brandIcon}</span><span>TG2Cloud</span><span class="brand-divider"></span><span class="brand-docs">Docs</span></a>`;
  const sidebar = c.navigation.map(g=>`<div class="sidebar-group"><p class="sidebar-label">${e(g.title)}</p>${g.items.map(p=>`<a href="${link(p.slug)}" ${p.slug===slug?'class="current" aria-current="page"':''}>${e(p.title)}</a>`).join('')}</div>`).join('');
  const versionMenu = `<details class="version-menu"><summary aria-label="版本与发布记录">v${e(c.version)} ${icon('down')}</summary><div class="version-popover"><span class="menu-caption">本文档对应版本</span><a href="/changelog/#${slugify('TG2Cloud v'+c.version)}">v${e(c.version)} <span class="badge">当前</span></a><a href="${c.repo}/releases/latest" ${ext}>GitHub 最新 Release ↗</a><div class="menu-line"></div><span class="menu-caption">历史更新记录 · 非文档快照</span><a href="/changelog/#${slugify('TG2Cloud v1.0.1')}">v1.0.1 更新记录</a><a href="/changelog/#${slugify('TG2Cloud v1.0.0')}">v1.0.0 更新记录</a><a href="${c.repo}/releases" ${ext}>全部 Releases ↗</a></div></details>`;
  const sourcePath= slug==='changelog' ? 'CHANGELOG.md' : slug==='operations/migration'?'docs/MIGRATION_FROM_TG115.md':slug==='reference/config'?'deployer_products.py':slug==='reference/security'?'SECURITY.md':slug==='reference/development'?'CONTRIBUTING.md':'README.md';
  const toc = headings.filter(h=>h.level===2 || h.level===3).map(h=>`<a class="toc-h${h.level}" href="#${encodeURIComponent(h.id)}">${e(h.title)}</a>`).join('');
  let main = '';
  if (home) main = homeContent(c);
  else if (notFound) main=`<main id="main-content" class="not-found"><span class="eyebrow">404 · PAGE NOT FOUND</span><h1>这条路径暂时没有文档</h1><p>链接可能已变更。回到首页，或用搜索找到你需要的内容。</p><a class="button primary" href="/">返回文档首页 ${icon('arrow')}</a></main>`;
  else main=`<div class="docs-shell"><aside class="sidebar" aria-label="文档导航"><a class="sidebar-overview" href="/">${icon('book')} 文档中心</a>${sidebar}<div class="sidebar-bottom"><span class="dot"></span> v${e(c.version)} 文档<br><small>核对于 ${e(c.verifiedAt)}</small></div></aside><main id="main-content" class="article-main"><div class="breadcrumbs"><a href="/">文档</a><span>/</span><span>${e(section)}</span></div><article class="prose">${body}</article><div class="article-meta"><span>内容核对：${e(c.verifiedAt)} · v${e(c.version)}</span><a href="${c.repo}/blob/main/${sourcePath}" ${ext}>核对项目原文 ↗</a></div><nav class="page-navigation" aria-label="前后篇">${previous ? `<a class="previous" href="${link(previous.slug)}"><span>上一篇</span><strong>← ${e(previous.title)}</strong></a>`:'<span></span>'}${next ? `<a class="next" href="${link(next.slug)}"><span>下一篇</span><strong>${e(next.title)} →</strong></a>`:'<span></span>'}</nav><div class="feedback-note">发现文档与实际行为不同？<a href="${c.repo}/issues" ${ext}>反馈前先脱敏 ↗</a></div></main><aside class="toc" aria-label="本页目录"><p>本页目录</p><nav>${toc}</nav><a class="toc-help" href="/faq/">${icon('info')} 遇到问题？查看 FAQ</a></aside></div>`;
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${e(fullTitle)}</title><meta name="description" content="${e(description)}">
<meta name="theme-color" content="#f8faff"><meta name="color-scheme" content="light dark">
<meta property="og:type" content="website"><meta property="og:title" content="${e(fullTitle)}"><meta property="og:description" content="${e(description)}">
${url?`<link rel="canonical" href="${e(url)}"><meta property="og:url" content="${e(url)}">`:''}
${notFound?'<meta name="robots" content="noindex">':''}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/assets/tg2cloud-icon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/tg2cloud-icon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/tg2cloud-icon-256.png">
<script src="/assets/theme-init.js?v=${hashes.init}"></script>
<link rel="stylesheet" href="/assets/style.css?v=${hashes.css}">
<script defer src="/assets/app.js?v=${hashes.js}"></script>
</head>
<body class="${home?'home-page':notFound?'error-page':'doc-page'}">
<a class="skip-link" href="#main-content">跳转到主要内容</a>
<header class="site-header"><div class="header-inner">${brand}<nav class="top-nav" aria-label="主导航">${navLinks}</nav><div class="header-tools">
${versionMenu}
<button class="search-button" type="button" data-open-search aria-label="搜索文档">${icon('search')}<span>搜索文档</span><kbd>Ctrl K</kbd></button>
<button type="button" class="icon-button theme-toggle" aria-label="切换深色主题" title="切换深浅色主题">${icon('sun','sun-icon')}${icon('moon','moon-icon')}</button>
<a class="icon-button github-link" href="${c.repo}" ${ext} aria-label="访问 TG2Cloud GitHub">${icon('github')}</a>
<button class="icon-button mobile-nav-toggle" type="button" aria-label="打开导航菜单" aria-haspopup="dialog">${icon('menu')}</button>
</div></div></header>
${!home&&!notFound?`<div class="mobile-doc-toolbar"><button class="mobile-nav-toggle" type="button">${icon('menu')} 文档导航</button><a href="#main-content">正文 ↑</a></div>`:''}
${main}
<footer class="site-footer ${home?'':'compact'}"><div class="footer-inner"><div><strong>TG2Cloud</strong><span> From Telegram to Your Cloud.</span></div><div><a href="/reference/credits/">来源与致谢</a><a href="/reference/security/">安全与隐私</a><a href="${c.repo}" ${ext}>GitHub ↗</a></div></div><p>基于 whyhhh20/TG115 演进 · MIT License · 与 Telegram、CloudDrive2、OpenList 及云存储运营方无官方隶属关系。</p></footer>
<dialog id="search-dialog" aria-labelledby="search-label"><div class="search-head">${icon('search')}<label class="sr-only" id="search-label" for="search-input">搜索 TG2Cloud 文档</label><input id="search-input" type="search" placeholder="搜索部署、WebDAV、401、备份…" autocomplete="off" spellcheck="false"><button class="icon-button" type="button" data-close-search aria-label="关闭搜索">${icon('close')}</button></div><p class="search-status" aria-live="polite"></p><div id="search-results" role="list"></div><div class="search-foot"><span>本地全文搜索 · 不上传搜索内容</span><span><kbd>↑</kbd><kbd>↓</kbd> 选择 <kbd>Enter</kbd> 打开 <kbd>Esc</kbd> 关闭</span></div></dialog>
<dialog id="mobile-nav-dialog" aria-label="站点导航"><div class="mobile-menu-head">${brand}<button class="icon-button" type="button" data-close-nav aria-label="关闭导航">${icon('close')}</button></div><nav class="mobile-primary">${navLinks}<a href="/download/">部署器下载</a></nav><nav class="mobile-sidebar">${sidebar}</nav></dialog>
<button class="back-to-top" type="button" aria-label="回到顶部" hidden>↑</button>
<div id="toast" role="status" aria-live="polite"></div>
</body></html>`;
}

function homeContent(c) {
  const features=[
    ['monitor','Windows 图形化部署','测试 SSH、探测资源、安装基础环境，在部署器内完成配置与验收。','/guide/quick-start/'],
    ['queue','持久队列，重启可恢复','SQLite 保存任务状态，提供去重、失败保留与有边界的恢复机制。','/usage/status/'],
    ['stream','大文件也有另一条路径','超过本地任务预算时走流式管道，不必先保留完整本地文件。','/usage/streaming/'],
    ['server','资源预算，更稳妥地运行','检查 CPU、内存、磁盘与 inode；按 VPS 实况选择合适预算。','/deploy/resources/'],
    ['shield','私人 Bot，明确的权限','只接受配置用户的私聊；管理面板通过 SSH 隧道访问。','/reference/security/'],
    ['check','分阶段验收，不模糊完成','区分网关接收、大小检查与云盘最终状态，让每一步可核对。','/deploy/verification/']
  ];
  return `<main id="main-content">
<section class="hero-section"><div class="hero-wrap"><div class="hero-copy">
<a class="release-pill" href="/changelog/"><span class="dot"></span> v${e(c.version)} 文档 <span class="pill-divider"></span> 双 Edition ${icon('arrow')}</a>
<h1><span class="hero-brand">TG2Cloud</span><span>从 Telegram，</span><span>到你的云存储。</span></h1>
<p class="hero-description">转发给自己的 Bot，剩下的交给 VPS。<br>通过 CloudDrive2 或 OpenList，把文件有序存入<br class="desktop-break">你自己挂载的云端。</p>
<div class="hero-actions"><a class="button primary" href="/guide/quick-start/">从零开始部署 ${icon('arrow')}</a><a class="button secondary" href="/download/">${icon('download')} 部署器下载</a></div>
<div class="hero-tags"><span>${icon('code')} 开源自托管</span><span>${icon('shield')} 私人 Bot</span><span>${icon('cloudsmall')} 多云目标</span></div>
</div><div class="hero-visual">
<div class="route-card"><div class="route-header"><span class="route-title"><span class="mini-brand">${brandIcon}</span> 你的文件，你的路径</span><span class="route-label">工作原理</span></div>
<div class="route-source"><span class="route-source-icon">${icon('telegram')}</span><div><strong>Telegram</strong><span>转发到自己的私人 Bot</span></div><span class="small-tag">手动选择</span></div>
<div class="route-connector"><span></span><small>文件与任务</small></div>
<div class="route-core"><div class="core-top"><span>${icon('server')} TG2Cloud <small>on VPS</small></span><span class="core-chip">自动处理</span></div><div class="core-steps"><span>持久排队</span><b>→</b><span>下载 / 流式</span><b>→</b><span>大小校验</span></div></div>
<div class="route-split"><span></span><span></span></div>
<div class="gateway-pair"><a href="/deploy/clouddrive2/" class="gateway">${icon('cloudsmall')}<strong>CloudDrive2</strong><span>WebDAV 网关</span></a><a href="/deploy/openlist/" class="gateway">${icon('folder')}<strong>OpenList</strong><span>WebDAV 网关</span></a></div>
<div class="route-merge"><span></span><span></span></div>
<div class="route-destination">${icon('cloud')}<div><strong>Your Cloud</strong><span>你自行挂载、授权的云存储</span></div><span class="destination-tag">不止 115</span></div>
<div class="route-foot">${icon('info')} 网关接收成功，不等于云盘官方最终完成。</div>
</div><div class="hero-visual-caption"><span class="caption-line"></span> FROM TELEGRAM TO YOUR CLOUD <span class="caption-line"></span></div>
</div></div></section>
<section class="edition-section home-container"><div class="section-heading"><div><span class="eyebrow">ONE CORE. TWO EDITIONS.</span><h2>选你熟悉的网关，开始转存。</h2></div><a class="text-link" href="/guide/editions/">查看版本差异 ${icon('arrow')}</a></div>
<div class="edition-grid"><a href="/deploy/clouddrive2/" class="edition-card"><div class="edition-icon cd2">${icon('cloudsmall')}</div><div class="edition-copy"><span class="eyebrow">CLOUDDRIVE2 EDITION</span><h3>CloudDrive2 部署指南</h3><p>使用 CloudDrive2 挂载云存储，通过专用 WebDAV 用户写入文件。</p><div class="edition-meta"><span>固定隧道 :19798</span><span>受管部署需要 FUSE</span></div></div><span class="round-arrow">${icon('arrow')}</span></a>
<a href="/deploy/openlist/" class="edition-card"><div class="edition-icon openlist">${icon('folder')}</div><div class="edition-copy"><span class="eyebrow">OPENLIST EDITION</span><h3>OpenList 部署指南</h3><p>在自己的 OpenList 后台挂载存储，配置目标目录与写入权限。</p><div class="edition-meta"><span>固定隧道 :5244</span><span>直接写入最终路径</span></div></div><span class="round-arrow">${icon('arrow')}</span></a></div></section>
<section class="features-section home-container"><div class="section-heading"><div><span class="eyebrow">BUILT FOR YOUR WORKFLOW</span><h2>不只传过去，也把过程管起来。</h2></div><p class="section-side-note">部署、传输、验收、运维<br>一份文档，按步骤找到答案。</p></div><div class="feature-grid">${features.map(([i,title,desc,href])=>`<a class="feature-card" href="${href}"><span class="feature-icon">${icon(i)}</span><h3>${title}</h3><p>${desc}</p><span class="feature-link">阅读文档 ${icon('arrow')}</span></a>`).join('')}</div></section>
<section class="reading-section home-container"><div class="reading-copy"><span class="eyebrow">START HERE</span><h2>第一次使用？<br>沿这条路线就好。</h2><p>不必一次读完整站。先让一个小文件<br>安全到达，再逐步扩大使用规模。</p><a class="text-link" href="/guide/quick-start/">查看完整部署教程 ${icon('arrow')}</a></div><div class="reading-steps">${[['01','准备环境与凭据','确认 VPS、Telegram 与云存储目标。','/guide/prerequisites/'],['02','下载并部署对应 Edition','校验 EXE，连接 SSH，完成基础安装。','/download/'],['03','配置 WebDAV，完成验收','按步骤确认真实写入、检查与清理。','/deploy/verification/'],['04','发送第一个小文件','观察任务，在云盘客户端核对结果。','/usage/first-transfer/']].map(([n,t,d,h])=>`<a href="${h}" class="reading-step"><span>${n}</span><div><h3>${t}</h3><p>${d}</p></div>${icon('arrow')}</a>`).join('')}</div></section>
<section class="release-section home-container"><div class="release-banner"><div><span class="eyebrow">DOCUMENTED RELEASE</span><h2>从 v${e(c.version)} 开始，选好你的 Edition。</h2><p>下载对应部署器与 SHA256SUMS.txt，先校验，再运行。</p></div><div><a class="button primary" href="/download/">${icon('download')} 查看下载与校验</a><a class="release-secondary" href="${c.repo}/releases/latest" ${ext}>前往 GitHub 最新 Release ↗</a></div></div><div class="home-notice">${icon('info')}<p><strong>使用前请注意：</strong>当前不自动监听频道，不批量抓取历史。只转存你有权保存的内容。项目基于 <a href="${c.upstreamRepo}" ${ext}>whyhhh20/TG115</a> 演进；115 是示例，不是唯一目标网盘。</p></div></section>
</main>`;
}
