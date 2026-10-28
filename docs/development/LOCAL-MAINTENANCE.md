# 维护与发布记录

本文保存 v1.4.6～v1.5.1 的开发与发布历史；当前使用步骤见[运行维护](../OPERATIONS.md)，最新发布及实机证据见[v1.5.1 记录](V151-ACCEPTANCE.md)。历史“待发布”标题为保留旧链接而保留，所在段落的现状在下方注明。

## v1.4.8 维护与发布核验（2026-10-25）

v1.4.8 已正式发布：简化外部 WebDAV 安装与普通输入，增加真实目录读取／有效历史值复用、管理页地址及绑定变化保护。A／B、同标签原生双架构与实际资产核验全部通过，详细证据见文末。账号原生只读仍须人工确认，未知／加密配置首次补录，不改 Bot 配置、Session、数据库或网关。下方历史记录按原版本理解。

版本同步后完整本地回归 1216 项：1183 通过、33 项平台／工具条件跳过；Python 3.10 标准库回归 121 项：119 通过、2 跳过。Ruff、语法、Bandit、ShellCheck、网站 37 项和4096以上本地链接检查通过。已静态核实 v1.4.7 原 Tag 提交并补入两版载荷摘要；未访问真实 VPS 或用户网盘。

## v1.4.7 维护与发布核验（2026-10-25）

本轮源码为 v1.4.7：统一外部 WebDAV、退役两个独立 Shell 入口，完善 Certbot 挂载复验和维护代码失败恢复。v1.4.7 已完成辅助 A、入口 B、同标签双架构及实际资产核验，正式发布完成。下方 v1.4.6 记录按当时范围保留。

本地完整回归 1198 项（1166 通过、32 跳过）；3.10 最小宿主环境 146 项（143 通过、3 跳过）；静态检查、ShellCheck、网站 37 测试和历史资产正负校验通过。本版远端 CI 与资产结果见文末，不以本地或旧版实机数据替代。已核实 v1.4.6 原 Tag 对应提交并补入升级基线。

新布局由 external WebDAV API 2 明示；API 1 和旧 Tag 按原清单验证。当前 shell 阶段逐项检查两个保留入口，继续检查全部维护 hooks。版本示例下方按历史上下文理解，制定后续版本计划应高于当前源码版本。

# v1.4.6 维护与发布准备

本文说明 v1.4.6 的外部 WebDAV 界面与维护改动，已于 2026-10-24 正式发布。辅助 A、入口 B 与同标签门禁全部通过；新工具和新界面随对应离线代码升级提供；不是新增 Windows 支持或运行数据库迁移。

## 外部 WebDAV 界面

本地源码运行：

```bash
python3 -B scripts/run_source.py webdav
```

沿用原有 10 项中文菜单及英文子命令。状态／连接检查页面执行后停留，1 刷新或重新检查，0 返回功能菜单；重新检查仍需输入本次认证密码，不保存明文。状态仅为本地登记信息，不能代替实际连接检查。修改操作没有“刷新执行”按钮。

用户管理显示所选 Edition／工具版本、共同目录与账号状态，返回文字区分功能菜单和用户管理。卸载或升级操作后退出当前进程，避免继续读取已删除或替换的运行代码。明确子命令仍执行一次后退出；权限、锁、账号隔离、后端人工只读配置及确认规则不变。

安装主流程、Bot 菜单和传输流程保持原行为。主项目升级不会代替独立附加功能升级。

## 发布准备工具

完整源码 checkout 中执行；`--version` 是计划目标，必须高于当前版本。以下 1.4.9 只是演示，不表示已确定下个版本号：

```bash
python3 -B .github/scripts/prepare_release.py --version 1.4.9
python3 -B .github/scripts/prepare_release.py --version 1.4.9 --directory build/review-release-149
```

第一条只输出计划；第二条只向 `build/` 下全新的目录写入 `plan.json` 和 `version.patch`。不修改工作树版本、依赖、CHANGELOG、Release Notes 或 pin，不执行 Git、网络、部署或发布操作。拒绝已有候选目录、链接路径、同版／降版和异常元数据。

