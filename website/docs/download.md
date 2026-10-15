# 下载与 SHA-256 校验

本文档对应 **TG2Cloud v1.2.1** 待发布源码；以下下载暂保持已发布并核对的 v1.2.0。v1.2.1 两个 EXE 和 SHA256SUMS 由 GitHub Actions 完成构建、自检和发布后再更新链接。

## 下载已发布版本

| 版本 | 发布文件 | 教程 |
| --- | --- | --- |
| CloudDrive2 Edition | [下载 CloudDrive2 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.0/TG2Cloud-CloudDrive2-Deployer.exe) | [CloudDrive2 部署](/deploy/clouddrive2/) |
| OpenList Edition | [下载 OpenList 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.0/TG2Cloud-OpenList-Deployer.exe) | [OpenList 部署](/deploy/openlist/) |
| 校验清单 | [下载 SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.2.0/SHA256SUMS.txt) | 与下载的 EXE 逐项核对 |

[查看 v1.2.0 发布页](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.0) · [查看最新 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/latest) · [全部 Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases)

:::info 固定版本与最新版本
本页下载按钮固定到已发布 v1.2.0，两个 EXE 与 SHA256SUMS 来自同一次 Actions 构建，不使用旧版本的摘要。“最新 Release”可能指向更新版本，应使用那个版本自己的校验文件和发布说明。源码 Push 与正式发布是不同操作，不能用 main 版本号证明 Release 已经存在。
:::

两个正式 EXE 由 GitHub Actions 的 Windows Runner 从同一标签构建并自检，Release 复用该次构建产物。校验值来自这次 Actions 实际生成的文件，不要求与本机旧构建一致。

下载新版 EXE 不会自动更新 VPS Bot 或 HTTPS 续期容器；已有实例请按 [升级与修改配置](/operations/update/) 操作，不要卸载重装。

## 在 Windows 中计算校验值

打开文件所在目录，在 PowerShell 中执行与你下载的 Edition 对应的一条命令：

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

打开同一 Release 下载的 `SHA256SUMS.txt`，找到相同文件名，比较完整 SHA-256。只下载一版时，另一条命令可跳过。

校验不一致时停止运行，删除损坏的下载文件并从项目正式 Release 重新获取。文件大小相同不能替代 SHA-256 比较。

## Windows 提示未知发布者

已发布的 Windows EXE 尚未提供商业代码签名，SmartScreen 可能显示“未知发布者”。这与文件是否来自正确发布源是不同的问题。

核对仓库、Release 标签、文件名和 SHA-256；无法确认来源时不要运行。**不建议关闭 Defender、Windows Security 或全局安全检查。**

## 没有 Windows：VPS 单行入口

两个 PySide6 部署器仍是主力入口。没有 Windows 时，可在自己的 Debian/Ubuntu x86_64 VPS 上，以 root 运行以下命令；需要 Python 3.10+、curl、CA 证书及可交互终端。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

向导先选择 Edition、检查现有实例并收集必要信息，显示脱敏计划，确认后才执行。全新 VPS 走安装；完整且可核验的受管实例走保留配置升级。旧 TG115、部分安装或自定义实例不会被静默覆盖。Docker 环境和 HTTPS 复用现有部署资源，云存储授权仍由你在 CloudDrive2 / OpenList 中完成。

只做 CloudDrive2 只读检查可使用：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

OpenList 先只读检查，不安装／升级：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --check
```

检查通过后，运行 OpenList 安装／升级向导；写入前仍需预检与最终确认：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist
```

轻量入口来自主分支；Python 向导模块固定到审查并通过 CI 的源码 commit，实际部署 payload 只取正式稳定 Release 的不可变 commit，不取 main、RC 或草稿。出现下载错误应停止，不要把命令退出当作安装成功。

:::warning 验收范围
当前脚本完成 CloudDrive2 真实 VPS 的只读预检，没有执行首次安装或实际跨版本升级；OpenList 脚本实机验收暂缓。执行写入前请备份、安排维护窗口，并阅读 [完整 VPS 脚本指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。不要同时运行 EXE 和命令行向导。
:::

## 没有公网域名：独立内网入口

可信内网 Debian / Ubuntu x86_64 主机可使用独立脚本，按向导选择 Edition 并人工输入本机私有 IPv4：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

内网 HTTP 不加密，禁止公网端口转发；要求 Python 3.10+ 和 Docker 28+，不保证兼容所有 NAS 或 ARM。不会申请域名证书、占用 80/443 或转换已有 HTTPS 实例，也不修改两个 EXE 的强制 HTTPS 规则。入口检查通过后，验收前会再次显示实际 `http://IP:19798`（CloudDrive2）或 `http://IP:5244`（OpenList）。

用户提供的 CloudDrive2 内网 Debian 日志显示首次部署和 WebDAV 验收通过；OpenList 内网、其他 NAS、升级/回退及 Telegram 转存仍待验收。详见 [内网安装指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/LAN-INSTALL.md)。

## 独立卸载：先预检

卸载不是升级步骤。v1.2.0 Tag 中的原入口默认保留实例数据、证书和历史备份；主分支追加的完整清理增强会在双重确认后删除所选配置、数据库、下载和可识别历史备份。需要保留数据时必须明确使用 `--keep-data`。用户已反馈原保留数据卸载在其 VPS 通过，但完整清理增强仍待新的实机验收，不据此推定 NAS 或两个 Edition 均通过。两个 EXE 与正式 Release 不变，详情见 [卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md)。

在线入口固定到审查并通过 CI 的源码 commit。可先用以下只读命令查看范围；`--check` 不会停止容器或删除数据：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

确认前请结束传输、将需要保留的备份复制到清理目录之外并核对资源归属；未知安装、外部引用、使用中的网络或 FUSE 挂载不会强制清理。系统 Docker/Nginx、其他项目与云端文件不操作；镜像缓存、锁元数据、系统软件包和 DNS 变化不自动回滚，完整清理不等于把 VPS 恢复到安装前。本页只提供只读预检，不提供无人值守删除命令。

## 只查看已有凭据

v1.2.0 提供独立凭据查看模式，按已安装的 Edition 选择一条命令，在自己的私有交互终端运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --show-credentials
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --show-credentials
```

逐项确认后才显示已保存的凭据，每项默认不显示。此模式不安装、升级、改密或重建服务；不能与 `--check`、`--configure-https`、`--verify` 组合。保存的 OpenList 初始化管理员密码可能已在管理页更改，不能保证是当前登录密码。输出不要截图、录屏或公开分享。

## 从源码构建部署器

这部分用于从 main 构建 v1.2.1 待发布源码，不是下载已发布 EXE，也不是构建本文档站。正式 Release 资产仍以 Actions 本次产物为准，本机构建的 SHA256 不要求相同。

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout main
git rev-parse HEAD
.\build.ps1 -Edition All
```

仅构建一版时，把 `All` 改为 `CloudDrive2` 或 `OpenList`。产物位于主项目 `dist/`。当前正式发布不包含 Classic/Tkinter 部署器。

完整开发说明见 [开发与贡献](/reference/development/)。
