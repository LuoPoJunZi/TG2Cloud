<p align="center">
  <img src="assets/brand/tg2cloud-logo.svg" alt="TG2Cloud — From Telegram to Your Cloud" width="520">
</p>

<p align="center">
  <strong>Telegram 文件自动转存 · CloudDrive2 / OpenList · Linux 一键部署</strong>
</p>

<p align="center">
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/releases/latest"><img alt="最新版本" src="https://img.shields.io/github/v/release/LuoPoJunZi/TG2Cloud?style=flat-square&amp;label=release&amp;color=1677ff"></a>
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/actions/workflows/tests.yml"><img alt="自动测试" src="https://img.shields.io/github/actions/workflow/status/LuoPoJunZi/TG2Cloud/tests.yml?branch=main&amp;style=flat-square&amp;label=tests"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/github/license/LuoPoJunZi/TG2Cloud?style=flat-square&amp;color=22a06b"></a>
</p>

<p align="center">
  <a href="docs/VPS-INSTALL.md"><strong>安装指南</strong></a> ·
  <a href="docs/README.md">仓库文档</a> ·
  <a href="https://github.com/LuoPoJunZi/TG2Cloud/releases">版本下载</a> ·
  <a href="https://tg2cloud.pages.dev/">文档网站</a> ·
  <a href="README_EN.md">English</a>
</p>

TG2Cloud 是一个自托管的个人文件转存工具：把文件发送或转发给自己的 Telegram Bot，由 Linux 主机自动排队、下载并写入你挂载的云存储。

Telegram → TG2Cloud → rclone → CloudDrive2 / OpenList WebDAV → 你的云存储

## 主要能力

- 两个 Edition 共用 Bot 核心，各自保留配置、任务数据库与 Session。
- 持久队列、去重、取消恢复、失败保留及视频说明命名。
- 普通下载与大文件流式传输，配合动态并发和磁盘保护。
- 公网 HTTPS / 可信内网部署，提供磁盘预算推荐和保留配置升级。

当前正式版本 **v1.4.2**，以 Linux 脚本维护，支持原生 AMD64 / ARM64；源码包与校验清单见 [Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.2)。更新文档不会替换已有实例，需显式升级。Windows 部署器停留在 [v1.2.1](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)。CloudDrive2 v1.3.3 正式升级及用户转存确认见[历史验收记录](docs/development/V133-ACCEPTANCE.md)，不外推当前版本或其他部署与恢复场景。

2026-10-21，专用 Debian AMD64 测试机已完成 CloudDrive2 v1.3.4 → v1.4.2 人工保留配置升级，健康、数据保留、只读 WebDAV 和外部 HTTPS 检查通过；旧 Release 已删除的自动升级限制、实际转存及新代理模式未验收范围见[本次记录](docs/development/V142-ACCEPTANCE.md)。

## 开始使用

1. 按[填写信息清单](docs/填写信息清单.md)准备 Telegram Bot、API 信息和服务器环境；不要把真实凭据填写到公共文档。
2. 选择 CloudDrive2 或 OpenList，以及公网 VPS 或可信内网入口，按向导核对安装计划后执行。
3. 在自己的网关中挂载云存储，按安装指南完成 WebDAV 配置与验收；网盘账号授权由你自行管理。
4. 向 Bot 发送或转发文件，查看接收结果；任务查询、失败恢复及验证含义见[任务使用与恢复指南](docs/RECOVERY.md)。

两个 Edition 共用转存能力，但网关配置不同；各自的实例数据互相独立。已有实例升级使用对应入口并保留配置，不需要先卸载。

