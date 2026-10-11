# 参与贡献

1. 不得提交任何真实账号、Token、密码、Cookie、私钥、个人 ID、文件名或服务器地址；
2. 修改代码后运行全部自动化测试；
3. 涉及安装脚本、远程命令或路径处理时，必须同时补充异常和恶意输入测试；
4. 不要把 CloudDrive2 WebDAV 接收误写成 115 官方端已经完成；
5. 不要提交构建目录、缓存、日志、数据库、下载文件或本地配置。

仓库职责、文档同步和本地产物处理见 [仓库维护规范](docs/development/REPOSITORY.md)，用户文档入口见 [文档目录](docs/README.md)。不为了统一目录修改稳定核心或公开安装脚本路径。

## Python 检查

完整检查使用 Python 3.12 / 3.13，以及现有两个 requirements 文件中的依赖和 Ruff 0.16.0。可以通过 uv 创建临时检查环境，无需改变 Docker 运行依赖：

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  --with ruff==0.16.0 `
  python .github/scripts/check_python.py all
```

已经准备好本地 Python 环境时，在仓库根目录直接执行：

```bash
python .github/scripts/check_python.py all
```

`all` 顺序运行公共文件 / 构建输入 / 文档索引检查、标准库 unittest、Ruff、compileall，任一步失败立即停止。也可分别执行 `repository`、`test`、`lint`、`compile`；检查入口使用运行它的同一个 Python 环境，不自动安装依赖、打包 EXE 或修改实例。compileall 的字节码统一写入已忽略的 `build/check-pycache/`，不写入 payload 或 EXE 资源目录。

`repository` 和 `all` 需要完整 Git checkout。检查覆盖已跟踪文件和未被忽略的新文件；已跟踪的产物即使后来加入 `.gitignore` 仍会报错。个人本地排除的资料不参与检查。下载的源码 ZIP 不具备 Git 跟踪信息，可分别运行 `test`、`lint`、`compile`，但不能据此宣称公共仓库文件检查通过。

独立 Linux 向导的无桌面依赖检查使用 Python 3.10 / 3.13，只需要现有 Ruff 工具，不要求 PySide6、Paramiko 或 Bot 依赖：

```bash
uv run --with ruff==0.16.0 python .github/scripts/check_python.py all --scope cli
```

`.ruff.toml` 统一原有 lint 规则；全范围自动发现 Python 文件，CLI 范围集中在检查入口。不要用 `ruff format .` 或 `--fix` 对稳定源码进行无关批量改写。

真实本地 WebDAV 集成测试需要 `rclone` 在 PATH 中；缺少时明确跳过。Shell 故障回归需要 Bash（Windows 可通过兼容变量 `TG115_TEST_BASH` 指定 Git Bash 的绝对路径，不为品牌清理改坏测试）。Linux 全量 CI 安装两者并使用 Python 3.12，Windows 使用 Python 3.13；独立向导 CI 另测 3.10 / 3.13。默认测试只创建临时文件、模拟配置和回环 WebDAV 服务，不使用个人凭据或联系真实 VPS。Docker 集成由已有显式测试开关控制，自动测试通过不代表实机验收通过。

涉及 Shell 时，执行 Bash 语法检查以及 CI 中已有的 ShellCheck 范围：

```bash
bash -n install.sh
bash -n install-lan.sh
bash -n uninstall.sh
```

提交前另外执行 `git diff --check`。缺少 rclone、Docker 或其他集成条件时，应记录跳过原因，不能把跳过写成通过。

## 文档与网站检查

索引、规范和 CI 入口的离线检查不需要第三方 Python 依赖：

```bash
python -B .github/scripts/check_repository.py
python -B -m unittest discover -s tests -p test_repository.py -v
python .github/scripts/validate_release_notes.py RELEASE_NOTES.md
```

公共文件检查只读，不删除或取消跟踪任何文件：禁止提交的常见产物、缓存、本地配置或内部记录会报告路径；正式构建文件和两 Edition 的 payload 输入必须存在且进入候选公共文件集合；新增 `docs/` 下的公开 Markdown 文档必须链接到 `docs/README.md`。这不是秘密内容 / Git 历史扫描，也不执行 EXE 构建或 VPS 验收。公共文件 CI 对 main 的 Push / PR 均运行，不因“只有文档变更”而跳过；Release 在 Windows 构建之前执行同一检查。

文档站使用 Node.js 22。在 `website/` 中执行现有命令：

```bash
npm ci --ignore-scripts
npm run build
npm test
```

版本、品牌副本和公开脚本命令的一致性测试需要完整 TG2Cloud 仓库；不只拷贝 `website/` 来执行仓库级检查。网站与根目录文档允许不同篇幅，但安全边界、操作命令和发布事实必须同步审阅。实际构建/预览方式仍见 [网站维护说明](website/README.md)。

## Windows 构建

修改 Windows 部署器公共行为或版本号时，要同时检查 `installer.py`、`installer_clouddrive2.py`、`installer_openlist.py` 和 `deployer_products.py`；运行 `.\build.ps1` 会构建并自检 CloudDrive2、OpenList 两个 PySide6 产品。当前项目不再保留 Classic/Tkinter 部署器源码或 CMD 启动器。

## 版本与 Release

唯一版本源为 `payload_clouddrive2/app/version.py`，部署器与 Bot 均引用该文件。修改版本后运行 `python .github/scripts/release_metadata.py --sync-windows` 同步两个 Windows 版本资源，再更新 CHANGELOG 和 RELEASE_NOTES。`python .github/scripts/release_metadata.py --tag vX.Y.Z` 检查标签、源码、Windows 资源和发布文档是否一致；这个命令不会创建标签或发布。

Release Workflow 仅接受严格版本标签 `vX.Y.Z` 或 `vX.Y.Z-alpha.N` / `beta.N` / `rc.N`。手动触发也必须选择已有 Tag，不允许把 main 当作发布来源。预发布的 Release Notes 必须写明完整预发布标签；Workflow 自动标记 Pre-release。Windows 和 Linux 检查必须来自同一标签，Release Job 继续复用 Windows 一次构建并通过自检的两个 EXE 与实际 SHA256 清单；不替换已有 Release，不上传本机 EXE。
