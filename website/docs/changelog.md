# 更新日志

TG2Cloud 与上游 TG115 分别记录版本。以下是仓库 CHANGELOG 和发布说明的整理，不把历史 TG115 的版本号当成 TG2Cloud 发布版本。

## TG2Cloud v1.0.2

当前文档核对版本。两个 Windows EXE 从同一标签源码构建，并使用实际产物计算 SHA-256。

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

## v1.0.2 仍然存在的限制

没有正式自动 Restore 或 Uninstall；CloudDrive2 没有手动 Backup UI；没有旧 TG115 状态/队列的自动原地迁移；没有跨实例 Token 分布式锁；Windows EXE 未提供商业代码签名。

使用前查看 [备份边界](/operations/backup/) 与 [迁移说明](/operations/migration/)。
