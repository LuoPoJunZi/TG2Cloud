# 更新日志

TG2Cloud 与上游 TG115 分别记录版本。以下是仓库 CHANGELOG 和发布说明的整理，不把历史 TG115 的版本号当成 TG2Cloud 发布版本。

## TG2Cloud v1.1.3

状态：源码更新，待发布；内容核对日期：2026-10-09。当前已发布 EXE 仍为 v1.1.2，本次不创建新 Tag/Release。

- 新增可选 VPS 单行安装/保留配置升级向导；先收集信息、预检及确认，两个 PySide6 部署器仍是主力。
- 向导模块固定已验证的 commit，实际 payload 始终来自最新正式稳定 Release，不安装 main/RC 未发布业务代码。
- 已有完整实例复用配置，核对官方源码、运行指纹与挂载；TG115、部分实例、手改代码、目录冲突和网关数据库迁移安全停止。
- 复用现有 Docker、备份/有限回退与强制 HTTPS；健康域名不隐式切换，WebDAV 写入验收另行确认。
- 同步 Bot、两个部署器、Windows 资源和文档版本；保留真实下载基线与历史验收记录，不把版本号更新当作已发布或实机验收。
- 合入限定范围的 Telethon 1.45.0、PyInstaller 6.22.3 兼容验证；新版 EXE 与真实 Telegram 转存仍待对应验收。

CloudDrive2 脚本仅通过真实 VPS 只读预检，未执行首次安装、跨版本升级或回退；OpenList 脚本实机验收暂缓。

[查看源码更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md) · [下载与 VPS 单行入口](/download/) · [脚本完整指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。

## TG2Cloud v1.1.2

发布日期：2026-10-08。本次聚焦运行状态、故障提示与 HTTPS 维护，两个 Windows EXE 继续由 Actions 从同一不可变标签构建一次，并以该次实际产物生成 SHA-256。

**实际版本与阶段。** 运行状态分别显示本机部署器和 VPS Bot 实际版本；未知不当作最新版，不自动升级或降级。既有进度、日志与弹窗显示实际执行阶段和核对建议，不虚构百分比或根因。

**共享代理维护。** 两版 HTTPS 对话框新增私密代理备份、完整性检查、隔离解包和当前域名续期 dry-run。历史备份可选择核验；清理须先预览再确认，默认取消、至少保留一份，清单变化或校验失败拒绝执行。维护增加远端时限与精确任务清理，断连时不冒充清理已完成。

**续期与限流诊断。** 区分续期检查成功与证书实际变更；续期失败、已有记录超过 26 小时未更新或证书临近到期显示黄色警告，当前 HTTPS 自检通过时入口仍可用。OpenList `/doctor` 显示真实探测时间、401/429 分类和剩余冷却，原有退避与转存逻辑不变。

**构建与发布。** 部署器与 Bot 共用版本源，校验 Tag、源码、Windows 资源和发布文档一致性；修复打包备份助手的相对路径问题，增加备份对话框自检。Release 等待同标签 Windows/Linux 检查成功，复用已构建的 artifact，拒绝替换已有 Release。

本地回归与标签 CI 通过。专用 Debian 13 VPS 的代理备份/核验/隔离解包、OpenList 路由移除后恢复和续期 dry-run 通过；两版各 11 项 HTTPS 自检通过，CloudDrive2 既有配置与容器保持不变。历史备份清理只做无删除预览。

真实 Bot/网盘转存、401/429 实际恢复、长期自动续期、完整灾难恢复、独立网络的后端端口隔离及真实 Windows 桌面交互仍待验收，不把隔离解包或本机 HTTPS 自检当作全链路通过。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.1.2) · [维护与诊断说明](/operations/maintenance/) · [备份与恢复边界](/operations/backup/)。

## TG2Cloud v1.1.1

**共享 HTTPS 事务保护。** 配置/移除使用 VPS 级事务锁，状态原子提交；移除路由同步 Certbot 活动域名，并检查保留 Edition，失败回退旧配置。

**OpenList 探测与路径保护。** 大目录检查不再截断至 10,000 项；只读探测区分 401/429，合并短时间刷新并增加冷却与限流退避。CloudDrive2 上传、改名命令与探测策略不变。

**发布门禁。** 同一标签的 Linux 验证和 Windows 构建均成功后，才发布一次构建生成的两个 EXE 与实际 SHA-256。

本轮双网关 HTTPS 共存、外部访问/跳转/公开 WebDAV 阻断及真实 SSH 锁互斥/断锁释放通过。OpenList Bot/WebDAV/限流恢复、路由移除和长期续期尚未重新实测；沿用旧版转存验收基线，不宣称本版全链路重新验收。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.1.1)。

## TG2Cloud v1.1.0

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**强制 HTTPS 管理入口。** 受管 CloudDrive2/OpenList 基础容器健康后自动进入域名配置；证书、HTTPS、HTTP 跳转、公开 `/dav` 阻断和后端回环监听全部通过后才显示“部署完成”。

