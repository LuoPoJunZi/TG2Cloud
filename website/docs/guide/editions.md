# 选择合适的 Edition

两个部署器共用任务核心，但分别管理自己的存储网关。下载其中一个即可开始；不是在同一个 EXE 里切换后端。

## 两个版本的区别

| 对比项 | CloudDrive2 Edition | OpenList Edition |
| --- | --- | --- |
| 部署器文件 | `TG2Cloud-CloudDrive2-Deployer.exe` | `TG2Cloud-OpenList-Deployer.exe` |
| 存储网关 | CloudDrive2 | OpenList |
| 默认安装目录 | `/opt/tg2cloud-clouddrive2` | `/opt/tg2cloud-openlist` |
| 本机管理入口 | `127.0.0.1:19798` | `127.0.0.1:5244` |
| 受管部署需要 FUSE | 是 | 产品配置不要求 |
| 最终写入方式 | 临时文件 → 改名 → 复验 | 预留最终文件名 → 直接写入 → 复验 |
| 手动安全备份界面 | 无 | 有，操作会短暂停止服务 |
| 外部已有网关 | 可取消受管安装并填写可达地址 | 按 OpenList Edition 的受管部署流程操作 |

## 已经在用 CloudDrive2

选择 CloudDrive2 Edition，可以沿用你熟悉的网关管理方式。先检查 VPS 是否支持 `/dev/fuse`。同机受管安装时使用部署器默认 Docker 内网地址，不要改成电脑的 `127.0.0.1`。

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

TG2Cloud 当前文档对应 v1.0.3。TG115 v1.6.2 属于前身项目；不能因为数字更大就认为 TG115 更“新”。当前 TG2Cloud 不再提供 Classic/Tkinter 正式部署器。
