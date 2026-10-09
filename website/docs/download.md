# 下载与 SHA-256 校验

本文档对应 **TG2Cloud v1.1.3** 源码（待发布），当前可下载的正式 EXE 仍为 v1.1.2。获取程序请使用项目自己的 GitHub Releases，不使用第三方改包。

## 下载已发布版本

| 版本 | 发布文件 | 教程 |
| --- | --- | --- |
| CloudDrive2 Edition | [下载 CloudDrive2 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.1.2/TG2Cloud-CloudDrive2-Deployer.exe) | [CloudDrive2 部署](/deploy/clouddrive2/) |
| OpenList Edition | [下载 OpenList 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.1.2/TG2Cloud-OpenList-Deployer.exe) | [OpenList 部署](/deploy/openlist/) |
| 校验清单 | [下载 SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.1.2/SHA256SUMS.txt) | 与下载的 EXE 逐项核对 |

[查看 v1.1.2 发布页](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.1.2) · [查看最新 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/latest) · [全部 Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases)

:::info 源码版本不等于已发布版本
v1.1.3 的源码提交不会自动创建 Release。本页下载按钮继续指向真实存在的 v1.1.2 资产；新版本正式发布后再更新，不能用旧 EXE 的校验值代替新产物。“最新 Release”可能指向更新版本，应使用那个版本自己的校验文件和发布说明。
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

轻量入口来自主分支；Python 向导模块固定到审查并通过 CI 的源码 commit，实际部署 payload 只取正式稳定 Release 的不可变 commit，不取 main、RC 或草稿。出现下载错误应停止，不要把命令退出当作安装成功。

:::warning 验收范围
当前脚本完成 CloudDrive2 真实 VPS 的只读预检，没有执行首次安装或实际跨版本升级；OpenList 脚本实机验收暂缓。执行写入前请备份、安排维护窗口，并阅读 [完整 VPS 脚本指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。不要同时运行 EXE 和命令行向导。
:::

## 从源码构建部署器

这部分用于构建当前主分支的 v1.1.3 源码，不是下载已发布 EXE，也不是构建本文档站。

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout main
git rev-parse HEAD
.\build.ps1 -Edition All
```

仅构建一版时，把 `All` 改为 `CloudDrive2` 或 `OpenList`。产物位于主项目 `dist/`。当前正式发布不包含 Classic/Tkinter 部署器。

完整开发说明见 [开发与贡献](/reference/development/)。
