# Linux AMD64 / ARM64（v1.4.1）

2026-10-21：[v1.4.1 已正式发布](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.1)，修复下述公网 NAT 的 HTTPS 预检；支持范围、镜像和 Bot 依赖不变。辅助 A `3d222b90599f777d7646ff14ccebe466b25ad7eb`、入口 B／Tag `dde550bc7fa6047ddcc945ef82131962611fec05` 各五项 CI 与[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39525213331)全部成功，不能替代真实 Oracle 入站、ACME 或转存验收。

2026-10-20：[v1.4.0 已正式发布](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.0)。辅助提交 A `1480fd60ad94bd841961a4932a3b03e4cfde4414` 与固定入口 B `8bd4cf1fd7180f31579f5fe702d2c2d07c3b13f8` 各五项 CI、同标签双架构发布均通过，实际源码包与公开资产摘要已核验。业务只取正式稳定 Release，不下载 main 业务源码代替；Oracle／真实 VPS 验收由用户发布后执行。

## 支持范围

| 内核名称 | 标准架构 | Docker 平台 |
| --- | --- | --- |
| `x86_64`、`amd64` | AMD64 | `linux/amd64` |
| `aarch64`、`arm64` | ARM64 | `linux/arm64` |

仅 Debian / Ubuntu Linux、64 位用户态、Python 3.10+、root、本机默认 rootful Docker。沿用既有发行版检查与 APT codename 策略，内网仍要求 Docker Engine 28+。不支持 32 位 ARM、其他 CPU、Windows/macOS 部署、Docker Desktop、远端 daemon 或 rootless；不自动接管其他 context，不安装 QEMU。

两架构共用同一份 Bot、Dockerfile、Compose 和安装入口，不新增 ARM 专属配置。内核、Python 指针宽度、`dpkg --print-architecture`、Docker daemon 和实际镜像必须一致。显式的 `DOCKER_DEFAULT_PLATFORM`、`BUILDX_BUILDER`、远端 Docker/BuildKit 和 Compose 覆盖会被拒绝，避免误用模拟或其他项目配置。

安装脚本调用 `deployment/architecture.py`，不再另写 uname 分支。拉取并核验原生基础／网关镜像、构建候选后，才进入已有备份和切换流程。启动后检查容器实际 Image ID 的平台，保留 Bot 健康与网关 HTTP 检查；平台正确本身不代表 WebDAV、Telegram 或云端最终写入通过。

## 现用镜像证据

2026-10-20 直接查询 Docker Hub Registry v2：核验索引、两个子 manifest 与 config 的 SHA256 和 `linux/architecture`。没有拉取镜像层或运行容器。

| 用途 | 当前引用 | 核验结果 |
| --- | --- | --- |
| Bot Python | `python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` | OCI 索引含 amd64、arm64/v8 |
| CloudDrive2 | `cloudnas/clouddrive2@sha256:5491c21fb14a5774576515f8483ecdbe2780bf525985f426785b99488e7cc09d` | OCI 索引含 amd64、arm64 |
| OpenList | `openlistteam/openlist@sha256:c555c6e1c8af2aead38ed12ec761ac077fdf046d19cf033414be8e056aec6b64` | OCI 索引含 amd64、arm64 |
| HTTPS / LAN Nginx | `nginx:1.30.5-alpine` | 当前标签索引含 amd64、arm64/v8 |
| Certbot | `certbot/certbot:v5.8.0` | 当前标签索引含 amd64、arm64/v8 |

前三个固定 digest 不变；后两个沿用既有版本标签，并非新增 digest 固定。没有改成 latest、升级镜像或降低原有固定摘要保护。Nginx 标签本次解析为 `sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94`，Certbot 为 `sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20`；标签仍可能被上游重建，实际部署必须重新检查本机原生镜像。

三组固定镜像的原生子 manifest：

