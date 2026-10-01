<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.1.1** 是 HTTPS 事务与 OpenList 稳定性补丁。两个 PySide6 Windows EXE 均由 GitHub Actions 从同一不可变标签构建，校验值来自本次 Actions 的实际产物。

## 本次更新

- 共享 HTTPS 配置与移除增加 VPS 级事务锁；竞争操作明确停止，锁丢失后拒绝后续远程命令。
- 域名状态通过同目录原子替换提交；提交后的临时清理失败不再误触发旧状态回退。
- 移除一个 Edition 后同步 Certbot 活动域名，并检查保留 Edition；失败时恢复旧路由和续期配置。
- OpenList 父目录检查使用完整清单，避免超过 10,000 项时漏判已有同名文件。
- OpenList 只读健康探测区分 401/429、限制重试并合并刷新；401 冷却 5 分钟，429 从 60 秒逐步退避至最多 15 分钟。显式 WebDAV 写入验收不使用此缓存。
- Release 增加同标签 Linux 验证门禁，继续复用 Windows Build Job 已生成并自检的 artifact，不重复构建。
- 文档明确本机 HTTPS 自检与公网验收的区别，并补充共享代理独立备份边界。

## 验证范围

- 双管理网关 HTTPS 共存已在 Debian 13 测试 VPS 检查：两 Edition 各 11 项运行检查通过，外部 HTTP 308、严格 TLS 的 HTTPS 200、公开 `/dav` 与 `/dav/` 各 403。
- 两个真实 SSH 通道验证事务锁互斥及断锁自动释放；原 CloudDrive2 域名、容器启动/重启记录和已核对配置保持不变。
- 本地完整 pytest：338 passed、10 skipped、70 subtests passed。定向回归：95 passed、5 skipped、13 subtests passed。缺少 Linux/集成条件的本地跳过项不计为通过，标签发布由 Actions 另行执行 Linux 验证。
- v1.1.0 两版基础部署、强制 HTTPS 与 WebDAV 验收继续作为历史基线；本轮没有启动新的 OpenList Bot，也没有重新实测 OpenList WebDAV、401/429 恢复、路由移除/失败回退、长期续期及备份恢复。网关通过不等同于转存全链路重新验收。

## 下载与校验

| Edition | Release 文件 |
| --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` |
| SHA-256 校验 | `SHA256SUMS.txt` |

只发布以上三个文件。源码仓库不包含本地 EXE、`build/` 或 `dist/`；Release 校验值不要求与此前本机构建一致。

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

## 升级与安全边界

先备份再使用对应 Edition 的新版部署器升级；仅下载 EXE 不会自动更新 VPS Bot。既有完整安装默认保留当前 `.env` 与持久化数据，只有明确选择应用本页配置才覆盖。

CloudDrive2 上传/改名命令及健康探测策略保持不变，Telegram 下载、SQLite 队列、streaming 和部署脚本未重写。CloudDrive2/OpenList 管理后端继续只监听回环地址，公网只开放共享 Nginx 的 80/443，域名入口不代理 WebDAV。

两个 Edition 的备份不包含 `/opt/tg2cloud-proxy`；域名状态、代理配置和完整 Let's Encrypt 目录需独立私密备份。没有正式自动 Restore/Uninstall，Windows EXE 未商业代码签名；不要关闭 Defender 或跳过证书校验。

完整说明见 [README](README.md)、[从 TG115 迁移](docs/MIGRATION_FROM_TG115.md) 和 [HTTPS 回归清单](docs/development/DOMAIN-HTTPS-ACCEPTANCE.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、原作者版权及必要致谢。
