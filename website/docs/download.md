# 安装、下载与校验

文档对应 **TG2Cloud v1.4.11**（待发布）；正式源码当前仍为 v1.4.10，下方资产链接继续指向已发布版本。

正式源码 **TG2Cloud v1.4.10** 已发布，源码包、SHA256 与标签文件核验通过；真实 Telegram／VPS 交互仍需发布后验收。

当前正式稳定版为 **TG2Cloud v1.4.10**。业务部署只使用正式稳定源码，历史 Windows EXE 停留在 v1.2.1。已有外部 WebDAV 工具须在主菜单 15 的子菜单选择 8 升级，才会使用新向导。

## 公网 VPS 安装与升级

在自己的 Debian / Ubuntu 原生 AMD64 / ARM64 主机上，以 root 运行；需要 Python 3.10+、curl、CA 证书和可交互终端：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

向导选择 Edition：未安装时收集信息并展示计划；已有可核验实例进入管理菜单，选择“安装与升级”。确认前不执行安装，升级默认保留已有配置和数据。完整过程见[从零部署](/guide/quick-start/)与[升级说明](/operations/update/)。

只做 CloudDrive2 预检：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

OpenList 先检查，再按需要进入安装 / 升级向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --check
```

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist
```

`--check` 是只读预检，不代表安装、升级或 WebDAV 验收完成。旧 TG115、未知代码、部分安装和身份不符时停止，不添加强制覆盖参数。

## 可信内网 / NAS 安装

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

按向导输入主机实际拥有的私有 IPv4，不需要域名或 ACME。HTTP 不加密，不允许把内网管理入口转发到公网；要求本机 rootful Docker 28+，不保证兼容任意 NAS 系统。实际管理地址由向导显示，详见[内网指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/LAN-INSTALL.md)。

## 可选的外部 WebDAV

主安装不询问或默认启用此功能。v1.4.7 从 `tg2cloud` → 15. 外部 WebDAV 按需安装与维护，无需额外安装命令；历史 v1.4.6 尚无该菜单：

```bash
tg2cloud
```

它使用独立域名和独立只读账号，不复用 Bot 或网关管理员凭据。配置与维护见[外部 WebDAV](/deploy/external-webdav/)。

## 日常管理、凭据与卸载

安装后运行 `tg2cloud`。查看状态、日志、WebDAV 凭据和卸载均在[本地管理菜单](/operations/maintenance/)；v1.4.7 也包含外部 WebDAV 子菜单，历史 `tg2cloud-webdav` 仍兼容。

仅查看已有凭据，也可在自己的私有交互终端运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --show-credentials
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --show-credentials
```

每项确认后才显示，不安装、升级、改密或重建；已保存的 OpenList 初始化密码可能已在后台修改。不要截图、录屏或公开分享。

卸载不是升级步骤。新版主分支不再提供两个独立 Shell 文件；菜单卸载仅作用于当前 Edition，预检全部实例可用：

```bash
tg2cloud uninstall --edition all --check
```

命令损坏时重新运行原公网／内网安装入口，进入已有实例管理菜单，不选择重新安装；部分实例使用核验过的完整源码 CLI。历史脚本保留在原 Tag。实际默认完整卸载会在确认后清理所选实例数据与可识别备份；需要保留时使用 `--keep-data`。不删除云端文件或卸载系统 Docker / Nginx；完整清理不等于把 VPS 恢复到安装前。范围与依赖保护见[卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md)。

历史 v1.2.0 Tag 记录的是早期默认保留数据行为，不可套用为当前完整清理的默认值。

## 源码包与 SHA-256

| 文件 | 用途 |
| --- | --- |
| [TG2Cloud-v1.4.10-source.tar.gz](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.4.10/TG2Cloud-v1.4.10-source.tar.gz) | 同标签源码，包含两 Edition 运行资源 |
| [SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.4.10/SHA256SUMS.txt) | 对应该次 Actions 源码包的校验清单 |

将两个文件保存到同一目录，在 Linux 中执行：

```bash
sha256sum -c SHA256SUMS.txt
```

本版源码包 SHA256 为 `1c9ddb0e95ed5748e6e15d47b539e63a761e1af339215a49f9fe347dbf532fa4`。校验不一致时停止，不混用其他版本或 EXE 的清单。校验和不是数字签名。

[本版 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.10) · [最新 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/latest) · [全部 Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases)

### 在线入口与源码资产的区别

公网 / 内网两个轻量入口固定向导 commit，卸载通过 `tg2cloud` 菜单或子命令进入；业务部署资源解析正式稳定 Release 的不可变 commit。它们与手动下载源码资产、执行 SHA-256 清单检查不是同一条路径。

外部 WebDAV 从 `tg2cloud` → 15. 外部 WebDAV 按需进入，并验证正式源码资产及同版校验清单。任一路径下载失败都不回退未校验的 main / RC 业务代码；不会因为更新网站就自动更新已运行实例。

## 历史 Windows 部署器

| Edition | v1.2.1 发布文件 |
| --- | --- |
| CloudDrive2 | [TG2Cloud-CloudDrive2-Deployer.exe](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.1/TG2Cloud-CloudDrive2-Deployer.exe) |
| OpenList | [TG2Cloud-OpenList-Deployer.exe](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.1/TG2Cloud-OpenList-Deployer.exe) |
| 校验清单 | [SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.1/SHA256SUMS.txt) |

[历史发布页](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) · [历史 Windows 教程](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/README-%E5%B0%8F%E7%99%BD%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.md)

历史 EXE 由同标签 Actions 构建。下载后在 PowerShell 中计算实际文件的 SHA-256，并与 v1.2.1 清单逐字核对：

```powershell
Get-FileHash ".\\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

仅下载一版时只计算该文件。旧 EXE 没有商业代码签名，不能因“未知发布者”就关闭安全软件；来源或校验不能确认时不运行。

### 恢复历史部署器构建

仅供维护历史版本，在独立目录操作，不覆盖当前工作树：

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout v1.2.1
git rev-parse HEAD
.\\build.ps1 -Edition All
```

main 不维护桌面源码或 Windows 构建。开发与 Linux 检查见[贡献说明](/reference/development/)。

## 发布记录与实机证据

下载列表不等于完整开发历史。GitHub 保留哪些历史 Release / Tag 可能变化，逐版功能见[全版本记录](/changelog/)，不要维护一份容易过时的“仅保留几版”清单。

| 记录 | 说明 |
| --- | --- |
| [v1.4.4 双架构升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md) | 用户确认 CloudDrive2 两次升级通过；写入、真实转存、外网与回退未覆盖项单列 |
| [v1.4.3 用户日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md) | 基础升级与 WARNING 核验，不扩展为所有业务已通过 |
| [v1.4.2 人工升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md) | 旧发布基线缺失时的授权人工路径 |
| [v1.4.1 ARM64 首装](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md) | 用户提供的公网 NAT 首装及本机 HTTPS / WebDAV 记录 |
| [v1.3.0 历史迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md) | 人工核对、备份与迁移边界 |

发布及校验成功不等于真实 VPS、Telegram 或云存储验收。维护者自动检查与用户实机反馈的完整来源见[文档来源](/reference/sources/)。

现有记录中 OpenList 脚本实机验收暂缓；完整清理增强仍待新的实机验收。历史环境通过不外推当前版本、其他架构或所有故障路径。
