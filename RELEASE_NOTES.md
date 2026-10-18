**TG2Cloud v1.3.3** 新增家庭共享，增强多语言视频命名，并精简 VPS 资源页。CloudDrive2 / OpenList 继续共用 Bot 核心和 Linux Python＋Bash 架构；Windows EXE 保留在 v1.2.1。

## 本次更新

- **Bot 家庭共享**：安装仍只填写一个管理员 ID，安装后在 `tg2cloud` 的“10. Bot 用户管理”授权最多 32 位可信家人。成员各自管理任务、接收通知，共用目录与资源；全局管理仅管理员可用。停用不删除历史或云端文件。
- **外部 WebDAV 多账号**：独立 `tg2cloud-webdav` 用户管理为家人登记原生只读账号，共用已确认目录；与 Bot 授权互相独立。单账号换密／停用失败关闭所选账号，不自动删除网关账号，不新增个人目录。
- **多语言命名**：补识别混合随机 ID，按同条消息和本媒体组可见文字评分选择标题；支持 Unicode 多语言，过滤域名变体、账号、话题、推广和画质行。保留集数、年份、有意义原名、真实扩展名、媒体组指定命名和无说明兜底；识别异常不阻断接收，不抓评论、不做 OCR。
- **资源页精简**：移除文件系统容量清单，保留 CPU、内存、磁盘、暂存额度和数字时间；后台多文件系统采样与磁盘保护不变。
- **兼容与回归**：新增权限、授权撤销、账号失败关闭、媒体组、命名和两 Edition 接收→下载→重启恢复→上传复验的离线回归；保持原有去重、远端冲突及两后端提交差异。

不新增依赖、任务数据库结构迁移、环境变量或网关镜像。Bot 授权使用既有 SQLite 元数据；附加功能首次管理新账号后，私密账号记录升级到 schema 2，旧工具拒绝操作，禁止手工降 schema。现有 `.env`、任务、Telegram Session、rclone、上传策略及两 Edition 身份保留。内网实例不会因改用公网入口而隐式申请证书。

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

先按正式流程升级所选 Bot 与本地管理工具，再配置家人；旧 Bot 不支持授权协议时会停止，不直接编辑数据库绕过。旧离线代码不会自动更新；同版本无业务升级时可确认仅更新管理命令，不重启容器。见[运维指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.3/docs/OPERATIONS.md)与[家庭共享](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.3/docs/FAMILY-SHARING.md)。

## 独立外部 WebDAV

本 Release 发布完成后，单独执行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

要求完整受管实例、可用的原生独立只读账号、专用域名和 HTTPS 签发条件。使用原网关和共享代理，不复制数据；原生账号能力不足、目录不明或身份不符时停止。完整步骤见[外部 WebDAV 指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.3/docs/external-webdav.md)。已有主机需单独显式升级附加功能离线工具，再使用“10. 用户管理”；主 Bot 升级不会自动更新它。密码不长期明文保存，分享终端记录前必须脱敏。

手机参数为 HTTPS、你的专用域名、443、根路径 `/dav/`，使用新外部账号与新密码。管理域名仍禁止 `/dav`。停用使用 `tg2cloud-webdav disable --edition openlist`，独立卸载使用 `tg2cloud-webdav uninstall --edition openlist`；CloudDrive2 改为 `--edition clouddrive2`。

## 下载与校验

| 文件 | 用途 |
| --- | --- |
| `TG2Cloud-v1.3.3-source.tar.gz` | 同标签公共源码与两 Edition 资源 |
| `SHA256SUMS.txt` | 本次 Actions 源码包的实际校验清单 |

下载两个文件到同一目录，执行 `sha256sum -c SHA256SUMS.txt`。校验和不是数字签名；不用于历史 EXE。Windows 历史资产仍见 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)。

## 验证与兼容范围

本地已通过 Python 3.13 的 818 项回归（792 执行成功、26 环境跳过）及网站 19 项检查；辅助源码已通过远端 Linux 回归与宿主 Python 3.10 / 3.13 兼容检查。非 root Runner 的认证文件测试夹具已修正，并新增改属主失败保留旧认证文件的回归，生产权限不变。同一 Tag 的 Release Actions 再执行 Python 3.12、Compose、非 root 候选镜像及隔离 Nginx / WebDAV 检查。验证成功后只打包一次，发布任务复用该产物并核对 SHA256；是否已完成以该 Tag 的实际工作流为准。

**本轮不连接真实 VPS、Telegram 或用户网盘。新版安装／升级／卸载、两网关原生账号与目录权限、手机播放、公网 ACME 和 ARM64 的端到端验收仍需单独完成。** 主安装支持范围仍为 Debian / Ubuntu x86_64、rootful Docker、宿主 Python 3.10+；附加功能预检接受 ARM64，不等于主安装支持已扩大。隔离测试不能代替网关会员能力或原生 ACL 审计。

附加功能启用后代理状态升级到 schema 2；旧 v1.3.0 严格写入工具会拒绝维护，禁止用更旧脚本或桌面恢复包覆盖新代理。主卸载前先独立卸载附加入口，仅 disable 不解除依赖。完整卸载会删除所选本地数据及可识别备份，需保留时使用 `--keep-data`；系统 Docker / Nginx、云端文件、镜像缓存和锁元数据不删除，不承诺主机逐字节恢复原样。CloudDrive2 历史迁移范围见 [v1.3.0 原验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)，不扩展为本版实机通过结论。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢；云存储授权由用户在自己的网关完成。
