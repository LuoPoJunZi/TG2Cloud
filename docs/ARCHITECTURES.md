# Linux AMD64 / ARM64（v1.4.0）

2026-10-20：v1.4.0 发布准备中，本地源码已加入统一原生检查；**正式下载仍为 v1.3.4**。当前线上稳定包和 helper 不包含本次改动。不能把下面的发布后命令当成当前 ARM64 可用性承诺，也不能下载 main 业务代码绕过稳定 Release 校验。

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

镜像内 rclone、tini、CA 证书沿用 Debian 原生 APT；CloudDrive2 宿主 fuse3、kmod 亦按 `dpkg` 架构安装。不下载硬编码的 x86 二进制。CI 中构建实际镜像并调用 cryptg 加解密、psutil、Telethon 导入、rclone version；这些原生 CI 仍需发布前实际运行。

CloudDrive2 保留 `/dev/fuse`、privileged、host PID 与挂载传播权限；OpenList 不因此增加 FUSE 或高权限。Bot 非 root、cap_drop、只读程序目录和回环后端端口不变。Ubuntu 26.04 的 Python 可能高于 CLI CI 的 3.13，本地单元测试不代替对应 Oracle 系统验收。

## Oracle Ampere A1 准备与验收

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

### 本轮实际验证（2026-10-20）

本机为 Windows，下面不属于原生 Linux／ARM64 验收：

| 检查 | 实际结果 |
| --- | --- |
| Python 3.13 `check_python.py all` | 880 项，853 执行成功／27 环境或显式集成条件跳过／0 失败；公共文件、Ruff、compileall 通过 |
| Python 3.10 CLI 标准库回归 | 408 项，396 执行成功／12 环境条件跳过／0 失败；最终新增架构 15 项另行复验通过 |
| Shell | 四个现有入口、三个候选入口、两版 hooks 的 ShellCheck／Bash 语法和 21 项部署回归通过 |
| 载荷／发布基础 | 两 Edition 各 84 个源码模块与当前清单逐字节一致、共享指纹一致；版本、Release Notes 格式、候选 bootstrap 与 Bandit 通过 |
| 网站 | Node.js 22 构建、19 项测试、33 HTML 页面／3652 内部引用检查通过 |
| 原生 CI | YAML 结构与离线矩阵回归通过，远端工作流未执行 |

没有本地 Docker daemon／Linux rclone，27 项跳过中包括新增网关 Docker smoke 和原有平台集成项；没有删除失败测试或增加无依据的 skip。尚未执行实际 Linux 镜像构建／Compose 运行、ARM64 原生依赖运行、Oracle Ubuntu 24.04／26.04 与 Debian ARM64、真实 Telegram／云存储、HTTPS ACME、外部手机及升级回退。不能将索引／wheel 元数据或模拟用例解释成这些项目通过。

发布前必须：

1. 提交本次源码 A，让原生双架构 CI 实际通过；按用户本次授权先发布 v1.4.0，再由用户执行 Oracle Ubuntu 24.04/26.04 与 Debian ARM64 的真实安装／升级／转存验收，结果另行记录。
2. 保持当前有效的 helper pin，先公开并验证 A，再产生入口 B：运行 `prepare_bootstrap.py --directory <新的候选目录>`，以实际公开 A 的 SHA 更新三个 helper 入口与版本，不允许伪造或自指 SHA。当前本地不更改在线 pin。
3. 外部 WebDAV 从正式稳定源码资产加载本包；必须随新 Release 一并包含新部署模块、runtime/bootstrap 清单、hooks 和共享代理代码。
4. 按授权选择下一个版本、同步版本元数据／网站，严格执行 `source_release.py` 的 pin 和校验清单检查后发布；不覆盖 v1.3.4 Tag／Release。

已有 AMD64 的目录、`.env`、`data/tg115.db`、`bot.session`、rclone 配置、容器身份、备份和升级回退保留，不新增数据库迁移或用户环境变量。此前使用远端 context／强制异平台镜像的环境将被明确拒绝，不视为受支持的旧实例。不能通过把磁盘或数据库复制到另一架构直接宣称完成跨 CPU 迁移。

参考：[GitHub 原生 runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[Docker Ubuntu 安装](https://docs.docker.com/engine/install/ubuntu/)、[镜像索引检查](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/)、[cryptg 固定版本](https://pypi.org/project/cryptg/0.6.0/)、[psutil 固定版本](https://pypi.org/project/psutil/7.2.2/)。
