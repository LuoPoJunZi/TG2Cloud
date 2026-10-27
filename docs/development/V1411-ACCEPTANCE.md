# v1.4.11 发布与监听目录验收

## 当前状态

2026-10-26：用户授权提交推送并正式发布 v1.4.11。[v1.4.11 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.11) 已发布；辅助 A／入口 B、最终 main 五项检查、[同标签原生双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40318301764)和实际源码资产核验通过。发布当时未执行真实 VPS、Telegram、用户网关及生产恢复；2026-10-27 用户补充的两台主机升级反馈见文末，不自动连接用户主机。

## 本版范围与兼容

- 新来源位于真实 Bot 保存目录下：来源名称／视频、图片、音频、文档、压缩包、其他文件。默认仍暂停、仅视频、确认后转存，不因分类增加而放宽筛选。
- 来源名去 Emoji，最多 60 显示列，相当于 30 个全宽汉字；UTF-8 组件不超过 112 字节，完整类型相对路径不超过 128 字节。同名加来源编号，删除后仍保留绑定；重新添加或频道改名不搬迁旧目录。
- 已有来源维持旧布局；主动选择来源目录分类、保存后暂停，再核对启用。计划冻结路径、来源修订校验、目录授权和原任务去重不变。
- 仅取消对保护标记的本地单独拦截；真实成员权限、管理员身份、个人 Session、附件变化和 Telegram API 读取拒绝仍安全停止。不借用其他账号，不自动加入、不抓评论。
- 目录创建失败保留来源记录，可按钮重试；根目录漂移不自动重绑。补充返回状态导航，添加错误按固定脱敏类别展示。
- 业务 schema 仍为 3，无新增 DDL／依赖／必填配置。新目录字段写入现有 JSON；回退须使用匹配代码和升级前一致性数据库快照，不能让旧代码解释新目录策略。

## 安装与升级（正式发布后）

