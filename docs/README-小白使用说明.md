# TG2Cloud v1.0.1：小白使用说明

> TG2Cloud v1.0.1；适用电脑：Windows 10 / Windows 11
> 64 位；适用 VPS：Ubuntu 或 Debian 64 位；推荐 VPS：2 核 CPU、4GB 内存、50GB 硬盘。

---

## 一、它能自动做什么

填写资料后点击“一键部署基础环境”，程序会自动：

1. 通过密码或 SSH 私钥连接 VPS；
2. 显示并确认 VPS 主机密钥指纹；
3. 只读检查 Linux 系统、CPU、内存、目标文件系统、inode 和 FUSE，并给出实例级存储建议；
4. 上传完整部署包；
5. 安装 Docker、Docker Compose、FUSE 等运行环境；
6. 按所选产品安装并启动 CloudDrive2 或 OpenList 容器；
7. 构建并启动 Telegram Bot；
8. 建立 SQLite 持久化任务队列；
9. 默认配置 20GB 本地任务预算和 8GB 磁盘安全线，也可由你手动应用 VPS 实例建议；
10. 单文件超过预算时自动切换为不完整落盘的流式传输；
11. 启用 CPU、内存、磁盘、网络和错误率动态调度；
12. 配置异常自动重启、VPS 开机自动启动和日志轮转；
13. 执行 Bot 容器基础健康检查并显示结果。

以下两件事必须由你本人完成：

- 登录所选存储服务；
- 在 CloudDrive2 或 OpenList 中由本人添加自己的云存储、创建专用 WebDAV 用户并设置权限。

部署器不会要求开发工具账号密码，也不会替你登录任何云存储。

---

## 二、使用前必须准备

### VPS

- Ubuntu 22.04 / 24.04，或 Debian 12 64 位；
- 个人基础使用推荐 2 核 CPU、4GB 内存、50GB SSD；
- 大量或长期批量传输推荐 4 核 CPU、8GB 内存、80～100GB SSD；
- 公网 IP 或域名；
- SSH 端口、用户名；
- VPS 登录密码，或者 SSH 私钥；
- 如果登录用户不是 root：准备 sudo 密码，或者确保该用户可以免密 sudo；
- CloudDrive2 版必须支持 `/dev/fuse`；OpenList 版不需要 FUSE；
- VPS 应能稳定访问 Telegram 和 Docker 镜像仓库，端口带宽建议 100Mbps 或以上，并准备
  足够的月流量。实际速度仍受 Telegram、VPS 线路、CloudDrive2 和 115 状态共同影响。

50GB 硬盘配合默认的 20GB 本地任务预算和 8GB 磁盘安全线可以使用，但最终应以部署器对
当前可用空间给出的建议和部署前复检为准。CloudDrive2 可能另外占用缓存。单文件超过本地
预算时 Bot 自动使用流式模式，不会先完整写入 VPS；经常批量处理大文件时仍应优先选择更大的
硬盘，因为 CloudDrive2 缓存不受 Bot 额度直接控制。

### Telegram

- Bot Token：从 `@BotFather` 获取；
- API ID：从 `https://my.telegram.org` 获取；
- API Hash：从 `https://my.telegram.org` 获取；
- 你自己的 Telegram 数字 ID。

### CloudDrive2

- 可正常使用 WebDAV 的 CloudDrive2 环境；具体会员或功能要求以 CloudDrive2 和所选云存储
  当前规则为准；
- CloudDrive2 WebDAV 用户名；
- CloudDrive2 WebDAV 密码；
- 计划由本人挂载的云存储（115 可作为常用示例）；
- 所选云存储有足够剩余空间；云存储会员资格不是 TG2Cloud 代码本身的要求；
- WebDAV 根目录后的相对子目录；WebDAV 根目录已经选中目标文件夹时留空。

CloudDrive2 和云存储账号由你本人在 CloudDrive2 管理页登录。部署器不需要这些账号的
登录密码，只需要你另外设置的 WebDAV 用户名和密码。

---

## 三、第一次部署

### 第 1 步：运行

根据希望使用的中转方式，运行对应的 PySide6 部署器：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

两个程序都使用相同的新版 PySide6 界面，但安装目录、容器、网络和端口彼此隔离。原
Tkinter Classic 版及 CMD 启动器已经从当前项目清理，请直接运行对应的 EXE。