公网／内网入口选择 Edition 后，新装进入向导，已有实例进入管理菜单；确认安装管理工具后，可直接运行 `tg2cloud`。卸载仅作用于所选 Edition，旧卸载 URL 保留救援。菜单、更新与清理边界见[运维指南](docs/OPERATIONS.md#本地管理菜单)。

## 快速安装

要求 Debian / Ubuntu、64 位原生用户态、root、Python 3.10+、curl 和可交互终端；主机需能访问 GitHub、Telegram、镜像仓库及目的端。CloudDrive2 还需要 `/dev/fuse`。

支持 AMD64 / ARM64（`linux/amd64` / `linux/arm64`），不使用 QEMU；v1.4.1 修复公网 NAT 的 HTTPS 预检，仍须确认公网映射并通过证书与 HTTPS 检查。用户已完成 CloudDrive2 在 Ubuntu 26.04.1 ARM64 公网 NAT 环境的首次部署、本机 HTTPS 与 WebDAV 验收，见[实机记录](docs/development/V141-ACCEPTANCE.md)；OpenList、升级回退、手机外网访问及长期续期不外推。完整步骤见[安装指南](docs/VPS-INSTALL.md)与[双架构说明](docs/ARCHITECTURES.md)。

### 公网 VPS

准备指向 VPS 的域名，并允许 TCP 80/443；向导中选择 CloudDrive2 或 OpenList：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

脚本先收集信息、检查并等待确认，业务代码只安装正式稳定 Release。已有实例建议先追加 `--edition clouddrive2 --check`（OpenList 使用 `openlist`）；只读检查不执行升级。核对后重新运行不带参数的入口，选择 Edition 和“安装 / 升级”并确认，可同时获得离线管理命令；显式参数仍兼容。完整参数见 [VPS 指南](docs/VPS-INSTALL.md)。

### 可信内网 / NAS

无公网域名时使用独立入口，按提示填写本机私有 IPv4；仅支持符合上述环境的 Linux 主机，不保证所有 NAS 系统兼容：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

内网 HTTP 不加密，禁止公网端口转发；不要用此入口绕过公网 HTTPS。详见[内网指南](docs/LAN-INSTALL.md)。

### 卸载预检

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

这条命令只预览，不卸载。实际完整卸载会删除所选实例的数据和可识别备份；需保留数据时使用 `--keep-data`，先保存清理范围之外的独立备份。详见[卸载指南](docs/UNINSTALL.md)。

## 使用文档

**v1.4.3 正在准备发布**：包含以下维护、可选功能与测速／菜单修复。业务数据库将事务迁移至 schema 2，升级前须备份，回退需匹配旧数据库与旧代码；当前正式下载仍以已发布版本为准。详见[本次发布说明](RELEASE_NOTES.md)。

本地待发布的升级兼容、实例快照、业务就绪与命名预览，见[维护增强说明](docs/development/MAINTENANCE-IMPROVEMENTS.md)；现有正式 v1.4.2 在线入口不包含这些新增能力。

另有[可选分类、主动通知、家庭配额与脱敏报告](docs/FEATURE-ENHANCEMENTS.md)的本地增强：分类/通知默认关闭、成员默认不限额，尚未发布，升级前需备份数据库。

v1.3.3 起，[家庭共享](docs/FAMILY-SHARING.md)支持安装后授权家人转存、共用保存目录及各自的外部只读账号；安装仍只填一个管理员 ID。v1.3.4 增强网址污染名、图片自身说明及一图一视频同标题；完整规则与边界见[命名指南](docs/NAMING.md)。已有实例与离线工具需显式升级。

可选附加功能：[外部 WebDAV](docs/external-webdav.md)。独立安装，通过新 HTTPS 域名只读访问已有上传目录；不复用 Bot/管理员账号，不加入主安装流程。v1.3.1 起提供专用在线安装与离线维护入口。

v1.4.2 新增[复用已有 Docker Nginx](docs/DOCKER-NGINX.md)：显式授权接入，不停止原代理、不增加第二层 Nginx；默认 managed 模式不变。支持条件、证书责任与实机验收边界见专题。

按主题查阅仓库内文档；全部文档见[仓库文档目录](docs/README.md)，网页版见[文档网站](https://tg2cloud.pages.dev/)。

| 主题 | 仓库文档 |
| --- | --- |
| 安装与配置 | [公网 VPS 安装 / 升级](docs/VPS-INSTALL.md) · [局域网 / NAS 安装](docs/LAN-INSTALL.md) · [填写信息清单](docs/填写信息清单.md) |
| 网关与首次转存 | [CloudDrive2 / OpenList 配置与验收](docs/STORAGE.md) · [Bot 使用、菜单与命令](docs/BOT-USAGE.md) |
| 命名与常见问题 | [视频、说明及媒体组命名](docs/NAMING.md) · [FAQ](docs/FAQ.md) |
| 配置与备份 | [配置字段及运行目录](docs/CONFIGURATION.md) · [备份范围与恢复预检](docs/BACKUP-RESTORE.md) |
| 家庭与手机读取 | [Bot 家人授权](docs/FAMILY-SHARING.md) · [外部 WebDAV 只读入口](docs/external-webdav.md) |
| 运行与故障排查 | [管理命令、日志与 HTTPS 维护](docs/OPERATIONS.md) · [任务恢复、验证与备份](docs/RECOVERY.md) |
| 升级验收 | [v1.4.2 人工升级与检查边界](docs/development/V142-ACCEPTANCE.md) · [v1.3.3 正式升级与转存确认](docs/development/V133-ACCEPTANCE.md) · [v1.3.0 历史迁移](docs/development/V130-ACCEPTANCE.md) |
| 卸载与迁移 | [卸载指南](docs/UNINSTALL.md) · [从 TG115 迁移](docs/MIGRATION_FROM_TG115.md) |
| 开发与测试 | [贡献指南](.github/CONTRIBUTING.md) · [仓库结构](docs/development/REPOSITORY.md) · [Linux 架构与兼容](docs/development/LINUX-REFACTOR.md) |
| 版本与发布 | [所有版本分别做了什么](CHANGELOG.md) · [当前发布说明](RELEASE_NOTES.md) |
| 历史 Windows 版 | [v1.2.1 图形部署教程](docs/README-小白使用说明.md) · [脚本优先与桌面版冻结](docs/development/SCRIPT-FIRST.md) |
| 品牌与第三方组件 | [品牌使用规范](docs/development/BRAND-GUIDE.md) · [第三方组件说明](docs/第三方组件说明.md) |

## 使用边界

- 仅转存你有权保存的内容；不自动监听频道、不绕过内容保护。115 只是示例，不是唯一目标网盘。
- 云存储登录与授权在你自己的 CloudDrive2 / OpenList 中完成；TG2Cloud 无遥测或凭据回传。
- WebDAV 大小验证不等于内容哈希校验或云盘官方最终完成；重要文件需自行复核。
- 不公开 Token、密码、Session、数据库、配置或备份；升级前备份，不用旧 EXE 覆盖新实例。详见[安全政策](.github/SECURITY.md)。

## 致谢与项目来源

<table>
  <tr>
    <td align="center" width="50%">
      <a href="https://github.com/LuoPoJunZi">
        <img src="https://github.com/LuoPoJunZi.png?size=96" width="72" alt="LuoPoJunZi"><br>
        <strong>LuoPoJunZi</strong>
      </a><br>
      <sub>TG2Cloud 项目维护者</sub>
    </td>
    <td align="center" width="50%">
      <a href="https://github.com/whyhhh20">
        <img src="https://github.com/whyhhh20.png?size=96" width="72" alt="whyhhh20"><br>
        <strong>whyhhh20</strong>
      </a><br>
      <sub>上游 TG115 原作者</sub>
    </td>
  </tr>
</table>

感谢 **whyhhh20** 创建并公开上游项目 [TG115](https://github.com/whyhhh20/TG115)。

TG2Cloud 从该项目演进而来，以原项目代码为基础并保留 MIT 许可证、版权和必要致谢；当前在 Telegram → rclone → CloudDrive2/OpenList → 用户云存储链路上继续完善可靠性、部署安全和运维体验。

同时感谢 Telethon、rclone、Docker、Paramiko 等开源项目，以及 CloudDrive2 提供的 WebDAV 和网盘挂载能力。第三方组件分别受各自许可证与服务条款约束。

## 许可证与免责声明

本项目采用 [MIT License](LICENSE)。

本项目与 Telegram、CloudDrive2、OpenList、各云存储服务及其运营方没有隶属、授权或官方合作关系。使用者应自行评估账号、数据、网络、VPS 权限和第三方闭源组件风险。
