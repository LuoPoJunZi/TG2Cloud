# v1.5.2 发布与验收

## 当前状态

2026-10-28，正式 v1.5.2 源码 Release 已发布，同标签双架构与实际源码资产核验通过。Compose 两架构镜像与两 Edition 部署包也已发布、下载核验；首次发布的清单兼容问题已按用户授权修复，保留完整过程记录。未连接真实 VPS、Telegram 或用户网盘。

## 本版范围

- 监听连接／身份查询超时、临时故障退避恢复、授权状态复核、断开客户端替换；失效授权继续停用。
- 历史维护分批事务及三个幂等索引，schema 保持 3，保留原期限、pending 和引用保护。
- 直接 Compose 部署：复用网关模板、共享 Bot 镜像、初始化／检查／凭据与离线备份；明确 root 读取私有配置。第一版适合内网或已有 HTTPS 代理，不接管脚本实例。
- 原正式 v1.5.1 基线提交为 `2741c6b5f40469a2bc035c87274b62fc66ef1a74`，两 Edition 载荷摘要由本地不可变 Git 对象生成并纳入兼容白名单。
- 保留历史文档、许可、旧入口兼容、配置、Session、任务及网关上传策略；不操作真实云端文件。

## 本地检查

开发阶段完整检查 1424 项，1389 通过、35 条件跳过、0 失败；随后补充注册表错误分类回归，最终 Compose 单独 20 项和 Python 3.10 标准库 20 项通过。网站 37 项、35 HTML／4544 引用检查通过；Ruff、compileall、Bandit、源码清单和 YAML／Bash 语法完成。版本同步后的最终检查单独追加，不以开发阶段结果代替。

本机没有 Docker。新增直接 Compose 测试只在明确启用的原生 CI 上执行，包含初始化、私有配置、两 Edition 非 root 访问；非 root Runner 读取 root/600 配置时使用 sudo，生产权限不放宽。公共 CI 会重新测试最终提交。

## A/B 与发布门槛

先产生真实辅助提交 A，等待对应 CI 通过，再在入口 B 固定 A；入口不自指。当前有效 helper pin 保留到 A 公开验证完成，不填写候选／伪造 SHA。主分支及最终 Tag 验证后发布源码，再从相同正式 Tag 运行 Compose images and bundles。

Compose 镜像公开可见性与匿名访问须通过；既有版本 index 或资产不覆盖，已存在时必须匹配提交及字节。正式源码资产仍是原源码归档和 SHA256SUMS.txt，Compose 另附两部署包及 COMPOSE-SHA256SUMS.txt。

## 发布后人工验收

1. 用所选 Edition 的固定版本入口先 `--check`，确认原配置、数据、Session 和代理模式，备份后升级；退出重开菜单，核对 Bot／CLI 1.5.2。
2. 单独运行业务就绪、WebDAV 验收及一个真实小文件转存；检查远端大小与本地清理，不把 WebDAV 接收当成官方云端最终入库。
3. 在独立测试实例模拟临时网络故障，观察重试等待和恢复，确认手动停用优先；授权失效必须停用，不发送密码／Session 或原始异常日志。
4. 在隔离副本核对历史维护保留规则、积压分批处理和失败回滚；不直接操作生产数据库。
5. 两种原生平台分别运行正式 Compose 包，root 初始化、创建网关专用账号、非 root Bot、内网或已有代理访问、小文件上传、停机备份及隔离恢复。不要同时启动相同 Bot Token。
6. 升级失败先停止新实例，保留日志和备份；恢复须匹配代码、数据库与 Session，保留 downloads，不能只回退镜像。共享 HTTPS 由原模式独立维护。

以上人工项目尚未执行。公开日志需脱敏，不上传 .env、数据库、Session、Token、密码或完整主机信息。实际 CI 与资产核验完成后按阶段追加真实链接和摘要。


## 版本同步后的本地验证

1.5.2 最终候选完整检查 1425 项：1390 通过、35 因既有平台／工具和显式 Docker 条件跳过、0 失败；仓库文件、Ruff、compileall 通过。Python 3.10 无第三方依赖检查 42 项通过；网站 37 项、35 HTML 与4548本地引用通过；Bash／ShellCheck、发布文档及 Bandit 完成，未关闭检查规则。Bandit 存在注释解析提示，没有安全发现。

网站版本同步最初因缺少待发布标识与历史验收链接出现 6 项文档失败，补齐实际说明后 37 项通过；没有降低测试。原生 Compose CI 临时服务以 sudo 读取 root/600 配置，保持生产保护。真实 Docker、远端 CI 与发布资产结果仍待后续阶段追加。


## 首轮辅助 A 与受限修复

首轮 A 为 `6d7870d92a0ac94ff75adcae188f7571178597df`；仓库、文档、网站和 CLI 检查通过。Linux ARM64 完整测试及隔离 Docker 通过，AMD64 在两项监听通知竞争测试失败，尚未进入其 Docker 步骤，不将整轮记为通过。

已用模拟系统单调时钟 10 秒复现：首次通知计时器原值为 0，系统启动不足 60 秒时首条通知被误抑制。用户明确授权限定修复；改为显式未通知状态，首条登记允许通知，后续仍保留原 60 秒限流。新增短运行时间回归，不删除／跳过原测试。修复后的 A 将重新执行五项 CI，通过后再固定入口。


## 修复后的辅助 A 验证

辅助 A 为 `fa91d616ed03b1ad3f8d8442e92d2d803487ac90`；五项CI全部通过：[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40660713080)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40660718410)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40660723550)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40660729120)、[Linux](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40660733578)。含两原生平台实际Compose初始化、非root访问、网关/FUSE和代理检查；真实VPS/账号不据此认作通过。入口B只固定此已验证A，main/Tag和资产核验仍待追加。


