## TG2Cloud v1.4.5 · 稳定性与本地管理体验维护

继续维护 Linux Python + Bash、CloudDrive2 / OpenList 与原生 AMD64 / ARM64，不生成 Windows EXE。公开安装命令不变，Bot 主菜单和转存策略不变。

## 本次更新

- 统一本地管理次级页面的标题、当前 Edition／版本和返回方式。2 状态、3 日志、10 业务就绪检查可停留刷新，刷新重新核验所选实例；升级摘要不再立即被主菜单刷走。
- 状态中文分项展示，停止容器不复用旧健康成功记录，未知结果不判正常；日志按 Bot／网关分组，保留 30 分钟／每源 100 行的脱敏快照，单源失败不遮住另一个源。
- 备份子菜单重排为实例 1～3、共享代理 4～7；主菜单编号不变。其余页面整理上下文、参数与结果，保留权限、锁、身份复核和危险操作确认。
- 只读诊断增加 HTTPS／内网入口检查和认证、权限、冷却、容量、远端冲突的处理建议，不自动重启或修复；终端与 Markdown 导出分别渲染。
- 快照预检拒绝超出声明范围的文件及 SQLite 日志旁文件；数据库初始化／迁移失败或普通中断关闭连接。新增隔离数据库启动／迁移与重启恢复演练，只使用已核验的临时副本，不加载 Session 或启动网关，不是生产 Restore。
- 补齐 v1.4.3／v1.4.4 的可信原提交与两 Edition 摘要，增加工作树维护发布预检。扩充合成多语言命名样例与两后端重启后避免重复上传的回归，不更改现有命名优先级或传输流程。

## 安装与升级

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

内网实例使用 `install-lan.sh`，不混用公网入口改变模式。须实际升级离线管理工具和所选 Bot；只更新文档或重启容器不会安装新版实现。外部 WebDAV 仍独立维护，不默认启用。

**升级前保存配置、Session 和业务数据库备份。** 本版不新增依赖、环境变量或数据库结构，继续使用 schema 2；更旧实例的既有事务迁移和版本拒绝规则保留。回退须核验匹配的旧代码与数据库快照，不能只降级镜像。配置、历史任务、rclone 语义、云端文件及两网关权限保持。

## 验证与发布边界

发布准备中的本地完整回归 1121 项：1090 执行通过、31 因既有环境条件跳过，0 失败／错误。新页面在 Python 3.10／3.13 各 16 项通过；Ruff、Bandit、语法、清单与仓库检查，以及网站构建和 34 项测试通过。这些不是远端 CI 或实机通过记录。

发布采用先公开并验证辅助 A、后由入口 B 固定真实 A 的流程；同一不可变 Tag 须通过原生 AMD64／ARM64、隔离 Docker／WebDAV、静态与依赖检查后才发布 `TG2Cloud-v1.4.5-source.tar.gz` 和 `SHA256SUMS.txt`。当前处于准备阶段，不借用旧版 CI 宣称本版已经发布，不在失败时回退未校验 main；SHA256 是完整性校验，不是数字签名。

本版尚未连接真实 VPS、Telegram 或用户网盘；真实新装／升级、ACME／长期续期、手机播放和完整生产恢复仍需独立验收。历史 [v1.3.0 人工迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3 用户升级日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)和 [v1.4.4 双架构用户升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)按原版本与范围保留，不外推本版。

详细说明见[管理与运维](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md)、[备份与恢复](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/BACKUP-RESTORE.md)、[本版维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-NEXT.md)及[完整版本记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。
