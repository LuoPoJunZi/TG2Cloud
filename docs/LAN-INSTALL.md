# 局域网 / NAS 独立安装脚本

TG2Cloud 的主力仍是两个 Windows 部署器，公网 VPS 仍使用 `install.sh` 和强制 HTTPS。本入口单独使用 `install-lan.sh`：手填运行脚本的 Linux 内网 IPv4，用内网 HTTP 管理网关，不收集域名、不申请证书，也不修改原部署器或 VPS 向导。

> 当前为测试阶段，尚未完成真实 NAS 验收。公开一行入口固定下载经过 CI 验证的不可变源码 commit，不直接运行 moving main 中的依赖；业务 payload 仍只取最新正式稳定 Release。脚本独立发布于源码仓库，不要求现有 Release 包含它；没有新增 EXE 或改动产品版本号。

## 支持范围与边界

- Debian/Ubuntu、x86_64、root、Python 3.10+、Bash、curl（在线入口）、iproute2、CA 证书、时区数据库及可交互终端。
- 本机默认 rootful Docker Engine 28+、Compose v2；不支持远端 Docker、rootless 或外部 Compose 覆盖。Docker 尚未安装时，由原安装器在最终确认后安装；已安装的旧引擎需要人工升级，脚本不会为此重启 NAS 上的其他容器。
- CloudDrive2 仍需要 `/dev/fuse`，容量和磁盘保护沿用原安装器。容器权限、APT 依赖安装等原有要求不会因“内网模式”消失。
- 首版不承诺直接支持 DSM、QTS、Unraid、OpenWrt、ARM NAS 或 Docker Desktop。这类 NAS 建议先建立符合上述条件的 Debian/Ubuntu 虚拟机，并填写**虚拟机自己的 IP**。
- 必须能连接 GitHub、Docker 镜像源、Telegram 和使用的云存储。内网安装不是离线安装。
- 只接受本机启用网卡上的 `10.x.x.x`、`172.16.x.x`—`172.31.x.x`、`192.168.x.x` 标准 IPv4。拒绝公网、回环、通配地址、域名、URL、端口和 Docker 自动桥接网卡；不自动猜测安装位置。

Docker 28 之前存在同一二层网络可访问回环发布端口的问题，故本入口设置独立最低版本要求。见 [Docker 官方端口发布说明](https://docs.docker.com/engine/network/port-publishing/)。

## 为什么保留回环后端

原安装器、网络修复和健康检查仍使用固定回环地址。内网脚本不修改它们，而是增加一个独立 Docker Nginx 管理入口：

```text
局域网浏览器
  → 手填内网 IP:固定端口（HTTP，独立 Nginx）
  → Linux 本机 127.0.0.1:固定端口
  → 原 CloudDrive2 / OpenList 网关
```

| Edition | 内网管理地址示例 | 后端仍保持 | 独立入口容器 |
| --- | --- | --- | --- |
| CloudDrive2 | `http://192.168.26.5:19798` | `127.0.0.1:19798` | `tg2cloud-lan-cd2` |
| OpenList | `http://192.168.26.5:5244` | `127.0.0.1:5244` | `tg2cloud-lan-openlist` |

Nginx 仅监听指定内网 IPv4，不监听 `0.0.0.0`、公网 IPv4 或 IPv6，不占用 80/443。它拒绝 `/dav`、`/dav/` 及大小写变体；Bot 的内部 WebDAV 地址不变。管理页使用 HTTP，账号、密码和云存储授权可能在局域网中以明文传输，**只适合可信内网**。

不要配置路由器公网端口转发或 UPnP，不要把管理入口放入公网反代。只绑定私有 IP 也不能防止人为路由、端口转发或不安全的共享网络。脚本不调整路由器、NAS 防火墙或宿主机 Docker daemon 配置。

## 在线一键向导（推荐）

目标 Linux 能联网，并已具备上述运行条件时，以 root 执行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

无需预先下载完整项目。向导先选择 Edition，首次安装手工填写运行脚本的 Linux 内网 IPv4，再收集 Telegram 和专用 WebDAV 信息、检查容量并展示计划。最终确认默认 **N**；确认前不安装软件、不写入实例或内网模式记录。原 VPS 向导的域名/HTTPS 步骤不会出现在本入口中。

分别选择 CloudDrive2 或 OpenList：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh) --edition clouddrive2
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh) --edition openlist
```

首次只读预检需明确 Edition 和本机地址；例如：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh) --edition clouddrive2 --lan-ip 192.168.26.5 --check
```

示例 IP 必须换成自己的 Linux / 虚拟机地址，不能填写另一台设备的地址。后续升级复用已保存信息与 IP，不必重复输入。下载失败直接停止，不回退到 main/RC 或其他源；在线引导的私有临时源码目录退出时清理，不清理用户的运行数据。

## 从本地源码运行（备选）

先把经过审查、包含本入口的完整源码放到目标 Linux，在项目根目录运行。示例地址必须替换成实际运行脚本的 Linux 地址。

CloudDrive2 只读预检：

```bash
bash ./install-lan.sh --edition clouddrive2 --lan-ip 192.168.26.5 --check
```

安装 / 升级向导：

```bash
bash ./install-lan.sh --edition clouddrive2
```

