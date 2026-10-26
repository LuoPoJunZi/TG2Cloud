## TG2Cloud v1.4.11 · 监听来源归档与恢复维护

## 本次改动

- 新添加的监听频道／群组在现有 Bot 保存目录下创建来源目录，并按视频、图片、音频、文档、压缩包和其他文件归档。目录去表情、限制为 30 个全宽汉字等价长度，重名加来源编号；手动转存和已有监听来源不自动改目录。
- 已有来源可在“保存目录”选择“来源名称下按类型保存”，草稿保存后暂停、核对再启用；创建失败保留来源记录并可按钮重试。根目录变化时停止，不自动搬迁或扩大范围；已登记计划和任务保持冻结路径。
- 监听不再仅凭保护标记拦截来源或附件；保留已加入／读取权限、管理员身份、Session、附件复核、筛选、去重、配额与资源保护。Telegram 实际拒绝读取时暂停来源并停止自动下载重试，不绕过服务端拒绝。
- 添加来源细分无效链接、未加入／无权限、授权失效、限流、网络与持久化错误；不输出敏感异常。补齐转存设置的三行双列返回按钮，以及监听来源列表上方的“返回系统状态”。
- 补充真实 v1.4.10 固定升级基线和目录、并发、恢复、权限及两后端普通／流式隔离回归；同步用户文档、网站和载荷清单。

## 安装与升级

正式资产就绪后，可使用固定版本入口。升级前先备份并运行只读预检：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.11/install.sh) --edition clouddrive2 --release v1.4.11 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.11/install.sh) --edition clouddrive2 --release v1.4.11
```

OpenList 将 Edition 换为 `openlist`；内网使用同标签 `install-lan.sh`，保持原安装模式。重新打开 `tg2cloud` 核对版本，升级 Bot 后 Telegram 新界面才会生效。默认来源仍暂停、仅视频、确认后转存；分类目录不扩大筛选范围，不补抓添加前旧消息。

## 验证与兼容

发布状态、自动化证据及实机步骤见[本版发布与验收](docs/development/V1411-ACCEPTANCE.md)，具体目录与权限说明见[监听指南](docs/LISTENING.md)。仅在对应检查实际结束后记录为通过。

本版沿用业务 **schema 3**，不增加数据库 DDL、运行依赖、必填环境变量、Compose 服务或端口；保留配置、任务、Bot／个人 Session、下载及网关数据。从 v1.4.8 及更早升级仍经过已有 schema 2 → 3 事务迁移。

新目录策略和绑定写入现有来源 JSON。回退必须停用监听／Bot，保留当前数据，使用匹配旧代码和升级前一致性数据库快照；不要让旧程序直接解释含新策略的数据库，不要通过删除目录或任务恢复旧布局。备份步骤见[恢复指南](docs/BACKUP-RESTORE.md)。

**真实 Telegram 登录／监听下载、两网关用户云端转存、VPS 升级与生产恢复仍待发布后验收。** 构建、模拟测试和大小复验不等于真实网盘最终完成或哈希一致。

历史验收按当时范围理解：[v1.3.0](docs/development/V130-ACCEPTANCE.md)、[v1.4.3](docs/development/V143-ACCEPTANCE.md)、[v1.4.4](docs/development/V144-ACCEPTANCE.md)、[v1.4.5](docs/development/V145-ACCEPTANCE.md)。
