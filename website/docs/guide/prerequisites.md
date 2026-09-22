# 部署前准备

准备好一台自己控制的 VPS、一台 Windows 电脑、Telegram Bot 配置，以及一个可写的云存储目标。

## 推荐环境与硬门槛

| 项目 | 基础建议 | 说明 |
| --- | --- | --- |
| VPS | 2 核 / 4GB 内存 / 50GB SSD | 批量使用可考虑 4 核 / 8GB / 80～100GB |
| 系统 | Ubuntu 22.04、24.04 或 Debian 12，64 位 | 项目说明支持 x86_64、ARM64 |
| 登录权限 | root 或可用 sudo | 非免密 sudo 需准备相应密码 |
| 本地电脑 | Windows 10/11，64 位 | 用于运行部署器和管理页 SSH 隧道 |
| 网络 | VPS 可达 Telegram、镜像仓库及目的端 | 按实际文件量准备流量 |
| CloudDrive2 | 受管容器需要 `/dev/fuse` | OpenList Edition 产品配置不要求 FUSE |

项目安装脚本约以 **1.8GB 内存、安装文件系统至少 8GB 可用空间**作为基础检查之一。50GB 是推荐磁盘容量，不是唯一硬门槛。满足最低检查也不等于可以安全使用默认 20GB 任务预算，最终以部署器实时探测和复检为准。

## VPS 信息清单

准备服务器 IP 或域名、SSH 端口、用户名，以及密码或 SSH 私钥。私钥设有口令时同时准备口令。非 root 用户还需确认 sudo 可用。

首次 SSH 连接应能通过服务商控制台核对主机指纹。不要只因“这是自己的 IP”就忽略指纹变化。

## Telegram 信息清单

| 字段 | 获取或确认方式 |
| --- | --- |
| Bot Token | 从 Telegram 的 `@BotFather` 创建或管理自己的 Bot |
| API ID | 在 [my.telegram.org](https://my.telegram.org) 创建应用后获取 |
| API Hash | 与 API ID 配套的应用凭据 |
| Allowed User | 你本人的 Telegram 数字 ID，不是 `@用户名` |

详见 [Telegram 配置](/deploy/telegram/)。

## 云存储与 WebDAV

云存储的登录、授权和挂载在你自己的 CloudDrive2 或 OpenList 后台完成。准备独立 WebDAV 用户，不要把云盘登录密码当成 WebDAV 密码。

建议先选一个专门的测试文件夹，确认能列目录、上传并删除小文件，再作为正式目标。CloudDrive2 还需要验证改名能力。

:::danger 不要把真实配置发出来
本网站不收集任何配置。不要将 Bot Token、API Hash、密码、私钥、Cookie、OAuth 凭据或含真实信息的截图发到公开 Issue。
:::

## 完成准备后

先 [下载并核对部署器](/download/)，再按 [完整部署流程](/guide/quick-start/) 操作。安装目录或网关管理方式变化后，需要重新探测 VPS 资源。