Windows 可能显示“未知发布者”，原因是本程序没有购买商业代码签名证书。你可以先在
`SHA256SUMS.txt` 中核对文件校验值。

### 第 2 步：填写 VPS

- `VPS IP 或域名`：服务商提供的公网地址；
- `SSH 端口`：通常是 22；
- `SSH 用户名`：通常是 root、ubuntu 或 debian；
- `登录方式`：选择“密码”或“SSH 密钥”；
- 密码登录：填写 VPS 登录密码；
- 密钥登录：选择私钥文件，有口令时再填写私钥口令；
- 非 root 用户：填写 sudo 密码；如果已经配置免密 sudo，可以留空。

先点击“测试 SSH”。连接成功后，部署器会同时读取 VPS 资源，并在“部署选项”页显示当前
实例的“均衡模式”和“流式优先”建议。

首次连接会出现 VPS 主机密钥指纹。应当与 VPS 服务商控制台显示的指纹核对，一致后才能点击
“信任并连接”。

### 第 3 步：填写 Telegram

- Bot Token；
- Telegram API ID；
- Telegram API Hash；
- 你的 Telegram 数字 ID。

API Hash、Bot Token 都是秘密信息，不要发到群聊或公开网页。

### 第 4 步：填写 CloudDrive2

如果由部署器安装 CloudDrive2，保持默认 WebDAV 地址：

```text
http://tg2cloud-clouddrive2:19798/dav
```

填写：

- WebDAV 用户名；
- WebDAV 密码；
- WebDAV 根目录后的子目录。

如果 WebDAV 根目录已经选中 `115open/Telegram`，子目录必须留空，文件会直接保存到
这个 `Telegram` 文件夹。不要再填写 `115/Telegram`，否则会产生
`Telegram/115/Telegram` 套娃。

如果勾选“在 VPS 中安装并管理 CloudDrive2”，Bot 会固定使用容器内网地址
`http://tg2cloud-clouddrive2:19798/dav`。不要填写 VPS 公网 IP，也不要把 19798 端口写成
`https://`；该端口本身是 HTTP，管理页面通过 SSH 隧道安全访问。

### 第 5 步：检测并选择存储方案

```text
安装目录：/opt/tg2cloud-clouddrive2
本地任务预算：20GB
磁盘最少保留：8GB
时区：Asia/Shanghai
```

上面仍是源码默认值，不会因为检测而自动变化。你可以在“部署选项”页点击：

- `检测 VPS 并推荐`：重新读取当前 VPS，不修改输入框；
- `应用均衡值`：为普通落盘和失败保留留出较多空间；
- `应用流式优先值`：降低完整落盘预算，更适合小硬盘 VPS，但线路中断后更可能从头传输。

建议优先使用部署器标注“推荐”的方案。点击应用只改本次部署表单，不修改项目源码默认值。
如果安装目录或“由 VPS 管理 CloudDrive2”选项发生变化，必须重新检测。部署器不会自动
分区、扩容、挂载或格式化磁盘。

### 第 6 步：一键部署

点击：

```text
一键部署基础环境
```

正常需要约 5～15 分钟，主要时间用于：

- VPS 安装 Docker；
- 下载 CloudDrive2 镜像；
- 构建 Bot 镜像；
- 安装 Python 依赖；
- 等待健康检查。

不要在部署过程中关闭部署器。

正式写入安装文件前，部署器会再检测一次。若内存不足、受管 CloudDrive2 缺少 FUSE、inode
过低，或当前预算和保留线超过实际可用空间，部署会安全停止并显示原因与可用建议。

### 使用 OpenList 版时

OpenList 版增加“部署 OpenList”和“配置 WebDAV”两个引导区：

1. 首次部署前复制界面生成的管理员密码。它只对全新 OpenList 数据目录生效；已有实例不会被
   自动重置。
2. 基础部署成功后点击“打开 OpenList 管理页”，浏览器固定访问 `http://127.0.0.1:5244`。
   这个地址通过 SSH 隧道连接 VPS，5244 不开放公网；本机端口被占用时不会随机改端口。
