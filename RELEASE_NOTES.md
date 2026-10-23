## TG2Cloud v1.4.3 · 可靠性与日常管理增强

本版继续维护 Linux Python + Bash、CloudDrive2 / OpenList 和原生 AMD64 / ARM64，不生成 Windows EXE。公开安装命令不变，业务代码仍只取正式稳定 Release。

## 本次更新

- 完善上传速度采样：兼容 rclone 总体统计、每秒读取、区分真实 0 与暂时无数据，排除已过期和校验／清理阶段的旧速度；保留简洁 Bot 首页与成员数据隔离，不推算网关到云盘速度。
- 统一 Linux 编号菜单左对齐；外部 WebDAV 交互选择回车默认 CloudDrive2，首次主账号默认 tg2-webdav，已有账号和隔离目录保持不变。
- 新增可信旧版升级基线，覆盖 v1.3.4、v1.4.0、v1.4.1、v1.4.2；删除旧 Release 时仍核对原不可变提交和载荷，未知版本／修改源码仍安全停止。
- 增加实例快照导出、隔离恢复预检、只读业务就绪检查、独立命名预览；扩展已有 Docker Nginx 生命周期回归。
- 新增可选类型／日期分类、持久化管理员异常通知、成员每日／排队／并发额度和白名单脱敏诊断报告。分类／通知默认关闭，成员默认不限额；不增加主安装问题或 Bot 首页按钮。

## 升级与兼容

**升级前备份配置、Session 和业务数据库。** 本版自动事务迁移业务数据库到 schema 2，保留历史任务和 data/tg115.db、bot.session 等运行名称。旧未完成任务纳入额度预留，不追溯计量旧完成历史；旧 Bot 拒绝打开新 schema。回退不能只降级镜像：先停止所选 Bot，保留当前副本，再人工核验并恢复匹配旧代码的数据库快照。没有删表降级或一键覆盖生产恢复。

同时升级 Bot 与离线 tg2cloud 管理工具；无需新增必填环境变量，不修改网关账号、rclone 配置或已有云端文件。共享代理 schema 与业务数据库 schema 相互独立。镜像增加系统时区包 tzdata；不增加 Python/npm 依赖，不升级固定镜像或恢复桌面部署器。

安装与保留配置升级：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

功能开关、额度与回退见[功能说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/FEATURE-ENHANCEMENTS.md)，实例快照与就绪检查见[维护增强](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-IMPROVEMENTS.md)。入口的只读预检不等于安装或转存验收。

## 发布与验证边界

发布工作流必须从同一不可变 v1.4.3 Tag 完成原生 AMD64／ARM64 回归、隔离 Docker／WebDAV、代码与依赖审计后，才发布 TG2Cloud-v1.4.3-source.tar.gz 和 SHA256SUMS.txt。helper 先公开并验证提交 A，再由入口 B 固定 A；不在失败时退回 moving main。校验和是完整性检查，不是数字签名。

版本整理后本地完整回归 1041 项：1010 项执行通过，31 项因缺少 Docker／rclone／原生 Linux 等条件跳过，0 失败；Ruff、Bandit、Python 3.10 关键 CLI、两 Edition 载荷及网站构建／19 项测试通过。修正了写死旧版本的就绪测试夹具，并补测版本不匹配仍须拒绝；生产校验保持不变。线上结果以本次 Actions 为准，不将环境跳过写成通过。

本轮不连接真实 VPS、不操作用户网盘。真实 Telegram 转存、生产升级／数据库回退、可选通知与配额的长期使用、ACME／续期和手机播放仍需独立验收；历史 [v1.3.0 人工迁移记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)与 [v1.4.2 升级记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md)不外推为 v1.4.3 实机通过。
