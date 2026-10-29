# Linux 部署与兼容性

TG2Cloud 维护 Linux 一键脚本和 Docker Compose。下表区分已实现的平台检查、CI 与真实环境验收；同一架构上的构建通过不代表任意发行版、NAS 或实际网盘都已通过。

当前发布的源码、共享镜像与两版部署包证据见[本版记录](development/V153-ACCEPTANCE.md)。

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

2026-10-21 实机反馈：原生 ARM64 环境检测已通过，但在只有私有网卡地址的公网 NAT 主机上，v1.4.0 的 HTTPS 预检会误报 DNS／端口问题。该反馈不代表安装或转存已验收。修复已进入 v1.4.1 正式包与匹配 helper，新增严格条件下的控制台公网 IPv4 人工确认；仍须通过 ACME、TLS 与用户实机验收，见[VPS 指南](VPS-INSTALL.md#公网-nat-与域名检查)。

新源码在严格候选条件下允许用户独立输入并确认云控制台的公网 IPv4；不自动查询出口 IP，不改网卡、DNS、防火墙或代理所有权。确认仅存于内存，绑定本次域名、DNS 和原有网卡地址，增加受管 Docker 网桥不使它失效，地址移除／DNS 或域名改变则停止复用。错误 AAAA、多 A、其他公网 IPv4 网卡和不安全端口不能走此分支；无交互确认仍按原规则拒绝。helper 与正式包已发布核验，用户本次 CloudDrive2 首装及证书流程通过；OpenList 及其他主机仍须单独验收。

Oracle 的 [VNIC 元数据](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingVNICs.htm)提供私有网卡信息，不能凭此假定已经取得并核实公网 IPv4 映射。此实现不请求云账号权限、不安装 OCI CLI、不读取云凭据。

Ubuntu 24.04 / 26.04 ARM64、Debian ARM64 是支持目标。本次用户记录只覆盖 Ubuntu 26.04.1 的一台主机；维护代理未登录或部署该 VPS，不外推其他发行版。先在服务商控制台确认自己的系统、磁盘与安全组，登录后只读检查：

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

使用当前正式稳定版的安装命令：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

OpenList 将 edition 换为 `openlist`。`--check` 仅预检，不部署；正式向导完成后，核对实际管理 HTTPS、Bot 健康、存储挂载、专用 WebDAV 写入和小文件转存，再按[恢复与验证](RECOVERY.md)测试大文件、流式、取消和重启。最终在云盘官方客户端确认文件。隔离 HTTP smoke 不覆盖真实网盘挂载传播、账号、ACME、手机或升级回退。

内网仍使用 `install-lan.sh`，填写本机私有 IPv4；外部只读功能通过 `tg2cloud` → 15. 外部 WebDAV 管理，不进入主安装向导。不改变 HTTPS、只读权限和凭据边界。

## 验证与发布门槛

CI 使用原生 AMD64、ARM64 Linux Runner，分别验证 CLI Python 3.10 / 3.13、共享 Bot、镜像平台、网关 HTTP／FUSE 和隔离代理。Release 从同一 Tag 验证源码，再发布相匹配的共享多架构镜像与 Compose 部署包。

自动检查不能代替真实 DNS／ACME、Telegram、网盘上传、NAS、长期续期或灾难恢复。当前检查结果和未执行清单见[发布记录](development/V153-ACCEPTANCE.md)，维护命令见[开发指南](development/DEVELOPMENT.md)。