先在当前 tg2cloud 菜单 13 创建并核验备份，保留配置、任务数据库、程序／镜像身份、网关与代理配置。监听个人 Session 停用、等待释放后私密备份，不上传原始日志或授权文件。不同时运行共用 Bot Token 的两套实例。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.11/install.sh) --edition clouddrive2 --release v1.4.11 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.11/install.sh) --edition clouddrive2 --release v1.4.11
```

OpenList 改为 `--edition openlist`；内网使用同标签 `install-lan.sh`，不改变安装模式。只有 Release 和资产就绪后使用上述命令。升级 Bot 并重新打开菜单才会更新 Telegram 页面；原 Session 和配置保留。

## 发布后实机检查（完整业务验收仍待执行）

| 项目 | 操作与预期 | 失败时收集与恢复 |
| --- | --- | --- |
| 升级及旧任务 | 核对 v1.4.10 → v1.4.11，schema 3、旧任务、配置和两个 Session 保留 | 保存脱敏阶段／版本摘要，不反复卸载 |
| 手动与旧来源 | 手动转存及既有监听来源保持原目录 | 对照冻结目标与规则，不移动云端文件 |
| 新来源 | 管理员添加测试频道／群组，暂停、仅视频、确认模式，父目录在 Bot 保存目录内 | 目录失败使用重试按钮，不重复添加 |
| 六类分类 | 明确开启相应类型后发送新附件，落入来源下正确子目录；切换手动分类不影响它 | 核对规则匹配与相对路径，不扩大根目录 |
| 名称与并发 | 去 Emoji、长名截短、同名来源区分；重启／重加同一来源不换目录 | 仅记录脱敏示例及来源编号，不清理历史目录 |
| 草稿与路径 | 旧来源主动切换后暂停；未保存不生效；先前计划／任务仍用原路径 | 取消草稿或恢复旧模式，仅影响新计划 |
| 真实读取 | 已加入且可读取的测试附件按规则接收；无权限、Session 失效、服务端拒绝停止 | 收集固定错误类别；核对授权，不借其他账号 |
| 创建失败 | 在隔离测试存储模拟不可写，来源暂停；恢复后按钮重试并显式启用 | 不通过删除云端目录或任务“修复” |
| UI 与权限 | 转存设置三行双列；监听管理返回按钮在来源列表前；家庭成员不能越权 | 重新打开新版菜单，截图前遮盖私人信息 |
| 两 Edition 传输 | CloudDrive2／OpenList 分别普通与流式、大小复验、重启及手动任务并行 | 大小复验不等于云盘官方完成或哈希校验 |
| 备份与恢复 | 仅在隔离目录预检匹配数据库／代码，保留当前可用数据 | 先停 Bot／监听，保护升级后新任务；不做生产自动恢复 |

每项由用户在发布后确认。新消息默认从启用时点开始，历史消息、暂停期间和评论区不属于完整补抓范围。

## 本地验证

本轮功能最终完整检查 1340 项：1306 通过、34 项工具／Linux 条件跳过、0 失败；Python 3.10 无 Bot 依赖 CLI 734 项：722 通过、12 跳过。Ruff、compileall、网站 37 项与构建、两 Edition 载荷组装和本地维护预检通过。发布版本同步后的结果另行追加，不用旧结果替代。

## 远端与资产证据

等待实际辅助 A、入口 B、main 和同标签双架构 CI；资产须下载后验证 SHA256 与标签内文件。未执行项不记为通过，不改写已有 Tag／Release。

### 辅助 A 已核验

辅助 A `7b115e1eef244ee2db7c7c08bb51d0ed3eaf045a` 的五项 CI 全部成功：[原生 AMD64／ARM64 与两 Edition](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40316758592)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40316753038)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40316748717)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40316744775)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40316740700)。66 个实际公开辅助文件与不可变 A 逐字节一致。入口 B 固定 A，不自指；本段不代表 B、Tag、资产或实机已通过。

版本同步时发现完整版本总表遗漏新行；只补齐 v1.4.11 行和“30 个版本”计数，索引与相关监听／基线回归 163 项中 162 通过、1 条件跳过，不修改检查规则。ShellCheck、Bandit 与两份依赖审计通过；本机 pip-audit 跨磁盘缓存警告不改变审计结果，远端 Linux 另行执行。

入口 B 初次 main 网站检查发现安装／卸载和网站开发指南缺少新的真实 helper pin；仅补充发布文档中的 A 身份，保留旧版本历史与现有断言，业务、权限和 helper 均未改动。修正后结果另行追加。

### 正式发布与资产核验

- 已验证辅助 A：`7b115e1eef244ee2db7c7c08bb51d0ed3eaf045a`；最终 B／Tag：`715999fd1fa64077172df6e43b78c3ab8bd2f7c2`，不自指、不改写历史标签。
- 最终 main 五项全部成功：[原生两架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40317744212)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40317810235)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40317742696)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40317742769)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40317742642)。[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40318301764)的 prepare、AMD64、ARM64 和 release 均成功。
- 实际源码包 `TG2Cloud-v1.4.11-source.tar.gz`：3841184 字节；SHA256 `da8d9027fbd1391e29ff537a1ee733767ad559280731c565b0e78557b083ed6d`。`SHA256SUMS.txt` SHA256 为 `d58a17b72ac0251244c2def2cac10a2ebb2435fd44c93c0d03aade9372f85d72`。
- 正式验证器、GitHub digest 和下载字节一致；按 Linux LF 归档规则对比不可变 Tag 的 372 个文件，逐文件相同。未用本机重打包替代正式资产。
- 发布版本同步后本地完整检查 1340 项：1306 通过、34 工具／平台条件跳过、0 失败；Ruff、compileall、网站 37 项和构建、ShellCheck、Bandit、两份依赖审计通过。最低 Python 与原生 Docker／网关由上述远端矩阵另行验证。
- 真实 VPS 升级、监听下载、用户云端转存、手机播放和生产恢复尚未执行。发布成功不等于实机验收通过；按本页清单由用户在发布后验收。

## 2026-10-27 用户提供的两台 Linux 升级记录

以下仅根据用户提供的脱敏后结论整理，维护者没有再次连接主机。两份原始日志不上传到仓库。

| 项目 | 主机一 | 主机二 |
| --- | --- | --- |
| 系统 | Debian 13，原生 AMD64 | Ubuntu 26.04.1，原生 ARM64 |
| Edition | CloudDrive2 | CloudDrive2 |
| 升级路径 | v1.4.10 → v1.4.11 | v1.4.5 → v1.4.11 |
| 配置与备份 | 配置保留标记、升级前数据库一致性快照通过 | 配置保留标记、升级前数据库一致性快照通过 |
| Bot | 实际运行版本 1.4.11、代码指纹和 healthy 通过 | 实际运行版本 1.4.11、代码指纹和 healthy 通过 |
| HTTPS | 本机自检通过 | 本机自检通过 |
| 业务就绪 | 最近观察的基础条件通过 | 最近观察的基础条件通过 |
| CLI | 菜单及帮助含 listen；未独立显示或核验 CLI 实际版本 | 菜单含监听管理；未独立显示或核验 CLI 实际版本 |
| 监听登录 | 无可确认的成功登录记录 | 在提示手机号之前停止；未完成 |
| WebDAV 写入、实际 Telegram 转存、公网、回退 | 本次日志未单独验收 | 本次日志未单独验收 |

现有日志不能证明“CLI 一定是旧版”：菜单及帮助已包含 listen。代码审计另外确认，管理工具原先从当前 helper 复制，确实可能与目标 Release 不同步；成功提示也缺少实际 CLI 版本证据。在线 Bash 将向导放入后台，监听原先只检查标准输入／输出是否为 TTY，可能拒绝仍有控制终端的菜单进程。后续本地维护候选已为这些路径补充回归及修复，但未在上述主机重新验收。

后续发布后需分别运行 `tg2cloud --version`、重新打开 `tg2cloud` 核对当前工具版本，并在监听管理中登录。核对升级摘要中的 Bot 实际版本、已安装 CLI 版本、目标是否一致及离线命令检查；不能仅以“本地管理命令已安装”判为全部通过。保留原 Session 和数据库，不通过卸载重装排查登录问题。
