## TG2Cloud v1.4.9 · 管理员监听与智能转存增强

## 本次改动

- 可选个人 Telegram 账号监听，默认关闭、仅管理员可用；独立 Session，不复用 Bot 登录，不自动加入来源或绕过内容保护。
- 按已加入频道／群组配置文件类型、扩展名、文件名、关键词、大小与有限 AND/OR 规则；有界补拉、持久化去重、冷却和接收上限。
- 手动和监听转存共用原队列、配额与 CloudDrive2／OpenList 提交策略；可选确认前改名、授权目录、批次审批、来源命名方案及明确保存／撤销修正规则。
- 业务数据库 schema 2 → 3 事务迁移；历史任务默认 Bot 读取身份。实例快照与离线包纳入已有个人 Session，锁文件不入包。
- 发布审计修复长 Unicode 文本超长发送、登录异常清理、停用期间的登记竞态和迁移中断回滚；补充两 Edition 镜像内的默认停用与 Session 隔离检查。
- 公网／内网安装器支持 `--release v1.4.9` 显式选择已发布正式版本；默认仍为最新稳定 Release，拒绝 RC 和 main，保留原有不降级保护。

## 安装与升级

[v1.4.9 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.9) 已发布，两个入口固定已验证的辅助提交，实际源码包与 SHA256 清单已核验。升级前备份，真实功能按验收指南逐项确认。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition clouddrive2 --release v1.4.9 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition clouddrive2 --release v1.4.9
```

OpenList 将 Edition 换为 `openlist`；内网使用同标签的 `install-lan.sh` 并保持原安装模式。先在独立测试实例验收，不启动共用同一个 Bot Token 的两个实例。升级离线工具后，使用 `tg2cloud listen login --edition clouddrive2` 在私有终端授权，再在 Bot 的 `/listen` 中启用。

## 验证与兼容

本地测试结果与远端 CI 状态在[发布准备及验收记录](docs/development/V149-ACCEPTANCE.md)中分别记录。A／B 各五项 CI 及[同标签 AMD64／ARM64 发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40268795680)全部通过，覆盖两 Edition 原生 Docker 与隔离集成；实际源码资产、SHA256 清单和 GitHub 摘要一致。

**新增监听功能尚待发布后真实 VPS 验收。** 个人 Telegram 登录／验证码／2FA、真实频道权限与媒体组、CloudDrive2／OpenList 云端转存和生产恢复尚未验证；正式版本标识不是实机验收结论。按用户决定发布 v1.4.9 正式版，不发布 v1.5.0 RC。

升级前在主菜单 13 创建并校验实例快照，另外保护程序／镜像身份、下载文件与共享代理／附加状态。迁移保留旧任务、配置和 Bot Session；不增加运行依赖、必填环境变量、端口或服务。**回退必须使用匹配旧代码的升级前数据库快照，不能只切换旧镜像读取 schema 3，也不能自动删除升级后新任务。** 完整范围见[备份说明](docs/BACKUP-RESTORE.md)与[监听指南](docs/LISTENING.md)。

历史验收仅保留当时范围，不代表 v1.4.9 已通过：[v1.3.0](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)、[v1.4.4](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)、[v1.4.5](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V145-ACCEPTANCE.md)。
