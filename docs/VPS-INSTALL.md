# VPS 安装与升级脚本

v1.4.9 发布准备：两个入口当前固定已公开、五项 CI 通过的辅助 A `80258deec5fc8979329cb1dbaa2c6d6c0b391e15`，66 个公开 helper 文件已逐项核对。入口 B 及正式资产仍在验证，当前稳定下载保持 v1.4.8；完成发布后再使用新版功能。下方 SHA 和验收属于历史版本，不代表本次实机通过。

v1.4.8 已正式发布。两个在线入口固定辅助 A `f2c089aeccc1de1c17c43654dad35249236e6e14`，入口 B／Tag 为 `e24cddfa77fe76b90ea63ee9e7d88008066cb0a3`；A／B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175950235)及实际源码资产核验全部通过。旧离线管理工具须显式更新，外部 WebDAV 另在子菜单 8 升级；下方历史记录保留原范围。

v1.4.7 已正式发布：两个在线安装入口固定辅助 A `85595a83f40371caabfa3f9a2dfeaf7dc756edc1`，入口 B／Tag 为 `322ae065d6cb6a7330f78b8cc0ee60c4c3c53cdb`。A／B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160704507)及实际源码资产核验全部通过。业务只使用正式稳定 Release；主菜单 14／15 保留卸载与外部 WebDAV 管理，下方历史记录按原版本理解。

历史 v1.4.6 已正式发布：当时的三个在线入口固定已公开且五项 CI 通过的辅助 A `56e5115e729356c40a10912bb7d7c000969e40df`，完整验证与使用范围见[本版说明](development/LOCAL-MAINTENANCE.md)。业务仍只使用正式稳定 Release；下方 v1.4.5 及更早发布信息按历史范围保留。

v1.4.5 已正式发布：三个主入口固定辅助 A `cff0d37ee0a7840ae8d9babd2edea1ca939c3558`，A／入口 B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40073091331)全部通过；实际源码包、SHA256 清单及 GitHub 资产摘要已核验。新版页面、诊断、隔离演练及未执行范围见[维护记录](development/MAINTENANCE-NEXT.md#7-v145-发布核验2026-10-24)。业务只取正式稳定 Release，不把向导版本当作部署完成，下方用户实机记录仍属于旧版。

2026-10-23 用户已确认两次 CloudDrive2 v1.4.3 → v1.4.4 升级验收通过：Ubuntu 26.04.1 原生 ARM64、Debian 13 原生 AMD64。两份日志中的配置保留、数据库备份、Bot 健康、代码／版本、本机 HTTPS 与最近业务就绪观察均通过；WebDAV 写入未执行，真实转存、外网、回退及 OpenList 等范围未覆盖。见[双架构升级记录](development/V144-ACCEPTANCE.md)，不是维护者再次登录实测。

v1.4.4 已正式发布：辅助 A `ea93c95eda0fa68c807b56c41871e09b7a19634b`、入口 B／Tag `6164a237108786c01a7a958ab56e16023df04d79` 各五项 CI 及[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39920070111)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要已核验。 新版日志分级、结果／验收摘要及管理菜单须显式升级匹配工具后使用；业务只取正式稳定 Release。下方旧记录保留历史范围，不作为本版实机验收。

2026-10-23 用户日志确认：CloudDrive2 在 Debian 13／AMD64 通过公开入口完成 v1.4.2 → v1.4.3 基础升级，Bot healthy、代码／配置和本机 HTTPS 检查通过。构建中的 pip root、CA rehash、UID 与推荐容量提示未阻断本次升级；具体含义见[FAQ](FAQ.md)，证据与尚未验收的转存／外网／回退范围见[脱敏记录](development/V143-ACCEPTANCE.md)。

v1.4.3 已正式发布：辅助 A `cace622ffbbcecd28db7b00a29c26901e8fa139d`、入口 B／Tag `5aaf6a9b158d785ffa2fee52750c022fb8654810` 各五项 CI 与[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39901152742)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要核验通过。 新清单带齐标准库 helper；业务数据库迁移至 schema 2，升级前须备份，不能只降级镜像回退。下面保留 v1.4.2 历史发布与实机记录，不外推本版。

v1.4.2 已正式发布：辅助 A `840472f919409531e99da55c62070ea262ebed6d`、入口 B／Tag `42e2c372823a085c36a7a7597ce775441598aaf9` 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39592291162)全部通过，实际源码包、SHA256 和 GitHub 摘要已核验。三个在线入口固定 A 并带齐递归清单；新增[复用已有 Docker Nginx](DOCKER-NGINX.md)，需显式授权，不改变默认 managed 模式。

2026-10-21，专用 Debian13／AMD64 测试机完成 CloudDrive2 v1.3.4 → v1.4.2 人工保留配置升级，健康、历史数据、只读 WebDAV 和外部 HTTPS 检查通过。原 Release／Tag 已删除，在线自动升级先安全停止；用户授权核验原提交、备份后调用正式升级核心，详见[独立记录](development/V142-ACCEPTANCE.md)。该路径不是自动升级缺失基线问题已修复；真实转存、OpenList、新增 external_docker 接入、ACME、长期续期和迁移仍需分别验收。