**收紧公网边界。** CloudDrive2 19798 与 OpenList 5244 继续只监听 VPS 回环地址，只有共享 Nginx 使用公网 80/443。普通工作台不再显示固定端口 SSH 隧道按钮，底层隧道代码仅保留兼容和故障恢复能力。

**验收门禁。** 受管网关在 WebDAV 最终验收前再次检查当前 Edition 的 HTTPS 状态；外部 WebDAV 模式不要求为不存在的本地管理容器配置域名。

CloudDrive2 与 OpenList 已在真实 VPS 完成受管部署、证书签发/复用、HTTPS 自检和 WebDAV 全流程验收。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.1.0)。

## TG2Cloud v1.0.4

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**Bot 状态首页。** 使用紧凑的任务与实时速度面板，根据实际 Edition 显示 CloudDrive2 或 OpenList，并以数字时间标记本次状态生成时间。

**按钮与资源页。** 首页按钮精简为任务、VPS 资源和原地刷新；CPU、可用内存、可用磁盘与 TG2Cloud 本地额度进入独立资源页，按钮结果继续编辑原消息。

**兼容与边界。** 目的端状态、任务统计、分阶段速度与 `ResourceMonitor` 均复用现有实现，旧 `menu:status` 回调继续兼容；Telegram 下载、SQLite 队列、rclone、WebDAV、streaming 和既有部署流程未被重写。

新 Bot 界面已通过自动回归测试；v1.0.3 已完成的共享域名 HTTPS 验收，以及两版既有基础部署和 WebDAV 真实 VPS 验收结果继续作为回归基线。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.0.4)。

## TG2Cloud v1.0.3

该版本的两个 Windows EXE 从同一不可变标签源码测试、构建和自检，并使用 GitHub Actions 实际产物计算 SHA-256。

**域名 HTTPS。** 新增两个 Edition 共用的 Dockerized Nginx/Certbot 网关，可为 CloudDrive2 与 OpenList 管理界面分别配置 HTTPS 域名；原 SSH 隧道和 Docker 内网 WebDAV 保持不变。

**安全与回退。** 增加 DNS、端口归属、证书、HTTPS、跳转、公开 `/dav` 阻断和后端回环监听检查；配置失败保留旧路由，不停止或覆盖外部 Web 服务。

**可靠性与界面。** 修复证书复用、失败清理、续期筛选、状态脚本和 NAT 回环误报，域名状态结果改为固定高度、可滚动和可复制的小型日志框。

共享域名 HTTPS 功能已完成验收，适用于 CloudDrive2 与 OpenList。两版原有基础部署和 WebDAV 真实 VPS 验收结果继续作为回归基线。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.0.3)。

## TG2Cloud v1.0.2

该版本的两个 Windows EXE 从同一标签源码构建，并使用实际产物计算 SHA-256。

**OpenList 写入兼容性。** 针对部分 OpenList/115 Open 对 MOVE 返回成功但目标文件未生成的情况，改成预留无冲突最终路径后直接写入，保留大小复验、失败保护和安全清理。

**CloudDrive2 稳定流程。** 继续使用临时上传、改名和大小复验；OpenList 新逻辑按后端隔离。

**部署界面与错误提示。** 修复 OpenList 工作台窄侧栏裁切，区分 401 凭据错误和 429 限流。

发布说明记载两版已完成真实 VPS 基础部署与 WebDAV 验收；Telegram 和不同文件规模仍应在用户实际环境继续验证。

[查看正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.0.2)。

## TG2Cloud v1.0.1

修复 CloudDrive2 首次部署时，网络修复发现逻辑把当前 Bot 容器误判为第二个网关的问题。

仅从网关发现中排除当前 Edition 的 Bot，保留多个真实网关和旧 TG115/固定端口冲突的保护，增加对应回归测试。该历史条目的验证说明按当时记录理解，不当作当前全链路验收承诺。

## TG2Cloud v1.0.0

建立两个 PySide6 正式 Edition，使用独立安装目录、容器、Docker 网络和固定管理隧道端口。

加入新命名空间与必要旧标记兼容，既有 TG2Cloud 重新部署默认保留 `.env`，明确旧 TG115 不会被自动接管。OpenList 增加管理、脱敏日志、一致性备份等专属操作。

正式构建不再包含 Classic/Tkinter 部署器。

## 与上游 TG115 的关系

TG115 v1.6.2 等记录属于代码演进历史，并不是 TG2Cloud 自身的版本。历史入口可查看 [仓库完整 CHANGELOG](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

本导航中的历史版本条目是更新日志入口，不是各旧版文档的完整快照。下载历史产物前，应自行核对对应 Release 是否存在及其具体资产。

## v1.1.3 仍然存在的限制

没有正式自动 Restore 或 Uninstall；CloudDrive2 没有手动业务备份 UI，但两版都有共享 HTTPS 代理备份工具；没有旧 TG115 状态/队列的自动原地迁移；没有跨实例 Token 分布式锁；Windows EXE 未提供商业代码签名。

使用前查看 [备份边界](/operations/backup/) 与 [迁移说明](/operations/migration/)。