3. 由本人登录 OpenList，添加 `115 Open` 存储。部署器不会读取或收集 115 Cookie、Token。
4. 在 OpenList 创建普通用户 `tg2cloud`，复制部署器生成的 28 位 WebDAV 密码。目标子目录
   默认留空，即使用该用户的 WebDAV 根目录；如需子目录可填写 `Telegram` 等相对路径。为用户
   授予目录列表、读取、写入、改名／移动和删除权限。
5. 返回部署器执行“WebDAV 验收”。基础部署成功和 WebDAV 验收成功是两个阶段；尚未完成
   115/WebDAV 配置时，看到“等待用户配置”是正常的。

OpenList 默认安装目录为 `/opt/tg2cloud-openlist`，本地任务预算 `20GB`、磁盘最少保留 `8GB`、
时区 `Asia/Shanghai`。密码只保留在当前界面会话中；只有主动点击“重新生成”才会改变。
以后重新打开部署器升级已有 TG2Cloud 实例时，默认保留 VPS 当前完整 `.env`。只有明确勾选
“使用本页配置覆盖 VPS 当前 .env”才应用本次表单；显式覆盖时还可选择继续保留 VPS 当前
WebDAV 与管理员配置。旧密码只在 VPS 内复用，不会显示或传回电脑。

---

## 四、登录 CloudDrive2 并挂载 115

部署成功后点击：

```text
打开 CloudDrive2 管理页
```

部署器会建立 SSH 安全隧道，然后在浏览器打开类似地址：

```text
http://127.0.0.1:19798
```

这不是公网地址，只有你的电脑通过当前 SSH 隧道才能访问。部署器会先实际访问一次这个地址，
收到 CloudDrive2 的 HTTP 响应后才打开浏览器；旧隧道失效时会自动重建。管理入口固定使用
本机 `127.0.0.1:19798`，不会回退到随机端口；如果该端口已被占用，先关闭占用程序后重试。

若提示 VPS 禁止 TCP 端口转发，需要检查 SSH 服务的 `AllowTcpForwarding`，以及
`PermitOpen` 是否允许 `127.0.0.1:19798`。浏览器的 `ERR_EMPTY_RESPONSE` 属于 SSH 隧道问题；
日志中的 `401 Unauthorized` 属于尚未配置或不匹配的 WebDAV 凭据，两者不要混在一起处理。

在 CloudDrive2 中完成：

1. 登录 CloudDrive2 会员账号；
2. 添加 115；
3. 按 CloudDrive2 提示登录或扫码；
4. 确认能浏览 115 文件；
5. 在设置中开启 WebDAV；
6. 如果 WebDAV 根目录已经是目标 Telegram 文件夹，部署器中的子目录保持空白。

完成后点击：

```text
WebDAV 验收（写入测试文件）
```

该验收不是只看容器是否运行，而是会自动执行：

```text
在 VPS 生成 256 字节随机测试文件
→ rclone 上传到 CloudDrive2 WebDAV
→ CloudDrive2 WebDAV 临时文件大小校验
→ 远端改名
→ 再次校验
→ 删除远端和 VPS 测试文件
```

只有输出 `TG2CLOUD_DESTINATION=OK`，部署器才会显示“验收通过”。这证明文件已经写入
CloudDrive2 WebDAV，但不能单独证明 115 官方端已经保存完成。最终应在 115 官方客户端
确认文件大小正常，并能打开或播放。

Bot 每 30 秒自动重新检查 CloudDrive2，不需要重新部署。

---

## 五、以后怎么使用

1. 在 Telegram 找到视频或文件；
2. 在与自己的私人 Bot 的一对一聊天中转发；
3. Bot 自动审核并返回任务编号；
4. 暂未开始的任务显示“在排队”；
5. VPS 根据 CPU、内存、磁盘、网络和服务状态动态放行；
6. 不超过本地预算的文件先下载到 VPS，再由 rclone 上传；
7. 超过本地预算的单个文件直接执行 Telegram → rclone → CloudDrive2 流式传输；
8. CloudDrive2 WebDAV 大小验证通过；
9. VPS 删除本地临时文件并释放额度；
10. Bot 显示“Bot 传输已完成（CloudDrive2 已接收）”，并自动处理后续任务；
11. CloudDrive2 继续处理网盘写入；这一步不一定出现在“上传任务”列表中；
12. 按自己的使用需要在 CloudDrive2 或 115 客户端查看文件。

