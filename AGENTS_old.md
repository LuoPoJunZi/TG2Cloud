# TG115 Agent Guide

本文件适用于整个仓库。开始开发前，先完整阅读
`.codex/PROJECT_MEMORY.md`，再阅读与任务直接相关的源码、测试和文档。项目记忆是导航，
源码和测试才是最终事实来源；如果两者不一致，先按源码核实，再更新记忆。

## 协作方式

- 默认使用中文沟通、写项目说明和面向用户的提示；代码标识符沿用英文。
- 先检查 `git status --short --branch`，不得覆盖或回退用户已有改动。
- 修改应小步、聚焦，并优先补充或更新对应的 `unittest` 回归测试。
- 不要把真实 VPS 地址、账号、密码、SSH 私钥、Bot Token、API Hash、Telegram ID、
  WebDAV 凭据、115 登录信息、文件名、聊天内容、日志、数据库或会话文件写入仓库。
- 除非任务明确要求，不要改动已锁定的镜像摘要、依赖版本、部署权限或产品语义。

## 项目结构

- `installer.py`：两个 Windows PySide6 产品共用的界面与部署后端，负责校验配置、SSH/SFTP
  部署、SSH 隧道、产品管理和 WebDAV 验收。
- `installer_clouddrive2.py`、`installer_openlist.py`：两个对称的产品入口；共用界面和部署
  后端仍由 `installer.py` 提供。
- `vps_resources.py`：VPS 只读资源探测、严格结果解析、实例级存储建议和部署容量校验。
- `payload_clouddrive2/app/main.py`：Bot、命令、任务调度以及普通/流式传输的核心状态机。
- `payload_clouddrive2/app/db.py`：SQLite 持久化、去重、原子额度预留、确认和崩溃恢复。
- `payload_clouddrive2/app/rclone_client.py`：WebDAV 的 rclone 适配层。
- `payload_clouddrive2/app/resources.py`：资源采样和动态并发窗口。
- `payload_clouddrive2/app/states.py`：集中状态文案、失败状态和本地额度归属。
- `payload_clouddrive2/app/interfaces.py`：媒体来源、目的端与上传流的可注入接口。
- `payload_clouddrive2/app/deployment_check.py`：配置预检及运行环境／代码指纹核验。
- `payload_clouddrive2/app/config.py`：服务端环境变量解析和校验。
- `payload_clouddrive2/remote_install.sh`、`payload_clouddrive2/repair_clouddrive_network.sh`、
  `payload_clouddrive2/manage.sh`、`payload_clouddrive2/backup_retention.sh`、
  `payload_clouddrive2/docker-compose.yml`：VPS 安装、
  备份盘点／显式保留和日常运维。
- `tests/test_core.py`、`tests/test_scenarios.py`：单元与端到端模拟回归基线。
- `tests/test_optimizations.py`、`tests/test_deployment.py`、`tests/test_webdav_integration.py`：
  优化故障回归、Bash 部署模拟和真实本地 WebDAV 集成测试。后两类需要 Bash、rclone；
  缺失时测试会明确跳过，不能把跳过表述为通过。

## 不可破坏的不变量

1. 项目只验证 CloudDrive2 WebDAV 已接收且大小正确；不得把它表述为 115 官方端已完成。
   `completed` 与用户人工执行 `/confirm` 后的 `confirmed` 必须保持分离。
2. 普通文件必须受本地任务预算和真实磁盘安全线约束；单文件超过预算时使用流式模式，
   流式任务不得按完整大小计入本地任务预算。
3. 下载完成时先持久化确定的最终本地路径，再执行原子改名；远端校验成功后先持久化
   `cleanup_pending`，再删除本地副本。这两个顺序用于崩溃恢复，不得颠倒。
4. `/cancel` 必须先安全删除并复查本任务远端文件，再删除本地副本并标记 `cancelled`；
   无法确认远端清理时应失败关闭并保留本地数据。
5. 远端先写 `.uploading-*` 临时名，大小校验成功后才改成不冲突的正式名，并再次校验。
6. 修改任务状态或迁移时，同时核对 `STATE_LABELS`、`LOCAL_STATES`、`GROWING_STATES`、
   数据库查询/迁移、调度、重试、取消、恢复、通知和测试。
7. 队列额度预留必须保持原子性；分页扫描要继续允许后方小文件越过暂时受阻的大文件，
   避免饥饿。
8. Bot 容器应保持非 root、只读根文件系统、丢弃 capabilities 和
   `no-new-privileges`。CloudDrive2 的特权/FUSE 配置是明确的第三方高权限边界。
9. 安装目录和远程命令必须继续使用严格校验及安全引用；涉及它们的改动要覆盖恶意输入、
   异常退出和清理失败测试。

## 跨文件同步规则

- 新增或修改配置：同步检查 `installer.py`、两个产品入口的界面、校验和配置生成，
  `payload_clouddrive2/app/config.py`、Compose/脚本、文档及测试。
- 新增 payload 文件：同步检查 `build.ps1` 打包、部署复制逻辑和 EXE 自检文件清单。
- 修改版本：至少同步两个产品配置、`installer.py::APP_VERSION`、
  `payload_clouddrive2/app/__init__.py::__version__`、
  README、CHANGELOG、RELEASE_NOTES 和版本一致性测试。
- 修改用户状态文案或命令：同步 README、小白说明、帮助文本和状态文本测试。
- Shell 文件必须保持 LF；PowerShell/CMD 文件保持 CRLF，遵循 `.gitattributes`。

## 验证基线

至少先运行与改动直接相关的测试。完整 Python 回归命令为：

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

提交前按改动范围追加：

```powershell
uv run --with ruff==0.16.0 ruff check installer.py installer_clouddrive2.py installer_openlist.py deployer_products.py vps_resources.py payload_clouddrive2/app tests
uv run --with bandit==1.9.4 bandit -q -r payload_clouddrive2/app installer.py installer_clouddrive2.py installer_openlist.py deployer_products.py vps_resources.py
uv run --with pip-audit==2.10.1 pip-audit -r payload_clouddrive2/requirements.txt
uv run --with pip-audit==2.10.1 pip-audit -r requirements-build.txt
```

改 Bash/Compose/Docker 时还需执行 ShellCheck、`docker compose config --quiet` 和镜像构建；
改部署器或 payload 交付结构时还需运行 `build.ps1 -Edition All`，并分别执行 CloudDrive2、
OpenList 两个成品的 `--self-test`。

## 维护项目记忆

完成会改变架构、状态机、配置、部署方式、外部边界、测试基线或已知问题的实质改动后，
同步更新 `.codex/PROJECT_MEMORY.md` 的日期、基线提交（如已提交）、决策和待办。不要在记忆
文件中写入秘密、运行数据或未经验证的猜测。
