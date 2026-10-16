# 开发与贡献

这里介绍 TG2Cloud 主项目的开发入口。本文档网站本身的维护方法见 [文档来源与维护](/reference/sources/)。

## 获取主项目源码

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout v1.3.0
git rev-parse HEAD
```

本文档对应正式 v1.3.0，实际下载见[下载页](/download/)。对已发布版本复现问题时使用对应标签；跟随主分支开发时使用 main 并记录提交号，避免把后续未发布修改当成 Release 行为。

## 关键目录与入口

下表为 main 的脚本优先结构。已发布 v1.3.0 Tag 保持原桌面布局；上面的标签命令仅用于复现历史版本。当前公共仓库不再跟踪桌面代码或专用测试，只保留本地恢复备份；完整回归只需 Bot requirements，不依赖 Qt、Paramiko 或 PyInstaller。

| 路径 | 用途 |
| --- | --- |
| `scripts/lib/deployer_products.py` | 两 Edition 标识、路径和载荷清单，复用共享版本源 |
| `payload_clouddrive2/app/version.py` | Bot 和脚本的版本源；Windows 资源冻结在 v1.2.1 |
| `scripts/lib/domain_proxy.py`、`scripts/lib/proxy_maintenance.py` | 共享 HTTPS 网关与私密维护助手 |
| `scripts/lib/vps_resources.py` | 资源探测、磁盘推荐与安全容量校验 |
| `install.sh`、`scripts/vps_installer.py`、`scripts/vps_runtime.py` | 主要 VPS 向导、稳定 Release 解析与运行环境适配 |
| `install-lan.sh`、`scripts/lan_installer.py` | 独立内网入口，人工指定私有 IPv4，不修改 EXE 的 HTTPS 规则 |
| `uninstall.sh`、`scripts/uninstaller.py` | 独立卸载、只读预检；主分支完整清理需双确认，`--keep-data` 保留数据，不卸载系统软件 |
| `payload_clouddrive2/` | CloudDrive2 部署脚本与共享核心文件来源 |
| `payload_openlist/` | OpenList 部署脚本 |
| `tests/` | 自动化回归 |
| `.github/CONTRIBUTING.md`、`.github/SECURITY.md` | 贡献规范、安全政策和公共 CI 规则 |

## 执行自动测试

开发当前 main 时先切回分支，再按贡献指南检查；不要把历史 Tag 和 main 的命令混用：

```powershell
git switch main
uv run --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

真实本地 WebDAV 集成测试需要 `rclone` 在 PATH 中；Shell 回归需要 Bash。缺少依赖时的跳过不能写成“所有集成测试均通过”。

仓库说明中 Linux CI 使用 Python 3.12，Windows 使用 Python 3.13；具体以当前 CI 配置为准。

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