| 镜像 | amd64 | arm64 |
| --- | --- | --- |
| Python | `sha256:2b4f19dae3a777dfc3b76730bda1e82e1f66ab2a2686fa93ca78edbfb4f04ffe` | `sha256:16bf2b5c59a08523519d3c8589deca849285dee1d62a3653e124c3dba340f15e` |
| CloudDrive2 | `sha256:d9d1d97d886e0628df54b9ca67596e288d4a9beadccdb6dfb77e0d6ace6293f5` | `sha256:ae3e82d11d68e7f3a49645ff8f6a4692899a31ffae011f3d0ae5582189930cbb` |
| OpenList | `sha256:c942c98018ae219aeed5bff38e7f638964febe0eddccc68e856b1aeb17a16d2e` | `sha256:e259dcf7300d65cc6ae404cd78d660b08bd39f62ea594ae71d5d28b7fff51f91` |

## 依赖与权限

宿主 CLI 仍仅使用标准库。Bot Python 3.12、Telethon 1.45.0、cryptg 0.6.0、psutil 7.2.2 及两个哈希锁文件不变。PyPI 已核实 Telethon 通用 wheel、cryptg CPython 3.12 manylinux x86_64/aarch64 wheel、psutil CPython abi3 manylinux x86_64/aarch64 wheel；这些 wheel 的 SHA256 已包含在 Bot 锁文件。wheel 存在不是安装／运行验收。

镜像内 rclone、tini、CA 证书沿用 Debian 原生 APT；CloudDrive2 宿主 fuse3、kmod 亦按 `dpkg` 架构安装。不下载硬编码的 x86 二进制。两个原生 CI runner 已实际构建镜像并通过 cryptg 加解密、psutil、Telethon 导入、rclone version 检查。

CloudDrive2 保留 `/dev/fuse`、privileged、host PID 与挂载传播权限；OpenList 不因此增加 FUSE 或高权限。Bot 非 root、cap_drop、只读程序目录和回环后端端口不变。Ubuntu 26.04 的 Python 可能高于 CLI CI 的 3.13，本地单元测试不代替对应 Oracle 系统验收。

## Oracle Ampere A1 准备与验收