历史 v1.4.1 已正式发布：辅助提交 A `3d222b90599f777d7646ff14ccebe466b25ad7eb` 与固定入口 B `dde550bc7fa6047ddcc945ef82131962611fec05` 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39525213331)全部成功，实际源码资产已下载核验。三个入口包含下述 NAT 预检修复，业务仍只取正式稳定 Release。开发审计的 uv／certifi 已限定修复，Bot 运行依赖与镜像不变。

2026-10-21 用户实机反馈：CloudDrive2 v1.4.1 在 Ubuntu26.04.1／原生ARM64／公网NAT 完成首次安装、Bot健康、本机HTTPS与WebDAV验收。APT源问题由用户先备份修正后重试成功；完整范围与未覆盖项目见[验收记录](development/V141-ACCEPTANCE.md)。该结论不是 OpenList 或已有实例升级／回退通过。

v1.4.0 已正式发布：三个主入口固定辅助提交 A `1480fd60ad94bd841961a4932a3b03e4cfde4414`，A／入口 B 各五项 CI、[同标签原生 AMD64／ARM64 发布检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39426176679)全部通过，实际源码资产已核验。业务代码只取正式稳定 Release，不用 main 业务源码代替；Oracle／真实 VPS 验收由用户发布后执行。

TG2Cloud 后续以 Linux 一键脚本为主入口，Windows 部署器停留在 v1.2.1。`install.sh` 是公网 VPS 入口，复用现有 Docker 安装、配置保留、备份、回退、HTTPS 与 WebDAV 验收流程，不另建一套 Bot 或 Compose 实现。

家庭内网 / NAS 的无域名安装请参阅独立的 [LAN 安装脚本](LAN-INSTALL.md)，具体 NAS 环境仍需验收。不要在公网 VPS 上用 LAN 脚本跳过 HTTPS，也不要把本页 `install.sh` 的域名输入替换成内网 IP。

> 当前正式版本为 v1.4.5，源码包和校验清单已发布。本脚本不依赖 EXE；向导固定到已验证 commit，业务代码只取正式稳定 Release。2026-10-17，CloudDrive2 旧测试候选经授权备份、人工核对后迁移到 v1.3.0，用户确认升级后使用验收通过。该历史记录与本页新增的 v1.4.1 ARM64 首装记录分别理解；正式版自动升级与回退仍需对应版本独立验证，OpenList 脚本实机验收暂缓。详见[历史迁移记录](development/V130-ACCEPTANCE.md)。下载入口或 EXE 不会自动更改已部署实例。

2026-10-19 补充：专用测试机已完成 CloudDrive2 正式 v1.3.2 → v1.3.3 保留配置升级，用户确认实际转存验收完成。该结论限此 Edition 和此次路径，不扩展到 v1.3.4、首次安装、OpenList 或故障回退。

## 公网 NAT 的已知限制与待发布修复

已发布 v1.4.0 的 HTTPS 检查要求域名地址匹配网卡地址，Oracle 等公网映射到私有网卡的主机可能误报 DNS 失败，即使 A 记录正确、80／443 空闲。不要将公网 A 改成私有网卡地址，也不要为此关闭防火墙或停止其他项目。

v1.4.1 增加交互确认：仅在单一公网 A、所有 AAAA 均匹配本机、没有其他公网 IPv4 网卡且端口归属安全时，要求手动输入**云控制台分配给本机的公网 IPv4**，与 A 记录比对后再确认映射。不会从 DNS 自动填写或通过第三方查询出口 IP。留空、拒绝确认、地址不一致均停止。该确认仅保留在当前进程，重新操作须再次核对；它不是自动证明入站映射，后续 ACME 和 HTTPS 自检仍须通过。

此修复已进入 v1.4.1 正式资产与匹配在线 helper；重新运行本页公开命令可获得新版向导。独立外部 WebDAV 和 `tg2cloud` 的 HTTPS 修复也需显式更新到本版代码，既有离线命令不会自动更新。NAT 不影响 CPU 架构检测；本次 CloudDrive2 ARM64 首装已收到用户验收，其他版本／场景仍单独验证。章节原标题保留以兼容既有链接，不表示当前版本仍未发布。

## 支持范围

v1.3.0 已发布 `src/tg2cloud` 新布局；本地可运行 `python3 scripts/run_source.py install --help`。在线一键命令 URL 不变，使用本版已验证 helper pin 和正式稳定 payload；修改本地源码或仅推送文档不会更新 VPS。迁移与本地预检说明见[Linux 重构](development/LINUX-REFACTOR.md)。

v1.3.1 的[外部 WebDAV](external-webdav.md) 是独立可选入口，主安装不增加询问。附加功能启用后共享代理为 schema 2，后续管理和主卸载须使用匹配的新脚本；主卸载前先独立 uninstall 附加入口，不删除网盘文件。

