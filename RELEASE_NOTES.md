<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.0.3** 同时提供 CloudDrive2 与 OpenList 两个 PySide6 Windows 部署器。两个 EXE 均由 GitHub Actions 从同一个不可变标签统一测试、构建和自检，并按 Actions 本次实际产物生成 SHA256。

## 本次更新

- 新增可选的 Dockerized Domain HTTPS Gateway，可通过自有域名和 Let's Encrypt HTTPS 打开 CloudDrive2 或 OpenList 管理界面；原有固定 SSH 安全隧道继续保留。
- 两个 Edition 共用 VPS 上的一套固定版本 Nginx/Certbot，分别使用独立域名；Bot 与 rclone 继续使用 Docker 内网 WebDAV，不经过公网域名。
- 域名入口固定拒绝公网 `/dav` 与 `/dav/`，后端仍只监听回环地址；未知 Host/SNI 被拒绝，不向代理容器挂载 Docker Socket。
- 增加域名格式、A/AAAA、80/443 端口归属、证书、Nginx 配置、HTTPS、HTTP 跳转、`/dav` 阻断和回环监听自检。Cloudflare 首次签发应使用“仅 DNS”，不需要提供 API Token。
- 配置采用事务式提交：首次签发失败会清理临时状态，更新失败保留旧路由，为第二个 Edition 配置失败不会破坏第一个 Edition；移除最后一个路由后共享代理停止，证书文件默认保留。
- 修复已有证书复用、损坏证书重试、最后路由移除后的 Certbot 状态、续期域名筛选、状态脚本初始化与 Bash 端口条件表达式；状态请求固定解析到本机回环地址，避免 VPS 不支持公网 NAT 回环时误报失败。
- 域名状态结果改为固定高度、可滚动和可复制的小型日志框，长检查结果不再撑高对话框。

## 真实环境验证

- 共享域名 HTTPS 功能已在 Debian 13 真实 VPS 上完成验收，适用于 CloudDrive2 与 OpenList：DNS A 直连、已有证书复用、HTTPS 管理页、HTTP 跳转、Nginx/Certbot 健康、当前域名续期配置、公开 `/dav` 阻断、后端回环监听以及证书域名与有效期检查均通过。
- CloudDrive2 v1.0.1 与 OpenList v1.0.2 已完成的真实 VPS 基础部署及 WebDAV 验收继续作为回归基线。
- Telegram 与不同文件规模仍应由用户在自己的环境继续验证。

## 项目定位

TG2Cloud 是一个将 Telegram 私聊中提交的文件自动转存到用户自有云存储的自托管工具：

```text
Telegram → Private Bot → TG2Cloud → rclone
         → CloudDrive2 / OpenList WebDAV → 用户挂载的云存储
```

115 是常用示例和主要测试场景之一，不是唯一目标网盘。最终可用的存储取决于用户本人在 CloudDrive2 或 OpenList 中实际挂载和授权的云存储。

## 下载选择

- `TG2Cloud-CloudDrive2-Deployer.exe`：部署 TG2Cloud Bot 和 CloudDrive2 Edition。
- `TG2Cloud-OpenList-Deployer.exe`：部署 TG2Cloud Bot 和 OpenList Edition。
- `SHA256SUMS.txt`：本次 GitHub Actions 实际生成的两个正式 EXE 的 SHA-256 校验值。

两个部署器都使用 PySide6 和同一套 TG2Cloud 品牌资源。正式发布不包含 Tkinter、Classic、TG115、debug 或 test EXE。

## 主要能力

