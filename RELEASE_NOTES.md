<!-- 本文件会直接作为 GitHub Release 正文：不要添加一级标题，不要按固定列宽硬换行。 -->

> [!IMPORTANT]
> **TG2Cloud v1.1.3** 新增可选 VPS 单行安装与保留配置升级入口。当前为源码发布准备，尚未创建对应 Tag/Release，已发布 EXE 仍为 v1.1.2；不要把 main 的版本号或分支 CI artifact 当作正式 Release。两个 PySide6 部署器仍是主力。

## 本次更新

- 新增 `install.sh` Linux 终端向导，支持全新 VPS 安装、完整已有实例保留配置升级和只读 `--check`。
- 单行入口下载已验证、固定到 commit 的向导模块；实际 payload 只来自 GitHub 最新正式稳定 Release，不安装 main/RC 未发布业务代码。
- 先收集信息、预检、展示不含秘密的计划，默认取消，明确确认后才安装软件或修改实例；秘密通过当前终端隐藏输入。
- 升级核对 Compose 身份、挂载、实际运行指纹和官方源码，保留配置及持久化数据；不接管 TG115、部分实例、手改代码或冲突目录，不隐式迁移网关数据库。
- 复用现有 Docker、备份/有限回退、共享 HTTPS 保护与 WebDAV 验收。健康域名不隐式切换，未选中的 Bot 不重启，写入验收另行确认。
- 同步中英文 README、脚本指南和文档站；产品、两个部署器、Bot、Windows 资源及文档版本统一为 1.1.3，历史记录与已发布下载基线保留原版本。
- 新增独立 Linux 脚本 CI 与单行引导回归；分支 CI 按实际 EXE 输入决定打包，正式 Release 复用同一次 Windows 构建的 artifact。
- 已合入 Telethon 1.45.0、PyInstaller 6.22.3 的限定兼容验证；没有重写 Telegram、SQLite、rclone、streaming 或稳定落盘流程。

## VPS 单行入口

在 Debian/Ubuntu x86_64 VPS 的可交互 Bash 终端，以 root 运行；需 Python 3.10+、curl、系统 CA 证书和时区数据库：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

建议先在测试 VPS 对 CloudDrive2 执行只读检查：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

命令会执行仓库代码，只应在信任本仓库时使用；也可先下载并检查脚本。正式 v1.1.3 Release 发布前，目标仍是当前已发布的稳定 payload，不会仅因本次源码版本提高而安装未发布代码。完整范围见 [VPS 安装与升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。

## 验证范围

- 离线测试覆盖稳定 Release/不可变 commit、单行引导、下载与版本失败、Tag 漂移、路径/归档安全、配置保留、确认取消、HTTPS 和 WebDAV 结果边界。
- CloudDrive2 专用 VPS 的脚本 `--check` 已通过：识别官方旧版、核对运行指纹、配置/挂载、容量与现有 HTTPS，并生成升级计划；没有安装、升级、重启或切换域名。
- 单文件入口的真实公开下载与本地进程替换 `--help` 验证通过；不等于在 Linux VPS 完成部署。
- 本次源码回归、Windows 构建自检与 Linux/POSIX 检查以实际测试和 Actions 结果为准，跳过项不计为通过。
- 脚本首次安装、实际跨版本升级、中断/回退、真实云盘和 Telegram 转存仍待实机验收；OpenList 脚本实机验收暂缓。既有 EXE 的历史验收不作为新脚本全流程通过的证据。

## Windows 构建与校验

正式发布时仍只上传以下三个文件，由 GitHub Actions 从同一个不可变 Tag 测试、构建、自检，对该次实际 EXE 计算 SHA256：

| Edition | Release 文件 |
| --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` |
| SHA-256 校验 | `SHA256SUMS.txt` |

本次 Push 不创建 Tag/Release，不上传或提交本机 EXE、`build/`、`dist/`。现有 v1.1.2 Release 不被替换；未来发布 Job 复用 Windows Build Job 的 artifact，不重复构建。

## 升级与安全边界

两个 Windows 部署器仍是主要安装方式。下载部署器或更新文档不会自动更新 VPS；CLI 安装/升级也需明确确认。不要同时从 EXE 和 CLI 操作同一实例。`manage.sh update` 只重建本机已有 payload，不自动获取 GitHub 新版本。

管理后端继续仅监听回环地址，共享 Nginx 提供公网 80/443，公开 `/dav` 被拒绝；域名不代理 Bot WebDAV 传输。云账号、Cookie、OAuth 和 Token 仍只在自己的 CloudDrive2/OpenList 配置，没有遥测或开发者侧凭据收集。

备份包含敏感配置、证书私钥或 ACME 账户时只保存在 VPS 私密目录，不要公开上传；有限内部回退不是正式自动 Restore/Uninstall。基础健康与 VPS 本机 HTTPS 自检不等于公网访问或云存储最终完成。Windows EXE 未商业代码签名，不要关闭 Defender 或跳过 TLS 校验。

完整说明见 [README](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/README.md)、[运行维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md) 和 [HTTPS 验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/DOMAIN-HTTPS-ACCEPTANCE.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。