2026-10-21 实机反馈：原生 ARM64 环境检测已通过，但在只有私有网卡地址的公网 NAT 主机上，v1.4.0 的 HTTPS 预检会误报 DNS／端口问题。该反馈不代表安装或转存已验收。修复已进入 v1.4.1 正式包与匹配 helper，新增严格条件下的控制台公网 IPv4 人工确认；仍须通过 ACME、TLS 与用户实机验收，见[VPS 指南](VPS-INSTALL.md#公网-nat-的已知限制与待发布修复)。

新源码在严格候选条件下允许用户独立输入并确认云控制台的公网 IPv4；不自动查询出口 IP，不改网卡、DNS、防火墙或代理所有权。确认仅存于内存，绑定本次域名、DNS 和原有网卡地址，增加受管 Docker 网桥不使它失效，地址移除／DNS 或域名改变则停止复用。错误 AAAA、多 A、其他公网 IPv4 网卡和不安全端口不能走此分支；无交互确认仍按原规则拒绝。新 helper 与正式源码发布、NAT 入站 ACME 和两网关实机仍须后续验证。

Oracle 的 [VNIC 元数据](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingVNICs.htm)提供私有网卡信息，不能凭此假定已经取得并核实公网 IPv4 映射。此实现不请求云账号权限、不安装 OCI CLI、不读取云凭据。

Ubuntu 24.04 / 26.04 ARM64、Debian ARM64 是本次目标；**本轮未登录或部署 Oracle／真实 VPS**。先在服务商控制台确认自己的系统、磁盘与安全组，登录后只读检查：

```bash
uname -m
getconf LONG_BIT
dpkg --print-architecture
python3 --version
test -c /dev/fuse && echo FUSE_DEVICE_OK
docker version
docker compose version
docker info --format '{{.OSType}}/{{.Architecture}}'
```

ARM64 应为 aarch64/arm64、64、arm64、Linux arm64 daemon。尚未安装 Docker 时，最后几条不可用是预期；正式首次安装仍只在确认后配置官方 APT，不主动升级已有 Docker。CloudDrive2 缺少 `/dev/fuse` 时应先核实 Oracle 内核 FUSE 模块、宿主权限，不通过随意创建设备或移除安全检查绕过。OpenList 安装不要求 FUSE。

确认 CPU 原生、资源足够、DNS A/AAAA 指向正确公网地址、80/443 可达。脚本不为本次兼容改动自动调整 Oracle 安全组、系统防火墙或服务商网络。

包含本次改动的正式稳定版及匹配 helper 发布后，安装命令仍相同：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

OpenList 将 edition 换为 `openlist`。`--check` 仅预检，不部署；正式向导完成后，核对实际管理 HTTPS、Bot 健康、存储挂载、专用 WebDAV 写入和小文件转存，再按[恢复与验证](RECOVERY.md)测试大文件、流式、取消和重启。最终在云盘官方客户端确认文件。隔离 HTTP smoke 不覆盖真实网盘挂载传播、账号、ACME、手机或升级回退。

内网仍使用 `install-lan.sh`，填写本机私有 IPv4；外部只读功能仍使用独立 `install-webdav.sh`，不进入主向导。不改变 HTTPS、只读权限和凭据边界。

## 本地验证与发布门槛

可先在完整源码中执行标准库帮助和离线回归；在目标原生 Linux 上可运行架构诊断：

```bash
python3 scripts/run_source.py install --help
PYTHONPATH=src python3 -B -m tg2cloud.deployment.architecture host
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_architecture.py -v
```

原生隔离 Docker CI 使用 `ubuntu-24.04` 与 `ubuntu-24.04-arm`，不设置 QEMU。完整 Bot／传输回归、两 Edition 非 root 候选、网关 HTTP／FUSE、Nginx／Certbot、外部 DAV Range 及 LAN 入口均在各自原生 runner 执行；CLI Python 3.10/3.13 亦覆盖两个 runner。网关 smoke 仅用随机命名的新容器与空卷，不登录网盘；FUSE 共享挂载的真实读写另行验收。条件缺失必须失败或明确未运行，不写成实机通过。

Release 等待两个原生 job 成功，但只生成和上传一次与 CPU 无关的源码包。历史 immutable Tag 按当时能力仅重跑 AMD64，不改写历史 ARM 支持事实。

### v1.4.1 实际验证（2026-10-21）

- 本地完整894项：867成功、27环境条件跳过、0失败；Python3.10宿主／NAT专项21项全部成功，无Bot依赖的CLI帮助通过。仓库48项、发布包11项、网站19项与33HTML／3655内部引用、ShellCheck、Ruff、compileall和Bandit通过。
- 首轮辅助 CI 检出两项开发依赖漏洞；仅更新 uv0.13.4、certifi2026.10.19，统一生成哈希锁，Bot锁无差异。两个锁文件的 pip-audit 无已知漏洞，不忽略或关闭审计。
- 最终辅助 A 的[双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524547503)与[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524551589)、入口 B 的[双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524969669)与[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524969765)全部成功，A／B各自仓库、文档和网站也成功。同标签发布的两个原生验证与release job全部成功；含隔离LAN、外部DAV／Range、两Edition候选及网关HTTP／FUSE，不使用QEMU或真实用户目录。
- 实际下载 `TG2Cloud-v1.4.1-source.tar.gz` 的 SHA256：`2f0f75f11c7e1ad4debc4bf3221732e26c4f2d213863cd0a875a9672db509249`；清单摘要 `d2928cd3a1f604d8ea06f5441f3a4e1087808e5211d22627888f9c78248c7945`。`source_release.py verify`、同次清单与GitHub公开digest一致；只有这两项正式资产，没有EXE。校验和不是数字签名。
- 没有连接或修改VPS、没有创建真实Session或写入网盘。NAT人工确认只是操作员核对，不自动证明公网可达；Oracle Ubuntu／Debian ARM64安装、ACME、真实挂载与转存、手机和故障回退仍待用户执行。

### v1.4.0 历史验证（2026-10-20）

本机为 Windows，下面不属于原生 Linux／ARM64 验收：

| 检查 | 实际结果 |
| --- | --- |
| Python 3.13 `check_python.py all` | 880 项，853 执行成功／27 环境或显式集成条件跳过／0 失败；公共文件、Ruff、compileall 通过 |
| Python 3.10 CLI 标准库回归 | 408 项，396 执行成功／12 环境条件跳过／0 失败；最终新增架构 15 项另行复验通过 |
| Shell | 四个现有入口、三个候选入口、两版 hooks 的 ShellCheck／Bash 语法和 21 项部署回归通过 |
| 载荷／发布基础 | 两 Edition 各 84 个源码模块与当前清单逐字节一致、共享指纹一致；版本、Release Notes 格式、候选 bootstrap 与 Bandit 通过 |
| 网站 | Node.js 22 构建、19 项测试、33 HTML 页面／3652 内部引用检查通过 |
| 原生 CI | 辅助 A、入口 B 与同标签的 AMD64／ARM64 Bot 构建、原生扩展／rclone、两网关 HTTP／FUSE 和外部 DAV／Range 均通过；A／B 四组 CLI、仓库、网站及文档也通过 |

本地 Windows 没有 Docker daemon／Linux rclone，27 项跳过如实保留；对应的原生集成在 GitHub 两个原生 runner 上另行通过。首轮新测试的空命名卷 copy-up 重置属主问题已修正，只调整隔离卷的 volume-nocopy，不修改生产权限或跳过测试。Oracle Ubuntu 24.04／26.04 与 Debian ARM64、真实 Telegram／云存储、挂载传播读写、HTTPS ACME、外部手机及升级回退仍未实机验收。

### 正式发布核验

- 辅助 A 的[双架构运行](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39424410971)、入口 B 的[双架构运行](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39425830276)与[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39425830192)均成功；另三项仓库／文档／网站检查也成功。
- [v1.4.0 同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39426176679)的两个原生 job 和发布 job 均成功；只在 AMD64 job 打包一次平台无关源码，不发布 EXE。
- 正式 `TG2Cloud-v1.4.0-source.tar.gz` 实际 SHA256：`5e701f3a61dc99cd9e8ce996958ce019954aff5b4ae1eee10b3a92d116734302`。实际下载核验通过 `source_release.py verify`、同次 SHA256 清单与 GitHub digest；校验和不等于数字签名。Windows 本地重打包只作候选检查，不拿其校验值替代 Actions 产物。
- 三个入口固定真实 A 的 SHA 与匹配清单，严格 pin 校验通过；外部 WebDAV 从正式稳定资产加载新模块。未覆盖历史 Tag／Release、未连接真实 VPS、未创建新 Session 或迁移数据库。

后续发布仍须先公开并验证辅助 A，再生成固定 A 的入口 B，待 B 和同标签检查成功才发布；不使用伪造、自指 pin 或 moving main。用户将执行 Oracle Ubuntu 24.04／26.04、Debian ARM64 及真实云存储安装／升级／转存验收，结果另行记录。

已有 AMD64 的目录、`.env`、`data/tg115.db`、`bot.session`、rclone 配置、容器身份、备份和升级回退保留，不新增数据库迁移或用户环境变量。此前使用远端 context／强制异平台镜像的环境将被明确拒绝，不视为受支持的旧实例。不能通过把磁盘或数据库复制到另一架构直接宣称完成跨 CPU 迁移。

参考：[GitHub 原生 runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[Docker Ubuntu 安装](https://docs.docker.com/engine/install/ubuntu/)、[镜像索引检查](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/)、[cryptg 固定版本](https://pypi.org/project/cryptg/0.6.0/)、[psutil 固定版本](https://pypi.org/project/psutil/7.2.2/)。
