## TG2Cloud v1.5.1 · 性能与监听维护

## 本次改动

- 受阻任务仅在等待原因变化时写数据库，继续在事务内核对取消状态、磁盘和成员额度；个人任务统计复用现有索引。
- 监听接收上限只统计排队与执行任务；每个来源增加 30 秒超时，按轮次预算公平轮询，保留串行请求、账号限流、持久化游标和去重。
- 计划创建仅检查当前用户的过期计划；全局历史维护在后台定期执行，失败事务回滚，审批有效期仍实时核验。
- 资源控制只查询需要的任务状态，同一轮复用暂存用量和流式任务数；同一文件系统复用采样，独立文件系统继续检测。
- 普通上传不再重复写入相同字节进度，速度样本仍更新；重试、取消、失败保留与完成验证顺序继续有效。
- 增加只操作临时合成数据库的性能工具；不增加遥测或生产后台采集。补充 v1.5.0 两 Edition 的不可变升级基线。

## 安装与升级

[v1.5.1 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.5.1) 已发布；[同标签 Linux 检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622910178)与实际源码资产、SHA256 和 Tag 文件核验通过。使用下方固定版本入口。已有实例先通过菜单 13 备份，保留原安装模式与配置，不需要卸载。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.1/install.sh) --edition clouddrive2 --release v1.5.1 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.1/install.sh) --edition clouddrive2 --release v1.5.1
```

OpenList 使用 `--edition openlist`；内网使用同标签 `install-lan.sh`。从旧离线工具升级优先使用在线入口；更新后退出旧菜单并重新运行 `tg2cloud`，核对 Bot 和 CLI 均为 1.5.1。

## 验证与兼容

沿用业务 **schema 3**，不增加数据库 DDL、依赖、必填配置、端口或服务。保留配置、任务、Telegram Session、失败后本地副本及两网关提交策略；v1.4.8 及更早仍经过既有 schema 2 → 3 迁移。回退使用匹配旧代码和升级前一致性数据库快照，不直接覆盖当前数据库。

详细证据、待执行实机步骤与回退说明见[本版发布与验收](docs/development/V151-ACCEPTANCE.md)及[备份恢复指南](docs/BACKUP-RESTORE.md)。本地自动检查已覆盖优化行为，远端 CI、同标签发布与实际资产核验结果已记录。**真实 VPS、Telegram、两网关转存、小时级负载和生产恢复尚未执行。** 合成数据库耗时不能视为实际传输提速或长期稳定性承诺。

历史验收按原范围保留：[v1.3.0](docs/development/V130-ACCEPTANCE.md)、[v1.4.3](docs/development/V143-ACCEPTANCE.md)、[v1.4.4](docs/development/V144-ACCEPTANCE.md)、[v1.5.0](docs/development/V150-ACCEPTANCE.md)。