| 场景 | 行为 |
| --- | --- |
| 全新 VPS | 选择 Edition，收集信息，预检，确认后安装 Docker 环境、基础服务及强制 HTTPS |
| 完整的已有 TG2Cloud | 识别目录、Compose 身份、持久化挂载和版本，复用现有配置升级所选 Edition |
| 已是最新稳定版 | 不重建、不重启；可以另行确认 HTTPS 续做或 WebDAV 验收 |
| 当前版本高于 latest | 不降级；停止隐式 HTTPS 变更 |
| 两个完整 Edition 同时存在 | 明确选择一套；`--edition both` 仅用于显式升级两套，依次执行，不是跨 Edition 原子事务 |
| TG115、残留目录、部分容器、同名外部容器 | 停止，不覆盖、不自动迁移或接管 |
| 手工修改过程序、Compose 或 Dockerfile | 停止，请先人工核对；不提供强制覆盖参数 |
| 新稳定版更换云网关镜像 digest | 停止自动升级；不隐式迁移 OpenList/CloudDrive2 数据库，先备份并在隔离环境验证网关迁移；不使用旧 EXE 绕过检查 |

正式 v1.4.1 面向 Debian/Ubuntu 原生 AMD64／ARM64，两架构共用检查和入口，仍要求 root、64 位用户态、Python 3.10+、Bash 和可交互终端。匹配 helper 与稳定包均已发布核验；CI 通过不等于 Oracle 或任意 NAS 实机通过。镜像证据、Oracle Cloud 与验证结果见[双架构说明](ARCHITECTURES.md)。系统需有可用 CA 根证书和时区数据库，CloudDrive2 仍需 `/dev/fuse`，内存和磁盘检查不变。

缺少 Python 时请先自行确认系统环境，并安装 `python3`、`ca-certificates`、`tzdata`。脚本不会在信息收集与确认前自动安装软件。APT/Docker 的安装权限只在首次基础安装的最终确认后交给现有安装器；升级要求已有 Docker daemon 和 Compose 可用，不自动升级 Docker 引擎。

## VPS 单行安装命令

以 root 登录 VPS，在 Bash 可交互终端运行（需 Python 3.10+、curl 和系统 CA 证书）：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

不带参数时先选择 Edition，随后识别全新安装或已有实例。脚本不会在收集信息、预检及最终确认之前安装软件或修改实例。当前仍建议先在专用测试 VPS 使用。

HTTPS 预检还需要宿主机的 `ss`、`ip`（`iproute2`）、`getent`、`flock` 和 `timeout`。缺少工具时会列出名称及对应安装命令，不会当作 DNS 错误，也不会在预检阶段自动安装软件。确认执行后的基础安装依赖包含 `iproute2` 和 `python3`；共享代理备份兼容宿主 Python 3.10。

只检查 CloudDrive2，不安装／升级：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

检查通过后，再运行 CloudDrive2 安装／升级向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

只检查 OpenList，不安装／升级：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --check
```

检查通过后，再运行 OpenList 安装／升级向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist
```

两套命令只操作所选 Edition；全新 VPS 收集信息后安装，完整已有实例保留配置升级。OpenList 脚本实机验收仍暂缓，请先在专用测试 VPS 验证；`--check` 通过不等于安装或升级成功。

进程替换 `<(...)` 不占用交互标准输入；向导仍通过 `/dev/tty` 隐藏读取秘密。不支持用 `curl | bash`、无人值守管道或命令行参数传入密码。

这类命令会立即执行从仓库下载的代码，只有信任仓库和维护者时才使用。不希望直接运行远程代码时，可先下载、检查，再运行：

```bash
curl -fSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh -o tg2cloud-install.sh
less tg2cloud-install.sh
bash ./tg2cloud-install.sh --edition clouddrive2 --check
bash ./tg2cloud-install.sh --edition clouddrive2
```

不要覆盖自己已有的同名文件。网络、API 限流或下载校验失败时停止，不安装替代代码。`curl -f` 会显示 HTTP 下载错误；若首段脚本未下载成功，不会进入向导，即使外层 Bash 的退出码是 0 也不代表安装完成。

## 从本地源码试用

在 VPS 上进入包含这些新增文件的源码目录，以 root 运行：

```bash
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
bash ./install.sh --help
bash ./install.sh --edition clouddrive2 --check
bash ./install.sh --edition clouddrive2
```

OpenList 使用 `--edition openlist`，其脚本实机验收仍暂缓。不指定 Edition 时出现选择向导。已有两套完整实例可使用 `--edition both`；不支持一次向导在全新 VPS 批量安装两套。

`--check` 只读运行实例及 HTTPS 状态，不收集秘密、安装软件或修改运行配置。它仍会访问公开 GitHub API 并在私有临时目录下载源码，因此需要网络和一定的临时磁盘空间。检查通过不代表 WebDAV、HTTPS 公网访问或 Telegram 实际转存已验收。

### 旧版本 Release／Tag 已删除

