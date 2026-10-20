# 从零开始部署

按下面的顺序完成第一次安装。先部署基础环境，再挂载云存储，最后做真实写入验收；不要把其中一个阶段的成功当成整个流程已经完成。

:::tip 先选对教程分支
使用 CloudDrive2 的用户跟随 [CloudDrive2 专页](/deploy/clouddrive2/)；使用 OpenList 的用户跟随 [OpenList 专页](/deploy/openlist/)。下面先给出两版共用的完整路线。
:::

从 v1.3.0 起优先使用 [VPS 单行入口](/download/)，内网使用独立 LAN 入口。向导收集信息、确认计划，再复用 Docker 部署资源；脚本实机验收范围与 EXE 不同。下文保留 v1.2.1 历史图形部署教程。

## v1.3.0 脚本部署路线

:::tip v1.3.2 安装与管理
默认向导使用中文编号与分段提示：WebDAV 用户名回车默认 tg2cloud、密码回车生成 8 位，保存子目录可留空，账号根目录在自己的后台设置。新装不再询问时区，默认 Asia/Shanghai；升级保留原有配置。计划确认后安装离线 `tg2cloud` 菜单，首次建号凭据只向当前私有终端汇总显示，请勿录屏。已部署主机需重新运行相应入口并确认升级，不会自动改变。菜单边界见[本地管理](/operations/maintenance/)。
:::

1. 通过 SSH 登录自己的 Debian／Ubuntu 原生 64 位 AMD64／ARM64 主机，准备 Telegram 配置；公网 VPS 还需正确解析的管理域名。正式 v1.4.0 与匹配 helper 已发布，Oracle 与 NAS 的实际限制及待验收项目见[部署前准备](/guide/prerequisites/)。
2. 从[下载页](/download/)选择公网或内网入口，运行单行命令并选择 CloudDrive2／OpenList。
3. 首次安装选择流式优先、均衡或手动磁盘预算，填写 Telegram 和专用 WebDAV 信息；已有完整实例升级复用原配置。
4. 核对计划后确认执行。公网向导配置 HTTPS；可信内网向导使用手填私有 IPv4 和固定管理端口。
5. 在自己的网关中挂载云存储，配置专用 WebDAV 用户，返回终端确认执行验收，再向 Bot 发送小文件检查实际结果。

CloudDrive2 本次旧候选到正式 v1.3.0 的人工迁移及用户使用验收已完成；这不是新装流程或标准自动升级的验收。OpenList 脚本实机验收暂缓，首次安装、故障回退和 NAS 等需独立验证，见[验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。完整参数和中断处理见 [VPS 指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)及[内网指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/LAN-INSTALL.md)。

## v1.2.1 历史图形部署路线

## 第一步：下载并检查文件

进入 [下载与校验](/download/)，选择对应 Edition 的 EXE，同时下载同一 Release 中的 `SHA256SUMS.txt`。在 Windows PowerShell 计算 EXE 的 SHA-256，与清单中的相应条目逐字符比较。

不要把别的版本的校验值用于当前文件，也不要为了运行程序关闭安全软件。

## 第二步：连接自己的 VPS

打开部署器，填写服务器地址、SSH 端口、用户名和登录方式。点击 **“测试 SSH”**；第一次连接时，通过服务商控制台核对显示的主机指纹，再确认连接。

SSH 成功后读取资源。连接失败先处理 [SSH 问题](/troubleshooting/ssh/)，不要反复点击部署。

## 第三步：配置 Telegram

填写 Bot Token、API ID、API Hash 和本人数字 ID。四项用途不同，不能互相替代。

确保没有旧 Bot 实例使用同一个 Token 运行。TG2Cloud 只处理允许用户的一对一私聊。

## 第四步：设置网关与任务预算

CloudDrive2 同机受管安装保持默认内网 WebDAV 地址，预先选定专用用户名和密码。OpenList 根据“配置 WebDAV”页记录本次生成的用户凭据。

点击 **“检测 VPS 并推荐”**，按需求主动选择均衡值或流式优先值。确认安装目录、本地任务预算和磁盘最少保留，再继续。

:::warning 默认值不是对所有 VPS 的建议值
20GB 本地任务预算、8GB 磁盘保留只是源码默认。小磁盘机器请以实际探测为准；不要为了通过检查把安全线改为接近零。
:::

## 第五步：部署基础环境

点击 **“一键部署基础环境”**，观察日志。构建或拉取镜像期间，不要重复点击部署、网络修复或验收。基础容器健康后，部署器会自动打开 HTTPS 管理入口配置；HTTPS 全部自检通过前，主界面保持“待配置 HTTPS”。

此阶段检查 Bot、网关和网络健康。尤其 OpenList 首次安装时，尚未挂载云盘或创建 WebDAV 用户，并不自动意味着基础部署失败。

## 第六步：配置 HTTPS 并挂载自己的存储

| 使用的版本 | HTTPS 通过后点击 | 后端回环端口 |
| --- | --- | --- |
| CloudDrive2 | 打开 CloudDrive2 域名 | `127.0.0.1:19798`（不公开） |
| OpenList | 打开 OpenList 域名 | `127.0.0.1:5244`（不公开） |

为当前 Edition 配置独立域名，等待证书、HTTPS、HTTP 跳转、公开 `/dav` 阻断和回环监听全部通过，再通过域名管理页完成登录、存储授权、目标目录和 WebDAV 用户设置。管理域名只代理界面，不能作为 Bot 的 WebDAV 地址。

CloudDrive2 创建与部署器完全一致的 WebDAV 用户，取消只读并确认读写、改名、删除权限。OpenList 创建专用普通用户，确认列表、读取、写入和删除权限。

## 第七步：WebDAV 真实验收

回到部署器，点击 **“WebDAV 验收”**。只有出现下面的标记才说明整体验收通过：

```text
TG2CLOUD_DESTINATION=OK
```

CloudDrive2 验收包含临时写入、改名及复验；OpenList 当前采用最终路径直接写入，不依赖 MOVE。失败时看第一处失败阶段，不要只看最后一行错误。

## 第八步：发送第一个测试文件

与自己的 Bot 私聊，先发一个有权保存的 5～20MB 小文件。记下任务编号，用 `/queue`、`/task 编号` 和 `/status` 观察处理。

Bot 完成后，在所用云存储的官方客户端确认文件位置、大小与可打开性。随后再测试普通落盘文件、流式文件及测试任务取消。

## 首次部署完成清单

1. SSH 主机身份已核对，资源检查已通过。
2. Bot 仅允许本人数字 ID 使用。
3. 当前 Edition 的 HTTPS 管理入口通过全部自检，19798/5244 没有暴露公网。
4. 网关已经挂载存储，专用 WebDAV 用户具备实际写入权限。
5. 出现 `TG2CLOUD_DESTINATION=OK`。
6. 小文件完整传输，目的端文件位置和内容符合预期。
7. 明白“Bot 完成”与云盘官方最终状态的区别。

日常用法见 [Bot 命令速查](/usage/commands/)，故障按 [FAQ](/faq/) 分类处理。
