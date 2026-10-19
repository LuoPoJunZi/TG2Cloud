**TG2Cloud v1.3.4** 改善图片／视频的说明命名和媒体组名称，并补全 Linux 使用与恢复文档。保留 CloudDrive2 / OpenList 共用 Bot 核心、Python＋Bash 架构，以及现有下载、上传和安全恢复流程；Windows EXE 停留在 v1.2.1。

## 本次更新

- **有效说明优先**：网址、账号或处理前缀污染的视频原名，可使用实际送达的可靠正文；无原名、数字／默认名或污染名的单图片也可使用自身说明。正常有意义的原名、无说明兜底和原名记录保留。
- **一图一视频同标题**：同一验证媒体组恰好一张图片和一个视频、真实后缀可区分时，共用标题，例如 `城市夜景旅行记录.jpg` 与 `城市夜景旅行记录.MP4`。多成员、同类媒体或无法区分后缀时继续种类编号，不覆盖远端同名文件。
- **识别边界修复**：接收以 `/` 开头的媒体说明；区分正常作品名与推广／凭据字段；识别表情标题标签和同条说明的相邻作品名／集数；保留斜杠两侧文字，改善紧贴中文的域名和尾部画质过滤。
- **扩展名与安全**：明确的视频元数据可修正明显不符的原名后缀，正常 MKV 等视频格式保留；沿用 Unicode 规范化、路径清理、UTF-8 长度限制、隐藏实体处理、鉴权、去重及远端冲突保护。提取异常回退原安全名称，不阻断接收。
- **文档补齐**：新增命名、配置、备份恢复预检和 FAQ 专题，完善安装、管理、家人授权、网关与卸载说明；README 保持简短并直接导航仓库文档，网站独立同步。

不新增依赖、环境变量、任务数据库结构迁移或网关镜像，不更改主安装、Bot 菜单、传输和两后端提交策略。不抓评论、来源频道或网页，不做 OCR；未实际收到的文字不会被猜测。旧任务和远端文件不追溯改名。

## 安装与升级

公网 VPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

已有实例先追加 `--edition clouddrive2 --check`（OpenList 使用 `openlist`）只读预检，核对备份和升级计划后重新进入菜单，确认“安装 / 升级”。保留 `.env`、数据库、Telegram Session、rclone、目录、预算和 Edition 身份，不需要卸载重装。只有实例实际升级后，新命名才会用于新接收的媒体；旧任务重复转发仍遵守原去重和恢复规则。

主安装要求 Debian / Ubuntu x86_64、rootful Docker 和宿主 Python 3.10+。日常使用离线 `tg2cloud`；单纯查看状态、重启容器或更新仓库文档不会更新 Bot。操作见[安装指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)、[命名指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/NAMING.md)和[运维指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md)。

## 家庭共享与独立外部 WebDAV

继续保留 v1.3.3 起的家庭共享：安装只填一个固定管理员 ID，之后在 `tg2cloud` 的“10. Bot 用户管理”授权家人；成员管理自己的任务，共用保存目录与资源。Bot 授权与手机读取账号互相独立，详见[家庭共享](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/FAMILY-SHARING.md)。

外部 WebDAV 仍为独立附加功能，不加入主安装或 Bot 菜单。需要时单独运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

它复用原存储网关与共享代理，要求独立原生只读账号、明确目录和专用 HTTPS 域名，不复用 Bot／管理员密码。手机填写 HTTPS、实际域名、443、根路径 `/dav/` 和外部专用凭据；管理域名继续拒绝 `/dav`。附加工具单独显式升级，维护命令为 `tg2cloud-webdav`，例如 `tg2cloud-webdav uninstall --edition openlist` 只卸载所选附加入口，不删除云端文件或后台账号。CloudDrive2 使用 `--edition clouddrive2`。见[完整指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/external-webdav.md)。

## 下载与发布状态

当前为 **v1.3.4 待发布候选**，尚不能从稳定入口取得本版 Bot。正式下载基线仍为 [v1.3.3](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.3.3)；候选发布需要先公开并验证辅助提交 A、更新固定入口 B，再通过同标签 Actions 发布。

| 本版发布后资产 | 用途 |
| --- | --- |
| `TG2Cloud-v1.3.4-source.tar.gz` | 同标签公共源码与两 Edition 资源 |
| `SHA256SUMS.txt` | Actions 为实际源码包生成的校验清单 |

正式资产出现后，将两文件放在同一目录执行 `sha256sum -c SHA256SUMS.txt`。校验和不是数字签名，不混用其他版本清单。Windows 历史资产见 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)，本版不构建 EXE。

## 验证与兼容边界

命名和接收流程使用合成文字、临时 SQLite 及离线 Telegram 对象回归，不使用用户媒体或生产凭据。本轮本地检查、远端 CI 与正式资产核验分别记录；待同标签工作流完成后，以其真实结果作为正式发布依据，不把候选源码或 main 上的版本文字当作已发布。

**v1.3.4 尚未进行真实 VPS 升级、Telegram 转存或用户网盘验收。** 需升级测试实例后，分别验证单视频、单图片、一图一视频、多成员、无说明、正常原名和重名保护；CloudDrive2 / OpenList、家庭权限、手机／Range、公网 ACME、ARM64 和故障回退仍按实际环境单独验收。用户对 CloudDrive2 v1.3.3 实际转存的确认不扩大为本版结论，见 [v1.3.3 记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V133-ACCEPTANCE.md)与 [v1.3.0 历史迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。

大小复验仅证明 WebDAV 目的端大小，不是内容哈希或云盘官方最终完成。主卸载前先独立卸载外部入口；完整清理会删除所选本地数据和可识别备份，需保留时使用 `--keep-data` 并准备独立备份。旧工具不得覆盖新代理状态，也不要通过删除数据库／Session 绕过兼容校验。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢；云存储授权由用户在自己的网关完成。