v1.4.3 已增加四个受支持旧版的[可信目录](development/MAINTENANCE-IMPROVEMENTS.md#1-旧版本可信基线)，旧 Release 删除时仍核对原提交和载荷。未知版本继续要求正式基线。下面保留 v1.4.2 当时的限制与人工验收记录，不要下载任意 SHA 或绕过源码核验。

当前向导需要核验已安装版本的正式源码基线。若该版本的 GitHub Release 或 Tag 已删除，旧版本查询可能返回 404 并在升级前停止；即使版本号、容器和现有服务正常，也不能据此跳过基线检查。先保留原实例，不卸载、不改版本标记、不从未知来源覆盖代码。

应先保存配置、数据库一致性快照、Session、必要网关配置和共享代理备份，再由维护者单独审阅可追溯的原提交与目标正式资产。本次 v1.3.4 → v1.4.2 按明确授权完成了这条人工路径，见[验收记录](development/V142-ACCEPTANCE.md)；它不是新增的自动接管功能，不提供通用强制升级参数。升级后同版本在线 `--check` 通过，也不代表升级前缺失的 Release 已恢复可用。

### 终端输入错误

若旧向导在显示正式 Release 后立即报 `File or stream is not seekable.`，这是交互终端打开方式的兼容问题，不是 Docker、HTTPS 或 WebDAV 部署失败。该错误发生在升级计划及最终确认之前，尚未执行安装/升级，不需要卸载或删除已有数据。

终端修复只影响独立向导，不要求重建 EXE 或改写已有 Release。单行入口固定到不可变向导 commit，只有维护者将入口 pin 更新到通过 CI 的修复提交后，重新下载才会使用修复；不要通过删除实例、改为无人值守管道或跳过确认绕过错误。

目标 payload 始终来自 GitHub 最新正式稳定 Release 的源码，不是本地工作树或 `main`。v1.3.0 起已包含脚本和模块化源码；未来从本地试用新向导时，也不会把尚未发布的业务代码装到 VPS。

### APT 软件源错误

如果执行确认后停在“安装基础软件”，并提示没有 Release 文件，先区分系统 APT 与 TG2Cloud 容器问题。在自己的终端直接运行 `apt-get update` 复现原始错误；它更新软件包索引，不执行软件安装或升级。

核对当前系统使用的活跃源文件（通常为 `/etc/apt/sources.list`、`/etc/apt/sources.list.d/*.sources` 或 `*.list`），尤其是 URI 的协议、主机名与路径，以及 Suites 的发行代号和 Signed-By。`.bak` 文件不等于活跃配置。先备份具体文件，只修正已经确认错误的条目；不整份覆盖源列表、不混用发行代号、不删除安全更新源或关闭签名验证。

本次 Ubuntu26.04.1 ARM64 用户反馈中，源文件实际为 `https:///ubuntu-ports/`，APT 输出为 `https:/ubuntu-ports`；日志地址可能经过格式化，不能只按其缩写精确搜索就认定源文件无误。用户备份并修正缺失主机名的 URI 后，索引更新成功，再运行原安装入口完成验收，见[v1.4.1 记录](development/V141-ACCEPTANCE.md)。这是该主机的系统配置修正，不是脚本自动换源功能。

分享排查信息前移除私有源账号、令牌和全部建号密码。APT 失败或终端提示交错时，不通过删除数据库、Session、整个安装目录或批量结束 Python 进程“修复”；先核对实际失败阶段与对应进程。本次重跑未复现此前的提示交错，不代表其根因已被代码修复。

### 候选镜像源码权限错误

若升级在候选镜像预检时报 `PermissionError: [Errno 13] Permission denied`，且路径是 `/opt/tg115/app/__init__.py` 等程序文件，这是公开源码的权限问题，不是 Telegram、WebDAV 凭据错误，也不表示安装到了旧 TG115 宿主机目录。旧镜像沿用了这个容器内部程序路径。

此次源码修复为两 Edition 的公开 Docker 构建文件设置 `644`、子目录设置 `755`，外层临时目录仍为 `700`；候选配置仍在构建上下文之外，权限为 `600`。Dockerfile 也确保复制进镜像的 `app/` 对非 root Bot 用户可读，并继续由 root 拥有。不要把 Bot 改为 root，也不要对配置、数据或整个安装目录执行 `chmod 777`。

此处失败发生在候选校验阶段，尚未进行旧 Bot 停止和程序替换；前面的 APT 依赖检查、Docker 服务启用、临时目录和镜像构建可能已经执行。不要因此删除数据库、Session、云网关数据或重新授权云盘，请先查看原实例状态，再使用已发布的修复重试。

v1.1.4 源码同时把新镜像的程序目录改为 `/opt/tg2cloud`，容器用户/组改为 `tg2cloud`，日志名称改为 `tg2cloud` / `tg2cloud.log`；数字 UID/GID 仍为 `10001:10001`。持久化 `tg115.db`、`bot.session`、既有环境兼容变量和校验临时文件前缀不改名、不删除，旧日志也保留。宿主机安装目录、容器名称、HTTPS 和传输流程不变。

这些修复随 v1.1.4 源码提供，不代表旧版本 EXE 已包含修复。公开向导只有在 CI 通过后更新不可变 pin 才能使用脚本权限补丁；新的镜像命名随正式 v1.1.4 Release 发布。已发布 Tag 应保持不可变，使用新补丁版本，不删除并重建同名 Tag，否则已安装实例的官方源码校验可能失败。若原版本 Tag 已被删除而无法核对官方基线，脚本会停止，请保留实例和备份人工核对，不用新 Tag 冒充旧版本源码。

## 入口与稳定部署版本

单行命令从 `main` 获取轻量 Bash 入口；必要的公开 Python 向导模块固定到不可变源码 commit，不逐文件追随移动的 `main`。v1.3.0 向导包含磁盘推荐；准确的辅助源码身份由三个入口中的 `installer_commit` 给出。新向导先经过 CI，再更新三个入口的 pin；源码发布检查会拒绝 pin 与新版本辅助文件不一致的情况。业务 payload 仍只取最新正式稳定 Release。

v1.4.1 的三个入口固定向导 commit 为 `3d222b90599f777d7646ff14ccebe466b25ad7eb`，模块版本为 `1.4.1`；辅助 A 与固定入口 B 各五项公开 CI、同标签发布检查均通过。正式 payload 来自 v1.4.1 标签提交 `dde550bc7fa6047ddcc945ef82131962611fec05`，源码包与实际 SHA256 已下载核对。正式 payload 的 Tag commit 与向导 commit 分别核对，不要求两者相同；发布不等于本版 VPS 已升级验收。

历史 v1.3.4 向导 commit 为 `72be98e6b15075f71c58dd6ee110e47db2f42ce0`，Tag 为 `ef35d133a9e25572ff5f8363819d5c8e8984e74c`；历史资源不覆盖。

历史 v1.3.3 的向导 commit 为 `ea43d845b7f4c7185166a7474ef30e44ba2af8df`，模块版本为 `1.3.3`；该辅助提交的五项公开 CI 已通过，历史 Tag 和资产不修改。

历史 v1.3.0 的辅助提交仍为 `ee6feef5cfd35e50c315cddf91ab0cb35c40a384`，Tag commit 为 `27874c12c6166e12f2f57759199576cffb9f3234`；不改写旧版，也不用旧辅助工具覆盖 schema 2 代理。

这是向导源码身份，不是要部署的 Bot 版本。独立脚本另行通过 GitHub `/releases/latest` 排除草稿及预发布，解析正式 Tag 到不可变 commit；所有实际安装的 payload 来自这个正式 commit。向导会核对 Tag、commit 和 payload 版本。Release Tag 在引导后变化、API 限流、辅助模块缺失或版本不匹配时停止；不会退回 `main` 或 RC 的业务代码。

因此已有 `v1.1.2` Release 不必包含新增脚本，单行入口也不需要构建或替换 EXE。仍不要从旧 `v1.1.2` Tag 下载 `install.sh`。从本地源码运行时使用该 checkout 的向导代码，部署目标仍只取正式稳定 Release。

下载使用系统 HTTPS 校验，源码身份固定到 commit。v1.2.1 的 `SHA256SUMS.txt` 校验 Windows EXE；后续脚本版发布工作流生成源码归档校验清单。当前向导不读取该资产清单，不宣称新增了签名验证。仓库和发布账号仍是信任边界。

## 首次安装

### v1.3.2 安装与管理交互

v1.3.2 的公网／内网入口不带参数时进入新版向导；业务 payload 仍只取正式稳定 Release，不部署 main 或预发布 Bot。本地运行 `bash ./install.sh` 同样有效。在线入口必须按[发布门槛](development/LINUX-REFACTOR.md#递归指纹与发布门槛)先验证 helper A，再更新入口 B 的 pin 和清单；已部署主机需显式运行向导确认更新。

不带参数的公网／内网入口先选择 Edition：未安装则确认进入其安装向导；已有实例则打开统一管理菜单，可按名称选择“卸载当前实例”，不必另找卸载命令。正式 v1.4.3 为 9，v1.4.4 新菜单为 14，须更新离线工具才会变化，完整说明见[运维菜单](OPERATIONS.md#本地管理菜单)。已保存的公网／内网模式优先于入口名称，不会隐式转模式。v1.4.7 移除根目录独立卸载脚本；卸载预检、全 Edition 和数据保留参数仍可用 `tg2cloud uninstall --edition all --check` 等子命令调用同一核心。快捷命令损坏时重新运行原安装入口，选择已安装实例的卸载项，不选择重新安装。

- Edition 使用编号选择；版本提示不显示提交摘要，实际 commit 仍保存在引导元数据并校验。
- WebDAV 用户名提示为“回车默认 tg2cloud”；手动填写的值原样使用。密码隐藏输入，回车生成 **8 位**大小写字母与数字，手动密码仍可使用更长值。只改变 Bot 默认 WebDAV 密码，不改变 OpenList 初始化管理员密码和外部 WebDAV 的密码策略。
- “Bot 保存子目录”可留空，表示使用该 WebDAV 账号根目录；账号根目录由用户在后台设置，不推断成 VPS 路径或固定网盘目录。
- 新安装固定默认 `Asia/Shanghai`，不再询问时区；升级保留已有 `.env` 原始字节，包括原时区、密码和预算。
- 计划确认后安装私密、不可变的离线管理代码及 `/usr/local/bin/tg2cloud`。命令或运行目录被未知程序占用时停止，不覆盖；取消与 `--check` 不安装它。基础安装失败后，已安装的命令可用于核对状态，但身份不完整的实例仍会拒绝维护，不自动修复。
- 首次 HTTPS 成功后，建号凭据汇总到当前私有终端，不重复询问是否显示，也不写入普通日志。已有实例的“查看凭据”和 `--show-credentials` 仍逐项确认。避免录屏、旁观或分享终端内容。
- 跳过 WebDAV 验收会明确提示未执行；容器或 HTTPS 健康不等于转存通过。下次直接输入 `tg2cloud`，菜单及限制见[运维说明](OPERATIONS.md#本地管理菜单)。

显式 `--edition`、`--check` 等旧参数继续提供原有结果标记；自动化不应解析新版人类可读文案。新版默认交互及管理菜单调用安装器时安装离线命令，已有实例没有它时可从新版源码运行 `python3 scripts/run_source.py manage`。未选择实际安装/升级的已有最新实例，也可单独确认只安装管理命令，不重启容器。

### 已发布向导的流程

1. 选择 CloudDrive2 或 OpenList。
2. 填写管理域名和可选 Let's Encrypt 邮箱。A/AAAA 必须正确直指 VPS，首次签发时 Cloudflare 使用“仅 DNS”。检查 80/443 是否能安全使用；公网防火墙与 ACME 可达性仍需用户确认。
3. 向导先读取资源，选择流式优先、均衡或手动方案，再收集 Telegram 和 WebDAV 信息。新装时区默认 `Asia/Shanghai`，不再单独询问；秘密隐藏输入，Bot WebDAV 密码留空生成 8 位。
4. 任务预算不是磁盘分区，推荐数值由实际可用空间、Docker 分区、内存和 FUSE 条件计算；手动配置仍需通过检查，保留空间不低于 `8GB`。执行前再次探测，条件变化则停止。手动输入默认 `20GB/8GB`；升级保留原配置，不静默应用新推荐。见[切换说明](development/SCRIPT-FIRST.md)。
5. 查看不含秘密的计划，确认后执行。默认回答为取消。
6. 基础服务安装完成后使用既有共享 Nginx/Certbot 配置 HTTPS。后端仍仅回环监听，不开放 IP 加端口入口；公网 `/dav` 继续阻断。
7. 打开自己的 HTTPS 管理页，自行配置云存储，再创建填写过的专用 WebDAV 用户。TG2Cloud 不收集云盘 Cookie、OAuth 或 Token。两版具体权限与路径示例见[存储网关配置](STORAGE.md)。
8. 默认中文交互的新装流程会在当前私有终端集中显示后台建号所需的 WebDAV 信息及 OpenList 初始化密码，不再逐项询问；显式参数的兼容流程、升级后的查看凭据仍逐项确认。不会写入普通日志或重设已有管理员密码，请避免录屏或旁观。
9. 另行确认 WebDAV 写入验收。它会创建并清理随机测试文件，未确认则不执行。验收失败不自动反复重试；仍需在云盘官方客户端确认最终文件，并测试 Telegram 真实转存。

所有输入先在进程内收集；确认安装时才写入权限 `600` 的临时配置，并交给原安装器。Base64 只是避免 Shell 解析错误，不是加密。VPS 上的 `.env`、`rclone.conf`、备份仍是敏感文件，不要公开。

完成后按 [Bot 使用指南](BOT-USAGE.md)进行首次转存；运行管理、修改配置与排查入口见[运维指南](OPERATIONS.md)。

## 已有实例升级

```bash
bash ./install.sh --edition clouddrive2 --check
bash ./install.sh --edition clouddrive2
```

脚本读取 Docker/Compose 身份和绑定目录，核对实际运行代码与磁盘源码，再与当前版本的正式 Release 源码比较。Windows payload 的 CRLF 与 LF 差异不视为手工修改。

较早正式版本没有 `app/version.py` 时，只从 `app/__init__.py` 静态读取明确的 `__version__` 常量，不执行它的内容；升级计划仍要求全套程序与该版本官方源码一致。新版版本文件存在但无效时直接停止，不退回旧文件猜测版本。

升级不再询问 Bot Token、API Hash、WebDAV 密码。候选配置仅要求保留现有 `.env`；升级前后核对其原始字节。CloudDrive2 的现有安装器会规范化 `.env` 换行，因此该 Edition 的 `.env` 若含 CRLF/回车，CLI 会在写入前停止并要求人工核对，不擅自改成 LF。Session、SQLite、下载目录及云网关持久化目录保留，不清空、不重新授权云盘。

确认后，现有安装器复用 APT 基础依赖检查，可能更新相关系统软件包；不主动升级 Docker 引擎。随后做候选构建及隔离预检，保存程序备份、短暂停止所选 Bot 并创建 SQLite 一致性快照，再切换程序。健康检查失败时调用已有回退；请以回退日志和实例状态为准，不能保证所有外部故障都能自动恢复。CLI 自己不另写数据库恢复或网关迁移逻辑。

### 源码基线不一致时

出现“现有程序与已发布版本不一致”或额外/缺失源码时停止。版本号相同不代表代码相同；不要改版本文件、删 Session/数据库、关闭指纹校验或用旧 EXE 强制覆盖。先保存原程序、配置、数据库一致性快照、Session 和必要数据，再单独审阅差异及恢复方案。本次旧候选迁移属于经授权的人工处理，不是公开脚本新增的自动接管功能。

rclone 运行时可能重新混淆同一密码，导致 `rclone.conf` 字节变化；这与 `.env` 原始字节保留是不同检查。不能仅凭文件 hash 变化认定已改密，也不能忽略真正的 URL、用户或密码变化。仅在私有环境核对实际值，不将解混淆输出、完整配置或备份贴到 Issue；rclone 混淆不等于加密。

健康的已有 HTTPS 路由和证书原样保留；不切换域名、不重新签发，不重启未选中的 Bot。基础安装器仍可能对所选 Edition 的网关做既有的 Compose/网络操作；HTTPS 显式修复会操作共享代理，可能使管理页连接短暂中断。

新脚本的 Edition 锁只协调 CLI 之间的执行。共享 HTTPS 操作复用与 EXE 一致的代理事务锁；现有 EXE 基础安装器没有这个 Edition 锁，因此不要同时从 EXE 和 CLI 安装/升级同一实例。

## HTTPS 续做与验收

如果基础安装成功而 HTTPS 失败，保留已安装数据，不要删除容器或反复全新安装：

```bash
bash ./install.sh --edition openlist --configure-https
bash ./install.sh --edition openlist --verify
```

`--configure-https` 是明确的配置/修复授权，执行前仍需要确认。有已保存域名时只能沿用它，不提供隐式切换。已是最新版本时只续做 HTTPS，不重建 Bot。没有保存域名时才收集新域名。

首次 HTTPS 失败前生成的秘密已经由安装器保存到 VPS `.env`。v1.1.5 向导在 HTTPS 续做成功后再次提供逐项确认显示；也可单独查看已有凭据，不安装、不升级、不修复 HTTPS、不重置密码：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --show-credentials
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --show-credentials
```

每项默认不显示，仅在确认后写入当前私有终端，不进入普通日志。OpenList 显示的是保存的初始化管理员密码；如果后来在管理页改过密码，这不是当前密码。请避免旁观或录屏，不要把完整 `.env` 贴进日志、聊天或 Issue。该参数不能与 `--check`、`--configure-https` 或 `--verify` 组合。

公开单行入口固定到前文说明的不可变向导源码，包含这些修复和新参数；实际 Bot payload 仍只取最新正式稳定 Release。使用已下载的旧入口时，重新下载才能获得新向导；从本地 checkout 使用时，按该 checkout 的参数执行。

HTTPS 配置收到 Ctrl+C、TERM 或 HUP 时会尝试恢复原代理配置；状态提交与回退期间的重复信号会延后处理，保留原有命令超时。请等待退出后核对状态，不用强制杀进程加速；断网、断电、SIGKILL 或回退命令失败时仍可能需要人工恢复。已提交的新路由不会仅因提交结束时收到取消信号而恢复成旧运行配置。

`--verify` 仍需第二次确认，只有 HTTPS 自检健康才执行现有 `manage.sh verify`。返回 401、429 或业务错误不会触发自动改密、重装或循环验收。

状态结果区分：

- `TG2CLOUD_CLI_RESULT=NO_CHANGE`：未升级或重启。
- `TG2CLOUD_CLI_RESULT=CANCELLED`：用户取消，未执行计划内变更。
- `TG2CLOUD_CLI_BASE_HTTPS=OK`：基础服务及 VPS 本机 HTTPS 检查通过；不是公网或云盘验收结论。
- `TG2CLOUD_CLI_WEBDAV=NOT_RUN/OK`：独立写入验收的实际结果。
- `TG2CLOUD_CLI_RESULT=FAILED/INTERRUPTED`：停止后续操作；请核对备份、回退及当前实例状态，不假定已恢复。

无参数的统一菜单可按名称进入“卸载当前实例”，但核心安装器没有 `--uninstall` 参数，`manage.sh` 也没有 `uninstall` 子命令；菜单复用独立的[卸载核心](UNINSTALL.md)，不在升级流程中删除业务数据。不要用不存在的参数、手工删除目录或卸载来解决升级问题。旧 TG115 请参考[迁移说明](MIGRATION_FROM_TG115.md)。

## 停止并移除容器（保留数据，不是完整卸载）

标准安装目录下，可以在 VPS 上用下面的命令停止并移除所选 Edition 的 Compose 容器及项目网络。先确认没有进行中的传输，并做好必要备份；执行一条对应命令即可，不必同时移除两个 Edition：

```bash
# CloudDrive2
cd /opt/tg2cloud-clouddrive2 && docker compose down

# OpenList
cd /opt/tg2cloud-openlist && docker compose down
```

这里不使用 `--volumes`、`--rmi`、`--remove-orphans` 或目录删除命令。标准 TG2Cloud 的持久化数据使用宿主机目录挂载，`.env`、Session、SQLite、下载、云网关配置与备份仍保留；Docker 引擎和另一 Edition 不会由这两条标准项目命令卸载。`down` 的范围见 [Docker 官方说明](https://docs.docker.com/reference/cli/docker/compose/down/)。

**这不是完整的一键卸载**：共享 Nginx/Certbot、证书和已保存 HTTPS 路由仍存在，本节两条命令也不会移除独立 LAN 入口。需要统一移除受管资源与入口时，使用 [独立卸载向导](UNINSTALL.md)。当前主分支及在线增强版默认双重确认后清理所选数据与可识别备份，保留数据请明确加 `--keep-data`；不卸载系统 Docker / Nginx。用户已反馈原保留数据卸载在其 VPS 通过；完整清理仍待新的实机验证，在线只固定到通过 CI 的源码，不修改原 v1.2.0 Tag/EXE。请先只读预检，把必要备份保存到清理目录之外。

## 本地验证与待验收

新增离线测试覆盖 Release 选择、不可变 commit、归档解包安全、两 Edition payload 组装、与 GUI 配置格式一致、配置保留、实例冲突、版本判断、明确确认、HTTPS 和 WebDAV 结果边界。

源码权限修复另有 Linux 权限位测试及两 Edition 的真实 Docker 候选启动检查，分别覆盖正常 CLI 构建上下文和私有权限源码。Docker 检查通过 `TG2CLOUD_TEST_DOCKER=1` 显式启用，在分支和 Release Linux Job 中执行；容器不挂载生产数据、不连接 Telegram 或云存储。没有 Linux/Docker 的本地测试会明确跳过，不能视为镜像或 VPS 验收通过。

2026-10-09，CloudDrive2 专用测试机的实际 `--check` 通过：识别旧版 v1.0.2，核对官方旧版源码及运行指纹，固定最新稳定 v1.1.2 的源码 commit，完成容量和现有 HTTPS 自检，并生成保留配置升级计划。没有执行升级、重启或域名变更，检查前后容器标识与启动记录一致。这不是跨版本升级成功或云盘传输的验收结论。

OpenList 脚本实机验收暂缓。仅有网关、没有 Bot 的部分实例会安全停止，不自动当作全新安装覆盖；这不影响已发布 OpenList EXE 的既有验收结果。

2026-10-17，CloudDrive2 旧测试候选迁移到正式 v1.3.0，原生安装器切换和健康检查成功，历史任务及 Session 授权保留；代码指纹、本机/外部 HTTPS、只读 WebDAV 通过。在线 `--check` 复检识别为最新且不重建，用户随后确认使用验收完成。该实例不是官方旧版的逐文件一致基线，因此不能据此宣称标准正式版自动升级也已验收，完整证据和保留范围见[发布后验收记录](development/V130-ACCEPTANCE.md)。

Linux CI 和正式 Release 不再构建 EXE，分别执行对应回归与同 Tag 源码包校验。2026-10-19 的 CloudDrive2 正式 v1.3.2 → v1.3.3 升级已核对配置、任务、Session 与共享入口保留，用户确认实际转存完成；不是人工候选覆盖。2026-10-21 的[v1.4.1 ARM64 公网NAT 首装](development/V141-ACCEPTANCE.md)另有用户日志确认。中断／故障回退、NAS、OpenList、双 Edition 同时升级、长期续期及全部异常转存场景仍需独立验收。

## 参数、升级后检查与下一步

v1.4.4 源码在确认执行后增加日志分类、逐项结果摘要与一次只读业务就绪观察，原命令退出码、成功标记、WebDAV 确认和真实转存人工验收边界不变。旧 v1.4.3 入口及工具不含新增反馈，须升级为 v1.4.4 匹配的离线工具后才生效；完整用法见[安装日志与结果摘要](OPERATIONS.md#安装日志与结果摘要v144)。不重复调整已确认菜单，不改预算、配置、数据库或后端提交策略。

v1.4.2 提供[复用已有 Docker Nginx](DOCKER-NGINX.md)，由只读检测、明确授权和持久化条件决定是否接入，不停止原 Nginx、不增加第二层代理。新参数 `--proxy-mode`、`--nginx-container`、`--authorize-proxy` 的实际用法及支持边界见专题。原有 managed 实例不会自动切换。

| 参数／入口 | 用途 | 会不会修改实例 |
| --- | --- | --- |
| 无参数入口 | 编号选择 Edition，新装或进入已有实例菜单。 | 所选操作另行确认。 |
| `--edition clouddrive2`／`openlist` | 指定安装／升级对象。 | 展示计划并确认后执行。 |
| `--edition both` | 只用于两套完整已有实例。 | 确认所选计划后依次执行，不是一起回滚的事务。 |
| `--check` | 只读身份、版本、容量与已有 HTTPS 检查。 | 不升级；仍下载公开核验源码并占用临时空间。 |
| `--configure-https` | 显式续做／修复 HTTPS，已有域名不隐式更换。 | 确认后可能重载／重建共享代理。 |
| `--verify` | 使用现有配置执行 WebDAV 写入验收。 | 二次确认后创建并清理测试文件。 |
| `--show-credentials` | 私有终端逐项查看已保存凭据。 | 不升级／改密，不能与其他操作标志混用。 |
| `--install-dir /opt/自定义目录` | 单 Edition 的受支持安装／识别位置。 | 不搬迁数据；与其他受管路径重叠或身份不符会拒绝。 |

升级完成后核对：实际版本为目标正式版，Bot healthy 且不重启循环；配置、任务与 Session 保留；管理页在本机和外部网络均可访问；再用自己的小文件完成转存。后续再验证大文件、取消／恢复和家庭权限，不把一次正常转存写成全部场景通过。本次已执行范围见 [v1.3.3 记录](development/V133-ACCEPTANCE.md)。

完整字段和数据位置见[配置参考](CONFIGURATION.md)，独立备份见[备份与恢复预检](BACKUP-RESTORE.md)，命名规则见[命名指南](NAMING.md)，常见异常见 [FAQ](FAQ.md)。
