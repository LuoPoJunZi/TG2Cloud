# v1.5.4 发布与兼容记录

状态：2026-10-30，待发布。本地修复与自动检查已完成；同标签原生双架构、远端 CI、源码、镜像和 Compose 资产须逐项完成后补充。修复后的真实用户 VPS、Telegram 下载、两种网关转存与长期运行尚未执行。

## 范围与兼容

短时间 Premium 下载限速继续当前分片；普通限流及超限持久化冷却。临时服务错误进入有限重试，真实授权失效停止；迟到错误不得影响替换后的账号。监听新任务按限速信号退让并逐步恢复，不取消在途任务或改变手动任务资源窗口。普通／流式失败记录保留脱敏原因。

业务 schema 3 不变，没有新依赖、配置或数据迁移；保留数据库、Session、下载、用户配置和历史任务。新增 v1.5.3 正式提交 `2e6f06f09e1e2ac9fe8ae2d9c6e1d83cc7a3bee1` 的可信升级基线。一键脚本与 Compose 仍使用不同实例身份，互不接管。

## 本地验证

`python -B .github/scripts/check_python.py all`：1537 项，1501 通过、36 条件跳过、0 失败；Ruff 与 compileall 通过。额外 Ruff 0.17.0、Bandit、Python 3.10 标准库 CLI help、源码清单检查与网站 37 项测试通过。未执行的本机原生 Linux／Docker／rclone 检查交由远端 CI；真实服务验收单独记录。

## 发布门槛与资产

辅助 A 必须先公开核验，入口 B 再固定真实 A；目前候选未替换旧在线 pin。待核验资产为 `TG2Cloud-v1.5.4-source.tar.gz`、`SHA256SUMS.txt`、`TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz`、`TG2Cloud-v1.5.4-compose-openlist.tar.gz`、`COMPOSE-SHA256SUMS.txt`。核对实际下载 SHA256、Tag、包内版本、镜像平台与提交身份后才确认发布完成。

上一正式版仅作升级参考，不属于本版验证：[v1.5.3 CI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40844895202)，历史镜像 `ghcr.io/luopojunzi/tg2cloud@sha256:21b1da6d84cfccfebe4fc0dd88a0cfe3edd730e33dca241639834e1fb8e5dc44`；不得将其作为 v1.5.4 安装资源。

## 发布后验收与回退

1. 先按原部署方式生成一致性备份；确认两组件版本及数据库路径，不同时启动使用同一 Token 的实例。
2. 少量重试已失败的监听任务，核对短限速等待后继续、长冷却提示、临时错误重试与最终脱敏原因；不批量强制重传。
3. 分别核对手动转存、监听普通／流式传输、两种网关目的端大小验证、磁盘保护、重启与 Session 保留。
4. 对账号替换和真实权限拒绝验证隔离；不要使用用户云端文件测试删除或覆盖。
5. 如需回退，先停止任务并保护现场，使用匹配源码／镜像和升级前一致性备份在隔离目录核验；不要直接覆盖生产数据库或删除 SQLite 旁文件。

[升级说明](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [监听说明](../LISTENING.md) · [备份与恢复](../BACKUP-RESTORE.md)
