<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.1.5** 修复共享 HTTPS 中断回退、宿主 Python 3.10 维护兼容、VPS 向导续做凭据展示及精简系统依赖提示。两个 PySide6 部署器仍是主力；正式 EXE 由 GitHub Actions 从 `v1.1.5` 不可变 Tag 测试、构建、自检，SHA256 来自该次实际产物。

## 本次修复

- **HTTPS 回退：** Ctrl+C、TERM 和 HUP 会触发有限回退；提交和回退期间延后处理重复信号，避免状态文件与实际路由不一致。已提交状态保留，另一 Edition 的路由不被移除；回退失败会告警。
- **Python 3.10：** 共享代理备份改用分块 SHA256，证书及续期日期使用兼容的 UTC 接口。备份校验、损坏归档拒绝和隔离恢复检查纳入最低版本 CI。
- **续做凭据：** 首次基础安装成功但 HTTPS 失败后，续做成功再次提供逐项确认展示；新增单独 `--show-credentials`，仅在当前私有终端显示已有 WebDAV 信息和保存的 OpenList 初始化管理员密码，不安装、升级或改密。
- **依赖提示：** HTTPS 预检明确列出缺少的工具及安装命令；备份运行前检查宿主依赖，两 Edition 的 APT 清单补齐 `iproute2`、`python3`。预检阶段不自动安装软件。
- **回归覆盖：** 新增两 Edition 的中断回退、提交一致性、重复取消、备份兼容和凭据隐私测试；独立 Linux CI 在 Python 3.10/3.13 运行标准库维护测试。
- Telegram、SQLite、队列、rclone、WebDAV、streaming、UID/GID、数据库和 Session 等持久化兼容标识保持原有行为。

## 安装与升级

Windows 用户从下方 Assets 下载对应 Edition。下载新版部署器不会自动更新 VPS；已有实例重新部署默认保留配置和持久化数据，不要先卸载或删除数据。

没有 Windows 时，可在 Debian/Ubuntu x86_64 VPS 的可交互 Bash 终端，以 root 使用单行向导；需 Python 3.10+、curl 和系统 CA 证书。建议先只读检查：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

核对计划、备份和维护窗口后，再启动向导并明确确认：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

OpenList 对应入口：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist
```

仅查看已有凭据时使用 `--edition clouddrive2 --show-credentials` 或 `--edition openlist --show-credentials`。每项默认不显示，不能与 `--check`、`--configure-https` 或 `--verify` 组合；保存的 OpenList 初始化管理员密码可能已在管理页更改。

入口固定到通过 CI 的向导 commit，实际 payload 只来自最新正式稳定 Release，不安装 main/RC 未发布业务代码。已有实例核对官方源码、运行指纹与挂载后保留配置升级；不接管 TG115、部分实例、手改代码或冲突目录，不隐式切换域名，不重启未选中的 Bot。WebDAV 写入验收另行确认。

命令会执行仓库提供的代码，只应在信任本仓库时使用；可先下载检查。完整范围见 [VPS 安装与升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.5/docs/VPS-INSTALL.md)。原版本 Tag 已删除或官方源码无法核对时安全停止，不重建同名 Tag 来冒充旧版本基线。

## 验证范围

- 本地完整回归：470 passed、18 skipped、211 subtests passed；标准库独立检查：CLI 83 tests、6 skipped，宿主维护兼容 7 tests 通过。Ruff、Bandit、compileall、Bash 和版本/格式检查通过。
- 本地使用旧 API 模拟验证 Python 3.10 兼容；独立 Linux CI 另行运行真实 Python 3.10/3.13。发布等待同一 Tag 的 Windows/Linux 检查成功；本地跳过项不计为通过。
- CloudDrive2 脚本此前完成真实 VPS 只读预检；本轮的真实 HTTPS 中断/续做、首次安装、跨版本升级、回退及 Telegram/云盘转存仍待实机验收，OpenList 脚本实机验收暂缓。
- VPS 本机 HTTPS 自检或 WebDAV 接收/大小校验不等于公网访问、云盘官方最终完成或哈希验收。

## Windows 构建与校验

本次 Release 只提供同一次 GitHub Actions Windows 构建的三个文件：

| Edition | Release 文件 |
| --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` |
| SHA-256 校验 | `SHA256SUMS.txt` |

Release Job 校验并上传已通过自检的 Windows artifact，不重复构建，不上传或提交本机 EXE、`build/`、`dist/`。请用同一 v1.1.5 Release 的 `SHA256SUMS.txt` 核对完整摘要，不使用旧版本或本机旧构建的摘要。

管理后端仍仅回环监听，共享 Nginx 提供公网 80/443，公开 `/dav` 拒绝访问；域名不代理 Bot WebDAV 传输。云账号、Cookie、OAuth 和 Token 只在自己的 CloudDrive2/OpenList 配置；没有遥测或开发者侧凭据收集。有限内部回退不是通用 Restore/Uninstall；Windows EXE 未商业代码签名，不要关闭 Defender 或忽略 TLS 校验。

更多说明：[README](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.5/README.md) · [运行维护](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.5/docs/OPERATIONS.md) · [迁移与保留标识](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.5/docs/MIGRATION_FROM_TG115.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。
