# v1.5.1 性能维护发布与验收

## 当前状态

2026-10-28：用户授权推送并正式发布 v1.5.1。现已正式发布，辅助 A、入口 B、远端 CI、同标签发布及实际资产证据见文末。真实环境验收安排在正式版本可安装之后；未自动连接 VPS 或用户网盘。

## 改动与兼容

减少重复等待／上传进度写入、利用现有索引查询活动及个人任务、复用单轮资源采样；保留磁盘额度原子预留、实时取消核验与失败文件额度。监听来源串行轮询有超时和轮次预算，从下一来源继续；账号级限流、来源修订和消息去重继续生效。历史维护按间隔执行且失败回滚，计划审批仍实时检查过期。

沿用 schema 3，没有新 DDL、依赖、环境变量、Compose 或公开端口。保留两 Edition 配置、Session、数据库和各自存储策略。启动迁移与兼容回填保持原行为；补入原正式 v1.5.0 固定提交的两 Edition 升级基线。

## 发布门槛

1. 先公开辅助提交 A 并完成五项现有 GitHub CI，不改变 main 的稳定入口。
2. 两个入口 B 固定已验证 A 的真实 SHA，逐文件核对清单，完成 B 的全部 CI。
3. 创建不可变 v1.5.1 Tag，由同标签 Linux 原生两平台、两 Edition 和隔离集成检查通过后发布一次源码包与校验清单。
4. 下载实际资产，用正式验证器及 Tag 文件逐项复验；成功后更新 README／网站正式状态。

## 本地验证

版本同步前完整检查 1389 项：1355 通过、34 个既有环境条件跳过、0 失败；仓库、Ruff、compileall 与 Bandit 完成。Python 3.10 无第三方依赖回归 22 项通过；网站构建和 37 项测试通过。版本同步后的结果另记，不借用前版 CI。

十万条合成历史记录的一分钟循环完成 4008 轮、无重复行写入、数据库完整性正常；工具只创建临时数据库，不读取生产实例。测量定义与限制见[维护说明](LOCAL-MAINTENANCE.md#待发布资源循环上传进度与性能测量)。本地 Windows 缺少原生 Linux／Docker／rclone 条件，跳过不计为通过；一分钟合成循环不等于小时级真实负载。

## 发布后安装与验收

先在独立测试实例备份配置、业务数据库和 Session，并保存镜像／程序版本、网关和 HTTPS 备份；不要让两个实例共用同一 Bot Token。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.1/install.sh) --edition clouddrive2 --release v1.5.1 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.1/install.sh) --edition clouddrive2 --release v1.5.1
```

正式发布后才执行以上命令；OpenList 改为 `openlist`，内网保留原模式并使用同标签 `install-lan.sh`。

| 项目 | 操作与通过条件 | 出错时收集与恢复 |
| --- | --- | --- |
| 升级与身份 | Bot／CLI 为 1.5.1，配置、任务及两个 Session 保留，schema 为 3 | 保存脱敏摘要和停止阶段；保留备份，不卸载重装 |
| 手动转存 | 两 Edition 各转存自有小文件，远端大小复验后完成；网盘官方端另核实 | 记录任务号及错误分类，保留本地文件，不覆盖远端冲突 |
| 监听公平性 | 多来源新附件正常入队；一个来源超时不长期阻塞其余来源 | 保存来源状态／修订及脱敏超时提示；暂停问题来源后重试 |
| 限流与去重 | 账号冷却时不继续请求；重启后不重复入队，普通转存继续工作 | 核对冷却、游标和任务号，不重置 Session 或批量删除记录 |
| 过期审批 | 过期计划无法提交；后台清理不撤销监听授权 | 保存计划状态和时间，不手改数据库 |
| 进度和保留 | 速度变化正常显示；取消／失败保留本地副本；重试和最终验证记录正确 | 保留任务和本地副本；远端不确定时走原人工恢复 |
| 空间保护 | 在隔离条件模拟额度不足并恢复，调度安全暂停／恢复 | 记录资源页与等待原因，不删除非受管文件 |
| 持续运行 | 在测试实例观察数小时的队列、CPU、内存、DB／WAL 及错误 | 日志只保留脱敏任务信息；不要公开 Session、Token 或个人内容 |
| 回退演练 | 停止实例后在隔离目录核对匹配旧代码和升级前快照 | 先保护当前数据；不覆盖未经验证的数据库，不启动冲突 Token |

本表均为待执行实机项目；同标签 CI 的隔离容器检查和用户网关验收分别记录。

## 版本同步后的本地复核

首次完整运行 1389 项，1354 通过、34 个既有环境条件跳过、1 项文档失败：根 CHANGELOG 的历史索引漏列 1.5.1。补齐索引和 32 版总数后，关联仓库／发布准备回归 58 项通过，Ruff、compileall、Bash／ShellCheck、Bandit、Python 3.10 标准库回归 22 项通过。网站最初缺日期／版本标记与历史验收链接，补齐后构建及 37 项测试、4345 本地引用通过；没有删除测试或放宽检查。最终完整回归和远端结果完成后追加。

## 辅助 A 远端验证

辅助 A 为 `f17076544a28efc48c952f1114aea442ad809c00`，五项 CI 全部成功：[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621797117)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621801695)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621805119)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621808729)、[Linux](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621812271)。包含两组原生 Linux 运行、四组宿主 CLI、两 Edition 候选构建与现有隔离 WebDAV／网关／代理检查。入口 B 仅固定此真实公开 SHA；不使用旧版结果代替本版。

最终完整本地检查通过：1389 项中 1355 通过、34 个既有环境条件跳过、0 失败；仓库、Ruff 与 compileall 均通过。两个入口更新 pin 后，身份、清单、旧版基线与 66 个 helper 一致性四项正式静态门槛全部通过，Bash／ShellCheck 通过。

初始入口 B `bc24886dce771b6593a8571cfbfa3e35f8a8fe6b` 的网站检查指出四份完整指南仍显示旧 helper SHA。仅将当前版本／helper／验收链接同步到 v1.5.1，保留历史正文；未修改测试、工作流、生产能力或 pin。最终 B 各项 CI 重新验证。

## 正式发布与实际资产核验

- 辅助 A：`f17076544a28efc48c952f1114aea442ad809c00`；入口 B／不可变 Tag：`2741c6b5f40469a2bc035c87274b62fc66ef1a74`。
- 辅助 A 五项 CI 全部通过：[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621797117)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621801695)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621805119)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621808729)、[Linux](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40621812271)。
- 入口 B 五项 CI 全部通过：[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622547215)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622547317)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622547199)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622551071)、[Linux](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622547498)。
- [同标签正式发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40622910178)的准备、两个原生 Linux 平台和发布任务成功；正式版本为非草稿、非预发布。
- 实际资产 `SHA256SUMS.txt`：96 字节；SHA256 `08b7c92bf836734be706889abc1c912266ad5550e5b9b7aea4234b6210b91e3b`。
- 实际资产 `TG2Cloud-v1.5.1-source.tar.gz`：3873559 字节；SHA256 `fb8868f1f358eb7f157e37843860efe728d74e22a93a6b07dfc05e9a76b34b03`。
- 正式源码验证器通过；实际资产与 GitHub 摘要一致，378 个文件与 Tag 按 Linux LF 归档规则逐字节相同。两个公开 main 入口与 66 个公开 helper 逐文件核验通过；校验和不是数字签名。
- 未连接真实 VPS、Telegram 或用户网关；实际转存、长期负载、手机和生产恢复尚未验收。
