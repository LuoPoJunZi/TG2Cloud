# 域名访问与 HTTPS

TG2Cloud 可以为 CloudDrive2 或 OpenList 管理界面配置可选的公网 HTTPS 域名。它不会替代原有 SSH 安全隧道，也不会改变 Bot 与 WebDAV 的传输路径。

v1.0.3 的共享域名 HTTPS 功能已完成验收，适用于 CloudDrive2 与 OpenList 两个 Edition。

## 适用边界

- 域名入口只代理管理界面；
- 公网 `/dav` 与 `/dav/` 固定返回 403；
- CloudDrive2 仍只监听 VPS 的 `127.0.0.1:19798`；
- OpenList 仍只监听 VPS 的 `127.0.0.1:5244`；
- Bot 和 rclone 继续使用 Docker 内网 WebDAV；
- 不配置域名时，固定端口 SSH 隧道照常使用。

两个 Edition 共用 `/opt/tg2cloud-proxy` 中的一套 Nginx 与 Certbot 容器，但必须使用不同域名。Nginx 是唯一监听 80/443 的 TG2Cloud 组件。

## 配置前准备

1. 先完成当前 Edition 的基础部署，并确认 SSH 隧道管理页可打开。
2. 准备一个完整子域名，例如 `cloud.example.com`。
3. 把全部 A/AAAA 记录直接指向当前 VPS。错误 AAAA 会阻止配置。
4. Cloudflare 首次签发证书时使用“仅 DNS”，不需要 API Token。
5. 在服务商安全组和你自行管理的防火墙中开放 TCP 80/443。

部署器不会修改防火墙，也不会停止、覆盖或重配用户已有的 Nginx、Caddy、Apache、Traefik 或其他端口占用进程。

## 在部署器中配置

打开右侧“部署工作台”中的“域名访问 / HTTPS”：

1. 填写纯域名，不要填写 `https://`、端口、路径、通配符或 IP。
2. 可选填写 Let's Encrypt 邮箱；留空时无法接收到期提醒。
3. 点击“检测环境”。
4. 全部检查通过后点击“配置 HTTPS”。
5. 点击“检查状态”，确认 HTTPS、HTTP 跳转、证书、Nginx、自定义 Host、防止公网访问 `/dav` 和后端回环监听均正常。
6. 点击“打开域名管理页”访问 `https://你的域名`。

配置会先启用只服务 ACME challenge 的临时 HTTP 路由，然后签发或复用证书，执行 `nginx -t` 和真实请求自检，最后才写入正式状态。新域名失败时旧域名保持有效；为第二个 Edition 配置失败时，不会删除第一个 Edition 的路由。

## 自动续期

Certbot 容器每 12 小时尝试续期，Nginx 容器每 6 小时安全重载一次证书。两者都不挂载 Docker Socket，不依赖宿主机 cron、systemd、apt 或 snap。

## 更新或移除

在同一对话框填写新域名并配置，可以更新当前 Edition。只有新证书和全部自检通过后才提交。

“移除域名访问”只删除当前 Edition 路由。另一个 Edition 继续工作；移除最后一个路由后共享代理容器停止。证书文件默认保留，避免误删和短时间重复签发。原 SSH 隧道始终保留。

## 常见失败

| 提示 | 处理方式 |
| --- | --- |
| DNS 没有指向当前 VPS | 核对全部 A/AAAA，等待解析生效；Cloudflare 暂用“仅 DNS” |
| 80/443 被外部服务占用 | 自行决定如何处理外部服务；TG2Cloud 不会停止它 |
| 证书签发失败 | 检查 80 入站、DNS、Cloudflare 模式和 Let's Encrypt 频率限制 |
| Nginx 自检失败 | 查看部署器脱敏日志；旧域名状态不会被提交覆盖 |
| HTTPS 可用但 `/dav` 返回 403 | 这是预期安全策略，不要把公网域名填进 WebDAV 配置 |
