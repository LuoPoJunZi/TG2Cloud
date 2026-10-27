## TG2Cloud v1.5.0 · Linux 管理与监听稳定性

## 本次改动

- 离线管理工具改为从目标正式 Release 的已校验源码安装，版本读取实际源码；已有工具在参数方式升级时同步更新，保留配置、数据库、Session 及网关数据。
- 新增 `tg2cloud --version`；安装时分别核对 CLI 版本、目标一致性和监听帮助命令，升级结果单独展示 Bot 实际版本与 CLI 结果。当前菜单仍运行旧代码时，提示退出并重新运行。
- 修复在线 Bash 后台进程标准输入被重定向时监听登录失败：使用当前 SSH 控制终端，2FA 密码仍隐藏，失败提示指出检查阶段。
- 监听规则预览与接收共用同来源、同批次媒体组说明；保留附件自己的说明和集数，不读取评论或额外抓历史。修复配置变化后旧轮询回写状态，以及下载前账号／连接变化、失败复核沿用旧结果的问题。
- 补齐 Telegram Session 的 SQLite 辅助文件防误提交规则；首页与文档导航统一称为 Linux，保留实际架构检测、镜像选择与 CI 矩阵。精简网站维护说明，记录两台 Linux 的 v1.4.11 基础升级反馈。
- 补充真实 v1.4.11 不可变提交的两 Edition 升级基线。

## 安装与升级

[v1.5.0 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.5.0) 已发布；[同标签 Linux 检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40439954791)与实际源码资产、SHA256 和标签文件核验通过。保持原安装模式；先备份并运行对应入口的只读预检，确认后执行升级。可固定版本运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.0/install.sh) --edition clouddrive2 --release v1.5.0 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.0/install.sh) --edition clouddrive2 --release v1.5.0
```

首次从 v1.4.11 或更早版本升级，请使用上方在线入口，让新版向导同时更新 Bot 和离线管理工具；旧 CLI 已在运行的菜单不会自行加载新版逻辑。

OpenList 将 Edition 换为 `openlist`；内网使用同标签 `install-lan.sh`。工具更新后退出旧菜单，重新运行 `tg2cloud`，核对 `tg2cloud --version` 及升级摘要。CLI 的帮助检查不等于个人账号已登录或监听已转存。

## 验证与兼容

本版沿用业务 **schema 3**，无新增数据库 DDL、运行依赖、必填环境变量、Compose 服务或端口。v1.4.8 及更早升级仍经过已有 schema 2 → 3 事务迁移。回退前保留当前数据，停用监听／Bot，并使用匹配旧代码和升级前一致性数据库快照；不让旧程序直接解释新的来源目录策略。

发布过程和自动化结果见[本版发布与验收](docs/development/V150-ACCEPTANCE.md)，备份见[恢复指南](docs/BACKUP-RESTORE.md)。**本版真实 VPS、Telegram 登录、两网关转存、手机访问和恢复尚待发布后验收。** 两台主机的记录属于 v1.4.11 基础升级，不能当作本版修复实机通过。

历史验收按原范围保留：[v1.3.0](docs/development/V130-ACCEPTANCE.md)、[v1.4.3](docs/development/V143-ACCEPTANCE.md)、[v1.4.4](docs/development/V144-ACCEPTANCE.md)、[v1.4.5](docs/development/V145-ACCEPTANCE.md)、[v1.4.11](docs/development/V1411-ACCEPTANCE.md)。
