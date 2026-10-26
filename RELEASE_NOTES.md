## TG2Cloud v1.4.10 · 监听交互与维护恢复

## 本次改动

- 监听筛选、命名方案、保存目录与目录授权改为按钮和逐项文字交互，支持多关键词、大小单位、组合条件、草稿测试、明确保存和取消；不要求用户手写 JSON，已有规则兼容。
- Linux `tg2cloud` 新增 **16. 监听管理**，提供登录、状态和停用；手机号与验证码在终端可见，仅两步验证密码隐藏，个人 Session 仍与 Bot 分离。
- 来源详情用中文规则与统计摘要；转存计划显示中文状态、默认目录说明，补齐单项／批次、结果及修正记录返回按钮；历史恢复先预览完整配置再确认。
- 外部 WebDAV 维护代码升级与后台账号认证解耦。账号未完成或认证失败时，可以先更新维护工具再继续配置；不会自动启用路由、借用 Bot 凭据或修改后台账号。
- 纳入真实 v1.4.9 正式升级基线，新增交互、权限、并发、登录及维护恢复回归，更新部署载荷清单、CI 和使用文档。

## 安装与升级

[v1.4.10 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.10) 已发布，[同标签 AMD64／ARM64 工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40287434283)成功；实际源码包、SHA256、GitHub 摘要和标签内全部 369 个文件已核验。可使用下列固定版本入口，正常入口仍只安装正式稳定版。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.10/install.sh) --edition clouddrive2 --release v1.4.10 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.10/install.sh) --edition clouddrive2 --release v1.4.10
```

OpenList 将 Edition 换为 `openlist`；可信内网使用同标签的 `install-lan.sh`，保持原安装模式。先备份，再预检和升级；重新打开 `tg2cloud` 后通过 16 登录、检查个人账号，在 Bot 监听管理中显式启用。旧命令继续兼容。多项后缀或关键词放在同一条消息中分行发送，成功后返回更新页面，最后保存草稿。

外部 WebDAV 从 `tg2cloud` → 15 进入；维护代码须单独选择升级。未完成配置时继续配置，按提示核实专用只读账号；代码升级成功不代表账号认证、公开访问或手机播放验收通过。

## 验证与兼容

验证状态与发布后步骤见[本版验收记录](docs/development/V1410-ACCEPTANCE.md)。本地静态、单元及隔离测试与 GitHub 原生 AMD64／ARM64、两 Edition 和隔离网关结果分别记录；未运行项不计为通过。

本版沿用业务 **schema 3**，不新增数据库迁移、运行依赖、必填环境变量、服务或端口；保留配置、任务、Bot 与个人 Session、下载及网关数据。从 v1.4.8 及更早版本升级，仍须执行已有 schema 2 → 3 事务迁移，保护升级前一致性快照。

**真实 Telegram 按钮与登录、VPS 升级／回退、两种网关实际转存及手机播放尚待发布后验收。** 不自动操作用户 VPS 或云端目录。回退须使用匹配旧代码的数据库快照；不要仅切换旧镜像读取不兼容数据库，也不要覆盖升级后新任务。备份范围见[恢复指南](docs/BACKUP-RESTORE.md)。

历史验收仅保留当时范围，不代表 v1.4.10 实机通过：[v1.3.0](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)、[v1.4.4](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)、[v1.4.5](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V145-ACCEPTANCE.md)。