Bot 不再要求或提示逐个执行人工确认。完成传输并通过 WebDAV 远端大小复验后，日常界面统一
显示“Bot 完成”，历史兼容状态也会合并到同一个统计中。

你不需要手动分批，也不需要重新转发已经获得任务编号的文件。当前正式支持范围是
“你本人和 Bot 的一对一私聊”；群组和频道消息会被拒绝，即使发送者是配置的本人 ID。

文件直接保存在“WebDAV 根目录 + 可选子目录”中，不再按年份和月份建立子目录。
例如 WebDAV 根目录已经是 `115open/Telegram` 且子目录留空时，最终路径为：

```text
115open/Telegram/视频文件名.mp4
```

---

## 六、Bot 命令

```text
/start
/help
/queue [页码]
/status
/performance
/doctor
/pause
/resume
/task <任务编号>
/watch <任务编号>
/retry <任务编号>
/retry all
/cancel <任务编号>
/stream <任务编号>
/orphans
/orphans clean
```

Bot 启动后，Telegram 输入框左侧会出现原生命令菜单，菜单说明统一为 6 个中文字符：

```text
/status   查看系统状态
/queue    查看最近任务
/pause    暂停任务调度
/resume   恢复任务调度
/doctor   运行系统诊断
/orphans  检查临时文件
/help     查看使用帮助
```

点击菜单项会把对应命令发送给 Bot。Bot 的新回复不在消息下方放置按钮；全部文字命令仍然有效。
最近任务每页显示 5 项，使用 `/queue 2`、`/queue 3` 翻页；使用 `/task <任务编号>` 查看详情，
使用 `/retry <任务编号>`、`/stream <任务编号>` 和 `/cancel <任务编号>` 执行任务操作。取消仍会
先安全删除并复查本任务远端文件，再删除本地副本；远端无法确认删除时会保留本地数据。
“检查临时文件”只做只读巡检；删除遗留文件仍需输入 `/orphans clean` 并按一次性确认码操作。

`/status` 和 `/performance` 现在显示同一份完整单页状态，不需要在两个菜单之间切换。状态页用
四字标签对齐冒号，集中展示目的端、当前传输、并发窗口、空间、资源、速度和任务统计；数量为
零的历史任务分类不会显示，旧版确认状态统一计入“Bot 完成”。

`/pause` 不删除数据、不打断活动传输，只暂停启动新传输，重启后仍保持暂停；
`/resume` 恢复调度，但不会绕过磁盘、内存或目的端条件。已校验任务的清理可以继续。
`/doctor` 只显示已有采样和检查状态，不写远端。`/watch` 每 5 秒尝试更新同一条消息，
完成／失败后停止，服务重启后需重新订阅。进度不是 115 后台入库进度。
`/retry all` 每次最多重排 100 个失败任务，不处理取消清理未完成的任务。
`/stream` 可把仍在排队或下载失败的任务改成不完整落盘的流式传输，适合磁盘长期不足；
流式中断后通常从头重传。`/orphans` 只读统计未被活动任务跟踪的 `.uploading-*` 文件，
不显示原文件名。需要清理时发送 `/orphans clean`，Bot 会给出 5 分钟有效的一次性确认码；
按提示再次发送完整命令后才会删除。确认时会重新扫描，已关联活动任务的文件会跳过，
每项删除后还会复查远端确实不存在；一次最多处理 100 项。
取消失败时，本地数据与两个远端路径会保留；再次 `/cancel` 清理，或用 `/retry <编号>`
明确撤销取消意图后恢复传输。

---

## 七、重新运行部署器会怎样

重新运行“一键部署基础环境”用于：

- 修改 Telegram 或 WebDAV 配置；
- 更新 Bot 程序；
- 修复损坏的部署；
- 重新执行基础健康检查。

程序会保留：

- SQLite 任务数据库；
- 下载目录；
- 日志；
- CloudDrive2 配置；
- CloudDrive2 挂载数据。

重新部署后，Bot 会把已有 `rclone.conf` 中的 `cd2` 配置更新为本次填写的
WebDAV 地址、用户名和密码，不会继续使用旧凭据。

注意：只在输入框中改值后直接点击“WebDAV 验收”不会更新 VPS；必须先重新执行
“一键部署基础环境”，看到部署成功后再验收。

