# 常见问题 FAQ

按问题所属阶段排查，避免用一个“修复”按钮处理所有错误。

## 项目与使用

### 只能转存到 115 吗？

不是。目标取决于你在 CloudDrive2 或 OpenList 中挂载并授权的存储。115 是主要测试场景之一；其他存储是否可用，应做真实 WebDAV 和文件测试。

### 可以自动监听频道吗？

当前不可以。你手动选择文件并转发给自己的私人 Bot，VPS 自动处理之后的步骤。它不自动爬取频道，也不批量读取频道历史。

### 必须开 Telegram Premium 吗？

项目准备清单没有把 Premium 列为必需项。但可获取文件、平台限制和实际速率仍受环境影响。不能因此承诺任何会员权益或固定速度。

### 2GB 文件一定几分钟上传完吗？

不能保证。看 Telegram 下载、VPS 网络、WebDAV、网关和云存储的实际瓶颈。[速度说明](/usage/streaming/) 给出了带单位的理论计算，不是实测成绩。

## 安装与登录

### 升级出现 WARNING 需要处理吗？

不能只凭 WARNING 判断失败，也不能把所有警告屏蔽。当前工具区分 `[信息]`、`[提醒]`、`[待核对]` 与 `[错误]`，成功仍看真实退出码、完整标记与逐项摘要；旧工具须显式升级后使用。

| 常见提示 | 如何理解 |
| --- | --- |
| 镜像构建时 pip root 提醒 | 不等于 Bot 正式以 root 运行，仍核对运行用户和后续结果 |
| `skipping ca-certificates.crt` | CA 合集的 rehash 提醒，不单凭这一行判断 TLS |
| 固定 UID 超出系统账号建议范围 | 不代表创建失败，也不要求改成 root 或放宽权限 |
| 容量低于推荐 50GB | 不是唯一硬门槛，但必须通过实际容量和保留线校验 |

