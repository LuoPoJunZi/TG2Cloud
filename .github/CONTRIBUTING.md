# 参与贡献

1. 不得提交任何真实账号、Token、密码、Cookie、私钥、个人 ID、文件名或服务器地址；
2. 修改代码后运行全部自动化测试；
3. 涉及安装脚本、远程命令或路径处理时，必须同时补充异常和恶意输入测试；
4. 不要把 CloudDrive2 WebDAV 接收误写成 115 官方端已经完成；
5. 不要提交构建目录、缓存、日志、数据库、下载文件或本地配置。

仓库职责、文档同步和本地产物处理见 [仓库维护规范](../docs/development/REPOSITORY.md)，用户文档入口见 [文档目录](../docs/README.md)。不为了统一目录修改稳定核心或公开安装脚本路径。

## 产品宗旨与交互原则

TG2Cloud 的宗旨是方便用户使用。常用功能优先通过清晰的菜单、按钮和逐项文字交互完成，让用户专注于要保存什么、保存到哪里，而不必学习内部规则结构或记忆命令。

- 优先完善现有 Telegram Bot 与 `tg2cloud` 菜单；能选择的内容提供按钮或选项，只让用户输入确实需要自定义的文字。
- 普通配置流程不要求用户手写整段 JSON、内部字段名或字节数。规则由交互结果生成，大小使用易理解的单位，已有有效配置保持兼容。
- 配置页显示中文摘要、当前值和默认值；填写时给出具体示例、校验原因及明确的取消／返回入口，避免让用户到其他位置查找命令或参数。
- 修改规则先形成草稿，支持测试或预览，确认保存后再生效；测试与实际转存的区别必须清楚。
- 只增加有实际用途的交互入口，保持常用操作简洁；不为增加菜单数量而拆分无必要的功能。
- 便利性与数据安全同时维护：权限、来源保护、目录范围、去重和危险操作确认继续有效，凭据不得进入日志。

这些要求适用于后续功能及渐进改进；不能把尚未实现的交互写成已发布功能。

## Python 检查

原生平台验证使用 `ubuntu-24.04`（AMD64）和 `ubuntu-24.04-arm`（ARM64），不设置 QEMU；CLI Python 3.10 / 3.13 两架构均测试。完整 runtime job 保留原有回归，并执行两 Edition 候选、原生扩展／rclone、隔离网关 HTTP／FUSE 与代理测试。Release 等待两架构成功但只上传一次源码；历史 Tag 按当时能力验证。命令、缺失条件与 helper A/B 发布步骤见[双架构说明](../docs/ARCHITECTURES.md)，未运行项不得写成通过。

完整检查使用 Python 3.12 / 3.13 和 `requirements/dev.lock.txt`，宿主 CLI 另保持标准库边界。cryptography 显式作为证书夹具测试依赖，不进入 Bot 容器。依赖定义在 `pyproject.toml`，两份哈希锁文件由其中固定的同一 uv 版本统一生成，不单独手改版本；生成时从 Bot Dockerfile 读取 Python 3.12 作为解析下限，不能使用维护者当前 Python 版本作为下限而漏掉条件依赖。宿主 CLI 仍支持 Python 3.10+、只用标准库，不安装这两份 Bot／开发锁文件。请在隔离虚拟环境中准备：

```bash
python -m pip install -r requirements/dev.lock.txt
python -m pip install --no-deps -e .
python .github/scripts/check_python.py all
```

已经准备好本地 Python 环境时，在仓库根目录直接执行：

```bash
python .github/scripts/check_python.py all
```

`all` 顺序运行公共文件 / 构建输入 / 文档索引检查、标准库 unittest、Ruff、compileall，任一步失败立即停止。也可分别执行 `repository`、`test`、`lint`、`compile`；检查入口使用运行它的同一个 Python 环境，不自动安装依赖或修改实例。compileall 的字节码统一写入已忽略的 `build/check-pycache/`，不写入实例载荷。

`repository` 和 `all` 需要完整 Git checkout。检查覆盖已跟踪文件和未被忽略的新文件；已跟踪的产物即使后来加入 `.gitignore` 仍会报错。个人本地排除的资料不参与检查。下载的源码 ZIP 不具备 Git 跟踪信息，可分别运行 `test`、`lint`、`compile`，但不能据此宣称公共仓库文件检查通过。

独立 Linux 向导的标准库边界检查使用 Python 3.10 / 3.13，只需要现有 Ruff 工具，不要求 Bot 依赖：

```bash
uv run --no-project --with ruff==0.17.0 python .github/scripts/check_python.py all --scope cli
```