补丁覆盖唯一版本源、安装入口展示版本和网站版本元数据；网站保持旧的实际发布版本，将候选状态标为未发布。维护者必须审阅实际变更说明、兼容性、文档与下载链接，再决定是否应用候选补丁。

继续执行已有的 `maintenance_preflight.py`。新代理模块使当前 helper 一致性按预期阻断，不能忽略或改成通过：

已核对本地 v1.4.5 原正式 Tag 提交，使用现有工具静态生成并复核两 Edition 载荷摘要，补入受支持的历史基线。已有历史 Git 对象重生成测试继续核对，不能用当前工作树的新代码替代旧正式源码。

1. 本地审阅源码和载荷清单，运行回归。
2. 获得发布授权后，先公开辅助提交 A 并等待其 CI。
3. 用 `prepare_bootstrap.py --directory build/<新的候选目录>` 生成入口候选；入口提交 B 只固定已公开、通过验证的 A，不固定自身。
4. 等 B 的 CI 通过后，再按授权创建不可变版本 Tag，同标签原生双架构校验与发布。
5. 下载并核对实际资产；此后再更新网站的已发布状态。校验和不等于数字签名。

## 测试与 CI 组织

`tests/naming/` 集中四组命名质量、增强、接入边界和预览测试，保留原测试文件名和全部断言。混合测试及共享夹具暂留原位置，不为目录整齐搬动整套测试。移动前后，标准化模块前缀后的 1,121 项测试发现集合摘要一致；之后再独立计入新增维护测试。

完整发现仍使用 `python3 -B -m unittest discover -s tests -v`。直接按子目录运行接入类测试时，需让共享夹具可导入：

```bash
PYTHONPATH=src:tests python3 -B -m unittest discover -s tests/naming -v
```

日常原生运行测试与正式 Tag 的当前布局验证共用 `.github/scripts/linux_validation.py`：

```bash
python3 -B .github/scripts/linux_validation.py shell
python3 -B .github/scripts/linux_validation.py test
python3 -B .github/scripts/linux_validation.py quality
```

`shell` 逐个检查四个入口并执行原 ShellCheck 范围；`test` 沿用完整测试入口；`quality` 保留 Ruff、编译、版本／清单、Bandit 及两份依赖审计，任一步失败即停止。Docker、双架构、隔离 WebDAV、网关／FUSE、打包与发布门槛继续由现有工作流执行。历史布局的旧校验分支保留，不改写旧 Tag。

## 小范围模块整理

`deployment/proxy/rendering.py` 承载纯 Nginx／Compose／续期循环文本生成。`manager.py` 保留宿主操作、锁、激活和回退，并重新导出旧渲染接口，现有调用不必改导入。生成内容、镜像、权限与状态协议保持原行为；新模块进入 bootstrap 和 runtime 显式清单。

暂不拆分 SQLite 事务、上传提交顺序或所有 Telegram 命令。后续随实际维护需求逐项抽离，每次保持事务／锁边界并补回归。

## 发布准备前的本地验证结果（2026-10-24）

- Python 3.13 完整检查：1,137 项测试，1,106 执行通过、31 项按现有环境条件跳过，0 失败／错误；仓库检查、Ruff 和 compileall 完成。另用 CI 固定的 Ruff 0.17.0 检查通过。
- Python 3.10：发布工具 8、外部结果页 6、纯代理渲染 2、干净宿主管理包 2 项通过；WebDAV `--help` 无 Bot 依赖运行通过。
- 额外尝试在裸 Python 3.10 跑完整旧代理组时，有 3 个夹具错误：缺少开发用 cryptography，且两处旧测试使用 datetime.UTC。完整代理组按现有规范在 Python 3.13 验证通过（75 项中 4 项环境跳过）；未修改生产能力、删除测试或新增 skip 掩盖此次额外尝试。
- 四个入口 Bash 语法、原受管 ShellCheck 范围、Bandit 通过；Bandit 的既有 nosec 无匹配提示不当作新增漏洞。
- 两 Edition 构建上下文在新目录组装成功，递归代码指纹一致；7 个纯渲染函数的函数体与重构前相同，四组移动测试除包定位和文档字符串外 AST 一致。
- 网站构建、36 项测试及 4,081 个站内链接／资源／锚点检查通过，33 HTML、266 条本地搜索记录；未部署网站。
- 版本、显式清单和 7 个旧版基线预检通过。helper 一致性仍按预期阻断：须以后经授权公开 A／更新 B／远端 CI 后才能发布。正式版本仍为 1.4.5，未创建 Git 提交或改动远端。