如果日志出现 `lookup tg2cloud-clouddrive2`，点击“修复 CloudDrive2 网络”。部署器会保留现有
CloudDrive2 登录、115 挂载和文件，只刷新 Docker 网络别名，并自动执行真实 WebDAV 验收。

更新前，旧程序配置会备份到：

```text
/opt/tg2cloud-clouddrive2-backups/
```

部署完成时会统计备份数量和占用，超过 5GB 会提示，但不会自动删除。查看备份统计：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh backups
```

确认旧回退点不再需要后，可手动按类型各保留最近 5 份：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh prune-backups 5
```

参数只能是 1～50。命令只处理该目录下程序生成的 `config-*`、`database-*` 和 `env-*` 文件，
不会删除下载文件、日志、CloudDrive2 数据或其他文件。旧备份删除后不能通过 TG2Cloud 恢复，
因此第一次升级完成并实际传输验证前不要急于清理。

---

## 八、安全设计

- VPS 密码、私钥口令和 sudo 密码不会写入本地配置文件；
- 本地临时配置在部署结束后自动删除；
- 上传到 VPS 的临时目录为随机名称，权限为 700，结束后自动删除；
- VPS 正式 `.env` 权限设置为 600；
- rclone 将 WebDAV 密码转换为 obscure 格式；
- CloudDrive2 和 Python 基础镜像锁定到经过复核的不可变 SHA-256 摘要；
- 普通重新部署不会自动拉取未经复核的新基础镜像；
- CloudDrive2 的 19798 端口只绑定 VPS 的 `127.0.0.1`；
- 管理页通过 SSH 隧道访问，不直接暴露公网；
- 只有配置的 Telegram 数字 ID 能够使用 Bot；
- Bot 容器使用专用非 root 用户运行，并启用只读根文件系统、移除 Linux capabilities；
- VPS 的配置、下载、日志和备份目录仅允许对应服务用户或 root 访问；
- 安装目录经过完整校验和 shell 参数转义，不能把异常路径当成远程命令执行；
- Docker 构建上下文使用白名单，只包含 Dockerfile、依赖清单和 Bot 源码，不包含
  `.env`、下载文件、日志或 CloudDrive2 挂载内容；
- 普通落盘模式在远端验证成功前不会删除本地完整文件；
- 普通落盘模式上传失败会保留本地完整文件；
- 流式模式使用准确文件大小和背压控制，不在 VPS 保留完整副本；中断后会从头重试；
- `/cancel` 必须先确认本任务远端文件已经清理，才会删除 VPS 本地副本并标记取消。

注意：CloudDrive2 为实现 FUSE 挂载仍需特权容器和宿主机 PID 命名空间；因此建议这台 VPS
只运行本项目。服务器 root 用户始终能够读取容器配置，任何 VPS 自动化都无法防范已经取得
root 权限的攻击者。

20GB 是 Bot 普通落盘模式的下载和待上传文件预算。大于该预算的单文件使用流式模式，不按
完整文件大小占用这 20GB。CloudDrive2 是专有程序，可能为 115 后台上传建立额外缓存；
程序会监控整个 VPS 分区的真实剩余空间并在安全线触发时暂停新传输，但不能保证
CloudDrive2 的内部缓存也严格限制为 20GB。若其任务长期堆积，应暂停继续转发；需要硬隔离
时应给 CloudDrive2 使用单独数据盘或文件系统配额。

---

## 九、常见问题

### 提示 VPS 没有 `/dev/fuse`

CloudDrive2 官方 Docker 挂载方式需要 FUSE。请在 VPS 控制台开启 FUSE，或联系服务商。

### Bot 一直显示在排队

依次检查：

1. CloudDrive2 是否已经登录；
2. 115 是否已经添加；
3. WebDAV 是否开启；
4. WebDAV 用户名、密码是否正确；
5. 目标路径是否正确；
6. `/status` 中 CloudDrive2 状态是否正常；
7. VPS 是否还有足够磁盘空间。

如果 Docker 数据目录在另一个文件系统，部署器会分别显示和检查两边空间；不能只看 TG2Cloud
安装目录所在磁盘。

### 单文件超过 20GB 会怎样

