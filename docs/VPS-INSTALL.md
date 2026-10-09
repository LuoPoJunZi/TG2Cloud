# 可选 VPS 安装与升级脚本

TG2Cloud 的主力安装方式仍是两个 PySide6 Windows 部署器。`install.sh` 是没有 Windows 电脑时可用的 Linux 终端入口，复用现有 Docker 安装、配置保留、备份、回退、HTTPS 与 WebDAV 验收流程，不另建一套 Bot 或 Compose 实现。

> 产品及已发布 EXE 保持 v1.1.2；本脚本是单独的源码入口，尚未随正式 Release 发布。CloudDrive2 已完成真实 VPS 的只读预检，首次安装、实际跨版本升级和回退仍未验收，OpenList 脚本实机验收暂缓。既有 Windows EXE 和已部署实例不会因此自动改变。

## 支持范围

| 场景 | 行为 |
| --- | --- |
| 全新 VPS | 选择 Edition，收集信息，预检，确认后安装 Docker 环境、基础服务及强制 HTTPS |
| 完整的已有 TG2Cloud | 识别目录、Compose 身份、持久化挂载和版本，复用现有配置升级所选 Edition |
| 已是最新稳定版 | 不重建、不重启；可以另行确认 HTTPS 续做或 WebDAV 验收 |
| 当前版本高于 latest | 不降级；停止隐式 HTTPS 变更 |
| 两个完整 Edition 同时存在 | 明确选择一套；`--edition both` 仅用于显式升级两套，依次执行，不是跨 Edition 原子事务 |
| TG115、残留目录、部分容器、同名外部容器 | 停止，不覆盖、不自动迁移或接管 |
| 手工修改过程序、Compose 或 Dockerfile | 停止，请先人工核对；不提供强制覆盖参数 |
| 新稳定版更换云网关镜像 digest | 停止自动升级；不隐式迁移 OpenList/CloudDrive2 数据库，改用部署器并人工验收 |

首版面向 Debian/Ubuntu、x86_64、root、Python 3.10+、Bash 和可交互终端。系统需有可用 CA 根证书和时区数据库。CloudDrive2 仍需 `/dev/fuse`，内存和磁盘条件沿用部署器的资源检查。

缺少 Python 时请先自行确认系统环境，并安装 `python3`、`ca-certificates`、`tzdata`。脚本不会在信息收集与确认前自动安装软件。APT/Docker 的安装权限只在首次基础安装的最终确认后交给现有安装器；升级要求已有 Docker daemon 和 Compose 可用，不自动升级 Docker 引擎。

## 从本地源码试用

在 VPS 上进入包含这些新增文件的源码目录，以 root 运行：

```bash
bash ./install.sh --help
bash ./install.sh --edition openlist --check
bash ./install.sh --edition openlist
```

CloudDrive2 使用 `--edition clouddrive2`。不指定 Edition 时出现选择向导。已有两套完整实例可使用 `--edition both`；不支持一次向导在全新 VPS 批量安装两套。

`--check` 只读运行实例及 HTTPS 状态，不收集秘密、安装软件或修改运行配置。它仍会访问公开 GitHub API 并在私有临时目录下载源码，因此需要网络和一定的临时磁盘空间。检查通过不代表 WebDAV、HTTPS 公网访问或 Telegram 实际转存已验收。

目标 payload 始终来自 GitHub 最新正式稳定 Release 的源码，不是本地工作树或 `main`。例如当前正式版本尚未包含本脚本时，从新增源码试用仍只会安装已发布的 payload；它不会把未发布业务代码装到 VPS。

## 正式发布后的下载方式

只有后续正式稳定 Tag 实际包含 `install.sh`、`scripts/` 和必要模块后，才可发布远程使用命令。届时可从该正式 Tag 下载 `install.sh` 到文件，检查后运行。不要使用 `curl | bash` 输入凭据，也不要使用 `main/install.sh` 作为稳定入口。