`pyproject.toml` 的 `[tool.ruff]` 统一 lint 配置：保持原有隐式默认规则、Git ignore 和 `website/` 排除，目标版本为 Python 3.10。全范围自动发现 Python 文件，CLI 范围集中在检查入口；无需另建 Ruff 配置文件。不要用 `ruff format .` 或 `--fix` 对稳定源码进行无关批量改写。

真实本地 WebDAV 集成测试需要 PATH 中的 `rclone`；缺少时明确跳过。Shell 回归需要 Bash（本地 Windows 可用兼容变量 `TG115_TEST_BASH` 指定 Git Bash，不为品牌清理改坏测试）。公共 CI 只维护 Linux：全量 Python 3.12，宿主 CLI 3.10 / 3.13。历史兼容测试读取固定公开 Git 对象，需要完整历史 checkout。默认只操作临时文件、模拟配置和回环 WebDAV，不使用个人凭据或真实 VPS；Docker 使用显式开关，自动检查不代表实机验收。

涉及 Shell 时，执行 Bash 语法检查以及 CI 中已有的 ShellCheck 范围：

```bash
bash -n install.sh
bash -n install-lan.sh
```

提交前另外执行 `git diff --check`。缺少 rclone、Docker 或其他集成条件时，应记录跳过原因，不能把跳过写成通过。

## 文档与网站检查

索引、规范和 CI 入口的离线检查不需要第三方 Python 依赖：

```bash
python -B .github/scripts/check_repository.py
python -B -m unittest discover -s tests -p test_repository.py -v
python .github/scripts/validate_release_notes.py RELEASE_NOTES.md
```

公共文件检查只读，不删除或取消跟踪任何文件：禁止提交的常见产物、缓存、本地配置或内部记录会报告路径；正式构建文件和两 Edition 的 payload 输入必须存在且进入候选公共文件集合；新增 `docs/` 下的公开 Markdown 文档必须链接到 `docs/README.md`。这不是秘密内容 / Git 历史扫描，也不执行构建部署或 VPS 验收。公共文件 CI 对 main 的 Push / PR 均运行，不因“只有文档变更”而跳过；Release 在 Linux 验证与源码打包之前执行同一检查。

文档站使用 Node.js 22。在 `website/` 中执行现有命令：

```bash
npm ci --ignore-scripts
npm run build
npm test
```

版本、品牌副本和公开脚本命令的一致性测试需要完整 TG2Cloud 仓库；不只拷贝 `website/` 来执行仓库级检查。网站与根目录文档允许不同篇幅，但安全边界、操作命令和发布事实必须同步审阅。实际构建/预览方式仍见 [网站维护说明](../website/README.md)。

## Dependabot 镜像检查

`packaging/Dockerfile` 的共享 Bot 基础镜像使用 `docker` 更新器；`packaging/compose/` 的两个网关使用 `docker-compose` 更新器。清单采用 `docker-compose.clouddrive2.yml` 和 `docker-compose.openlist.yml`，匹配更新器的文件名规则；部署时仍组装成实例内的 `docker-compose.yml`。不要给 OpenList 复制一个独立 Dockerfile 来满足错误扫描配置。回归测试核对更新器与实际清单，并保留 Python 基础镜像禁止自动跨主/次版本升级的保护。pip 更新器读取根 `pyproject.toml`，依赖升级后仍需用统一工具重新生成并审阅两份锁文件。

更新器只检查依赖并提出 PR，不会自动合并、发布或更新 VPS。镜像 digest 变化仍需单独审查和测试；修正更新器类型本身不修改运行镜像。Dependabot 的历史失败记录不会消失，修复是否在 GitHub 生效应以推送后的新检查结果为准。

## 版本与 Release

Bot、包和脚本唯一版本源为 `src/tg2cloud/version.py`；重构不自动提版本。新版本同步安装入口、网站、CHANGELOG 和 RELEASE_NOTES。`python .github/scripts/release_metadata.py --tag vX.Y.Z` 仅检查，不创建标签或发布。新目录、载荷组装、递归清单和未发布 helper pin 的 A/B 步骤见[开发与测试](../docs/development/DEVELOPMENT.md)；本地验证不能绕过正式发布门槛。

Release Workflow 仅接受严格版本标签 `vX.Y.Z` 或 `vX.Y.Z-alpha.N` / `beta.N` / `rc.N`。手动触发也必须选择已有 Tag，不允许把 main 当作发布来源。预发布的 Release Notes 必须写明完整预发布标签；Workflow 自动标记 Pre-release。Linux 检查从同一标签执行，包含完整回归、两 Edition Docker 和本地 WebDAV。`source_release.py build` 从该 Tag 打包一次并校验在线向导 pin；Release Job 下载同一 artifact，再次 verify 后发布源码归档和 SHA256。旧 pin 与本版辅助代码不一致会阻断发布；不替换已有 Release，不上传本机产物。
