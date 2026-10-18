# 状态、日志与重启

先用只读检查定位问题，再决定是否重启或执行会写文件的验收。路径要与安装的 Edition 一致。

## 本地管理菜单（待发布）

新版源码的默认安装向导在确认计划后安装离线 `tg2cloud` 命令；先选择 CloudDrive2／OpenList，再使用编号菜单：安装升级、状态、日志、启停、WebDAV 验收、HTTPS／入口、备份、凭据、卸载，以及 0 退出。状态与日志不下载代码；安装升级仍只选正式稳定 Release。当前在线入口须先更新已验证的不可变 helper pin 才能获得新菜单，不是已发布功能。

公网／内网安装命令不带参数时共用此入口：所选 Edition 未安装就确认进入对应向导，已有实例就显示管理菜单。新安装使用入口对应的公网／内网模式；已有模式不因入口变化而改变。比如选择 `2. OpenList` 而尚未安装时，会进入 OpenList 安装引导，不会把它当作“运行状态”。日常无需单独记卸载命令，旧 `uninstall.sh` 仍作兼容／救援入口。

```bash
tg2cloud
tg2cloud manage --edition clouddrive2
# 从已审阅的源码本地运行（不依赖当前目录）：
python3 /path/to/TG2Cloud/scripts/run_source.py manage
```

启停默认只操作 Bot；网关需另选并确认。验收会真写并清理随机测试文件，单独确认，不自动反复重试。HTTPS 修复沿用已有域名，续期 dry-run 另行确认；LAN 实例保留原内网模式，不隐式申请证书。查看凭据每项私有终端确认，不进日志。卸载复用原有归属、附加功能依赖保护和删除确认，自定义目录不自动卸载。

备份菜单可查看实例升级回退点，以及创建／查看／隔离校验最近共享代理备份；代理清理先预览、再确认，固定保留最近 5 份有效备份。不提供覆盖生产数据的自动恢复。离线代码只包含管理源码与版本／哈希清单，保存在私密 `/opt/tg2cloud-cli/runtime/`，不复制 Bot 配置、Session 或数据库，不覆盖未知同名命令。

序号 9 显示“卸载当前实例”，仅作用于当前所选 Edition。卸载 CloudDrive2 不删除或重启 OpenList 的 Bot/网关，也不清理其数据或域名；共享代理路由更新可能短暂重载。最后一套默认完整卸载后，若无其他实例、保留数据/备份、附加路由或挂载依赖，才核验并删除 `tg2cloud` 与全部受管管理代码，然后退出菜单。未知资源、忙碌和保留数据模式不强删。系统 Docker/Nginx、云端文件、镜像缓存与锁元数据仍保留，不能承诺系统逐字节恢复原状。详细限制见[仓库运维文档](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md#本地管理菜单待发布)。

以下弹窗与桌面按钮属于历史 v1.2.1，不是新的 Linux 菜单；原每实例 `manage.sh` 继续有效。

## 查看实际运行版本

从 v1.1.2 起，部署器“查看运行状态”的结果弹窗与运行日志分别显示本机部署器版本和 VPS Bot 实际版本。VPS 版本来自正在运行的 Bot，不用本机 EXE 版本代替；未安装、已停止或旧 Bot 无法报告版本时明确显示未安装或未获取。

下载新 EXE 不等于 VPS 已升级，也不会自动降级较新的 Bot。需要升级时按 [升级与修改配置](/operations/update/) 保留配置重新部署；容器健康不等于 WebDAV 写入通过。

## 部署阶段与失败提示

既有进度区域与运行日志显示实际 SSH、基础环境、资源上传、运行环境、存储服务、Bot 和健康检查阶段；HTTPS 另有环境、ACME 引导、证书与最终自检阶段，不使用猜测的百分比。

失败弹窗给出当时阶段、已有错误详情和核对建议。阶段不是根因；日志未确认时，不直接断言 DNS、证书或凭据错误。查看完整日志后再决定重试，不为排错自动重装、删除数据或停止未知服务。

## CloudDrive2 常用命令

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh status
sudo /opt/tg2cloud-clouddrive2/manage.sh logs
sudo /opt/tg2cloud-clouddrive2/manage.sh check
```

`status` 查看状态，`logs` 查看近期 Bot 日志，`check` 核对配置、代码指纹和基础心跳。输出可能含个人信息，分享前仍需自行审查脱敏。

## OpenList 常用命令

```bash
sudo /opt/tg2cloud-openlist/manage.sh status
sudo /opt/tg2cloud-openlist/manage.sh logs
sudo /opt/tg2cloud-openlist/manage.sh check
```

部署器的 OpenList 日常管理区也提供状态、脱敏日志和分别重启服务的操作。不要用另一 Edition 的路径处理当前实例。

## 重启 Bot

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh restart
```

OpenList 对应替换为 `/opt/tg2cloud-openlist/manage.sh`。`restart` 仅用于重启，不负责把你在电脑上刚改的表单应用到 VPS。

停止或启动时使用对应脚本的 `stop`、`start`；会影响服务可用性，操作前留意当前任务。

## 两种健康检查的区别

| 操作 | 是否真写目标文件 |
| --- | --- |
| Bot `/doctor` | 否，面向只读诊断 |
| `manage.sh check` | 不用于真写验收 |
| `manage.sh verify` | 是，会上传并删除小测试文件 |

不要把 `/doctor` 通过当作写权限已经验收。完整步骤见 [WebDAV 验收](/deploy/verification/)。

## OpenList 认证与限流诊断

当前 v1.2.1 源码的 Bot `/doctor` 显示最近实际探测时间、401/429 分类和下一次允许探测的剩余时间，状态首页仍保持简洁。

| 结果 | 只读探测策略 | 应如何处理 |
| --- | --- | --- |
| HTTP 401 | 冷却 5 分钟 | 核对网关用户与 VPS 当前 WebDAV 配置 |
| HTTP 429 | 按 60、120、240、480、900 秒退避，最长 15 分钟 | 停止重复验收，检查网关日志与上游限流 |

刷新消息不会绕过冷却，也不会把刷新时间写成真实探测时间。冷却结束只表示客户端允许再检查，不保证服务端解除限流；部署器显式 WebDAV 写入验收仍是独立流程，不复用只读缓存。详见 [WebDAV 错误排查](/troubleshooting/webdav/)。

## HTTPS 维护入口

两版部署器的“HTTPS 管理入口”底部都有“维护工具”：共享代理备份、完整性核验、隔离解包、历史备份管理与当前域名续期 dry-run。它们不会升级 Bot，也不备份业务数据库或云端文件。

操作范围、执行时限与警告见 [域名访问与 HTTPS](/deploy/domain-https/)；敏感备份与删除边界见 [备份与恢复](/operations/backup/)。不要把维护工具当作在线覆盖恢复。

## 发现旧 TG115

桌面状态会把旧 TG115 独立提示，不会把它当作 TG2Cloud 已安装。当前管理脚本仅面向本 Edition 的 TG2Cloud 命名空间，不会替你升级或删除旧实例。

## 提交问题前

记录 Edition、版本、最后一次成功操作、第一处错误和是否刚改过配置。提供经过自己复核的脱敏日志，而不是完整 `.env`、数据库或备份。见 [安全说明](/reference/security/)。