本轮没有 Docker daemon、Linux PTY／flock／原生 FUSE 或本机 rclone 集成条件，相应已有跳过不计为通过；未执行远端 CI、实际 VPS／网盘、手机播放、公网 ACME 或生产恢复。用户提供的旧代码验收与本地候选测试分别记录。

## 发布准备进度

以下保留辅助 A 阶段的状态；正式发布最终结果见下一节。

辅助 A `56e5115e729356c40a10912bb7d7c000969e40df` 的五项 GitHub 工作流已全部通过，包括[原生双架构与隔离 Docker](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089317744)和[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089317676)。入口 B 固定该已公开 A，新增渲染模块纳入下载清单；正式 v1.4.6 仍须等待入口 B 与同标签发布验证，不借用旧 CI 或跳过固定源码校验。

## 正式发布核验（2026-10-24）

v1.4.6 已于 2026-10-24 正式发布。辅助 A `56e5115e729356c40a10912bb7d7c000969e40df` 与入口 B／Tag `2e18eba718df83beec3a9d0784ca8037125bdd20` 各五项工作流全部通过；[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089991036)的准备、AMD64、ARM64 与发布任务成功。实际下载源码包与 SHA256 清单通过正式验证器，并与 GitHub 资产摘要一致。

源码包 SHA256：`d06803e0c00b73086f2d19520230e660958784da373430002b42b618f38f73b4`。Tag 保持指向入口 B，后续文档提交不改写 Tag 或资产；校验和不是数字签名。本版真实 VPS、用户网盘、手机与完整恢复仍需独立验收。

辅助 A：[双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089317744)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089317676)。入口 B：[双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089759086)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089759031)。仓库、docs 与 website 工作流亦分别成功，不用旧提交结果代替本版。


## v1.4.7 辅助提交验证

辅助 A `85595a83f40371caabfa3f9a2dfeaf7dc756edc1` 的五项工作流已全部通过：[原生 AMD64／ARM64](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40159809761)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40159809820)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40159809777)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40159809805)与[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40159809775)。入口 B 已仅固定该已验证 A，64 个 helper 文件逐项匹配；最终发布与实际资产证据如下。

## v1.4.7 正式发布核验

入口 B／不可变 Tag 为 `322ae065d6cb6a7330f78b8cc0ee60c4c3c53cdb`，辅助 A 为 `85595a83f40371caabfa3f9a2dfeaf7dc756edc1`。A、B 各五项工作流及[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160704507)全部成功；B 的[原生 AMD64／ARM64](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160484530)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160484571)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160484496)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160484494)和[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40160484521)分别核对到该提交。

[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.7) 为非草稿、非预发布的最新稳定版，仅含 `TG2Cloud-v1.4.7-source.tar.gz`（3,723,941 字节）与 `SHA256SUMS.txt`。实际下载经正式源码验证器校验，两资产 SHA256 均与 GitHub 摘要一致；源码包 SHA256 为 `3032914d0060137eaf543c8c11a3f884abaef2d0d037dffb765aa5771c4c1106`，校验清单 SHA256 为 `0759fb10c3e2feadf5ac6990431f1e9e98f55b69a4a5226ef770bfcb23c2ef7e`。校验和不是数字签名。

