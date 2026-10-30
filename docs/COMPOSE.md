# Docker Compose 部署

这份教程适合第一次使用 Docker Compose 的用户，按“检查环境 → 下载部署包 → 填写信息 → 配置网关 → 启动 Bot → 测试转存”的顺序操作。

示例对应 **v1.5.4**；同版镜像、两份 Compose 包及校验清单已发布并核验。CloudDrive2 和 OpenList 各有一份部署包，两者共用 Bot 核心；**选其中一个路线即可，不要把两套命令混着执行**。实际发布资产及测试范围见[本版记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V154-ACCEPTANCE.md)。

如果你已经通过 `install.sh` 或 `install-lan.sh` 安装，并能使用 `tg2cloud` 菜单，请继续按原方式升级。这篇教程用于独立 Compose 部署，不会自动迁移、接管或覆盖原来的实例。

> v1.5.4 资产随包 README 保留了 v1.5.3 的下载示例；安装和升级请使用本在线教程的 v1.5.4 命令。包内程序、镜像与 HTTPS 工具均为已核验的 v1.5.4，不混用旧版部署文件。

## 适用范围

### Compose 会帮你运行什么

你可以把 Compose 理解为“一份文件管理几个配套容器”。本项目部署包中的 `docker-compose.yml` 会运行 Bot 和你选择的存储网关；另有一个临时 `setup` 服务，负责收集信息、检查配置和备份。

```text
你在 Telegram 私聊发送或转发文件
        ↓
TG2Cloud Bot 排队、下载或流式传输
        ↓
CloudDrive2 / OpenList 的内部 WebDAV
        ↓
你自己挂载的云存储
```

`setup` 执行完就退出，不是需要一直运行的第三个后台服务。镜像里已经包含 Bot 所需的 Python、rclone 和依赖；当前普通 Compose 部署不用在宿主机另装 Python。可选 HTTPS 宿主向导另需 Python 3.10+，见后面的专节。

### 哪些事情仍需要你自己完成

