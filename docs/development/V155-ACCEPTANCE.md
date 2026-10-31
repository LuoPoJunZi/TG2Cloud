# v1.5.5 发布与兼容记录

状态：2026-10-31，v1.5.5 已正式发布。同标签原生双架构、源码、镜像与两份 Compose 包核验通过；专用测试 VPS 的 CloudDrive2 保留配置升级和基础检查已通过，单项真实恢复转存与独立目的端大小复验通过。真实用户 VPS 新装、OpenList 实机及长期运行尚未执行，不用 CI 代替这些结论。

## 改动与兼容

新文件推广前后缀清理、说明链接文字屏蔽保留、规则解释与可选排除范围、规则方案原子批量应用、分页失败恢复、有界历史预览、等待汇总及实际相对目录预览。新来源默认视频、至少 50 MB、排除广告／内部群／搜索引擎；不改写已有来源规则，不追溯改名。

业务 schema 3、运行目录、配置与历史任务继续兼容，不增加依赖或环境变量。规则方案使用现有 service_meta。显式 exclude_scope 不受旧程序支持，回退前在本版界面恢复“沿用文字范围”移除字段，或使用匹配的一致性快照。不得删表重建、重置 Session，或让两个实例同时使用同一 Bot Token。

已审阅原 v1.5.4 正式提交 `7d3a56ff3cb7b9d9f8d994930904c1749677c69b` 的两 Edition 升级基线。旧证据见[v1.5.4 记录](V154-ACCEPTANCE.md)。

## 代码审计与自动验证

补修清理原名后重新分析未变说明时丢失 Telegram 链接实体的问题，避免推广链接文字重新成为标题；先复现失败再修正。管理员、私聊、一次性确认、来源／连接修订、任务 CAS、事务、去重、配额与磁盘保护继续有效。源连接或规则在异步检查中变化时拒绝继续。

本地 `python -B .github/scripts/check_python.py all`：1573 项，1537 通过、36 环境条件跳过、0 失败，331.591 秒；仓库输入、Ruff、compileall 通过。固定 Ruff 0.17.0、定向 Bandit、Bash／ShellCheck、Python 3.10 无 site-packages 帮助与命名预览 6 项通过；网站构建与 37 项测试通过。纯 Git 导出副本的 34 项新增相关回归通过，不依赖私有归档。

## A/B 提交与正式发布

- 辅助 A：`d064ced682396c579b21b36e94c7c7502132c13a`，[运行与双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41046375782)、[CLI 矩阵](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41046376033)及仓库／网站／文档五组全部通过。
- 入口 B／正式 Tag commit：`30ffeefb76d20556d8e7dfcce8af1205d5371fbb`。两入口固定 A；[运行检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41047091009)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41047091069)及其余三组全部通过，PR #20 快进合入 main。main 的运行复核也[通过](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41047552924)。
- [同标签源码发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41047556579)、[镜像与 Compose 发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41048244806)成功。源码 387 个文件逐字节对应 Tag；两版包与同标签生成器一致，五份实际资产 SHA256、清单与 GitHub 摘要一致，匿名镜像索引及两平台核验通过。校验和不是数字签名。
- 已核验公网／内网公开 raw 入口逐字节对应 B。不移动 Tag、不替换资产、不执行 moving main 业务代码。

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| `COMPOSE-SHA256SUMS.txt` | 215 | `c1daa818155587f528c1bfb5ebf552ea2dbf06636cfb3501ae53534311fc0773` |
| `SHA256SUMS.txt` | 96 | `57302ec00a8af6b2f53ea2c1d6522722e0014116ad689ee0c604e642eff7794c` |
| `TG2Cloud-v1.5.5-compose-clouddrive2.tar.gz` | 240935 | `c91ded983c1c1d024e07fe7ee5de1911af2614326b047b879a8e59634f1dcda3` |
| `TG2Cloud-v1.5.5-compose-openlist.tar.gz` | 240829 | `ef5c45226b85768392ac870d52dc9d88bd281a60037f1eaab91749a647035b8b` |
| `TG2Cloud-v1.5.5-source.tar.gz` | 3896654 | `0f7033c1b0e4ab2f90b7eaa6f443f0c6b686b8a4f6d3a3ffb0574aa27b87eca4` |

镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:bcaba57c95e4730d95e89d2278d20b08bdb8abe1a39319daa8373d605fcc5cd4`。

- `linux/amd64`：`sha256:2760f1a6c1d478f95a79d1dda278a437d204b210bbf8f136cd2c4c9c657afb75`。
- `linux/arm64`：`sha256:7f9d60d2d6aec7331fb39043a7654d5e6f5166052ec1ac5966d8c5f50e1f84d4`。

不可变源码包的根 README 稳定版文字仍记录构建前的 v1.5.4；包内程序、镜像、HTTPS 工具及 Compose 下载示例均对应 v1.5.5。当前主分支文档已同步实际发布状态；安装与升级以[当前教程](../VPS-INSTALL.md)和[Compose 教程](../COMPOSE.md)为准，不通过改 Tag 或换资产修改历史快照。

## 专用测试 VPS 验收

2026-10-31 严格核验历史 SSH 主机指纹；在没有活动传输时用现有快照 API 备份，33 个文件、18,443,065 字节，隔离结构与数据库预检通过，原服务恢复。备份仅保存在测试机私有目录，没有导出凭据。

通过 GitHub 公开入口显式选择 v1.5.5，完成 CloudDrive2 v1.5.4 → v1.5.5 保留配置升级，退出码 0。Bot／CLI 均为 1.5.5，运行代码指纹、容器健康、数据库 schema 3 和 quick_check 通过。升级前后 961 条任务的身份、原名、候选名和目标目录、8 个来源配置与两份 Session 授权一致；.env 逐字节保留。rclone 派生配置仅密码混淆值重新生成，其余字段一致、权限 600、认证探测通过；不把混淆值的字节变化误判为修改网关密码。

8 个来源详情、规则方案和失败恢复页使用真实数据库只读渲染通过，非管理员拒绝；两个合成命名样例通过。该检查未创建 Telegram 客户端或发送消息，不等同于手机用户逐按钮验收。

本机 HTTPS 11 项通过，无提醒；外部执行网络通过正常 TLS 证书校验，管理页 HEAD 200、管理域名 /dav/ HEAD 403。单次外部检查不代表所有用户网络或手机环境均可达。

单项真实恢复：只选择一条无远端提交记录、可恢复的旧下载失败任务，沿用原编号和目标，先核对个人身份／原附件，再通过本版安全恢复服务重新排队。为避免并发打开个人 Session，维护检查短暂停止 Bot，独占 Session 后关闭临时客户端，再恢复同一 Bot；网关未变化，没有批量重试或修改来源规则。该任务实际完成下载和上传，各 171,460,210 字节，状态 completed、验证方式 size；随后独立只读查询 WebDAV 目的端大小仍为 171,460,210 字节。恢复审计 1 条，状态完整经过排队、下载、上传、验证与清理后完成；任务总数仍为 961，未创建副本。旧下载失败从 53 项减少为 52 项，仅恢复这一项，其余失败保留；没有本次新增失败。临时验收容器已移除，最后观察 Bot 健康、业务就绪、无活动任务或冷却，8 个来源仍启用。

## 未执行与回退边界

OpenList 未在测试机安装，实机转存未执行；原生 ARM64 真实 VPS、新装／NAS、手机 Range、证书长期续期、实际新增消息的命名、手机逐按钮操作、规则方案批量应用、历史补拉确认、灾难恢复和长期吞吐另行验收。一次文件接收与 WebDAV 大小复验不等于云存储官方最终入库或内容哈希验证。

回退先停用任务并保留现场，核对匹配版本／配置和一致性快照，在隔离目录预检后再决定恢复。不覆盖尚未验证的数据库，不让两个实例同时处理任务，不删除用户云端文件。本轮没有执行生产恢复或云端删除验证。

[升级](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [命名](../NAMING.md) · [监听](../LISTENING.md) · [备份](../BACKUP-RESTORE.md)
