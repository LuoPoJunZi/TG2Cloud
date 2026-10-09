<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.1.4** 修复 VPS 向导的交互终端与候选镜像源码读取权限，并统一两 Edition 共用 Bot 镜像的 TG2Cloud 内部名称。两个 PySide6 部署器仍是主力；正式 EXE 由 GitHub Actions 从 `v1.1.4` 不可变 Tag 测试、构建、自检，SHA256 来自该次实际产物。自动测试不等于真实 VPS 或文件转存已验收。

## 本次修复

- **终端输入：** 修复 `File or stream is not seekable`，分开打开 `/dev/tty` 读取/写入流，及时刷新提示；隐藏秘密输入，中断恢复回显，兼容 Python 3.10。
- **候选镜像权限：** 修复 `Permission denied: /opt/tg115/app/__init__.py`。只给公开 Docker 构建文件设置 `0644`、子目录设置 `0755`；外层私有目录仍为 `0700`，候选秘密配置仍为 `0600` 且位于构建上下文之外。
- **镜像读取保障：** Dockerfile 确保公开 `app/` 可被非 root Bot 用户读取，源码继续归 root 所有；不改为 root 运行、不使用 `777`。
- **TG2Cloud 命名：** 两版 Bot 镜像内程序目录/PYTHONPATH 改为 `/opt/tg2cloud`，用户/组和 logger 改为 `tg2cloud`，新日志为 `tg2cloud.log`。
- **保留已有数据：** UID/GID 仍为 `10001:10001`；保留 `tg115.db`、`bot.session`、旧日志、挂载、环境兼容变量、verify 前缀及旧实例检测。这些兼容标识不表示仍是 TG115 产品，也不会自动导入旧项目数据。
- **回归门槛：** 增加源码权限、秘密边界、日志及持久化路径检查；Linux 分支和 Release Job 实际以非 root 启动两 Edition 候选镜像，分别覆盖正常构建上下文和私有权限源码。
- 同步共享版本源、两个 EXE 的 Windows 版本资源、中英文 README、脚本指南、迁移说明和文档站；没有改写 Telegram、SQLite 队列、rclone、WebDAV、streaming 或 HTTPS 业务流程。

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

入口固定到通过 CI 的向导 commit，实际 payload 只来自最新正式稳定 Release，不安装 main/RC 未发布业务代码。已有实例核对官方源码、运行指纹与挂载后保留配置升级；不接管 TG115、部分实例、手改代码或冲突目录，不隐式切换域名，不重启未选中的 Bot。WebDAV 写入验收另行确认。

命令会执行仓库提供的代码，只应在信任本仓库时使用；可先下载检查。完整范围见 [VPS 安装与升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.4/docs/VPS-INSTALL.md)。原版本 Tag 已删除或官方源码无法核对时安全停止，不重建同名 Tag 来冒充旧版本基线。

## 验证范围

- 本地完整回归：448 passed、18 skipped、189 subtests passed；独立 CLI unittest：72 tests、6 skipped。Ruff、Bandit、compileall、Bash、ShellCheck 和版本/格式检查通过。
- 新权限回归使用旧实现时，两 Edition 均复现失败，修复实现通过。Linux/POSIX 权限与真实 Docker 启动检查由 Actions 执行，发布等待同一 Tag 的 Windows/Linux 检查全部成功；本地跳过项不计为通过。
- CloudDrive2 脚本已完成真实 VPS 只读预检；本轮权限修复后的首次安装、跨版本升级、回退及 Telegram/云盘转存仍待实机验收，OpenList 脚本实机验收暂缓。
- VPS 本机 HTTPS 自检或 WebDAV 接收/大小校验不等于公网访问、云盘官方最终完成或哈希验收。

## Windows 构建与校验

本次 Release 只提供同一次 GitHub Actions Windows 构建的三个文件：

| Edition | Release 文件 |
| --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` |
| SHA-256 校验 | `SHA256SUMS.txt` |

Release Job 校验并上传已通过自检的 Windows artifact，不重复构建，不上传或提交本机 EXE、`build/`、`dist/`。请用同一 v1.1.4 Release 的 `SHA256SUMS.txt` 核对完整摘要，不使用旧版本或本机旧构建的摘要。

管理后端仍仅回环监听，共享 Nginx 提供公网 80/443，公开 `/dav` 拒绝访问；域名不代理 Bot WebDAV 传输。云账号、Cookie、OAuth 和 Token 只在自己的 CloudDrive2/OpenList 配置；没有遥测或开发者侧凭据收集。有限内部回退不是通用 Restore/Uninstall；Windows EXE 未商业代码签名，不要关闭 Defender 或忽略 TLS 校验。

更多说明：[README](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.4/README.md) · [运行维护](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.4/docs/OPERATIONS.md) · [迁移与保留标识](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.1.4/docs/MIGRATION_FROM_TG115.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。