| 事项 | Compose 部署的处理方式 |
| --- | --- |
| Docker 和 Compose | 先按下文的[安装教程](#首次安装-docker-和-compose)准备；TG2Cloud 部署包本身不安装或重启 Docker。 |
| Bot 配置 | `setup` 逐项询问并生成，不需要手写 Base64 或 YAML。 |
| 云存储挂载 | 你登录 CloudDrive2 / OpenList 后台完成授权。 |
| Bot 的 WebDAV 用户 | 你在网关后台创建，用户名、密码必须与向导一致。 |
| 管理页访问 | 默认仅本机回环；可在初始化时选择本机可信内网 IPv4。 |
| 公网 HTTPS | 由你已有的代理和证书系统负责，不自动申请证书。 |
| 本地管理菜单 | 直接 Compose 不安装 `tg2cloud` 菜单，使用本页命令维护。 |
| 外部只读 WebDAV、家人授权管理、监听账号终端登录 | 当前 Compose 工具没有整合对应宿主维护入口；不能照搬脚本实例的菜单命令。 |

需要完整交互菜单、自动 HTTPS 和统一附加功能管理时，优先阅读[公网一键脚本](VPS-INSTALL.md)或[内网一键脚本](LAN-INSTALL.md)。

## 准备工作

### 1. 在哪里输入命令

在**实际运行 Docker 的 Linux／NAS 主机终端**操作：通常先通过 SSH 登录，再执行命令。不要在 Telegram 聊天窗口、浏览器地址栏或另一台连接远程 Docker 的电脑上粘贴部署命令。

本文所有 `docker compose` 命令都在**同一个部署目录**中执行。关掉 SSH 后重新登录，先 `cd` 回部署目录，再执行维护命令；不需要再次下载和初始化。

以下以 root 管理终端为例。普通 Linux 用户可先执行 `sudo -i`；NAS 则按自己的系统说明取得管理终端。检查：

```bash
id -u
```

输出 `0` 表示当前为 root。之所以需要它，是因为生成的 `.env` 含私密配置，归 root 所有、权限为 600；容器可以正常运行不代表普通用户能读取这个文件。**不要为了省事把它改成 644 或 777。**

### 2. 检查 Docker、Compose 和系统架构

已安装的用户先检查；尚未安装的用户可直接看下面的“首次安装 Docker 和 Compose”，完成后回到这里核对。

```bash
docker version
docker compose version
uname -m
```

逐项核对：

- `docker version` 能显示客户端和服务端信息，不是 `Cannot connect to the Docker daemon`；Engine 至少为 28，并选择仍受维护的版本。
- 使用带空格的 **`docker compose`**，版本至少 **2.24.0**；旧的 `docker-compose` v1 不适用。部署包使用了这个版本起支持的可选环境文件配置。
- `uname -m` 为 `x86_64` 或 `aarch64`，分别对应原生 Linux AMD64 / ARM64。Compose 会按平台拉取同一个 Bot 镜像的对应架构。

#### 首次安装 Docker 和 Compose

这一小节适用于**尚未安装 Docker、使用 systemd 的普通 Debian / Ubuntu 主机**。NAS 请看后面的 NAS 小节；已有 Docker 的主机跳到“只缺 Compose 插件”，不要照着重装。

先在前面说明的 root 管理终端查看系统：

```bash
cat /etc/os-release
dpkg --print-architecture
```

`ID` 应为 `debian` 或 `ubuntu`，架构应为 `amd64` 或 `arm64`。系统版本还必须在 Docker 官方支持范围内，分别见[Debian 安装说明](https://docs.docker.com/engine/install/debian/)和[Ubuntu 安装说明](https://docs.docker.com/engine/install/ubuntu/)。其他发行版、派生系统和 NAS 不套用这段命令，不通过手改发行版代号来冒充受支持版本。

**下面整块复制执行即可，不需要手填系统代号或 CPU 架构。** 它会从本机读取这些信息，添加 Docker 官方 APT 源，然后一次安装 Docker Engine、命令行和 Compose 插件。普通小白不需要分别下载架构对应的二进制。

```bash
(
  set -eu
  if command -v docker >/dev/null 2>&1; then
    echo '已检测到 Docker，请跳过首次安装，按原安装方式维护。'
    exit 1
  fi

  . /etc/os-release
  case "${ID:-}" in
    debian)
      tg2cloud_docker_os=debian
      tg2cloud_docker_suite="${VERSION_CODENAME:-}"
      ;;
    ubuntu)
      tg2cloud_docker_os=ubuntu
      tg2cloud_docker_suite="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
      ;;
    *) echo '这段安装步骤只适用于普通 Debian / Ubuntu。'; exit 1 ;;
  esac
  if [ -z "$tg2cloud_docker_suite" ]; then
    echo '无法读取系统代号，请先核对系统，不写入 Docker 源。'
    exit 1
  fi

  tg2cloud_docker_arch="$(dpkg --print-architecture)"
  case "$tg2cloud_docker_arch" in
    amd64|arm64) ;;
    *) echo '本教程仅适用于 amd64 / arm64 用户态。'; exit 1 ;;
  esac

  for tg2cloud_docker_pkg in docker-ce docker-ce-cli docker.io docker-compose docker-compose-v2 podman podman-docker containerd containerd.io runc; do
    tg2cloud_docker_status="$(dpkg-query -W -f='${Status}' "$tg2cloud_docker_pkg" 2>/dev/null || true)"
    case "$tg2cloud_docker_status" in
      *" ok installed")
        echo "发现已有容器组件 $tg2cloud_docker_pkg，请按原安装方式维护，不执行全新安装。"
        exit 1
        ;;
    esac
  done

  for tg2cloud_docker_file in /etc/apt/sources.list.d/docker.sources /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc; do
    if [ -e "$tg2cloud_docker_file" ] || [ -L "$tg2cloud_docker_file" ]; then
      echo '发现已有 Docker 源或密钥文件，请先核对原安装方式，不覆盖。'
      exit 1
    fi
  done

  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$tg2cloud_docker_os/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$tg2cloud_docker_os
Suites: $tg2cloud_docker_suite
Components: stable
Architectures: $tg2cloud_docker_arch
Signed-By: /etc/apt/keyrings/docker.asc
EOF

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
)
```

前后的括号让这些操作在单独的 Shell 环境中执行，`set -eu` 会在出错时停止后续步骤。遇到错误就先处理，不要把下面的“验证成功”当成已经完成。即使本段因已有源文件而停止，也不要删除那些文件再重试，先核对它们的来源。

这不是卸载或迁移教程。机器上已有 `docker.io`、Podman、containerd、Kubernetes、服务器面板或其他容器服务时，由原管理方式维护；若 APT 提示软件包冲突，不复制网上的批量卸载命令处理。Docker 与宿主软件包的安装可能启动系统服务，不能把这套全新安装步骤当成其他业务运行中的无影响操作。

#### 安装后启动并验证

只对刚才的新装普通 Debian / Ubuntu 主机执行：

```bash
systemctl enable --now docker
```

这会启动 Docker，并设置开机启动。然后检查：

```bash
docker version
docker compose version
docker run --rm hello-world
```

应能看到 Docker 的 Client / Server 版本、Compose 版本，以及测试容器输出中的：

```text
Hello from Docker!
```

`hello-world` 是独立的测试容器，`--rm` 会在运行结束后移除它，不连接 Telegram 或挂载你的网盘。首次会从镜像仓库下载；若拉取失败，先检查主机网络和 DNS，不关闭 TLS 校验。

本文使用 **Docker Engine 28 或以上的受维护版本**及 **Compose 2.24.0 或以上**；选择仍受维护的版本，不是只追求达到最低数字。Docker 官方说明旧于 28.0.0 的版本存在同网段访问回环发布端口的差异，详见[官方端口发布说明](https://docs.docker.com/engine/network/port-publishing/)。这里是安装前提说明，Compose 初始化工具不会替你完整核验宿主环境。

安装 Docker 不等于 TG2Cloud 已部署。上述检查成功后，继续下面的 FUSE、磁盘和 Telegram 信息准备，再下载 TG2Cloud Compose 包。

#### 已有 Docker，只缺 Compose 插件

如果 `docker version` 正常，但 `docker compose version` 提示命令不存在，先确定 Docker 原来怎么安装：

| 原安装方式 | 怎么补 Compose |
| --- | --- |
| 普通 Debian / Ubuntu，原本使用 Docker 官方 APT 源 | 可以按下方命令单独安装插件，不需要重装 Engine。 |
| NAS 官方容器套件、服务器面板或其他软件仓库 | 用原套件／面板／仓库的更新方式处理，不能直接套用官方源命令。 |

**仅在已经配置 Docker 官方 APT 源时**执行：

```bash
apt-get update && apt-get install docker-compose-plugin
docker compose version
```

安装前阅读 APT 的计划；如果它要移除或替换现有容器组件，就先不要确认。提示找不到软件包时，说明源或原安装方式需要核对，不要因此删除 Docker 或用户数据。已有 Engine 版本过旧时，应先安排原系统的升级维护，不在本教程中强制升级、重启其他容器。

#### NAS 用户怎么安装

NAS 通常先使用自己的应用／套件商店安装官方容器应用。例如群晖可以查找 [Container Manager](https://www.synology.com/en-us/dsm/packages/ContainerManager)，威联通使用 [Container Station](https://www.qnap.com/zh-cn/software/container-station)；是否支持以具体机型和系统说明为准，不是每台 NAS 都能安装。

基本顺序为：

1. 在 NAS 自己的应用／套件商店安装或按原方式维护容器应用，不运行上面的 Debian / Ubuntu APT 安装块。
2. 按 NAS 官方说明开启 SSH，连接到 NAS 并取得管理终端。
3. 在这个终端运行 `docker version`、`docker compose version`，核对实际 Engine／Compose 版本、CPU 架构和本地数据目录权限。
4. 选择 CloudDrive2 时再核对 `/dev/fuse` 与必要的挂载能力；满足这些条件后，继续本页部署步骤。

只在 NAS 网页中导入 YAML，不等于已经完成 TG2Cloud 的交互初始化。当前 `setup` 需要交互终端，因此仍要执行后面的填写向导。

NAS 只提供旧版插件、没有交互终端或不满足内核／权限条件时，先按厂商支持范围处理；也可以在自己的设备上准备一台符合条件的 Debian / Ubuntu 虚拟机。不要替换厂商的 Docker 二进制或关闭安全限制来强行安装。此处提供入口指引，不代表这些 NAS 机型已经做过 TG2Cloud 实机验收。

选择 CloudDrive2 还需要宿主机存在 `/dev/fuse`：

```bash
ls -l /dev/fuse
```

缺失就先解决宿主机的 FUSE 支持，再继续；OpenList 不要求这个设备。设备存在只是前提，不等于挂载功能已验收。CloudDrive2 网关保留既有 FUSE／高权限配置，Bot 本身仍为非 root，不要把 Bot 改成特权容器来解决错误。

### 3. 准备网络、空间和 Telegram 信息

主机需要能访问 GitHub、GHCR 镜像仓库、对应网关镜像仓库、Telegram 及你使用的云存储。内网安装也需要外网连接；`setup` 容器没有网络，并不表示 Docker 拉镜像或 Bot 运行可以离线。

先看磁盘和本机地址：

```bash
df -h
ip -br -4 addr
```

默认任务暂存预算为 **20GB**、最少保留空间为 **8GB**，初始化时可以调整。部署目录所在文件系统至少要容纳这两项，还要给镜像、日志和网关缓存另留空间。Docker 数据如果在另一块盘，也要检查那块盘；**任务预算不是磁盘分区，不限制网关的全部缓存，也不是单个文件大小上限。** Compose 没有一键脚本那套完整的宿主机资源推荐与预检。

提前准备：

| 信息 | 从哪里获得或如何决定 |
| --- | --- |
| Telegram API ID、API Hash | 在自己的 Telegram 应用信息中获取，入口为 [my.telegram.org](https://my.telegram.org)。 |
| Bot Token | 从 `@BotFather` 创建或管理自己的 Bot。 |
| 管理员 Telegram 用户 ID | 一个正整数用户 ID，不是 `@用户名`、手机号或频道 ID。 |
| WebDAV 用户名、密码 | 给 Bot 在网关中使用的专用账号；此时可以还没在后台创建，后面按相同值创建。 |
| 云存储 | 你准备在网关后台挂载的网盘或其他受支持存储。 |
| 管理端口绑定地址 | 同一可信内网访问时填 Linux／NAS 自己的内网 IPv4；VPS 可以保留回环，后面通过 SSH 隧道访问。 |

一个正在运行的 Bot Token 只能交给一套实例处理。已有 Bot 正在另一台主机工作时，不要再用同一个 Token 启动新实例；两 Edition 同时部署也应使用不同 Token。不要把真实凭据写进帖子、截图或公开配置。

## 获取正式部署包

### 4. 选择路线并下载

从[正式 v1.5.4 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.5.4)下载 **Compose 部署包**，不是 `source.tar.gz`。

| 选择 | 部署包 | 校验文件 |
| --- | --- | --- |
| CloudDrive2 | [TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz) | [COMPOSE-SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/COMPOSE-SHA256SUMS.txt) |
| OpenList | [TG2Cloud-v1.5.4-compose-openlist.tar.gz](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/TG2Cloud-v1.5.4-compose-openlist.tar.gz) | 使用同一个 Compose 校验文件。 |

下面两段**只执行所选 Edition 的一段**。示例会创建全新的目录，每行末尾的 `&&` 表示前一步成功后才继续；如果目录已存在或任一步报错，就停止核对，不删除旧目录来重装。

CloudDrive2：

```bash
mkdir /opt/tg2cloud-compose-clouddrive2 &&
cd /opt/tg2cloud-compose-clouddrive2 &&
curl -fLO https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz &&
curl -fLO https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/COMPOSE-SHA256SUMS.txt &&
sha256sum --ignore-missing -c COMPOSE-SHA256SUMS.txt &&
tar -xzf TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz --strip-components=1
```

OpenList：

```bash
mkdir /opt/tg2cloud-compose-openlist &&
cd /opt/tg2cloud-compose-openlist &&
curl -fLO https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/TG2Cloud-v1.5.4-compose-openlist.tar.gz &&
curl -fLO https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.5.4/COMPOSE-SHA256SUMS.txt &&
sha256sum --ignore-missing -c COMPOSE-SHA256SUMS.txt &&
tar -xzf TG2Cloud-v1.5.4-compose-openlist.tar.gz --strip-components=1
```

NAS 用户可以把示例 `/opt/...` 换成自己的**全新、本地、真实数据目录**，同一段中的两处路径一起替换；不要使用已有实例目录、云盘挂载目录或软链接。NFS／SMB 共享目录可能无法提供所需权限，优先使用宿主机的本地受支持文件系统。

### 5. 看懂校验和与解压结果

应看到所选文件显示 `OK`，例如：

```text
TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz: OK
```

只下载一版时，`--ignore-missing` 会略过没有下载的另一 Edition；仍须看到**自己这份包**显示 `OK`。失败或提示没有文件被验证时不要继续。`COMPOSE-SHA256SUMS.txt` 与源码用的 `SHA256SUMS.txt` 不同，不能混用；校验和用于检查完整性，不是数字签名。

`tar` 没有输出通常表示解压完成，接着检查：

```bash
pwd
ls -la
```

当前目录应有 `docker-compose.yml`、`compose-bundle.json`、`.env.example`、`README.md`、`LICENSE`、`https.sh` 和完整 `https-tools/`，以及刚才下载的归档与校验清单。

**不要把 `.env.example` 直接改名为 `.env`。** 它只是说明文件，正式 `.env` 由下一步生成。不要从源码目录随意复制另一份 Compose：正式包已经固定了实际多架构镜像 digest，使用同版文件才能保持一致。

## 交互初始化

### 6. 运行填写向导

确认仍在刚才的部署目录：

```bash
docker compose config --quiet
docker compose run --rm setup
```

第一条只校验 Compose 结构，成功时通常不输出内容；第二条首次可能先拉取 Bot 镜像，然后逐项提问。请使用有交互终端的 SSH 窗口，不要加 `-T`、放到后台或用管道喂答案。

| 向导输入项 | 怎么填写 |
| --- | --- |
| Telegram API ID | 填应用的 API ID。 |
| Telegram API Hash | 填对应 API Hash，输入不回显。 |
| Bot Token | 填自己的 Bot Token，输入不回显。 |
| 管理员 Telegram 用户 ID | 只填一个管理员 ID。 |
| WebDAV 用户名 | 回车默认 `tg2cloud`；后面在网关后台创建同名用户。 |
| WebDAV 密码 | 自己输入，或回车生成随机密码；输入不回显，后面可以在私有终端查看。 |
| Bot 保存子目录 | 没有明确需求就留空；具体含义见下一小节。 |
| 任务暂存预算 GB | 默认 `20`，按自己的可用磁盘调整。 |
| 最少保留空间 GB | 默认 `8`，不能小于 8GB。 |
| 管理页访问方式 | 默认本机／可信内网；也可选择自动 HTTPS 或接入已有代理，详见后面的 HTTPS 向导。 |
| 管理端口绑定 IPv4（本机／内网方案） | 默认 `127.0.0.1`；内网访问应填这台 Linux／NAS 自己的内网 IPv4。 |

密码输入时没有星号或光标变化不代表终端卡住。直接输入或粘贴后回车即可，不要把密码作为命令参数填写。

绑定地址选法：

| 场景 | 填写与访问方法 |
| --- | --- |
| NAS 是 `192.168.26.5`，电脑与 NAS 在同一可信网络 | 填 `192.168.26.5`，不是电脑自己的 IP。之后浏览器打开这个地址加对应端口。 |
| 公网 VPS，希望保持管理端口不公开 | 回车保留 `127.0.0.1`，通过下面的 SSH 隧道或自己的 HTTPS 代理访问。 |
| VPS 网卡上只有 `10.x.x.x` 等 NAT 内网地址 | 不能假定家里的电脑能直连；没有 VPN／内网路由时用 SSH 隧道或已有 HTTPS 代理。 |

不填写 `0.0.0.0`、公网 IPv4 或域名；第一版绑定地址只支持回环／私有 IPv4。不要选择 `docker0` 等容器桥接地址冒充主机的可信内网地址，端口也不要通过路由器映射到公网。

### 7. 保存子目录到底是什么

最终位置为：**网关中该 WebDAV 用户的根目录 + Bot 保存子目录 + 文件名**。

| 你在网关后台给 Bot 用户设置的根目录 | 向导中保存子目录 | 最终示例 |
| --- | --- | --- |
| `/我的云盘/Telegram` | 留空 | `/我的云盘/Telegram/文件名.mp4` |
| `/我的云盘` | `Telegram` | `/我的云盘/Telegram/文件名.mp4` |

这些是示例名称，要换成你自己挂载的实际目录，不是固定值。这里不填写 VPS 上的 `/opt/...`、手机路径 `/dav/` 或完整网址，也不要在两处重复填写 `Telegram`。

### 8. 确认并保存

向导会显示所选 Edition、预算和保留空间；核对后确认初始化。空间不足时会停止，请重新按实际容量填写，不要把保留空间设为 0。

成功后会提示“配置初始化完成”，并询问是否在当前私有终端显示后台要用的凭据。选择显示后，把 WebDAV 用户名、密码临时保存在你自己的密码管理器中，后面创建网关用户时使用；OpenList 还会显示独立的初始化管理员密码。

**这一步只生成配置，尚未自动挂载网盘、创建 WebDAV 用户或启动 Bot。** 重复运行向导会检查并保留已保存值，不会重新生成密码；它不是重新配置按钮。发现已有未知数据或初始化不完整时，程序会停止，而不是覆盖。

需要重新查看已保存的后台凭据：

```bash
docker compose run --rm setup python -m tg2cloud.compose credentials
```

仅在自己的私有终端确认显示，不截图、不公开分享。这个命令不重置密码；后台已经改过的管理员密码可能与保存的初始值不同。

## 启动网关并配置云存储

### 9. 先只启动所选网关

CloudDrive2：

```bash
docker compose up -d clouddrive2
```

OpenList：

```bash
docker compose up -d openlist
```

`-d` 表示后台运行，SSH 窗口关闭后容器仍继续工作。此时不要直接运行不带服务名的 `docker compose up -d`，先把网关配置好，再启动 Bot。

### 10. 打开管理页

如果初始化时填写了主机可信内网 IPv4，用自己的电脑浏览器打开：

| Edition | 管理地址示例 |
| --- | --- |
| CloudDrive2 | `http://192.168.26.5:19798` |
| OpenList | `http://192.168.26.5:5244` |

把示例 IP 换成你实际填写的值。这里只提供可信内网 HTTP，不是公网 HTTPS；访问失败先查同网段、主机防火墙和绑定地址，不要改成公网监听。

如果保留了默认 `127.0.0.1`，在**自己的电脑终端**建立 SSH 隧道，以下按默认 SSH 22 端口举例：

CloudDrive2：

```bash
ssh -N -L 19798:127.0.0.1:19798 用户名@服务器地址
```

OpenList：

```bash
ssh -N -L 5244:127.0.0.1:5244 用户名@服务器地址
```

把 `用户名@服务器地址` 换成你平时登录这台 Linux 的信息；不是 TG2Cloud 或网盘账号。SSH 端口非 22 时按实际端口加 `-p`。先核对服务器主机身份，保持这个终端打开，再在同一电脑浏览器访问 `http://127.0.0.1:19798` 或 `http://127.0.0.1:5244`。

隧道命令连接后不显示新提示符通常是正常的，它在保持转发。用完按 `Ctrl+C` 关闭隧道，不会停止服务器容器。这里是系统 SSH 的端口转发。

### 11. 在所选网关后台完成配置

**CloudDrive2 路线：**

1. 登录或按 CloudDrive2 自身流程配置你的账号；不要把它的登录密码填成 Bot WebDAV 密码。
2. 添加并授权自己的云存储，先确认后台能看到准备保存文件的目录。
3. 找到 WebDAV／WebDAV 用户设置，启用 WebDAV，创建刚才向导中使用的专用用户名和密码。
4. 把该用户根目录限定到准备给 Bot 使用的目录，按上面的例子避免与保存子目录重复。
5. Bot 需要读取、上传、创建目录、改名及受管清理能力，不能设置为只读。CloudDrive2 的版本／会员限制按实际环境核对。

**OpenList 路线：**

1. 用后台管理员账号登录；全新部署的初始化管理员密码由向导单独生成，可用上面的凭据命令查看。
2. 在后台添加并授权自己的云存储，确认可以浏览目标目录。
3. 在用户管理中创建专用普通用户，用户名、密码与初始化向导一致；不要让 Bot 使用管理员账号。
4. 设置该用户的基本路径／根目录，允许目录列表、读取、WebDAV 读取与写入、创建和必要的删除操作。不同版本界面名称可能不同，按实际权限核对。
5. OpenList 当前采用预留最终路径后直接上传的策略，不要求用 MOVE 完成正常提交，不要照搬 CloudDrive2 的提交要求。

**初始化向导不会替你在网关后台创建这个用户。** 只填写向导、不在后台创建同名同密码账号，Bot 启动后仍会认证失败。网关管理员、Bot WebDAV 用户和可选的手机只读用户是不同用途的账号。

根目录、两版权限差异和错误码详见[存储网关配置](STORAGE.md)。这里只在你自己的网关中授权云盘，不向 TG2Cloud 维护者提供 Cookie、OAuth、二维码或账号密码。

## 启动和检查 Bot

### 12. 启动 Bot 并看状态

CloudDrive2：

```bash
docker compose up -d tg2cloud-clouddrive2-bot
docker compose logs --tail=100 tg2cloud-clouddrive2-bot
```

OpenList：

```bash
docker compose up -d tg2cloud-openlist-bot
docker compose logs --tail=100 tg2cloud-openlist-bot
```

再检查：

```bash
docker compose ps
docker compose run --rm setup python -m tg2cloud.compose check
```

正常情况下应看到所选网关和 Bot 均在运行；Bot 初始可能为 `health: starting`，稍后再查看应进入 `healthy`。`setup` 已退出且不出现在常驻服务中是正常现象。

`check` 通过表示本地部署标记、版本和配置能被读取，不代表 Telegram、WebDAV 权限或真实转存已通过。Bot 日志用于在私有终端排错，不要公开完整内容；也不要贴出会展开秘密的 `docker compose config` 输出，需要结构检查时用 `docker compose config --quiet`。

### 13. 做一次真正的转存测试

1. 在 Telegram 打开自己创建的 Bot，使用向导里填写的管理员账号私聊，发送 `/start`。
2. 发送或转发一个自己有权处理的小文件，观察接收回执和任务进度；先不要大量导入。
3. 等待任务完成，再打开 CloudDrive2／OpenList 的目标目录，核对文件名、大小和可读取性。
4. 到云存储官方客户端核对文件是否可见、可打开；需要时等待后端自身处理。

如果 Bot 没回复，先查管理员用户 ID、Bot Token 和是否存在使用同一 Token 的另一实例；如果接收了但上传失败，先查网关挂载、专用账号、根目录与写权限。

“容器健康”“配置检查通过”和“任务完成”是不同层面的结果。WebDAV 接收并通过大小复验，不等于内容哈希验证或云盘官方已最终入库。更多任务操作见[Bot 使用](BOT-USAGE.md)和[失败恢复](RECOVERY.md)。

## 运行后文件放在哪里

以下目录图以 v1.5.4 全新安装为准；已发布的 v1.5.2 使用 `data/tg115.db`，升级后继续使用原文件，不手动改名。

下面是初始化和运行后逐步生成的目录示意；CloudDrive2／OpenList 的网关目录只出现所选版本对应的一项：

```text
部署目录/
├── docker-compose.yml       容器运行清单
├── compose-bundle.json      部署包的 Edition、版本和镜像来源
├── .env.example             说明文件，不是正式配置
├── .env                     初始化生成的私密配置
├── tg2cloud-compose.json    已初始化实例标记
├── data/                    业务数据库、Bot Session 等
│   ├── tg2cloud.db          v1.5.3 起新安装的业务数据库
│   └── bot.session          Bot 登录状态，不要公开
├── downloads/               下载暂存和失败后保留的本地文件
├── config/rclone/           传输配置
├── logs/                    本地日志
├── clouddrive/              CloudDrive2：config 与 mounts
├── openlist/data/           OpenList：网关配置与授权
└── backups/                 需要时生成的离线备份
```

云端最终文件在你配置的网关逻辑目录中，不等于这个主机目录。`clouddrive/mounts` 可能是 FUSE 挂载，不要把它当普通下载文件夹清理或递归备份。

初始化服务短暂以 root 运行，只挂载本实例目录与备份目录，没有 Docker Socket 或宿主机根目录。Bot 使用 UID/GID 10001；OpenList 网关为 1001，CloudDrive2 保留自身必要权限。不要用全局 `chmod 777` 或递归修改全部文件归属来修复某一个目录问题。

## 日常管理

重新登录主机后，先回到你自己的部署目录；按实际 Edition 二选一：

```bash
cd /opt/tg2cloud-compose-clouddrive2
```

```bash
cd /opt/tg2cloud-compose-openlist
```

如果使用了 NAS 自定义路径，换成原目录。后面的 `docker compose` 命令都在这里执行。

| 需要做什么 | 命令或操作 |
| --- | --- |
| 看当前容器状态 | `docker compose ps` |
| 查看 CloudDrive2 Bot 最近 100 行日志 | `docker compose logs --tail=100 tg2cloud-clouddrive2-bot` |
| 查看 OpenList Bot 最近 100 行日志 | `docker compose logs --tail=100 tg2cloud-openlist-bot` |
| 持续查看 CloudDrive2 Bot 日志 | `docker compose logs -f --tail=100 tg2cloud-clouddrive2-bot` |
| 持续查看 OpenList Bot 日志 | `docker compose logs -f --tail=100 tg2cloud-openlist-bot` |
| 看网关日志 | `docker compose logs --tail=100 clouddrive2` 或对应的 `openlist`；日志可能含账号信息，仅私下查看。 |
| 检查本地配置 | `docker compose run --rm setup python -m tg2cloud.compose check` |
| 查看已保存的后台凭据 | `docker compose run --rm setup python -m tg2cloud.compose credentials`，按提示私下确认显示。 |
| 停止本项目服务 | `docker compose stop` |
| 启动已有服务 | 配置已完成后使用 `docker compose up -d`。 |

持续日志界面按 `Ctrl+C` 只是退出查看，不会停掉容器。要重启某个服务，先等待传输结束，再用 `docker compose restart` 加上它的实际服务名；重启不会替你重新生成配置或应用新的环境变量。

## 已有反向代理与 HTTPS

默认本机／内网方案不占用 80/443。选择自动 HTTPS 后，宿主向导复用受管 Nginx＋Certbot；已有其他代理时只导出候选配置，不启动第二套争抢端口的代理。

必须区分代理在哪运行：主机上的代理可以连接主机回环端口；另一个容器里的 `127.0.0.1` 指向那个容器自己，不是 TG2Cloud 所在宿主机。容器代理需要按自己的部署方式明确配置可达且受控的网络，不能把管理端口直接改成公网监听来省事。

公网管理域名必须继续拒绝 `/dav` 和 `/dav/` 下的访问，不要用它给手机连接 WebDAV。直接 Compose 当前没有整合外部只读 WebDAV 的安装维护；需要该功能的用户应选择完整一键脚本方案。证书和续期由你的原代理负责，管理页打开也不等于 Bot 上传成功。

<a id="待发布可选-https-配置向导"></a>

### 可选 HTTPS 配置向导

v1.5.4 的完整 format 2 包包含 `https.sh` 与全部 `https-tools/`；必须使用同版镜像和清单。历史 v1.5.2 包只有五个公开文件，不包含该向导；不要给旧包只复制一个脚本或混合不同版本的 helper。

#### 先选访问方式，再配置 HTTPS

新版 `setup` 在收集 Telegram、WebDAV 和空间信息后增加：

```text
── 管理页访问方式 ──
1. 本机或可信内网
2. 自动配置 HTTPS
3. 接入已有反向代理
选择访问方式（回车默认 1）:
```

| 选择 | 向导会做什么 |
| --- | --- |
| 1. 本机或可信内网 | 保留现有方式，继续询问回环／私有 IPv4；不申请证书。 |
| 2. 自动配置 HTTPS | 收集管理域名、可留空的签发邮箱；网关固定绑定 `127.0.0.1`。之后在宿主机运行 HTTPS 向导。 |
| 3. 接入已有反向代理 | 收集管理域名，网关固定绑定 `127.0.0.1`；之后导出候选配置，由你按现有代理方式审阅接入。 |

选择本身只生成私有的 `compose-access.json` 访问计划，不会联网申请证书，也不表示 HTTPS 已经启用。这个文件与 Bot `.env` 分开，不包含 Bot Token 或 WebDAV 密码；仍应按私密配置保护，不能放宽权限。

#### 自动 HTTPS 怎么运行

以下命令只适用于**正式发布后、已校验的新版完整部署包**。先按前文初始化、启动并配置所选网关，启动本部署包的 Bot，再在同一个部署目录、宿主机的 root 终端运行：

```bash
bash https.sh
```

普通 Compose 部署仍不要求宿主 Python；只有这项可选功能需要宿主机 **Python 3.10+、Bash、本机 Docker** 及检查提示所需的基础命令。支持范围继续受 Linux 平台检查约束，不能因为 NAS 能运行 Docker 就假定它支持宿主 HTTPS 向导。`--help` 可以先查看：

```bash
bash https.sh --help
```

脚本从自身所在目录读取完整 helper，即使从其他工作目录调用也不依赖碰巧正确的当前目录。它先检查随包文件的清单和哈希，再运行包内固定代码，不会在每次查看状态时下载 main；哈希不是数字签名。不向 `setup` 容器挂载 Docker Socket，也不会为此安装 Bot 的全部 Python 依赖。

向导提供配置、状态检查、续期演练、移除此 Edition 路由、导出现有代理配置及共享代理备份。也可以直接调用：

```bash
bash https.sh configure
bash https.sh status
bash https.sh check
bash https.sh renewal-dry-run
bash https.sh proxy-backup
bash https.sh remove
```

自动模式复用 `/opt/tg2cloud-proxy` 下受管的 **Nginx＋Certbot**、证书、锁和续期机制。已有受管共享代理时保留另一 Edition 及外部 WebDAV 的域名；没有共享代理时，只有 80/443 可安全使用才建立它。工具不重启 Bot、存储网关或 Docker，不修改 Bot `.env`、rclone、数据库和 Session。

执行前会检查实际部署包、镜像 digest、容器身份、挂载、回环端口、共享状态和 DNS；显示域名与变更计划后再确认。域名须指向此主机，TCP 80/443 必须从外部可达；公网 NAT 场景按提示核对云平台分配的公网地址。证书签发、本机 HTTPS、跳转和管理域名 `/dav` 拦截通过后才报告对应检查结果，公网访问仍需外部设备验收。

**发现其他项目占用 80/443、未知共享代理文件／路由、额外 override、符号链接或身份不一致时会停止。** 不要关闭其他站点来强行继续，应选择下面的已有代理方式。如果旧实例已绑定内网地址，先按本页变更 IP 的步骤备份、调整为回环并自行应用；HTTPS 工具不会偷偷重建业务容器。

证书仍由共享 Certbot 定期检查续期，Nginx 保留既有的证书加载机制。`renewal-dry-run` 是 Let's Encrypt 测试续期，需要外网，不替换正式证书；成功不等于本次正式续签，也不代替公网手机检查。

#### 已有 Nginx 怎么接入

已有其他项目的 Nginx、Nginx Proxy Manager 等占用 80/443 时，不启动第二套争抢端口的代理。运行：

```bash
bash https.sh export-existing
```

向导询问管理域名和现有代理能够读取的证书／私钥绝对路径，确认后在部署目录生成新的 `nginx-<edition>-<随机编号>.conf` **候选文件**。程序不签发证书、不修改原站点、不执行原代理 reload，也不将导出成功说成 HTTPS 已经启用。

宿主 Nginx 按提示补充 WebSocket map、审阅候选配置，执行原代理自己的 `nginx -t` 后再 reload；证书申请、挂载与续期仍按原代理方式管理。Nginx Proxy Manager 等界面不是直接导入这份文件就完成，要按其代理规则填写并保留管理域名 `/dav` 的拒绝规则。

容器内的 `127.0.0.1` 是代理容器自身。候选默认连接宿主回环，仅 host 网络代理可以直接使用；bridge 代理需先自行确定并验证受控的宿主地址／网络与证书挂载，再调整候选。不要为连通而将网关端口开放到公网，不给代理新增 Docker Socket。

#### 检查、备份和停止使用

新安装数据库统一为 `data/tg2cloud.db`；旧实例保留唯一的 `data/tg115.db`。初始化、备份和恢复均不得通过新建空库代替历史数据；两库并存、链接或无主旁文件会停止。Compose 的安装标记与容器标签保持独立，一键脚本不会接管它，也不改变原脚本的安装入口。

- 初始化保存计划不等于证书已签发；导出配置不等于已接入；本机检查不等于公网、真实转存或长期续期通过。
- 新版业务离线备份会包含存在且通过校验的 `compose-access.json`；旧实例没有该文件仍可按原规则备份。
- 业务离线备份不包含共享 HTTPS。保留同版完整部署包和私有访问计划；共享代理可在本向导运行 `bash https.sh proxy-backup` 单独备份，并按[备份与恢复说明](BACKUP-RESTORE.md)处理，新维护器的共享备份会校验并包含 Compose HTTPS 归属记录。
- 要停用此入口，先运行 `bash https.sh remove` 并确认，再 `docker compose down`。只移除本 Edition 管理路由，保留业务数据和证书；其他路由仍需要代理时，不关闭共享代理。已经停止业务或执行 `down` 时，仍须保留完整部署目录和可验证归属，工具才能安全核对后移除路由。
- 不用旧的一键脚本卸载器接管 Compose 实例；共享代理的其他维护端也应更新到支持 Compose 归属保护的版本。历史离线工具无法承诺识别新状态，不要交叉使用旧代码修改入口。
- 若提示 `compose-transaction.json` 或状态／归属不一致，保留部署包、事务标记与已有备份，停止继续变更并人工核对。不要直接删除状态或事务标记来跳过保护。
- 失败时收集脱敏后的版本、动作、时间和检查失败项，不发送 `.env`、原始容器环境、证书私钥或 Session。

这项开发仍需发布后的原生 Linux、两种网关、已有共享路由、实际 DNS／ACME、视频与转存及失败回退验收；本地模拟和构建通过不能代替这些实机结果。

## 备份与升级

### 14. 先学会备份

在 Bot 私聊中由管理员发送 `/pause`，等待正在下载／上传的任务结束，再在部署目录执行：

```bash
docker compose stop
docker compose ps -a
```

核对所选项目的 Bot 和网关确实已停止，再运行：

```bash
docker compose run --rm setup python -m tg2cloud.compose backup --offline-confirmed
```

`--offline-confirmed` 是你确认已经停机，不是让工具帮你停机。工具没有 Docker Socket，无法替你证明其他容器已停止。不要在服务仍写数据库时填写这个确认。

成功时会显示 `离线配置／数据库备份完成：backups/...tar.gz`。备份包括配置、Compose、实例／版本标记、业务数据库、Bot Session、存在时的个人监听 Session、rclone 配置和网关配置；包含敏感信息，权限为 600。生成后应另存到你控制的安全位置。

它**不包含** `downloads/`、本地日志、云端文件或独立 HTTPS 代理配置；有失败后保留的暂存文件时，停机后还要单独保护 `downloads/`。不要递归打包 FUSE 云盘挂载。首次还没运行过 Bot、缺少数据库／Session、存在活跃数据库旁文件、容量不足或发现不安全链接时，备份可能停止；保留原文件排查，不要重建数据库来“修复”。

若只是备份、不升级，确认备份结果后可以：

```bash
docker compose up -d
```

回到 Telegram 发送 `/resume` 恢复调度；暂停状态重启后会保留。只有核验完成并准备恢复接收任务时才恢复调度。

### 15. 升级到后续正式版本

**这部分在以后出现新的正式版时使用，不需要反复重新安装当前版本。**

1. 阅读目标 Release 的改动和兼容说明，确认同时有该版 Compose 包和 `COMPOSE-SHA256SUMS.txt`，不要只把镜像改成 `latest`。
2. 在一个新的下载目录获取目标正式版本，校验后解压；不要在旧实例目录重新执行“首次创建目录”的步骤。
3. 按上面先暂停、等待活动任务结束、停止服务、完成离线备份。保留当前部署包、原镜像 digest 和必要暂存文件。
4. 确认新包与当前实例是同一个 Edition。旧 format 1 包替换其五个公开文件：`docker-compose.yml`、`compose-bundle.json`、`.env.example`、`README.md` 和 `LICENSE`；format 2 包还须同时替换同版的 `https.sh` 和**完整 `https-tools/`**。先把旧 helper 目录移到部署目录之外安全保留，再放入新目录，不把两版 helper 合并；工具会拒绝额外或缺失文件。不要只换镜像或单个脚本。
5. **保留原 `.env`、`tg2cloud-compose.json`、存在时的 `compose-access.json`、data、config、downloads、logs、网关数据和 backups。** 不要把旧数据复制进一个同时运行的新实例，也不要让两套容器共用 Session 或 Token。

文件替换完成后，在原部署目录执行：

```bash
docker compose pull
docker compose run --rm setup python -m tg2cloud.compose check
```

两条都成功后再启动：

```bash
docker compose up -d
docker compose ps
```

检查 Bot 日志、网关登录与原任务数据，再做一个小文件转存测试；确认正常后在 Telegram 发送 `/resume`。新版本可能同时变更网关固定镜像，不能在有活动写入时切换。

`check` 失败就停止，不要反复初始化、删除 `.env` 或继续 `up`。已有实例重新运行 `setup` 会保留配置，不是重置或自动配置迁移。升级需要的新字段／数据适配应按那一版的正式说明处理。

### 16. 出问题时怎么回退

先停止新实例，保留故障日志和当前数据，不要边运行边覆盖。如果版本包含数据库迁移，必须恢复与旧程序匹配的一致性数据库、配置和 Session；仅把镜像换回旧版可能不安全。

当前工具没有一键覆盖生产数据的恢复按钮。可以对备份做隔离结构与数据库预检，但预检通过不等于服务恢复成功。先按[备份与恢复说明](BACKUP-RESTORE.md)规划隔离验证，确认原实例不会同时处理同一 Token，再考虑切换。

## 停止使用

- 暂时不用：在对应部署目录执行 `docker compose stop`，容器停止，本地资料保留。
- 不再需要此项目容器和网络：确认无活动任务、完成备份并核对当前目录后，执行 `docker compose down`。它不删除绑定到主机目录的业务资料，也不删除云端文件。
- 需要彻底清理本地资料：先确认路径和共享引用、转移所需备份，再由你自行处理；本文不提供自动删除用户数据的命令。

不要用 `docker compose down -v`、`docker system prune` 或删除数据库来解决升级问题。Compose 实例不由一键脚本接管，不能用 `tg2cloud` 菜单卸载它；也不要直接关闭主机上的其他 Docker 项目或 Nginx。

## 常见问题

| 现象 | 先检查什么 |
| --- | --- |
| `docker: 'compose' is not a docker command` | Compose 插件没装好；按本页“已有 Docker，只缺 Compose 插件”或 NAS 小节处理。 |
| `Cannot connect to the Docker daemon` | 普通新装主机先检查 `systemctl status docker`；NAS 检查官方容器套件是否运行，同时核对本机 Docker context，不随意重启其他业务。 |
| APT 提示没有 Release 文件、404 或无法下载 | 核对系统版本是否受支持、系统代号、现有 APT 源和网络；不要随意改成另一发行版代号或关闭签名校验。 |
| APT 提示 `Signed-By` 冲突或发现已有 Docker 源 | 停止重复添加，先核对原来的 Docker 安装／源文件，不批量删除系统源。 |
| `Unable to locate package docker-compose-plugin` | 核对是否确实使用 Docker 官方 APT 源；发行版仓库、NAS 套件可能使用不同方式提供 Compose。 |
| `required` 字段不支持、Compose 文件校验失败 | 核对 `docker compose version` 至少 2.24.0，以及是否误用了旧 `docker-compose`。 |
| `no configuration file provided` | 当前目录不对；回到包含 `docker-compose.yml` 的那个部署目录。 |
| `.env` 找不到 | 首次先运行 `setup`，不要把示例文件当正式配置；旧实例则核对目录，不重新造空配置。 |
| `.env` 权限不足 | 使用 root 管理终端读取；不要把权限改宽。 |
| 镜像拉取超时或拒绝访问 | 查主机到 GitHub／GHCR／网关镜像仓库的网络、DNS和磁盘空间；不要改用未验证第三方镜像或关闭 TLS 检查。 |
| `/dev/fuse` 不存在 | CloudDrive2 的宿主环境未准备好；按主机／NAS 说明检查，不能删掉设备配置假装支持。 |
| 容器名已被占用 | 可能已有同 Edition 的脚本或 Compose 实例；先查归属，不删除旧容器来强行继续。 |
| 管理页打不开 | 查网关是否运行、端口冲突、初始化时绑定的 IP、电脑到主机的路由及防火墙。 |
| 默认 `127.0.0.1`，另一台电脑打不开 | 属于预期访问范围；用 SSH 隧道或已有 HTTPS 代理。电脑浏览器里的 `127.0.0.1` 是电脑自己。 |
| SSH 隧道提示本地端口已占用 | 本机已有程序使用该端口；选择另一个本地端口，并在浏览器使用同一个本地端口，不动服务器后台端口。 |
| 想修改已填的绑定 IP | 先暂停并结束活动传输、保留私密配置备份，再在私有终端编辑 `.env` 中的 `TG2CLOUD_BIND_IP`；只填实际本机回环／内网 IPv4。检查后用 `docker compose up -d` 应用，单纯 `restart` 不读取新配置。 |
| Bot 不回复 | 核对管理员用户 ID、Bot Token、Telegram 网络及是否重复运行同一个 Token，查看所选 Bot 日志。 |
| WebDAV 401 | 后台专用用户名／密码与向导不一致，或把管理员密码当成了 WebDAV 密码。 |
| WebDAV 403、能看不能上传 | 查账号基本路径、WebDAV 读取／写入权限及云存储本身权限。Bot 用户不能仅只读。 |
| 文件保存到了重复层级 | 检查是否在账号根目录和 Bot 保存子目录两处重复填写了同一层名称。 |
| Bot 启动后一直不健康 | 先读 Bot 与网关日志，核对配置和服务可达性；不要通过删除 Session／数据库反复重装来排错。 |
| 配置检查显示版本不匹配 | Compose、元数据和镜像不是同一正式版本；还原匹配的公开文件，保持原配置／数据不动。 |
| NAS 报目录权限、只读文件系统错误 | 查数据目录是否本地可写、文件系统是否支持所需 UID／权限，不全局提权或 `chmod 777`。 |
| 备份缺少数据库、Session 或提示活跃旁文件 | 确认曾正常运行 Bot、已停止本项目服务，并检查所选目录；不要手工删除 WAL、Session 或未知数据。 |

排错时可以收集脱敏后的版本、错误时间、容器状态和相关几行错误信息。不要分享 `.env`、数据库、Session、完整 `docker inspect`／`docker compose config` 输出或含密码的日志。

## 开发与发布前验证

以下只供维护者在完整源码仓库根目录执行，普通安装用户可以跳过；解压后的用户部署包不包含这些源码工具。

本地生成候选包（不会构建／发布镜像）：

```bash
python3 .github/scripts/compose_release.py bundle --directory build/compose-candidate
```

候选仍指向当前源码版本的镜像名称，不表示该镜像存在。开发者可用已有 `build_payload.py` 生成上下文并本地构建，在隔离 Compose override 中替换 setup 与 Bot 的 image；不要修改生产部署。

先正常发布包含本功能的新稳定 Tag，完成同标签原生 Linux 检查和源码资产验证，再人工运行 Actions 的 **Compose images and bundles** 并填写该 Tag。工作流从相同不可变提交构建两架构、运行两版隔离初始化与非 root 配置检查，再发布版本 manifest 和固定 digest 的部署包。禁止从 moving main 发布，不改稳定 helper pin，也不替换历史源代码资产。

发布维护工具固定到触发该工作流的不可变提交 `github.sha`，业务镜像和部署包仍取所选正式 Tag；不会为修正发布工具而移动业务 Tag。已有版本镜像先复核两平台的实际子镜像 digest、版本和提交标签；只有一致时才复用，不重新构建或覆盖。Docker manifest list 不支持 OCI index 注解时仍必须通过这些身份检查，未知格式或不匹配立即停止。

首次 GHCR 包可能默认私有。发布管理员需将其设为 public；匿名拉取检查未通过时不会发布用户部署包。修正可见性后可重跑：相同提交的版本 index 会复核并复用，已有资产逐字节相同才接受，不能通过 clobber 覆盖。

人工验收必须补充两架构安装、两种真实网关、已有反向代理、断网／重启、升级与隔离恢复；CI 成功不等于这些实机步骤通过。


## 官方参考

- [Docker Engine Linux 安装](https://docs.docker.com/engine/install/)。
- [Docker Engine Debian 安装](https://docs.docker.com/engine/install/debian/)。
- [Docker Engine Ubuntu 安装](https://docs.docker.com/engine/install/ubuntu/)。
- [Docker 端口发布与回环地址限制](https://docs.docker.com/engine/network/port-publishing/)。
- [Docker Compose 插件安装](https://docs.docker.com/compose/install/linux/)。
- [Docker Compose 临时运行与命令覆盖](https://docs.docker.com/reference/cli/docker/compose/run/)。
- [Docker Compose 日志选项](https://docs.docker.com/reference/cli/docker/compose/logs/)。
- [Docker Compose 可选 env_file 与最低版本](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)。
- [Docker 多架构 manifest 与注解](https://docs.docker.com/reference/cli/docker/buildx/imagetools/create/)。
- [GitHub Actions 发布镜像与权限](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)。
