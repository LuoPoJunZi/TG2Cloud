# Linux Python + Bash 重构（v1.3.0）

本文描述 v1.3.0 的 Linux 模块化布局。Windows 部署器停留在 v1.2.1；历史版本、桌面恢复 ZIP、本地归档和用户数据保留。运行支持仍为 Debian/Ubuntu x86_64、rootful Docker；宿主 Python 3.10+，Bot 镜像 Python 3.12。ARM64 和其他 NAS 系统不因源码重排自动获得支持。

## 源码与职责

```text
install.sh / install-lan.sh / uninstall.sh
scripts/run_source.py
src/tg2cloud/
  cli/             参数、终端输入、确认与预览
  deployment/      配置、正式版本下载、身份、预检、安装/升级/卸载
    proxy/         HTTPS、证书、状态、备份维护与独立 LAN 网关
  domain/          状态、命名、错误分类与扫描结果
  telegram/        Telethon 装配、事件鉴权、命令、菜单和展示
  transfer/        任务服务、调度、下载、上传、流式、恢复与取消
  storage/         rclone、两后端提交策略与目的端验收
  persistence/     SQLite、事务内迁移、一致性备份与离线预检
  monitoring/      资源、进度与健康检查
packaging/         Dockerfile、两版 Compose、Shell 钩子、薄兼容入口
requirements/      bot.lock.txt / dev.lock.txt
```

包初始化不导入 Telethon、cryptg 或 psutil。CLI 不导入 Bot 运行层；安装、内网和卸载使用公共部署模块，不通过另一个入口复用业务。任务阶段沿用 MediaSource / Destination / UploadStream 和仓库接口；应用装配保留 `TransferService` 接口。取消/遗留清理规则原样迁出，核心与展示尚保留应用组合对象的窄接口，不宣称已实现完全无状态的任务服务器。

## 主要旧路径映射

下表新 Python 路径以 `src/tg2cloud/` 为基准。

| 原位置 | 当前位置 |
| --- | --- |
| `scripts/vps_installer.py` | `cli/{vps,terminal}.py`、`deployment/{configuration,releases,payload,instances,preflight,install,upgrade}.py` |
| `scripts/lan_installer.py`、`scripts/uninstaller.py` | `deployment/proxy/lan.py`、`deployment/uninstall.py` |
| `scripts/vps_runtime.py`、`scripts/lib/vps_resources.py` | `deployment/host.py`、`deployment/resources.py` |
| `scripts/lib/deployer_products.py` | `deployment/profiles.py` |
| `scripts/lib/domain_proxy.py`、`proxy_maintenance.py` | `deployment/proxy/{manager,state,certificates,maintenance}.py` |
| 旧 `app/main.py` | `app.py`、`telegram/{client,handlers}.py`、`transfer/`、`logging_setup.py` |
| 旧 `app/bot_commands.py` | `telegram/{commands,views}.py`、`transfer/actions.py` |
| 旧 `app/db.py`、`recovery.py`、`interfaces.py` | `persistence/{sqlite,migrations}.py`、`domain/{models,errors}.py`、`transfer/{recovery,ports}.py` |
| 旧 `app/rclone_client.py`、`verify_destination.py` | `storage/`（保留 CD2 临时提交和 OpenList 直接最终路径差异） |
| 两个 `payload_*/` 的 Docker/Compose/Shell | `packaging/Dockerfile`、`packaging/compose/`、`packaging/hooks/` |

旧实现经清单和无旧源码副本回归后，仅移动至维护者本地忽略的迁移归档。公共测试不从归档导入；历史兼容夹具从完整 Git 历史的固定公开提交读取，因此测试 checkout 应包含历史对象。

## 本地入口与依赖

在源码目录，或从其他工作目录使用绝对路径：

```bash
python3 /path/to/TG2Cloud/scripts/run_source.py install --help
python3 /path/to/TG2Cloud/scripts/run_source.py lan --help
python3 /path/to/TG2Cloud/scripts/run_source.py uninstall --help
bash /path/to/TG2Cloud/install.sh --edition clouddrive2 --check
```

`--help` 只依赖标准库；`--check` 仍检查本机身份并解析正式 Release，不等于纯离线或已部署。实际安装必须在受支持 Linux 上确认执行。本地入口不会安装未发布 payload：业务下载仍只选正式稳定 Release。

可选安装宿主 CLI：`python3 -m pip install --no-deps .`，之后使用 `tg2cloud install --help` 或 `python3 -m tg2cloud.cli install --help`。这不安装 Bot 依赖；容器单独使用 `requirements/bot.lock.txt`。开发环境使用 `python3 -m pip install -r requirements/dev.lock.txt`。两个锁文件从 pyproject 经其中固定的同一 uv 版本生成，解析下限取 Bot Dockerfile 的 Python 版本（当前为 3.12）：

