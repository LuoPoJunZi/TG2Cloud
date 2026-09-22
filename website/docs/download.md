# 下载与 SHA-256 校验

本文档核对的发布版本为 **TG2Cloud v1.0.2**。获取程序请使用项目自己的 GitHub Releases，不使用第三方改包。

## 下载对应版本

| 版本 | 发布文件 | 教程 |
| --- | --- | --- |
| CloudDrive2 Edition | [下载 CloudDrive2 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.0.2/TG2Cloud-CloudDrive2-Deployer.exe) | [CloudDrive2 部署](/deploy/clouddrive2/) |
| OpenList Edition | [下载 OpenList 部署器](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.0.2/TG2Cloud-OpenList-Deployer.exe) | [OpenList 部署](/deploy/openlist/) |
| 校验清单 | [下载 SHA256SUMS.txt](https://github.com/LuoPoJunZi/TG2Cloud/releases/download/v1.0.2/SHA256SUMS.txt) | 与下载的 EXE 逐项核对 |

[查看 v1.0.2 发布页](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.0.2) · [查看最新 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/latest) · [全部 Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases)

:::info 固定版本与最新版本
本页直接下载按钮固定到 v1.0.2，确保教程、程序与校验清单对应。“最新 Release”可能在未来指向更新版本，届时应使用那个版本自己的校验文件和发布说明。
:::

## 在 Windows 中计算校验值

打开文件所在目录，在 PowerShell 中执行与你下载的 Edition 对应的一条命令：

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

打开同一 Release 下载的 `SHA256SUMS.txt`，找到相同文件名，比较完整 SHA-256。只下载一版时，另一条命令可跳过。

校验不一致时停止运行，删除损坏的下载文件并从项目正式 Release 重新获取。文件大小相同不能替代 SHA-256 比较。

## Windows 提示未知发布者

v1.0.2 的 Windows EXE 尚未提供商业代码签名，SmartScreen 可能显示“未知发布者”。这与文件是否来自正确发布源是不同的问题。

核对仓库、Release 标签、文件名和 SHA-256；无法确认来源时不要运行。**不建议关闭 Defender、Windows Security 或全局安全检查。**

## 从源码构建部署器

这部分用于构建主项目，不是构建本文档站。

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout v1.0.2
.\build.ps1 -Edition All
```

仅构建一版时，把 `All` 改为 `CloudDrive2` 或 `OpenList`。产物位于主项目 `dist/`。当前正式发布不包含 Classic/Tkinter 部署器。

完整开发说明见 [开发与贡献](/reference/development/)。
