# 开发与贡献

v1.4.3 已发布：辅助 A `cace622ffbbcecd28db7b00a29c26901e8fa139d`、入口 B／Tag `5aaf6a9b158d785ffa2fee52750c022fb8654810` 各五项 CI 与[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39901152742)全部通过，实际源码包、SHA256 清单与 GitHub 资产摘要核验通过。 隔离网络夹具补齐显式子网并保留原断言，不改生产网络。

当前源码 v1.4.4 待发布，开发使用 main 并记录提交；已发布 v1.4.3 的历史验证保留如下。业务数据库 schema 2 升级前须备份；后文的旧版 CI 和实机记录保留为历史事实。

以下保留 v1.4.2 及更早版本的历史发布证据，不外推为 v1.4.3 真实 VPS 验收。

历史 v1.4.2 辅助 A `840472f919409531e99da55c62070ea262ebed6d` 已通过五项 CI：[原生双架构与隔离 Docker](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39591006899)、[Python 3.10／3.13 四组检查](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39591011059)、仓库与两套文档检查。三个入口 B／Tag `42e2c372823a085c36a7a7597ce775441598aaf9` 固定 A，B 的五项 CI 与[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39592291162)亦全部通过，实际下载资产已核验；不把自动检查等同实机验收。

v1.4.1 辅助提交 A `3d222b90599f777d7646ff14ccebe466b25ad7eb` 与固定入口 B `dde550bc7fa6047ddcc945ef82131962611fec05` 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39525213331)全部成功，正式源码资产已下载核验。A 的[双架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524547503)及[四组 Python CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39524551589)记录可独立查看。NAT 修复与开发工具安全更新不改变 Bot 依赖、镜像、数据库或部署身份；真实 VPS／ACME／转存仍待用户验收。

发布后补充的[v1.4.1用户实机记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md)覆盖CloudDrive2／Ubuntu26.04.1／ARM64公网NAT的首装、本机HTTPS和WebDAV；自动检查、用户反馈与未执行场景分开记录，不补写OpenList、升级回退或外网手机通过。此次只更新文档，不改程序版本、helper pin、Tag或Release资产。

v1.4.0 辅助提交 A 为 `1480fd60ad94bd841961a4932a3b03e4cfde4414`，五项 CI 已通过，含原生 AMD64 / ARM64 Bot、网关、FUSE、扩展依赖及外部 DAV；[实际运行记录](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39424410971)。三个入口 B 使用本次递归清单并固定 A，B 的五项 CI 及[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39426176679)均通过，真实发布资产已下载校验。业务仍只取正式稳定 Release；Oracle／真实 VPS、用户网盘及手机验收仍由用户在发布后执行。

这里介绍 TG2Cloud 主项目的开发入口。本文档网站本身的维护方法见 [文档来源与维护](/reference/sources/)。

## 获取主项目源码