源码包采用 API 2，含两个安装入口、共享 Bot 与附加功能；不含两个退役 Shell 文件、EXE 或本地私有归档。后续文档提交不改写 Tag 或替换资产。本版未连接真实 VPS、Telegram 或用户网盘；真实升级、原生只读账号、手机播放／Range、公网 ACME、长期续期与完整恢复仍需人工验收。


## v1.4.8 辅助 A 验证

辅助 A `f2c089aeccc1de1c17c43654dad35249236e6e14` 的五项工作流全部成功：[原生 AMD64／ARM64](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175217707), [四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175217657), [仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175217660), [文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175217658), [网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175217673)。两个入口逐文件核对65个 helper 后仅固定该已验证 A；B、同标签与实际资产亦已验证，见下方最终记录。

## v1.4.8 正式发布核验

辅助 A `f2c089aeccc1de1c17c43654dad35249236e6e14`，入口 B／不可变 Tag `e24cddfa77fe76b90ea63ee9e7d88008066cb0a3`。A、B 各五项 CI 与[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175950235)全部成功。B 的[原生 AMD64／ARM64](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175676276)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175676253)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175676298)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175676231)和[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175676315)均核对到该提交。

[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.8) 为非草稿、非预发布的最新稳定版，仅含 `TG2Cloud-v1.4.8-source.tar.gz`（3,734,419 字节）与 `SHA256SUMS.txt`。实际下载通过源码验证器，两个资产摘要与 GitHub digest 一致。源码包 SHA256 `6282058970c09e05e0b74cab1df7d775373464b8c3b40bbfc90e3ae4cd57ee69`；清单 SHA256 `1b9ddb8834c5b02011789c5274264075d9921e713c0076ca59176bc60c0aa037`。校验和不是数字签名。

源码与两个引导入口采用现有 API 2，65 个 helper 逐文件一致；未恢复桌面文件或退役 Shell 入口。后续文档提交不移动 Tag 或替换资产。本轮未连接真实 VPS、Telegram 或用户网盘，真实 SSH／Web 终端、两版原生账号目录、手机播放／Range、公网 ACME、长期续期及完整恢复仍须独立验收。原生 Linux PTY、POSIX 权限及隔离网关／Nginx 由对应 CI 验证，不等同真实用户安装验收。


## 待发布：任务数据库热点优化

**状态：已随 v1.5.1 发布。** 以下为 2026-10-27 开发阶段记录，保留原锚点。

等待原因写入由 TaskDB.set_wait_reason 统一处理：先读取当前状态，原因相同则不更新 updated_at；真正写入时再次检查状态与取消标记，避免覆盖其他连接刚取消或推进的任务。磁盘／成员额度预留仍在原 BEGIN IMMEDIATE 事务内实时计算，不用缓存额度替代事务。等待未变化不代表服务失活，健康观察仍使用现有心跳。

监听的接收上限查询只计 queued、reserved、downloading、streaming；不统计已完成历史，不改变 100 项阈值，也不删除记录。个人任务统计直接按 sender_id 查询，沿用已有索引；全局统计仍包含全部状态。没有新增 DDL、依赖、环境变量或 UI。

回归入口：`python -B -m unittest discover -s tests -p test_database_hotpaths.py -v`。测试使用临时数据库和合成数据，核对查询结果、SQLite 执行工作量、重复等待无写入、取消竞争、事务回滚、重开数据库以及并发预算预留；监听回归另核对 100／99 项边界和冷却结束恢复。完整检查仍执行本页原有流程。模拟查询的加速比例不能视为真实 Telegram／网关传输提速，Linux 实机收益需后续验收。