它不会永久排队，也不要求把本地预算调大。系统会自动标记为流式模式，一边从 Telegram
读取，一边通过 rclone 写入 CloudDrive2。流式模式不会在 VPS 保留完整副本，所以线路中断
后需要从头重试；CloudDrive2 自身仍可能使用缓存，磁盘安全线仍然有效。

### 文件很多，还需要逐个确认吗

不需要。Bot 不再要求或提示逐个确认。`Bot 传输已完成（CloudDrive2 已接收）` 表示 VPS 已经
完成 WebDAV 远端大小复验和本地清理；`/status` 中的“Bot 完成”也会合并旧版留下的确认状态。
“当前传输”全部为 0 时，说明 Bot 此刻没有实际传输任务；历史完成数量不代表当前网速。

### SSH 连接失败

检查 IP、SSH 端口、用户名、密码或私钥；同时检查 VPS 服务商的安全组是否放行 SSH 端口。

如果提示 `Host key for server ... does not match`，不是密码填错，而是本机保存的旧 SSH 主机
密钥与当前服务器不一致。VPS 重装、恢复快照、重新生成 SSH 密钥或 IP 被重新分配后可能出现；
如果没有这些变化，先停止操作并通过服务商控制台确认服务器身份。

新版部署器遇到这种情况时，会显示服务器地址、旧／新密钥类型和两组 SHA-256 指纹：

1. 从 VPS 服务商网页控制台执行以下命令，记录当前 `SHA256:...` 指纹：

   ```bash
   sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
   sudo ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub -E sha256
   ```

2. 新指纹不一致或原因不明时点击“取消”。原主机记录不会改变，连接也不会继续。
3. 完全一致时点击“更新并重新连接”。部署器只更新当前 VPS 与 SSH 端口的对应记录，保留其他
   VPS 记录，并自动重试刚才的操作一次。无需手动编辑或清空 `known_hosts`。
4. 如果随后出现“身份认证失败”，再单独检查用户名、密码、私钥和私钥口令；这表示主机身份已
   核验通过，但登录凭据不正确。

部署器不会静默接受变化，用户取消时也不会把操作显示成普通连接错误。不要把真实 IP、主机
公钥、VPS 密码或私钥发布到 Issue、日志截图或聊天记录中。

### 部署器被安全软件提示

单文件 EXE 由 PyInstaller 打包，部分安全软件会对未签名的自解压程序作启发式提示。请核对
`SHA256SUMS.txt`，也可以直接查看随包附带的完整源代码。

### 想查看 VPS 日志

通过 SSH 登录 VPS 后执行：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh logs
```

只查看状态：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh status
```

手动执行与部署器相同的 CloudDrive2 WebDAV 写入验收：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh verify
```

重启 Bot：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh restart
```

`restart` 不应用配置变化。手工部署时，将新配置保存在安装目录之外，然后运行：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh apply-config /absolute/new-config.env
sudo /opt/tg2cloud-clouddrive2/manage.sh check
```

新配置会先备份和预检，再应用到 Bot，并核对运行环境、代码指纹和基础健康。
失败时恢复旧配置；如旧容器仍不能恢复，命令会报错，需人工检查。
整个流程不自动重启 CloudDrive2，不输出配置值，也不会写远端验收文件。
更换目的账号或目标目录前，应先处理完已有队列和失败保留任务。
程序升级仍使用新版部署器，或把新版 payload 交给 `remote_install.sh`。安装脚本会先在隔离目录
构建和预检，再备份旧程序／配置以及一致性 SQLite 快照；新 Bot 未通过健康核验时自动恢复
旧程序、旧配置、旧数据库和旧镜像。下载文件与 CloudDrive2 数据仍不复制进升级备份；
`manage.sh update` 不会从 GitHub 拉取代码。

---

## 十、当前验证边界

当前发布边界见 [发布说明](../RELEASE_NOTES.md)和 [更新记录](../CHANGELOG.md)。
源码测试不能代替真实 VPS 与目标云存储的生产环境验收。

由于没有你的真实 VPS、Telegram 和 CloudDrive2 凭据，交付前无法替你完成真实 VPS 的端到端上传测试。
第一次使用时，部署器会在你的 VPS 上执行真实安装和健康检查；完成 CloudDrive2 与 115 登录后，
建议先转发一个 5～20MB 的测试文件，确认 115 中出现并收到 Bot 完成通知，再开始批量使用。