独立下载的脚本会通过 GitHub `/releases/latest` 排除草稿及预发布，解析 Tag 到不可变 commit，再从同一 commit 获取必要的公开 Python 模块。向导会核对该 commit 和源码版本。入口缺失、Tag 变化、API 限流或源码版本不匹配时停止；不会退回 main 或 RC。

下载使用系统 HTTPS 校验，源码身份固定到 commit。Release 中的 `SHA256SUMS.txt` 是 Windows EXE 校验清单，不用于校验源码归档；本入口不是额外的数字签名验证方案。仓库和发布账号仍是信任边界。

## 首次安装

1. 选择 CloudDrive2 或 OpenList。
2. 填写管理域名和可选 Let's Encrypt 邮箱。A/AAAA 必须正确直指 VPS，首次签发时 Cloudflare 使用“仅 DNS”。检查 80/443 是否能安全使用；公网防火墙与 ACME 可达性仍需用户确认。
3. 填写 Telegram API ID、API Hash、Bot Token、允许的 Telegram 用户 ID，以及专用 WebDAV 用户、密码、子目录、任务预算和时区。秘密隐藏输入，WebDAV 密码可留空安全生成。
4. 默认预算 `20GB`，磁盘最少保留 `8GB`。预算是任务预算而非磁盘分区；不足时停止，不偷偷调整。可以重跑向导明确采用较小预算。
5. 查看不含秘密的计划，确认后执行。默认回答为取消。
6. 基础服务安装完成后使用既有共享 Nginx/Certbot 配置 HTTPS。后端仍仅回环监听，不开放 IP 加端口入口；公网 `/dav` 继续阻断。
7. 打开自己的 HTTPS 管理页，自行配置云存储，再创建填写过的专用 WebDAV 用户。TG2Cloud 不收集云盘 Cookie、OAuth 或 Token。
8. 新安装可以逐项确认是否只在当前私有终端显示 WebDAV 信息和首次 OpenList 管理员密码；不会写入普通运行日志，也不会重设已有管理员密码。请自行保存必要信息，避免录屏或旁观。
9. 另行确认 WebDAV 写入验收。它会创建并清理随机测试文件，未确认则不执行。验收失败不自动反复重试；仍需在云盘官方客户端确认最终文件，并测试 Telegram 真实转存。

所有输入先在进程内收集；确认安装时才写入权限 `600` 的临时配置，并交给原安装器。Base64 只是避免 Shell 解析错误，不是加密。VPS 上的 `.env`、`rclone.conf`、备份仍是敏感文件，不要公开。

## 已有实例升级

```bash
bash ./install.sh --edition clouddrive2 --check
bash ./install.sh --edition clouddrive2
```

脚本读取 Docker/Compose 身份和绑定目录，核对实际运行代码与磁盘源码，再与当前版本的正式 Release 源码比较。Windows payload 的 CRLF 与 LF 差异不视为手工修改。

较早正式版本没有 `app/version.py` 时，只从 `app/__init__.py` 静态读取明确的 `__version__` 常量，不执行它的内容；升级计划仍要求全套程序与该版本官方源码一致。新版版本文件存在但无效时直接停止，不退回旧文件猜测版本。

升级不再询问 Bot Token、API Hash、WebDAV 密码。候选配置仅要求保留现有 `.env`；升级前后核对其原始字节。CloudDrive2 的现有安装器会规范化 `.env` 换行，因此该 Edition 的 `.env` 若含 CRLF/回车，CLI 会在写入前停止并要求人工核对，不擅自改成 LF。Session、SQLite、下载目录及云网关持久化目录保留，不清空、不重新授权云盘。

确认后，现有安装器复用 APT 基础依赖检查，可能更新相关系统软件包；不主动升级 Docker 引擎。随后做候选构建及隔离预检，再进行程序备份、SQLite 一致性快照和短暂 Bot 停止。健康检查失败时调用已有回退；请以回退日志和实例状态为准，不能保证所有外部故障都能自动恢复。CLI 自己不另写数据库恢复或网关迁移逻辑。

