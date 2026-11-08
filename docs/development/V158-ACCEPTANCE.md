# v1.5.8 发布与兼容记录

状态：2026-11-08，待发布。用户已授权提交、推送、正式 Tag、源码、共享镜像和两份 Compose 部署包；真实 VPS 验收由用户在发布后执行。

## 改动与数据兼容

Compose format 3 新增随包离线 `manage.sh`，共享 Bot 与公共管理服务，独立处理 Compose 归属、升级、备份和卸载。Bot 配置白名单隔离 OpenList 初始管理员密码；新增默认进程数限制及可选 CPU／内存限制，核对 Docker 实际值。两网关固定镜像不变，CloudDrive2 必要权限保留。

内存采样参考标准 cgroup v1／v2；就绪与诊断增加下载放行条件和有界排队分类，不改变 Bot 首页。两种部署互相拒绝混合容器／目录，脚本实例快照不纳入 Compose 专属元数据。

业务 schema 3、现有 `.env`、任务、下载、两个 Session 和已有唯一 `tg115.db`／`tg2cloud.db` 保留，无数据库迁移。Compose 可选资源变量不影响原脚本模板。第三方代理仍仅导出候选；早期无 helper 的 format 1 不自动菜单升级。

已核对原 v1.5.7 Tag 实际提交 `0c71f9ee3f626510f00999ab2770beecf48cc029`，新增两 Edition 载荷基线；不把 main 的维护提交冒充原正式版。

## 本地验证

发布前共享兼容复核：完整检查1648项，1612通过、36既有平台／工具条件跳过、0失败；Ruff、语法、仓库清单、源码清单和 Bash／ShellCheck 通过。Python 3.10 专项187项，183通过、4条件跳过。干净公共副本分别组装两 Edition 脚本载荷和 Compose 包，模板与归属隔离核验通过。网站构建与37项测试通过。

宿主 GnuPG 口令参数隔离与失败不发布副本的模拟通过；本机 Windows Git GnuPG 因 agent 不可用未完成真实加密回读，Linux 实际回读尚待验收。没有把模拟结果写成真实网关或 VPS 通过。

版本、基线同步后的检查及远端结果在完成后补录。CI 条件下的隔离 Docker、模拟 WebDAV／网关不等于用户真实云盘、DNS 或长期运行验收。

## helper、CI 与发布资产

helper A `9e103d68f48e36503a76b87770980ff292329e63` 已公开，80 个文件的 Git blob 与远端目录树一致，3 个匿名 raw 下载样本与 Git 对象字节一致；入口 B 固定该真实提交。

A 的五组远端检查通过：[原生双架构测试](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/42473474071)、[Python 3.10／3.13 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/42473474202)、[仓库检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/42473474017)、[文档检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/42473474073)、[网站检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/42473474048)。AMD64／ARM64 原生 Compose 初始化、非 root 配置、两 Edition 候选和隔离 WebDAV 等测试通过；这不是用户真实网盘验收。

B、同标签发布 CI、实际 Tag 与资产摘要完成后补录。计划核验 `TG2Cloud-v1.5.8-source.tar.gz`、两 Edition Compose 归档及两份 SHA256 清单，当前不填写未生成摘要。真实用户 VPS 验收尚未执行。

## 发布后用户验收

1. 先做私密一致性备份，记录实际版本、目录、数据库名称与 Bot／个人 Session；不同时启动相同 Token 的两个实例。
2. 公网一键脚本可明确选择本版，例如 `bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --release v1.5.8`；OpenList 更换 Edition，内网实例仍使用 `install-lan.sh`，不转换部署方式。
3. v1.5.7 format 2 Compose 升级前先在 Bot 发送 `/pause`，等待活动传输结束。下载并核验完整新包，再运行新包 `manage.sh --root /原Compose目录`，选择“安装与升级”，指定 v1.5.8；保留原目录和配置。原 Bot 尚不支持新的宿主队列暂停接口。
4. 分别核对实际 Bot／CLI／包版本、原配置与 Session、管理入口、家人权限、分类通知、监听、业务就绪；检查有效内存、窗口和真实容器限额。
5. 用自有小文件测试手动与监听转存，检查网关目录、大小与可读性，再到云盘官方客户端确认。失败保留现场和脱敏诊断，不删除远端文件或数据库。
6. 需要时在隔离范围测试 HTTPS、外部只读 WebDAV、手机 Range、备份／加密回读、故障回退和单 Edition 卸载；不对生产数据做破坏性演练。

新 Bot 可能写库后失败不会自动恢复旧数据库，须人工核对事务记录与匹配快照。测试日志不要公开 Token、API Hash、密码、Session、数据库或私人文件名。

[一键脚本](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [Compose 管理](../COMPOSE-MANAGEMENT.md) · [备份恢复](../BACKUP-RESTORE.md)
