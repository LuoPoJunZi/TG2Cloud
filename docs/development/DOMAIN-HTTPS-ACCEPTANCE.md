# Dockerized Domain HTTPS Gateway — Manual Acceptance

本清单只用于真实 VPS 的人工验收。自动测试不得连接真实 Let's Encrypt、真实 DNS 或生产 VPS。测试前准备两个独立子域名，并备份 VPS 上已有配置。

v1.0.3 发布状态：共享域名 HTTPS 功能已完成验收，适用于 CloudDrive2 与 OpenList；以下清单继续作为后续版本回归基线。

## A. CloudDrive2 首次配置

- 基础服务已运行，19798 只监听回环地址；
- 配置第一个域名后 HTTPS 可打开管理页；
- HTTP 自动永久跳转到 HTTPS；
- `/dav` 与 `/dav/` 返回 403；
- 原 `http://127.0.0.1:19798` SSH 隧道仍可使用。

## B. OpenList 首次配置

- 基础服务已运行，5244 只监听回环地址；
- HTTPS 可打开管理页，公网 `/dav` 被阻断；
- 原 `http://127.0.0.1:5244` SSH 隧道仍可使用。

## C. 双 Edition 共存

- 两个域名分别打开正确的管理页；
- VPS 只有一个 `tg2cloud-proxy-nginx` 和一个 `tg2cloud-proxy-certbot`；
- 两个后端端口仍未公开。

## D. DNS 错误

- 错误 A、错误 AAAA、Cloudflare 代理地址均应在签发前明确停止；
- 修正并等待解析后可重试。

## E. 端口冲突

- 让外部服务占用 80 或 443；
- TG2Cloud 明确报告冲突，不停止、不重启、不改写外部服务。

## F. 非法输入

- URL、IP、通配符、Unicode 非 Punycode、路径、端口、空格和 shell 元字符均被本地拒绝；
- 同一域名不能分配给两个 Edition。

## G. 首次签发失败回退

- 模拟 80 入站被阻断或证书签发失败；
- 不提交域名状态；首次配置时安全停止临时代理；核心服务不重启。

## H. 第二 Edition 失败隔离

- 第一个 Edition 保持健康时，让第二个 Edition 签发失败；
- 第一个域名仍可访问，配置与证书未被删除。

## I. 域名更新回退

- 已有域名正常时尝试更新到无法签发的新域名；
- 旧域名继续可用，状态文件仍记录旧域名。

## J. 删除一个 Edition

- 双 Edition 状态下删除一个路由；
- 另一个域名继续可用，共享代理继续运行，证书文件保留。

## K. 删除最后一个 Edition

- 删除最后一条路由后两个共享代理容器停止；
- 核心 CloudDrive2/OpenList/Bot 仍运行；证书目录保留；SSH 隧道仍可用。

## L. 自动续期与重载

- 确认 Certbot 服务保持运行且续期周期为 12 小时；
- 确认 Nginx 周期重载为 6 小时；
- 两个容器均不挂载 Docker Socket，宿主机没有新增 cron/systemd 任务。

## M. 既有安装与传输回归

- 在已有 TG2Cloud 实例上直接配置域名，无需重新部署核心；
- Telegram、SQLite 队列、rclone、streaming、WebDAV 验收、OpenList 429 分类和 CloudDrive2 修复流程保持原结果；
- 域名管理操作不会重建或重启存储网关与 Bot。

人工验收记录必须注明 Edition、DNS 模式、VPS 系统、通过/失败项和已脱敏日志；不得粘贴私钥、Token、密码、Cookie、`.env`、`rclone.conf` 或证书私钥。