安装失败、权限拒绝、磁盘不足、TLS 错误或不健康容器需单独处理。详见[升级反馈](/operations/update/#v1-4-4-安装与升级反馈)。[v1.4.3 日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)与[v1.4.4 双架构记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)各有独立范围，不表示任意 WARNING 无害或全部业务已验收。

### Windows 提示未知发布者怎么办？

已发布 EXE 未提供商业代码签名。核对正式 Release、文件名和 SHA-256，不要直接关闭全局安全防护。[下载与校验](/download/)。

### 没有 Windows 电脑能安装吗？

可以。v1.3.0 起以 Linux 单行向导为主要入口，先检查、收集信息并确认，再复用 Docker 安装资源；已有可核验的受管实例走保留配置升级，业务代码只取正式稳定 Release。CloudDrive2 本次旧候选人工迁移及用户使用验收已完成，OpenList 脚本实机验收暂缓；Windows EXE 停留在 v1.2.1。详见 [下载页的 VPS 入口](/download/)。

### VPS 重装后 Host key 不匹配？

先在服务商控制台核对新指纹，确认身份后按所用 SSH 客户端说明，只更新当前主机与端口的记录；Linux 脚本没有该桌面按钮。不要删除所有服务器记录。[SSH 排查](/troubleshooting/ssh/)。

### ARM64 公网 NAT 首次安装是否有实机记录？

有。用户提供的v1.4.1日志覆盖Ubuntu26.04.1／原生ARM64／公网NAT的CloudDrive2首装、Bot健康、本机HTTPS及WebDAV认证／读写／大小／改名／测试清理，见[验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md)。不是OpenList、任意NAS、升级回退、外网手机或长期续期通过的承诺。

### APT 报没有 Release 文件怎么办？

先在自己的终端执行apt-get update，核对活跃源URI、发行代号和签名配置。本次实际错误是源URI缺少主机名，且APT显示的斜杠形式与源文件不同；用户备份并只修正错误URI后安装成功。不要整份覆盖源列表、禁用安全更新／签名检查或删除TG2Cloud数据。步骤见[仓库APT专题](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md#apt-软件源错误)，不要公开包含私有源凭据或建号密码的日志。

### 找不到 OpenList 首次管理员密码？

已有实例仍应使用当前管理员凭据；不要把新的本地表单值当成服务端已重置的密码。v1.1.5 的 `--edition openlist --show-credentials` 可在私有交互终端逐项确认后展示保存的初始化密码，但它可能已被更改；没有保存值时不会重新生成，也不会重置账号。命令见 [已有凭据查看](/download/)，部署步骤见 [OpenList 教程](/deploy/openlist/)。

### CloudDrive2 提示没有 FUSE？

同机受管 CloudDrive2 需要 `/dev/fuse`。请确认 VPS 虚拟化和服务商支持，而不是反复更改 WebDAV 密码。

## 管理页与 WebDAV

### HTTPS 管理页打不开？

运行 `tg2cloud`，选对应 Edition，再选 **7. HTTPS 与管理** 检查，核对 DNS、证书、80/443、Nginx、HTTP 跳转和后端回环监听。首次签发时 Cloudflare 使用“仅 DNS”；CloudDrive2 19798 与 OpenList 5244 不应直接暴露公网。

### HTTPS 能用，为什么显示黄色续期警告？

最近续期失败、已有记录超过 26 小时未更新、临近到期或时钟异常都可能触发提醒；当前严格 HTTPS 自检通过时，入口仍可用。检查续期记录、VPS 时间和 Certbot，不必因此重装 Bot。完全没有记录的旧实例只显示“尚无记录”，需按匹配版本的 Linux 维护流程显式更新记录组件，不能只更新网站。[HTTPS 维护说明](/deploy/domain-https/)。

### 填了 Let's Encrypt 邮箱就会收到到期提醒吗？

不会。其到期提醒邮件服务已停止，填写邮箱不能替代续期监测。续期检查成功也可能表示证书无需更新，不能当作已续签。

### 401 与 429 有什么不同？

401 优先检查运行配置中的 WebDAV 用户名、密码；429 属于限流，避免连续重试加重压力。两者不能用同一种方案处理。[WebDAV 排查](/troubleshooting/webdav/)。

当前 OpenList Bot `/doctor` 会显示实际探测时间与剩余冷却；刷新诊断不会绕过退避，也不会把消息刷新时间冒充新探测结果。

### 修改部署器密码后还是 401？

修改本地记录不等于 VPS 配置变更。重复部署默认保留原 `.env`，单纯 restart 也不应用新配置。按 [修改配置](/operations/update/) 明确应用后再验收。

### “修复 CloudDrive2 网络”能解决上传失败吗？

只针对适用的容器网络问题，不能修复错误密码、只读权限、未挂载云盘或配额不足。

### MOVE 返回成功就通过了吗？

不能这样判断。v1.0.2 对 OpenList 改为直接写入预留最终路径；CloudDrive2 仍使用临时文件改名后复验。必须看最终验收结果。

## 任务与数据

### 取消后能再次转存吗？遇到不完整远端文件怎么办？

v1.2.1 支持重新转发已取消文件或 `/restart 编号`，确认后重新排队，保留编号/历史与活动任务去重。远端结果不确定时使用 `/recover 编号` 确认换名重传，不自动覆盖或删除旧文件。旧 v1.2.0 Release 不包含这些功能，详见[命令](/usage/commands/)和[恢复排查](/troubleshooting/transfer/)。

### Bot 一直排队？

先看 `/status` 顶部运行状态和排队数量；需要检查 CPU、内存、磁盘与本地额度时，点击首页的 `🖥`。调度暂停状态可用 `/status` 顶部提示和 `/doctor` 进一步确认。[传输排查](/troubleshooting/transfer/)。

### 为什么暂停后还有传输？

`/pause` 只暂停新任务调度，不打断活动任务。暂停状态跨重启保存，恢复用 `/resume`。

### Bot 完成是否代表云盘官方完成？

不代表。Bot 校验 WebDAV 接收与文件大小，不接入云盘官方完成接口；重要文件需在官方客户端检查内容。

### 流式模式是不是完全不占磁盘？

不是。它不留完整本地副本，但网关缓存、日志、Docker 和备份仍占用磁盘。

## 升级与迁移

### 下载新版 EXE 后，Bot 还是旧版？

下载不等于更新 VPS。Windows EXE 停留在 v1.2.1；v1.3.0 起请按公网或内网选择对应 Linux 入口，先 `--check` 再确认升级，不用旧 EXE 覆盖较新实例。CloudDrive2 本次升级后使用验收已获用户确认，其他环境和异常路径不自动视为通过，见[升级说明](/operations/update/)。

### `manage.sh update` 会下载 GitHub 最新源码吗？

不会。它主要用已安装 payload 重建；安装新版应使用对应 Linux 稳定版本向导，保留配置并核对官方基线，详见 [升级](/operations/update/)。

### 出现“现有程序与已发布版本不一致”怎么办？

停止并保留数据，不要改版本号、删除数据库/Session、关闭指纹检查或用旧 EXE 覆盖。本次 CloudDrive2 旧候选是在额外授权、备份和人工核对后迁移，不代表脚本会自动接管任意自定义代码。处理边界及尚未验证项见[验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。

### TG115 能一键升级 TG2Cloud 吗？

当前 Linux 脚本不提供原地自动迁移或覆盖生产数据的一键 Restore。独立卸载不是迁移或升级步骤，也不会清理旧 TG115。主分支追加的完整清理默认双重确认后删除所选 TG2Cloud 数据与可识别备份；需要保留时明确使用 `--keep-data`。完整清理增强仍待新的实机验收，不能把原保留数据版本的用户验收当作新行为已经通过。详见 [独立卸载说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md) 和 [迁移说明](/operations/migration/)。

### CloudDrive2 现在能备份了吗？

可以。两版在 `tg2cloud` → **13. 数据备份管理** 都提供实例快照和隔离预检；共享代理另行备份，快照会短暂停止所选服务。两者不包含云端文件，也不提供覆盖生产数据的一键恢复。[备份范围](/operations/backup/)。

### CloudDrive2 和 OpenList 可以共用一个 Bot Token 吗？

不要让两版或新旧实例长期同时使用同一个 Token，否则可能争抢 updates。没有分布式锁替你自动防止这种冲突。
