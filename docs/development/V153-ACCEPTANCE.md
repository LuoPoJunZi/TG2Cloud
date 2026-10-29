# v1.5.3 发布与兼容记录

状态：2026-10-29，v1.5.3 已正式发布。入口 B、文档提交、同标签原生双架构与镜像／Compose 发布流程通过，实际下载资产已核验。真实用户 VPS、DNS／ACME、Telegram 与两种网关转存尚未执行；发布成功不等于实机验收。

## 本次范围

- 全新安装统一创建 `data/tg2cloud.db`，同一规则用于一键脚本与 Compose；不存在另一套 Bot 核心。
- 已有实例如果只有 `data/tg115.db`，继续使用该数据库，不移动、清空或重建。Telegram `bot.session`、个人监听 Session、任务、网关账号和下载目录保持不变。
- 若两个业务数据库并存，或发现链接、硬链接、无主 SQLite 旁文件，停止并要求核对；不会自动合并、覆盖或选择一个空库。
- 新配置只输出 TG2Cloud 项目变量，旧 `TG115_*` 只用于兼容读取、旧实例识别与隔离；上游许可证和致谢保留。
- 两版 Shell 升级、数据库快照和失败回退使用实际选中的数据库名称；旧配置／程序备份保留。
- 可选 Compose HTTPS：初始化只保存访问计划，宿主 `https.sh` 复用共享 Nginx／Certbot；其他项目的代理只导出候选配置。

## 两种部署互不接管

公网和内网一键脚本保持原入口和安装流程，不新增 Compose 的访问方式选择。

Compose 使用自己的初始化标记、容器标签和部署目录；一键升级／卸载拒绝接管 Compose。新增 HTTPS 使用独立路由归属清单，通用写入端、整体迁移和卸载都检查依赖，保留另一 Edition 和外部只读入口的路由、证书与数据。

同一主机同一 Edition 不能重复占用固定容器名和网关端口。不能同时运行两个使用相同 Bot Token 的实例；独立部署不表示允许它们冲突运行。

## 数据库、备份与回退

本轮不变更业务 schema 3，不做文件重命名迁移，不增加数据库路径环境变量。

备份和隔离恢复支持新旧两种文件名，但一份实例必须有且只有一个业务数据库。现有备份继续可读，恢复工具不连接 Telegram 或网关，不自动覆盖生产数据。业务备份不包含下载暂存和共享 HTTPS；代理证书备份单独处理。

旧实例保留旧文件名，可以按原有失败回退流程恢复匹配的数据库、程序和配置。全新 v1.5.3 实例使用新文件名，旧版本不一定识别；不得直接切换到旧镜像并让其创建空库。若确需降级，应停机保护现场，在隔离目录按旧版本实际布局验证一致性备份与 Session，确认后再人工规划切换。

不手动改名运行中的 SQLite 主文件，不删除 `-wal`、`-shm` 或 `-journal`；这些文件可能包含尚未合并的数据。

## 自动检查与发布门槛

2026-10-29 最终本地结果：

| 检查 | 实际结果 |
| --- | --- |
| `python -B .github/scripts/check_python.py all` | 退出 0；1508 项，1473 通过、35 条件跳过、0 失败；Ruff 和 compileall 通过。 |
| 裸 Python 3.10：`python -B .github/scripts/check_python.py test --scope cli` | 43 组共 845 项，833 通过、12 平台条件跳过、0 失败。 |
| 新命名专用回归 | 13 项纳入全量检查；含两 Edition 新旧数据库、无主旁文件、链接、备份／隔离恢复、实际 Bash 代码的快照与回退。 |
| Bash 语法与 ShellCheck | 两一键入口、HTTPS 入口及全部部署钩子通过。 |
| Bandit | 全部受检源码通过；原有 `nosec` 注释提示不表示新增失败。 |
| 网站 | `npm run build`、37 项测试通过；35 页、4638 个本地链接／资源／锚点检查通过。 |
| 版本、发布文案、源码清单及仓库检查 | 通过；`git diff --check` 通过。 |
| 干净公共副本 | 不含 legacy、私有记录或本地配置，Python 3.10 标准库可生成两 Edition 包并打开 HTTPS 帮助；新路径模块包含在宿主 helper 中。 |

本地测试使用临时目录、合成任务和模拟 Docker；平台条件跳过不计为通过。远端原生 Linux CI 另执行隔离 Docker、回环 WebDAV、两版网关／FUSE 及 Nginx 验证；没有连接用户 VPS、Telegram 或真实网盘。长期续期、真实公网 ACME、NAS 与生产恢复尚未验收。

## 实际发布链与资产核验