- 私人 Telegram Bot、Allowed User 限制、SQLite 持久队列和重启恢复；
- rclone WebDAV 上传、目的端大小校验、按后端安全落盘和失败清理；
- 超过本地任务预算时沿用现有流式传输策略；
- 默认 `LOCAL_TEMP_BUDGET_GB=20`、`MIN_FREE_DISK_GB=8`，也允许用户显式调整；
- CloudDrive2 固定 `127.0.0.1:19798`、OpenList 固定 `127.0.0.1:5244` SSH Tunnel；
- 可选域名 HTTPS 管理入口，以及 WebDAV auth/list/upload/size/rename/recheck/delete/cleanup 分阶段验收；
- Existing TG2Cloud 重复部署默认在 VPS 内保留完整 `.env`、SQLite、`rclone.conf` 和 Storage Gateway 持久化数据；只有用户明确勾选后才使用当前表单覆盖配置；
- CloudDrive2 网络 Repair、两版 Update/Status、OpenList 脱敏日志和一致性手动备份；
- 正式机器输出使用 `TG2CLOUD_*`，仅为旧脚本保留必要 `TG115_*` 读取兼容。

## 首次安装建议

1. 从本仓库的正式 Release 下载所需 Edition，并核对 `SHA256SUMS.txt`。
2. 准备本人控制的 Ubuntu/Debian VPS、私人 Telegram Bot 和 CloudDrive2/OpenList WebDAV 配置；不要把任何凭据提交到 Issue、聊天记录或截图。
3. 先在部署器中测试 SSH 和应用合适的 VPS 存储建议，再执行“一键部署基础环境”。
4. 通过固定 SSH Tunnel 打开 Storage Gateway，由本人登录并挂载测试云存储。
5. 执行 WebDAV 验收，确认出现 `TG2CLOUD_DESTINATION=OK` 后再发送 Telegram 测试文件。
6. 如需公网管理入口，再为当前 Edition 配置独立域名 HTTPS；该域名不能作为 Bot WebDAV 地址。
7. 最后在所用云存储的官方客户端确认文件大小和可打开性。

完整安装与验证步骤见 [README](README.md)，域名功能说明见 [域名访问与 HTTPS](website/docs/deploy/domain-https.md)。

## 旧 TG115 用户

TG2Cloud v1.0.3 不提供 TG115 原地自动升级。新安装使用独立目录、容器和 Network；旧目录、容器和备份不会被自动覆盖、停止、迁移或删除。若旧实例占用固定 19798/5244 端口，TG2Cloud 会停止并要求用户自行处理，不会自动换端口。详见 [从 TG115 迁移](docs/MIGRATION_FROM_TG115.md)。

不要让新旧实例长期同时使用同一个 Telegram Bot Token，否则可能争抢 Telegram updates。

## 隐私与安全

- 无遥测、无埋点、无第三方统计、无开发者侧凭据收集；
- SSH、Telegram、WebDAV、OpenList 和证书签发敏感字段不会写入普通日志，诊断日志会脱敏；
- 完整 `.env`、`rclone.conf`、SSH 私钥、Cookie、OAuth/云存储 Token 和证书私钥不进入公开诊断；
- CloudDrive2/OpenList 管理端默认只绑定 VPS 回环地址；可通过 SSH Tunnel 或可选 HTTPS 管理入口访问；
- 公网 HTTPS 域名不代理 WebDAV，用户的云存储登录、Cookie、Token 和 OAuth 授权只交给用户自己的 CloudDrive2/OpenList。

## Known Limitations

- 本版本没有正式自动 Restore 或 Uninstall；
- CloudDrive2 没有手动 Backup UI，只有重复部署前自动保护和备份盘点/显式 retention；
- 同 Bot Token 多实例冲突由用户避免，没有分布式锁或跨系统 Token 扫描；
- TG115 不会自动原地迁移到 TG2Cloud；
- Windows EXE 未使用商业代码签名，SmartScreen 可能显示“未知发布者”；
- 不同云存储、VPS 和网络组合仍以用户实际验收为准。

## 发布状态

当前版本为 **v1.0.3**。自动测试、两个 Windows EXE 构建、自检和 SHA256 生成均由 GitHub Actions 从 `v1.0.3` 标签执行；Release Job 直接发布 Windows Build Job 已验证的同一份 artifact，不重复构建。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进而来，继续保留 MIT 许可证、原作者版权和必要致谢。
