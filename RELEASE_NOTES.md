## TG2Cloud v1.4.4 · 稳定性与用户体验维护

继续维护 Linux Python + Bash、CloudDrive2 / OpenList 和原生 AMD64 / ARM64，不生成 Windows EXE。公开安装命令不变。

## 本次更新

- 安装日志区分 `[信息]`、已识别构建 `[提醒]`、未知 WARNING `[待核对]` 与明确 `[错误]`。保留原日志和失败退出码，同类解释仅出现一次，不把警告一概视为无害。
- 公网／内网安装与升级结束时逐项汇总基础步骤、原配置保留、数据库备份确认、运行代码／版本、容器健康和本机入口。失败或中断说明停止阶段，不冒充已完成或已回退。
- 入口通过后只读取一次 Bot 现有的业务就绪观察，不额外探测网络、不绕过冷却。明确区分基础升级、WebDAV 写入与大小复验、真实 Telegram 转存及外部网络验收。
- 按已确认的文案重排本地管理菜单：安装与升级仍为 1，分类／通知分别为 8／9，诊断 12、备份 13、卸载 14。服务启停、分类、通知和成员配额减少功能选择层级，保留权限、确认、锁与 revision 校验。
- 直接移除命名预览菜单及菜单分派；独立命令 `tg2cloud naming-preview`、Bot 自动命名和传输核心继续保留。
- 补充历史 v1.4.3 用户升级日志中的 WARNING 解释与验收边界，统一仓库及文档站操作说明。

## 安装与升级

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

内网实例使用 `install-lan.sh`，不混用公网入口改变模式。确认更新后，离线管理工具才使用新版菜单；只更新文档或重启容器不会升级工具。

**升级前保存配置、Session 和业务数据库备份。** 本版不新增依赖、环境变量或数据库结构变更，继续使用 v1.4.3 的 schema 2；更旧版本跨版本升级仍按既有事务迁移执行。回退需匹配旧代码和经验证的数据库快照，不能只降级镜像。

保留历史数据路径、用户账号、云端文件和 rclone 配置语义。不自动开启分类／通知，不改家庭授权、网关镜像或后端提交策略，外部 WebDAV 仍独立维护。

## 验收与发布边界

辅助 A `ea93c95eda0fa68c807b56c41871e09b7a19634b` 的五项 CI 已通过，包括[原生 AMD64／ARM64 与隔离 Docker](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39918850733)及[Python 3.10／3.13 四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39918854646)。限定修正普通 Runner 的临时配置夹具，并补充非 root／权限过宽拒绝及 root 0600 正例；不修改生产权限、不跳过测试。正式发布仍由同标签门禁决定，不借用 A 绕过检查。

普通升级不会擅自执行 WebDAV 写入；首次安装与显式 `--verify` 保留原确认。摘要未执行／未核实的项目不会显示通过。按提示完成业务就绪检查、WebDAV 验收，再向 Bot 转发自有小文件并在云存储官方客户端核对；本机 HTTPS 不替代外部连通性验收，大小复验不等于内容哈希或官方云盘最终入库。

发布使用先验证辅助提交 A、后固定入口 B 的流程；同一不可变 Tag 通过原生 AMD64／ARM64、隔离 Docker／WebDAV、静态与依赖检查后，发布 `TG2Cloud-v1.4.4-source.tar.gz` 和 `SHA256SUMS.txt`。不在失败时回退到未校验 main；SHA256 是完整性校验，不是数字签名。

修复测试夹具后，v1.4.4 本地完整回归 1081 项：1050 项执行通过，31 项因环境条件跳过，0 失败；网站构建与 22 项测试、Ruff、Bandit、语法、最低 Python 3.10 的独立 CLI／20 项反馈回归及发布资料检查通过。远端仍须通过本次同标签门禁，不将跳过或模拟测试写成实机通过。本轮未连接真实 VPS 或用户网盘，v1.4.4 的真实升级、Telegram 转存、故障回退、ACME／长期续期及手机播放仍需独立验收；历史 [v1.3.0 人工迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)及 [v1.4.3 用户升级日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)不外推本版。

详细操作见[运维与结果摘要](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md)、[升级与备份](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/BACKUP-RESTORE.md)及[完整更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

### 发布后核验（2026-10-23，仅补充仓库文档）

辅助 A `ea93c95eda0fa68c807b56c41871e09b7a19634b`、入口 B／Tag `6164a237108786c01a7a958ab56e16023df04d79` 各五项 CI 及[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39920070111)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要已核验。 源码包 SHA256：`521bfbc403a5cf13e0b9102c43909fc15aacfda8cf87033b1bd4772e4f86b152`。Release 仅含源码包与 SHA256SUMS.txt，不生成 EXE。本段不改写正式 Tag、资产或远端 Release 正文，也不代表真实 VPS／网盘验收。
