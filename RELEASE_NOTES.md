**TG2Cloud v1.3.2** 优化 Linux 安装交互，新增离线 `tg2cloud` 管理菜单，并简化独立外部 WebDAV 向导。CloudDrive2 / OpenList 继续共用稳定 Bot 核心；Windows EXE 保留在 v1.2.1。

## 本次更新

- **统一安装与管理**：公网、内网入口不带参数时先编号选择 Edition。尚未安装则确认进入对应向导，已安装则显示管理菜单；显式参数继续兼容。
- **离线管理命令**：确认安装后提供 `tg2cloud`，可查看状态与脱敏日志、启停、验收 WebDAV、维护 HTTPS、查看备份与凭据，或选择“卸载当前实例”。状态和日志不下载最新代码；写入操作保留确认和实例核验。
- **简洁中文向导**：WebDAV 用户名回车默认 `tg2cloud`，密码回车生成 8 位；保存子目录可留空。新装默认 `Asia/Shanghai`，升级不改已有时区、凭据、预算或数据。
- **限定卸载与收尾**：只卸载所选 Edition。最后一套完整卸载后，无其他实例、路由、保留数据或挂载依赖且归属核验通过，才移除管理命令和代码；未知文件、忙碌或部分失败不强删。独立卸载 URL 保留作兼容／救援。
- **外部 WebDAV 交互**：独立中文编号菜单、简洁版本提示、实际目录确认、9 位默认随机密码及集中手机配置输出；不加入主安装或 Bot 菜单，不改原生只读与失败关闭规则。

不新增 Bot 依赖、数据库结构迁移、环境变量或网关镜像。现有 `.env`、数据库、Telegram Session、rclone 配置、上传策略及两 Edition 身份保持兼容。内网实例不会因改用公网入口而隐式申请证书。

## 安装与日常维护

公网 VPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

已有实例可先追加 `--edition clouddrive2 --check`（OpenList 使用 `openlist`）只读预检；核对后去掉参数进入新版菜单，确认升级。日常在主机运行 `tg2cloud`；仅查看帮助或只读预检不会安装此命令。未知或修改过的实例不会被自动接管。

旧实例同版本无需更新业务时，新向导可在确认后仅安装本地管理命令，不重启容器。详细限制见[运维指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.2/docs/OPERATIONS.md)。

## 独立外部 WebDAV

本 Release 发布完成后，单独执行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

要求完整受管实例、可用的原生独立只读账号、专用域名和 HTTPS 签发条件。使用原网关和共享代理，不复制数据；原生账号能力不足、目录不明或身份不符时停止。完整步骤见[外部 WebDAV 指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.2/docs/external-webdav.md)。已安装主机不会自动更新离线工具，需显式执行附加功能升级。密码不持久化回显，分享终端记录前必须脱敏。

手机参数为 HTTPS、你的专用域名、443、根路径 `/dav/`，使用新外部账号与新密码。管理域名仍禁止 `/dav`。停用使用 `tg2cloud-webdav disable --edition openlist`，独立卸载使用 `tg2cloud-webdav uninstall --edition openlist`；CloudDrive2 改为 `--edition clouddrive2`。

## 下载与校验

| 文件 | 用途 |
| --- | --- |
| `TG2Cloud-v1.3.2-source.tar.gz` | 同标签公共源码与两 Edition 资源 |
| `SHA256SUMS.txt` | 本次 Actions 源码包的实际校验清单 |

下载两个文件到同一目录，执行 `sha256sum -c SHA256SUMS.txt`。校验和不是数字签名；不用于历史 EXE。Windows 历史资产仍见 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)。

## 验证与兼容范围

发布提交已通过主分支的 Linux 回归与宿主 Python 3.10 / 3.13 兼容检查。同一 Tag 的 Release Actions 再执行 Python 3.12 全量回归、Compose、非 root 候选镜像及隔离 Nginx / WebDAV 检查；验证成功后只打包一次，发布任务复用该产物并核对 SHA256。结果以实际工作流为准。

**本轮不连接真实 VPS、Telegram 或用户网盘。新版安装／升级／卸载、两网关原生账号与目录权限、手机播放、公网 ACME 和 ARM64 的端到端验收仍需单独完成。** 主安装支持范围仍为 Debian / Ubuntu x86_64、rootful Docker、宿主 Python 3.10+；附加功能预检接受 ARM64，不等于主安装支持已扩大。隔离测试不能代替网关会员能力或原生 ACL 审计。

附加功能启用后代理状态升级到 schema 2；旧 v1.3.0 严格写入工具会拒绝维护，禁止用更旧脚本或桌面恢复包覆盖新代理。主卸载前先独立卸载附加入口，仅 disable 不解除依赖。完整卸载会删除所选本地数据及可识别备份，需保留时使用 `--keep-data`；系统 Docker / Nginx、云端文件、镜像缓存和锁元数据不删除，不承诺主机逐字节恢复原样。CloudDrive2 历史迁移范围见 [v1.3.0 原验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)，不扩展为本版实机通过结论。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢；云存储授权由用户在自己的网关完成。
