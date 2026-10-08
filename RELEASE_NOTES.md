<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.1.2** 是运行状态、故障提示与 HTTPS 维护更新。两个 PySide6 Windows EXE 由 GitHub Actions 从同一不可变标签测试、构建和自检，SHA256 来自本次 Actions 实际产物；Release 复用 Windows Build Job 的包，不上传本机 EXE、不重复构建。

## 本次更新

- 查看运行状态分别显示部署器版本与 VPS Bot 实际版本；未知版本不冒充最新版，不自动升级或降级。
- 复用现有进度、运行日志和错误弹窗，显示实际部署/HTTPS 阶段及核对建议，不虚构百分比或根因。
- HTTPS 维护菜单新增共享代理私密备份、完整性检查、隔离解包及当前域名续期 dry-run；不提供在线覆盖恢复。
- 历史备份可按时间、大小和校验结果选择；旧备份清理须先预览再确认，默认取消、至少保留一份，清单变化或校验失败拒绝执行。
- 续期记录区分检查成功与证书实际变更。续期失败、已有记录超过 26 小时未更新或证书临近到期时显示黄色警告；当前 HTTPS 自检通过时仍保持入口可用。
- 一次性续期与备份操作增加远端执行时限和精确清理；SSH/Docker 不可达时明确提示清理尚未确认，不停止共享代理或 Bot。
- OpenList `/doctor` 显示真实探测时间、401/429 分类和剩余冷却；既有退避与转存逻辑不变。
- 统一部署器/Bot 版本源及 Windows 资源校验；修复 PyInstaller 备份助手相对路径问题，增加备份对话框打包自检。
- Release 校验 Tag、源码、Windows 资源和发布文档一致性；同标签 Windows/Linux 成功后发布同一次构建的 artifact，拒绝替换已有 Release。

## 验证范围

- 本地完整 pytest：367 passed、11 skipped、93 subtests passed；unittest：378 tests，OK（11 skipped）。Ruff、Bandit、compileall、Bash 语法及 diff 检查通过；本地缺少的 Linux/Docker/rclone 集成由 GitHub Actions 再行验证，不将跳过项计为通过。
- 本地两 Edition 测试 EXE 构建/自检通过，100%/125%/150% 中文离屏预览及 125%/150% EXE 隐藏自检通过；不代替真实 Windows 桌面交互验收。
- 专用 Debian 13 VPS：共享代理备份/核验/隔离解包、OpenList 路由移除后恢复、续期 dry-run 与一次性维护容器清理通过；恢复后两 Edition 各 11 项 HTTPS 检查通过。历史备份清理只预览，没有删除真实备份。
- CloudDrive2 的业务配置、容器、域名及受保护文件与实测前一致；稳定下载/上传/流式/恢复核心未重写。
- 真实 Bot/网盘转存、401/429 实际恢复、长期自动续期、完整灾难恢复及独立网络后端端口隔离仍待验收。VPS 本机 HTTPS 自检不等于公网隔离或转存全链路通过。

## 下载与校验

| Edition | Release 文件 |
| --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` |
| SHA-256 校验 | `SHA256SUMS.txt` |

只发布以上三个文件。源码仓库不包含本地 EXE、`build/` 或 `dist/`；本地测试包的 SHA256 不作为本次 Release 校验值。

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

## 升级与安全边界

先备份再使用对应 Edition 的新版部署器升级；仅下载 EXE 不会更新 VPS Bot。既有完整安装默认保留 `.env` 和持久化数据，只有明确选择应用本页配置才覆盖。已有 HTTPS 实例需要通过新版部署器重新配置同一域名，才能更新续期容器及记录能力；不要卸载重装或随意切换正常域名。

CloudDrive2 上传/改名与健康探测策略保持不变。两个管理后端仍只监听回环地址，共享 Nginx 提供公网 80/443，公开 `/dav` 被拒绝；域名入口不代理 WebDAV 转存。没有遥测、账号系统或开发者侧凭据收集。

共享代理备份包含证书私钥和 ACME 账户数据，只存 VPS 私密目录，不要上传 GitHub、公开网盘或工单；备份清理不可撤销，不提供在线覆盖 Restore。Let's Encrypt 已停止到期提醒邮件，填写邮箱不能代替续期监测。Windows EXE 未商业代码签名；不要关闭 Defender 或跳过 TLS 校验。

完整说明见 [README](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.2/README.md)、[运行维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.2/docs/OPERATIONS.md) 和 [HTTPS 验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.2/docs/development/DOMAIN-HTTPS-ACCEPTANCE.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。