监听轮次使用 `_poll_sources` 管理串行请求的取消、30 秒单来源超时和轮次预算，`_poll_after` 仅保存本进程的公平轮询位置，不替代数据库消息游标。等待中的来源编辑、账号切换、FloodWait、退出与超时后的去重由 `tests/test_listening.py` 覆盖。后台 `_maintain_if_due` 使用单调时钟每 60 秒到期检查；`Plans.create` 只过期当前用户的计划，不再逐附件执行历史 DELETE。完整维护沿用保留策略并在独立事务中提交，失败不影响监听授权；计划审批有效期不依赖该维护时钟。以上已随 v1.5.1 发布，详见[监听说明](../LISTENING.md#v151监听调度与维护优化)。


## 待发布：资源循环、上传进度与性能测量

**状态：已随 v1.5.1 发布。** 以下为发布前本地测量记录，不能代替后续实机验收。

资源循环通过 `counts(states=SCHEDULING_STATES)` 排除已完成历史；个人和全局状态页面仍保留原查询语义。暂存额度仍包含失败后保留的本地文件。同一轮内复用暂存占用与流式数量，不跨轮缓存；独立文件系统继续单独探测。实际接收／预留仍使用原数据库事务和即时空间检查。

普通上传只省略字节值未变化的重复写入，速度样本每次刷新。重试从新的进度记录开始；取消或失败保留已记录进度与本地文件。即使后端没有报告中间进度，验证完成仍先持久化完整字节数和清理待办，再删除本地副本。这不改变流式背压或两种网关的提交方式，不增加数据库结构、依赖或配置。

可在源码目录执行标准库性能工具：

```bash
# 默认：十万条合成历史，1000 轮；无需 Telegram 或 Docker。
python3 -B .github/scripts/benchmark_runtime.py

# 定时合成循环；最多一小时，可用 Ctrl+C 结束。
python3 -B .github/scripts/benchmark_runtime.py --tasks 100000 --duration-seconds 60 --interval-ms 10
```

工具始终创建并正常退出时清理临时数据库，没有生产路径参数；不打开现有实例，不访问网络。输出 JSON 包括全状态／调度状态／个人查询中位耗时、首次及后续数据库重开耗时、循环行变更数、DB／WAL 大小和完整性检查。`--duration-seconds` 非零时替代 `--cycles`；输入规模有上限，耗时样本只保留最后 4096 条。中断使用正常的临时目录／连接清理，不承诺强制杀进程后无残留。

内存指标是 `tracemalloc` 观察到的 Python 分配，包括有上限的测量样本，**不是**进程 RSS、SQLite 原生内存或 Bot 全程内存。该工具测量数据库热点，不能替代实际监听、媒体组、rclone、网关或长期运行验收。常规 CI 只运行小规模工具回归，持续负载需显式执行，不增加日常 CI 等待。

2026-10-27 本地 Python 3.13 合成测量：100000 条已完成历史、1 条排队及 1 条失败保留任务，60.003 秒执行 4008 轮；循环行变更 0、数据库完整性 `ok`。全状态查询中位 6.9493 ms，调度状态 0.0140 ms；首次重开 48.1307 ms、后续中位 48.3424 ms。机器、缓存和同时运行的回归会影响结果，不作为固定性能门槛或真实传输提速承诺。

本次保留数据库启动时的迁移和幂等修复：样本启动开销不足以支持跳过兼容逻辑。若后续超大历史实例出现启动瓶颈，应先在隔离副本测量并覆盖历史字段、额度、事件回填与恢复，再决定是否优化。

相关回归：`test_database_hotpaths.py`、`test_readiness.py`、`test_reliability.py`、`test_upload_progress_persistence.py`、`test_runtime_benchmark.py`。工具和这些优化在记录时属于本地待发布改动，现已随 v1.5.1 发布。

本轮完整本地检查：1389 项测试中 1355 通过、34 项因现有 Linux／Docker／rclone 等环境条件跳过、0 失败；仓库检查、Ruff、compileall 与 Bandit 完成。Python 3.10 无第三方依赖的数据库／就绪输出／测量工具回归 22 项通过；网站构建和 37 项测试通过。未执行真实 VPS、Telegram、用户网盘或小时级实际负载验收；未提交或发布。

上述 2026-10-27 待发布优化已随 v1.5.1 发布；完整发布证据与尚待实机验收范围见[v1.5.1 记录](V151-ACCEPTANCE.md)。此前本地阶段记录按当时范围保留。