```bash
python3 .github/scripts/lock_dependencies.py
python3 .github/scripts/prepare_bootstrap.py
python3 .github/scripts/build_payload.py --edition all --directory build/local-contexts
```

载荷输出必须是新路径。Docker 从生成的 `build/local-contexts/<edition>` 构建，不直接在 `packaging/` 构建。锁文件默认复用现有固定版本，只有明确升级依赖才使用 `--upgrade`；不单独手改两份清单。

## 已有实例和恢复边界

新代码部署为 `app/tg2cloud/`，外层 `app/` 保持不变；旧 `python -m app.healthcheck`、`app.deployment_check`、`app.backup_database` 等命令通过薄入口转发。两个 `/opt/tg2cloud-<edition>`、容器/网络、`.env`、rclone、`data/tg115.db`、`data/bot.session`、downloads、日志、网关及共享代理路径不变。不新增数据库结构变更、Session、环境变量，不重算旧预算。

旧版本按正式旧源码的实际清单验证。版本通过 AST 静态读取 `app/version.py` 或旧 `app/__init__.py`；支持历史 Windows CRLF。额外代码、缺失代码、未知结构或与正式基线不一致均停止覆盖；旧 TG115 不自动接管。保留候选构建、数据库快照、旧镜像标识、切换和失败回退顺序。

CloudDrive2 继续临时对象上传、大小检查、改名及最终复验；OpenList 继续预留最终路径并直接写入。旧 OpenList 临时对象和不确定 MOVE 保守停止，不新增“原子改名”承诺。流式保持有界缓冲和取消子进程回收，重新开始不是字节级断点续传。WebDAV 大小通过不等于云盘官方最终完成，也不是哈希校验。

## 递归指纹与发布门槛

新格式 `tg2cloud-code-v2:sha256:<摘要>` 递归覆盖 `app/` 的 Python 文件，按完整相对路径排序，部署和运行共用实现。同名子模块、添加、删除或修改均改变指纹。旧平铺包使用原无前缀算法；无标记的未知嵌套代码拒绝验证，指纹本身也不能绕过正式源码基线核对。

v1.3.0 的三个在线入口使用新布局清单和 `scripts/run_source.py`，固定辅助提交 A 为 `ee6feef5cfd35e50c315cddf91ab0cb35c40a384`。该提交已公开并通过主分支五个工作流；入口在后续提交 B 更新，辅助文件必须逐字匹配。业务代码仍只来自正式稳定 Release。今后更新必须：

1. 审阅新 helper、递归清单、载荷与历史兼容测试。
2. 经授权公开辅助代码提交 A，等待远端 CI。仅推送源码整理，不代表在线入口已切换到新助手。
3. 用 `python3 .github/scripts/prepare_bootstrap.py --directory build/bootstrap-candidate` 生成候选（保留当前 pin，不会自动切换）。将候选的清单和启动命令应用到入口提交 B，pin 指向已验证的 A，不能固定到 B 自身。
4. 核对 pin 内容与候选 Tag，执行 Docker/WebDAV 检查并明确实机未验收范围，得到发布授权后发布。不移动已有远端 Tag。

源码发布工具严格阻止旧清单或不匹配的 pin 混入新布局。离线测试在临时 Git 夹具验证 A/B、失效 pin 和旧清单拒绝；远端 CI、在线下载及实机部署必须分别记录结果。

下一版确定版本后，若版本源或辅助代码有变化，应先公开并验证对应的新辅助提交，再更新入口 pin；不要直接使用早期整理提交替代最终版本基线。仅推送 main 不会改变已有正式 Release。

## 验收范围

2026-10-17 已完成一次 CloudDrive2 测试实例到正式 v1.3.0 的授权人工迁移，用户确认升级后使用验收通过。保留历史任务、配置和 Session 授权，健康、递归指纹、HTTPS、只读 WebDAV 与官方入口复检均通过。原实例是与官方基线不一致的旧候选，不把本次操作写成标准自动升级；详细范围及未执行项见[验收记录](V130-ACCEPTANCE.md)。

统一 Python 检查、两个 Edition 组装/非 root 镜像、CLI 3.10/3.13、Bash/ShellCheck、网站测试应在不含旧源码、legacy 或私有资料的副本验证。Docker、Linux PTY、真实 Telegram、VPS 升级/回退和两后端网络操作缺少条件时单列未运行，不能用 Windows 模拟结果代替。生产恢复、卸载和云端删除不属于此重构的自动验收范围。