健康的已有 HTTPS 路由和证书原样保留；不切换域名、不重新签发，不重启未选中的 Bot。基础安装器仍可能对所选 Edition 的网关做既有的 Compose/网络操作；HTTPS 显式修复会操作共享代理，可能使管理页连接短暂中断。

新脚本的 Edition 锁只协调 CLI 之间的执行。共享 HTTPS 操作复用与 EXE 一致的代理事务锁；现有 EXE 基础安装器没有这个 Edition 锁，因此不要同时从 EXE 和 CLI 安装/升级同一实例。

## HTTPS 续做与验收

如果基础安装成功而 HTTPS 失败，保留已安装数据，不要删除容器或反复全新安装：

```bash
bash ./install.sh --edition openlist --configure-https
bash ./install.sh --edition openlist --verify
```

`--configure-https` 是明确的配置/修复授权，执行前仍需要确认。有已保存域名时只能沿用它，不提供隐式切换。已是最新版本时只续做 HTTPS，不重建 Bot。没有保存域名时才收集新域名。

首次 HTTPS 失败前生成的秘密已经由安装器保存到 VPS `.env`。若尚未显示，请仅在自己控制的 root 私有终端查阅对应配置，或使用部署器维护；不要把完整 `.env` 贴进日志、聊天或 Issue。

`--verify` 仍需第二次确认，只有 HTTPS 自检健康才执行现有 `manage.sh verify`。返回 401、429 或业务错误不会触发自动改密、重装或循环验收。

状态结果区分：

- `TG2CLOUD_CLI_RESULT=NO_CHANGE`：未升级或重启。
- `TG2CLOUD_CLI_RESULT=CANCELLED`：用户取消，未执行计划内变更。
- `TG2CLOUD_CLI_BASE_HTTPS=OK`：基础服务及 VPS 本机 HTTPS 检查通过；不是公网或云盘验收结论。
- `TG2CLOUD_CLI_WEBDAV=NOT_RUN/OK`：独立写入验收的实际结果。
- `TG2CLOUD_CLI_RESULT=FAILED/INTERRUPTED`：停止后续操作；请核对备份、回退及当前实例状态，不假定已恢复。

脚本不承担 uninstall、删除业务数据、备份清理、历史重写、自动证书续期策略变更或生产 VPS 故障注入。这些操作继续使用现有部署器/管理流程。旧 TG115 请参考 [迁移说明](MIGRATION_FROM_TG115.md)。

## 本地验证与待验收

新增离线测试覆盖 Release 选择、不可变 commit、归档解包安全、两 Edition payload 组装、与 GUI 配置格式一致、配置保留、实例冲突、版本判断、明确确认、HTTPS 和 WebDAV 结果边界。

2026-10-09，CloudDrive2 专用测试机的实际 `--check` 通过：识别旧版 v1.0.2，核对官方旧版源码及运行指纹，固定最新稳定 v1.1.2 的源码 commit，完成容量和现有 HTTPS 自检，并生成保留配置升级计划。没有执行升级、重启或域名变更，检查前后容器标识与启动记录一致。这不是跨版本升级成功或云盘传输的验收结论。

OpenList 脚本实机验收暂缓。仅有网关、没有 Bot 的部分实例会安全停止，不自动当作全新安装覆盖；这不影响已发布 OpenList EXE 的既有验收结果。

另有独立 Linux CI 检查本入口，不生成 EXE。分支 CI 继续执行测试，仅在实际 EXE 输入变化或手动触发时打包；正式 Tag 的 Release 构建工作流不变。实际首次安装、稳定版跨版本升级、中断与回退、真实云盘、双 Edition 共存、证书签发/续做及公网访问，仍需在专用测试 VPS 验收后再推荐生产使用。
