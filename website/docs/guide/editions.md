# 选择合适的 Edition

两个 Edition 共用任务核心，分别管理自己的存储网关。在同一套 Linux 入口中按编号选择，不需要两套桌面程序。

## 两个版本的区别

| 对比项 | CloudDrive2 Edition | OpenList Edition |
| --- | --- | --- |
| Linux 向导选择 | `1. CloudDrive2` | `2. OpenList` |
| 存储网关 | CloudDrive2 | OpenList |
| 默认安装目录 | `/opt/tg2cloud-clouddrive2` | `/opt/tg2cloud-openlist` |
| 后端回环端口 | `127.0.0.1:19798` | `127.0.0.1:5244` |
| 公网管理入口 | 独立 HTTPS 域名 | 独立 HTTPS 域名 |
| 受管部署需要 FUSE | 是 | 产品配置不要求 |
| 最终写入方式 | 临时文件 → 改名 → 复验 | 预留最终文件名 → 直接写入 → 复验 |
| 实例快照与隔离预检 | 菜单 13，两版均支持 | 菜单 13，两版均支持 |
| 共享 HTTPS 代理维护 | 有，不包含业务数据 | 有，不包含业务数据 |
| 可信内网管理 | 独立 LAN 入口和私有 IPv4 | 独立 LAN 入口和私有 IPv4 |

## 已经在用 CloudDrive2

选择 CloudDrive2 Edition，可以沿用你熟悉的网关管理方式。先检查 VPS 是否支持 `/dev/fuse`。标准安装使用受管 Docker 内网地址，不要改成 Bot 容器里的 `127.0.0.1`。已有外部或自定义网关不属于任意 URL 自动接管范围，先核对实例身份及冲突。

进入 [CloudDrive2 部署教程](/deploy/clouddrive2/)。

## 准备使用 OpenList

选择 OpenList Edition，在自己的 OpenList 后台添加存储，再创建专用普通用户供 Bot 使用。TG2Cloud 不替你获取云盘 Cookie 或刷新令牌。

进入 [OpenList 部署教程](/deploy/openlist/)。

## 能否同时安装

目录、容器和网络按 Edition 隔离；具备足够资源时可以分别部署。但同一个 Bot Token 不应被两个运行实例长期共用，以免争抢 Telegram updates。通常一个私人转存实例已足够。

:::warning 不等于“支持任意云盘”
最终是否可用，取决于网关、所选存储驱动、账号权限以及真实 WebDAV 写入能力。挂载后能看见文件，不代表一定能成功上传、删除或改名。
:::

## 版本名称不要混用

TG2Cloud 历史 EXE 下载固定为 v1.2.1；后续主要维护脚本入口。TG115 v1.6.2 属于前身项目；不能因为数字更大就认为 TG115 更“新”。当前 TG2Cloud 不再提供 Classic/Tkinter 正式部署器。