v1.4.3 的快照、命名预览等共用标准库模块，host helper 和 runtime 清单同步核验；原生 Nginx 生命周期沿用显式 CI 开关。A 先公开验证、B 再固定 A；没有自指 pin，不把隔离验证扩大为真实 ACME。用法见[维护增强](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/MAINTENANCE-IMPROVEMENTS.md)。

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout main
git rev-parse HEAD
```

本次候选源码使用 main；正式发布后使用不可变 v1.4.4 Tag，下载见[下载页](/download/)。开发使用 main 并记录提交号，不把后续修改当作 Release 行为。

## 关键目录与入口

下表为 v1.4.2 继续沿用的 Linux / Python + Bash 结构；复现正式版本使用对应不可变 Tag。桌面源码及专用测试仅在历史版本和本地恢复备份中保留，完整回归不需要 Qt、Paramiko 或 PyInstaller。

v1.3.1 沿用该结构，独立附加功能在 `src/tg2cloud/addons/external_webdav/`，专用入口为 `install-webdav.sh`。源码包已正式发布；下载、构建或发布成功都不等于实机安装通过。

| 路径 | 用途 |
| --- | --- |
| `src/tg2cloud/deployment/profiles.py` | 两 Edition 的标识、路径和载荷清单 |
| `src/tg2cloud/version.py` | Bot、包和脚本唯一版本源；Windows 冻结在 v1.2.1 |
| `src/tg2cloud/deployment/proxy/` | HTTPS、证书、状态、私密备份与 LAN 网关 |
| `src/tg2cloud/deployment/resources.py` | 资源探测、磁盘推荐与容量校验 |
| `scripts/run_source.py`、`src/tg2cloud/cli/` | 标准库宿主 CLI、终端、参数与三个公开 Shell 入口 |
| `src/tg2cloud/transfer/`、`storage/`、`persistence/` | 共享任务核心、两后端提交策略、SQLite 与备份 |
| `packaging/Dockerfile`、`packaging/compose/` | 共享 Bot 镜像与两 Edition 编排 |
| `packaging/hooks/`、`packaging/compat/app/` | 安装/管理钩子和旧运行命令的薄兼容入口 |
| `pyproject.toml`、`requirements/` | 依赖分组与统一 uv 工具生成的两份哈希锁文件 |
| `tests/` | 自动化回归 |
| `.github/CONTRIBUTING.md`、`.github/SECURITY.md` | 贡献规范、安全政策和公共 CI 规则 |

## 执行自动测试

开发当前 main 时先切回分支，再按贡献指南检查；不要把历史 Tag 和 main 的命令混用：

```bash
git switch main
python -m pip install -r requirements/dev.lock.txt
python .github/scripts/check_python.py all
python scripts/run_source.py install --help
python scripts/run_source.py lan --help
python scripts/run_source.py uninstall --help
```

真实本地 WebDAV 集成测试需要 `rclone` 在 PATH 中；Shell 回归需要 Bash。缺少依赖时的跳过不能写成“所有集成测试均通过”。

公共 CI 仅维护 Linux：Bot 使用 Python 3.12，宿主标准库 CLI 使用 3.10 / 3.13。不在新 CI 构建 Windows；历史 EXE 仍可下载。测试需完整 Git 历史以读取固定公开旧版本夹具，不依赖本地归档。

新 Docker 上下文由 `python .github/scripts/build_payload.py --edition all --directory build/local-contexts` 组装，不直接在 packaging 目录构建。部署后仍保留外层 `app/`、`data/tg115.db`、`data/bot.session` 和旧 `app.*` 维护命令。递归指纹使用显式 v2 协议；不确定的旧代码拒绝自动覆盖。

v1.3.0 在线 helper 已切换新布局，固定到已公开且通过 CI 的提交 `ee6feef5cfd35e50c315cddf91ab0cb35c40a384`。后续升级仍须先公开辅助提交 A 并通过 CI，再在入口提交 B 更新清单和 pin；不能改成 moving main。CloudDrive2 本次人工迁移及用户验收记录与自动测试分开，完整步骤见[重构与兼容说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LINUX-REFACTOR.md)和[验收范围](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。

v1.3.1 辅助提交 A 为 `90648bf0878958b976541f660df69fcb24ea807f`，已通过 Linux/Docker 和宿主 Python 3.10/3.13 CI；三个入口在 B 更新递归清单并固定 A。附加功能使用正式源码资产和 SHA256，不复用历史 v1.3.0 helper 维护 schema 2。

v1.3.2 辅助提交 A 为 `1879a8e1c498fbabaf7ba26ba4b9810f1cfd44e6`，已通过五个公开 CI；三个入口 B 的清单包含中文管理模块和宿主运行包，逐文件匹配 A。新增 `tg2cloud` 菜单不改变业务稳定 Release 选择或实例数据位置，不能用旧 helper 覆盖新布局。

v1.3.3 辅助提交 A 为 `ea43d845b7f4c7185166a7474ef30e44ba2af8df`，已通过同样五个公开 CI；三个入口 B 同步家庭授权与附加账号模块清单并逐文件匹配 A。临时测试夹具不要求 root，但生产认证文件仍强制受管属主和读取权限，改属主失败保留旧认证文件。业务来源仍为正式稳定 Release，不代表真实 Telegram、网关或 VPS 验收。

v1.3.4 辅助提交 A 为 `72be98e6b15075f71c58dd6ee110e47db2f42ce0`，辅助 A 与固定入口 B 各五项公开 CI、[同标签发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39204327020)均已通过；三个入口 pin 严格匹配 A，不使用 moving main。正式标签 commit 为 `ef35d133a9e25572ff5f8363819d5c8e8984e74c`，实际源码包、SHA256 与 GitHub digest 已核验；本版真实 VPS、Telegram 和用户网关验收尚未执行。工作流记录见[重构与兼容说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LINUX-REFACTOR.md#递归指纹与发布门槛)。

v1.1.1 至 v1.2.1 的 Release 等待同一不可变标签的 Linux 验证与 Windows 构建全部成功。历史 EXE 和对应 SHA256 保留，不由新工作流重写。

v1.1.2 进一步核对 Tag、共享版本源、Windows 版本资源、CHANGELOG 和 Release Notes 的一致性；维护助手与备份对话框纳入打包自检。已有 Release 不会被新运行覆盖，本地 EXE 的校验值不作为 Actions 产物校验值。

v1.3.0 停止分支和 Release 自动构建 EXE。Linux 验证保留 Shell、Docker 配置、两 Edition 候选镜像和本地 WebDAV；源码包在验证任务生成一次，发布任务复用同一 artifact 并核对 SHA256。三个在线入口的辅助代码固定 commit 必须与本版辅助代码一致，发布检查拒绝旧向导混入新版本。

v1.1.4 另有真实 Docker 候选启动检查：Linux 分支与 Release Job 显式启用 `TG2CLOUD_TEST_DOCKER=1`，以 UID 10001 验证两 Edition 的公开源码权限及候选配置，不连接 Telegram/云存储。默认离线测试跳过这一用例，不等于镜像验收通过。

v1.1.5 的独立 VPS 脚本 CI 使用真实 Python 3.10/3.13，覆盖标准库维护兼容和终端凭据隐私；共享 HTTPS 增加中断、重复取消及提交一致性回归。这些自动检查不替代真实 VPS 中断/续做或完整转存验收。

## 恢复 v1.2.1 历史部署器构建

请使用 v1.2.1 Tag 或独立本地源码备份，在新目录校验后构建。main 不再包含桌面入口、构建资源或专用测试；共享模块继续用于 Linux 向导。不要在较新版本上更新 Windows 资源再构建旧部署器。

```powershell
git checkout v1.2.1
.\build.ps1 -Edition All
```

公共行为和版本号变更应同时检查两个产品入口及产品定义。不要只构建一个 Edition，就认为另一个必然不受影响。

## 提交规范

不提交账号、Token、密码、Cookie、私钥、用户 ID、服务器地址、下载文件、日志、数据库、缓存或本地配置。

涉及安装脚本、远程命令、路径处理时，补充异常输入与恶意输入测试。变更传输策略时，同时保护 CloudDrive2 与 OpenList 的不同落盘语义。

不要把 WebDAV 接收成功改写成云盘官方最终完成，也不要把模拟测试当作真实 VPS 端到端验收。

## 截图与文档

只提交实际界面的脱敏截图，注明版本与 Edition。本次文档首页展示的是 HTML/CSS 流程示意，不是伪造的部署器运行截图。