- 辅助 A：`9dbae452c81c170fe74e03a4a52afecb6e60d721`，67 个宿主 helper；A 的过渡版本校验失败原因及 B 的修复保留在下方。
- 入口 B：`b098fb6d36cc39a7dcd555ce8faafbb23a4385c9`，固定真实 A；所有 helper 与 A 的换行正规化内容一致，B 五项 CI 全部通过。
- 随包教程提交与正式 Tag：`2e6f06f09e1e2ac9fe8ae2d9c6e1d83cc7a3bee1`。只补同步 v1.5.3 下载说明、完整 HTTPS 文件与旧锚点，三个文档／仓库检查通过，不修改 B 的业务或 helper。
- [同标签源码发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40844895202)通过两个原生 Linux 平台检查，生成一次源码包并复用校验后的 artifact。[共享镜像与两版部署包](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40845397585)按同一 Tag 构建，匿名拉取及非 root 初始化检查通过。
- 下载五份真实资产：SHA256 同清单及 GitHub 资产 digest 一致；源码文件逐项对应 Tag 的 `git archive`，两版部署包完整内容逐字节对应 Tag 生成器。没有覆盖旧版资产或修改历史 Tag。
- 两版部署包均为 format 2，提供 `https.sh` 和带摘要的离线 helper；固定同一真实镜像 index。各原生子镜像的架构、版本和源码 revision 均核验。

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| `COMPOSE-SHA256SUMS.txt` | 215 | `08e1efeac5c6b94bf8d2e54b66c2b5649b70954c046ff90bc0bddf1da943f2a0` |
| `SHA256SUMS.txt` | 96 | `f335d1b90df4fbe1ee9475f609cdcc9df2ec10eb639b95e082957b24f50ae2d0` |
| `TG2Cloud-v1.5.3-compose-clouddrive2.tar.gz` | 239927 | `a1cd4baad71fb9eb941617fda1874acee5742b03009dc720c3e33a0f02be9450` |
| `TG2Cloud-v1.5.3-compose-openlist.tar.gz` | 239742 | `6cebeb8e84ece45566fc523dc5ebf03b20f2b3180b516c2362f7c388ada69f65` |
| `TG2Cloud-v1.5.3-source.tar.gz` | 3979513 | `46232fe261ba2c13ff076c4f0c69d9e173c30f28fafd8d27f47b670e88d67b68` |

镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:21b1da6d84cfccfebe4fc0dd88a0cfe3edd730e33dca241639834e1fb8e5dc44`。

- `linux/amd64`：`sha256:9e46fd31750e986326d4a40dc74a518d9aac3356d2b38f023b9eeea0d505b0ad`。
- `linux/arm64`：`sha256:c6ffc43a829a0181df8808f977e8071a6506cac75868e26ed84e12c118eeb9b3`。

远端分支只保留 main；正式 [v1.5.3 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.5.3) 已发布。在线公网／内网入口固定辅助 A，业务仍从正式稳定 Release 解析不可变提交，不下载 moving main 业务代码。

## 发布后人工验收

- 两 Edition 分别验证一键新安装、保留配置升级、Bot 与 CLI 版本一致；既有任务和 Session 不丢失。
- 新安装出现 `tg2cloud.db`；旧实例仍打开原库，不生成第二个业务数据库。
- 验证手动转存、监听、家庭用户管理、配额、取消与重启恢复。
- 分别验证 Compose 默认内网方案、自动 HTTPS 和已有代理候选导出；确认没有 Docker Socket 挂入初始化容器。
- 验证另一 Edition 及外部 WebDAV 路由保留、证书续期演练、代理备份和停止业务后的安全移除。
- 在隔离目录验证两种数据库文件名的备份和恢复；不要通过生产数据库恢复测试回退。

操作指南：[Compose](../COMPOSE.md)、[一键脚本](../VPS-INSTALL.md)、[备份恢复](../BACKUP-RESTORE.md)。

## 辅助 A 与入口 B

辅助代码 A：`9dbae452c81c170fe74e03a4a52afecb6e60d721`，已公开至 main；不创建额外远端分支。A 保持线上入口的旧版本标识与旧 pin，以免切换未发布入口。宿主 CLI 四组及文档／仓库／网站检查通过；双架构完整回归各有 4 项版本元数据错误，原因是入口标识仍为 1.5.2，而源码为 1.5.3。该过渡状态不用于正式 Tag。

入口 B 已将两个入口固定到真实 A，清单扩展为 67 个 helper，并同步 installer_version 为 1.5.3。所有 helper 文件与 A 逐字节（换行正规化）相同；版本元数据回归已在本地通过。没有降低校验门槛；B 的完整 CI 全部通过后创建正式 Tag，最终结果见上方发布链。

A 的实际执行：[完整回归](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820012181)、[宿主 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820012227)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820012195)。A 的失败记录按原样保留，不记为通过。

入口 B：`b098fb6d36cc39a7dcd555ce8faafbb23a4385c9`。版本元数据回归修复后，[完整双架构 CI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820413412)、[宿主 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820413413)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820413382)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820413422)和[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40820413432)五项全部通过，包含原生 Docker／隔离 WebDAV 与 Nginx 测试；不等于真实用户 VPS 或网关验收。

正式 Tag 前已同步随 Compose 包分发的教程：下载命令对应 v1.5.3、列出完整 HTTPS 工具，并保留旧锚点；业务 helper 和 Docker 配置不变。实际 Tag／资产结果见上方记录。