首次安装会要求输入内网地址；也可以提前通过 `--lan-ip` 指定。向导随后收集 Telegram 和专用 WebDAV 信息、检查容量、展示 HTTP 风险和安装计划。最终确认默认 **N**：确认前不安装软件、不写入实例或内网模式记录。

首次 `--check` 使用默认 20GB 任务预算与 8GB 最低剩余空间，不收集秘密；自定义预算在交互向导中填写并重新校验。安装目录使用 Edition 的标准 `/opt` 路径，首版不提供自定义目录或迁移功能。

OpenList 对应命令：

```bash
bash ./install-lan.sh --edition openlist --lan-ip 192.168.26.5 --check
bash ./install-lan.sh --edition openlist
```

不要使用 `curl | bash` 或把秘密放入命令参数。密码输入复用私有终端读取与隐藏回显；脱敏日志不会输出完整配置。安装后，凭据逐项确认才会显示，不建议录屏。

下方维护示例使用本地 `bash ./install-lan.sh`；也可替换为上面的 `bash <(curl -fsSL …/install-lan.sh)` 在线入口，保留相同的 `--edition`、`--verify` 或 `--show-credentials` 参数。

## 已有实例与升级

只有同时满足下列条件，才自动生成保留配置的升级计划：

1. 由本脚本创建并具有完整、未修改的内网模式记录。
2. 原 Bot、网关、Compose 身份、数据挂载及实际运行代码核对通过。
3. 安装代码与对应正式 Release 一致，新 Release 没有改变云网关镜像 digest。
4. 已保存内网 IP 仍属于本机启用网卡，所选 Edition 没有 HTTPS 路由。

升级保留 `.env` 原始字节、Telegram Session、SQLite、下载和网关持久化数据，复用原安装器备份与有限回退。可能更新基础 APT 软件包，所选 Bot 可能短暂停止；不会主动升级已有 Docker 引擎。另一 Edition 不会被重启或修改。

最新版本且入口健康时，不重建、不重启。入口故障需要重新预检和明确确认，只恢复经核对的受管入口。当前版本高于 latest 时不降级。公网 VPS/EXE 创建的实例、TG115、部分容器、外部同名容器、手改配置都停止，不自动接管；**不要用本脚本把已有 HTTPS 实例改成 HTTP**。

内网模式存放在 `/opt/tg2cloud-lan/<edition>/`，与原 `/opt/tg2cloud-clouddrive2`、`/opt/tg2cloud-openlist` 分开。升级复用已保存的 IP，不能用 `--lan-ip` 隐式换地址。建议预先设置 DHCP 地址保留或静态 IP；地址失效时停止并提示，不尝试切换到公网模式。

原 payload 备份不包含这个独立目录。备份运行实例时应另行保留对应内网模式目录；当前不提供内网模式转换、地址迁移或自动卸载功能。不要并发用 EXE、原 VPS 脚本或另一终端操作同一实例，EXE 的 HTTPS 管理流程不会因本功能改变。

## 管理页、WebDAV 与实际转存分别验收

本机入口成功标记：

```text
TG2CLOUD_LAN_BASE=OK；TG2CLOUD_LAN_ENTRY=OK；HTTPS=NOT_APPLICABLE
```

这只表示基础服务、指定地址上的本机管理页和 `/dav` 阻断通过，**不等同于另一台内网电脑可访问、WebDAV 写入通过或云盘转存通过**。`--check` 不安装、不升级、不写测试文件；已有入口故障时不会给出通过标记。

从另一台局域网电脑访问管理页，配置自己的云存储，再建立与 Bot 保存信息一致的专用 WebDAV 用户。云盘 Token、Cookie 和 OAuth 仍只在自己的 CloudDrive2/OpenList 中填写，脚本不收集。

另行请求 WebDAV 写入验收：

```bash
bash ./install-lan.sh --edition clouddrive2 --verify
bash ./install-lan.sh --edition openlist --verify
```

即使指定了 `--verify`，也会再次说明随机测试文件的创建与清理并要求确认，失败不自动重复。真实 Telegram 转存还需发送小文件，并在云存储官方客户端核对最终文件。

单独查看已保存凭据：

```bash
bash ./install-lan.sh --edition clouddrive2 --show-credentials
bash ./install-lan.sh --edition openlist --show-credentials
```

每项默认不显示，不安装、不升级、不改密；不能与 `--check` 或 `--verify` 组合。OpenList 显示的是保存的初始化管理员密码，不保证等于后来在管理页改过的当前密码。

## 失败后如何处理

- **IP 不属于本机或固定端口占用**：核对虚拟机地址、DHCP 与占用服务，不自动改端口或停止外部服务。
- **基础安装失败**：核对原安装器脱敏日志、备份和回退结果。部分实例不会自动重装，不要删除数据目录求“重试”。
- **基础安装成功但入口失败**：模式记录与数据保留；重新运行本入口进行预检及确认，续做入口，不当作首次安装覆盖数据。
- **取消、中断、掉线或断电**：不能假定已经完全回退。重新只读检查，确认容器、版本和数据状态；SIGKILL/断电不保证自动恢复。
- **旧 Docker、非受管实例或手改配置**：人工核对，不提供强制接管参数。

真实 NAS、跨版本升级与回退、局域网浏览器访问及实际云盘转存仍需单独验收，离线测试不替代这些检查。
