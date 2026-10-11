> [!IMPORTANT]
> **TG2Cloud v1.2.0** 增加独立内网安装与卸载入口。两个 PySide6 部署器仍是主力；公网 VPS / EXE 的强制 HTTPS 和稳定传输核心保持原行为。正式 EXE 由 GitHub Actions 从同一不可变 Tag 测试、构建、自检，SHA256 来自该次实际产物。

## 下载选择

| Edition | Windows 部署器 | 管理网关 |
| --- | --- | --- |
| CloudDrive2 | `TG2Cloud-CloudDrive2-Deployer.exe` | CloudDrive2 |
| OpenList | `TG2Cloud-OpenList-Deployer.exe` | OpenList |
| 校验清单 | `SHA256SUMS.txt` | 校验本次 Release 的两个 EXE |

只需下载所用 Edition 的 EXE 和同一 Release 的校验清单。下载新版 EXE 不会自动更新已部署 Bot；已有实例使用保留配置升级，不必卸载重装。

## 本次更新

- **独立内网入口**：人工输入并核对私有 IPv4，运行独立管理 Nginx，不申请域名证书、不占用 80/443、不接管已有 HTTPS 实例。通过入口检查后，在 WebDAV 验收前再次显示完整 `http://IP:端口`。
- **独立卸载向导**：先预览资源、再明确确认；可选择 CloudDrive2、OpenList 或全部。默认保留实例数据和证书，删除本地实例数据另需参数与二次输入确认。
- **卸载边界**：另一 Edition 路由继续保留；没有剩余 HTTPS 路由才移除受管 Nginx/Certbot。检查 Compose 身份、挂载、不可变资源 ID、外部引用及 FUSE，拒绝不明归属。不卸载系统应用，不清理云端文件、旧 TG115、历史备份或镜像缓存。
- **发布验证**：三个 Shell 入口、独立脚本和两 Edition 隔离 LAN Nginx 纳入检查；版本、Windows 资源、中英文文档及网站说明同步。

Telegram、SQLite、队列、rclone、WebDAV 上传策略、streaming 和兼容持久化标识未改动。115 是常见示例，不是唯一目标；云存储授权仍在自己的 CloudDrive2 / OpenList 中配置。

## Linux 安装入口

公网 VPS 继续使用原向导，完成域名 HTTPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网 Debian / Ubuntu x86_64 主机使用独立入口，按向导输入内网 IP：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

内网 HTTP 不加密，禁止公网端口转发；要求 Python 3.10+、Docker 28+ 等预检条件，不保证兼容所有 NAS / ARM 系统。在线入口固定经 CI 验证的向导 commit，实际业务 payload 只取最新正式稳定 Release，不运行移动 main 的业务代码。

## 独立卸载

仅在确实要移除服务时使用，先结束传输并备份。建议先只读预检：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

预检不是卸载成功。实际执行会展示计划并等待确认，默认不删除实例数据：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh)
```

范围、单 Edition 卸载、二次数据删除确认和部分失败处理见 [卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.0/docs/UNINSTALL.md)。不会卸载系统 Docker/Nginx，也不使用全局 prune。新卸载功能尚未完成真实 VPS/NAS 卸载验收，不推荐跳过预检或把生产实例作为试验目标。

## 验证范围与限制

发布须通过同标签 Windows / Linux 自动验证；Windows 构建并自检两个 EXE，Linux 检查 Shell、两版非 root 候选镜像、本地 WebDAV 与隔离 LAN 网关。独立脚本另有 Python 3.10/3.13 分支 CI。卸载使用离线模拟核验资源归属、双确认、取消/失败、共享路由和 FUSE 保护，不对真实主机执行删除。

用户提供的 CloudDrive2 内网 Debian 日志显示首次部署和 WebDAV 验收通过；这不等于 OpenList 内网、其他 NAS、跨版本升级/回退、真实卸载或 Telegram 转存已经验收。构建和发布成功也不是业务全链路验收。仍无正式自动 Restore；未知安装、自定义目录和旧 TG115 不自动接管。

## Windows 构建与 SHA256

Release Job 校验并上传已经通过自检的 Windows artifact，不重复 Build，不提交或上传本机 EXE、`build/` 或 `dist/`。请以本次 v1.2.0 Release 的 `SHA256SUMS.txt` 核对完整摘要，不使用旧版本或本机旧构建的校验值。

Windows EXE 尚未商业代码签名；未知发布者提示不等于来源已获验证。请核对仓库、标签、文件名和 SHA256，不关闭系统安全检查。

更多说明：[README](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.0/README.md) · [VPS 安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.0/docs/VPS-INSTALL.md) · [内网安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.0/docs/LAN-INSTALL.md) · [运行维护](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.0/docs/OPERATIONS.md)。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。