## 入口 B、正式源码及在线入口核验

- 入口 B／Tag：`dc02d879cc44ee6bbf1f858ea383ede2ea71022b`；固定已验证辅助 A `fa91d616ed03b1ad3f8d8442e92d2d803487ac90`，不自指。
- B 的五项 CI 全部通过：[Linux](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40661760358)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40661760418)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40661760424)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40661760326)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40661760489)。两原生架构各运行完整 1426 项回归，1415 通过、11 条件跳过；显式 Docker 集成检查另行通过。
- [同标签正式发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40662297206)两架构通过；[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.5.2)为非草稿、非预发布。
- 实际下载源码包 3906109 字节；SHA256：`29ac52d30141610a7f0ef632239317902e3f3e1abcb3aa067aa4bf62d8be13fc`。与清单及 GitHub 资产 digest 一致，390 个文件逐字节匹配 Tag 的 Linux LF 内容；本机 Git CRLF 转换不作为源码差异。
- main 的两个实际在线入口与 Tag 内容一致，均固定上述 A。真实安装、Telegram 与网关转存不据此认作已通过。

## Compose 首次发布结果

[首次镜像发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40684041192)的 AMD64、ARM64 构建、两 Edition 隔离初始化及非 root 检查通过，提交专用镜像推送成功。版本清单匿名可见且包含两平台，但 Docker manifest list 不保留 index 注解，工具按原规则拒绝后续部署包发布。没有覆盖版本镜像、修改 Tag 或跳过身份检查；后续处理须核验两子镜像 digest 和各自提交身份，不以成功构建代替完整发布。


## 限定发布工具修复

用户明确授权限定修复。Docker v2 manifest list 不保留 OCI index 注解，因此发布工具同时复核两项实际 digest、平台、版本及子镜像配置中的提交标签；缺注解不再单独阻断，身份不符仍拒绝，不通过放宽覆盖规则解决。已有正确镜像只复用，不重新构建或改写版本清单。

工作流的维护工具另固定到触发时的不可变提交 `github.sha`；两平台业务源码、部署包和原有两个源码资产继续来自原 v1.5.2 Tag。关联单元测试 25 项及 Python 3.10 标准库回归通过，完整回归、修复提交的 CI 和最终资产结果另行追加。

只读匿名核验得到版本清单 digest `sha256:45f951b114374b62fbc79e1a70d792005755c4b326609c9bef4f7747ddadba1c`；AMD64 子镜像为 `sha256:1a79f9f42ab66d1f5a50f660ca025b8c1782a25de64766a4bfc170eddf2390f3`，ARM64 为 `sha256:7bd42de664c4b9b8e873b729bf02be4c971020b6533cacdbab94695ab97d9f79`。两配置的版本均为 1.5.2、提交均匹配 B／Tag；没有凭此宣称真实用户部署通过。


## 最终发布完成

发布工具固定提交为 `34b3c7268d3268f91b6b9c00bfa353d1c0d99ec4`；[双架构完整 CI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40686570620)、[CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40686570581)及[仓库检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40686570559)全部通过。这次只改发布工具、对应工作流及测试，业务 Tag、原镜像和源码包均未改写。

[最终 Compose 发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40687059238)通过：prepare 与 publish 成功，native-images 因复用已验证的原有两平台镜像而跳过；它不是第二次构建验收。首次运行的两平台构建及隔离测试已分别通过，两个子镜像的配置身份和 digest 在本次认证／匿名检查中再次核验。

正式 Release 现有五项资产：原源码包与 SHA256SUMS.txt，另加两份 Compose 部署包与 COMPOSE-SHA256SUMS.txt。没有替换原资产，实际新增包如下：

| Edition | 大小（字节） | 实际包 SHA256 |
| --- | --- | --- |
| CloudDrive2 | 7090 | `f5ca601f496cfb921d23f7ff527c0e358185ac159f11e274309ecdcc6be275a6` |
| OpenList | 7045 | `3039371ed32d8d0728d5de8ef6a2ec0671c31081bda3f25fc7a36f1d4c38b5a2` |

实际下载包与独立校验清单、GitHub 资产 digest 一致；每包五个文件均匹配原 Tag 对应生成内容，包括原 Tag 的 README 和 LICENSE。元数据均为 1.5.2、业务提交 B，两包固定同一个实际多架构镜像 digest `sha256:45f951b114374b62fbc79e1a70d792005755c4b326609c9bef4f7747ddadba1c`。没有混入发布后的文档或工具改动。

发布工具修复后的本地完整检查为 1431 项：1395 通过、36 条件跳过、0 失败，Ruff 与 compileall 通过。其中一项因本次终端未配置 Git Bash 而跳过，补设现有 TG115_TEST_BASH 后单独通过；其他既有平台／工具／Docker 条件仍按真实结果记录。关联 25 项在本地 Python 3.13 与无第三方依赖的 Python 3.10 下均通过；Bandit、工作流 YAML／Bash 检查通过。最终文档同步后，网站 37 项测试、35 个 HTML、4548 个本地链接／资源／锚点及 305 条搜索项均通过，仓库索引和发布说明检查通过。

**未执行项不变：真实 VPS／NAS 安装升级、真实 Telegram、两网关实际转存、长期吞吐和生产恢复；CI、镜像匿名可读和资产校验均不替代这些验收。** 使用步骤见[Compose 指南](../COMPOSE.md)，原脚本实例继续用[VPS](../VPS-INSTALL.md)或[内网](../LAN-INSTALL.md)入口，不自动迁移。
