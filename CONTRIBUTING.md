# 参与贡献

1. 不得提交任何真实账号、Token、密码、Cookie、私钥、个人 ID、文件名或服务器地址；
2. 修改代码后运行全部自动化测试；
3. 涉及安装脚本、远程命令或路径处理时，必须同时补充异常和恶意输入测试；
4. 不要把 CloudDrive2 WebDAV 接收误写成 115 官方端已经完成；
5. 不要提交构建目录、缓存、日志、数据库、下载文件或本地配置。

测试命令：

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

真实本地 WebDAV 集成测试需要 `rclone` 在 PATH 中；缺少时明确跳过。Shell 故障回归需要 Bash（Windows 可通过 `TG115_TEST_BASH` 指定 Git Bash 的绝对路径）。Linux CI 安装两者并使用 Python 3.12 运行全部测试，Windows 使用 Python 3.13。测试只创建本机临时文件、模拟配置和回环 WebDAV 服务，不使用个人凭据或联系真实 VPS。

修改 Windows 部署器公共行为或版本号时，要同时检查 `installer.py`、`installer_clouddrive2.py`、`installer_openlist.py` 和 `deployer_products.py`；运行 `.\build.ps1` 会构建并自检 CloudDrive2、OpenList 两个 PySide6 产品。当前项目不再保留 Classic/Tkinter 部署器源码或 CMD 启动器。

## 版本与 Release

唯一版本源为 `payload_clouddrive2/app/version.py`，部署器与 Bot 均引用该文件。修改版本后运行 `python .github/scripts/release_metadata.py --sync-windows` 同步两个 Windows 版本资源，再更新 CHANGELOG 和 RELEASE_NOTES。`python .github/scripts/release_metadata.py --tag vX.Y.Z` 检查标签、源码、Windows 资源和发布文档是否一致；这个命令不会创建标签或发布。

Release Workflow 仅接受严格版本标签 `vX.Y.Z` 或 `vX.Y.Z-alpha.N` / `beta.N` / `rc.N`。手动触发也必须选择已有 Tag，不允许把 main 当作发布来源。预发布的 Release Notes 必须写明完整预发布标签；Workflow 自动标记 Pre-release。Windows 和 Linux 检查必须来自同一标签，Release Job 继续复用 Windows 一次构建并通过自检的两个 EXE 与实际 SHA256 清单；不替换已有 Release，不上传本机 EXE。
