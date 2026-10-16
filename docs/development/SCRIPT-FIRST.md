# 脚本优先维护与桌面版冻结

从 v1.3.0 起以 Linux 一键脚本为主入口，CloudDrive2 和 OpenList 两个 Edition 继续维护。最后一个 Windows 部署器版本为 v1.2.1，历史 Tag、Release、EXE 和原校验文件保留。

## v1.3.0 发布核对

2026-10-16，[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.3.0) 已发布，Tag 指向 `c07734cab666defb6ae5b5351a06361711d24190`。[发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/38892441721) 从该 Tag 校验并生成一次 `TG2Cloud-v1.3.0-source.tar.gz` 与 `SHA256SUMS.txt`；公开下载摘要、两版 payload 与 11 个固定向导文件已核对。首次发布的历史 Windows 入口权限检查由主分支 Workflow 修正后重试，Tag 未移动，资产没有混入 main 的新业务代码。

这些是自动发布结果；下方真实 VPS／NAS 验收门槛仍保留，桌面源码尚未物理删除。

## 本轮实现与当前上线边界

- VPS 与 LAN 首次安装复用 `vps_resources.py` 的均衡／流式优先推荐，用户明确选择或手动输入；手动输入不能绕过资源校验。
- 安装目录与 Docker 数据盘分别检查；任务预算不是分区、扩容，也不代表网关全部缓存受限。
- 已有实例保留原始配置；新安装和升级在执行前再次探测，磁盘条件变化时中止。
- 分支 CI 保留回归测试，停止自动构建 EXE；Release 改为同一 Tag 的 Linux 验证、源码打包和 SHA256，再由发布任务复用 artifact。
- 源码包检查 Tag 身份、两 Edition 载荷、Python 语法、路径安全、实际 SHA256，以及三个在线入口的辅助源码 pin。

公开单行命令由入口中固定的 commit 决定使用哪版向导；仅修改本地 Python 不会更新在线命令。v1.3.0 发布流程先提交向导、验证 CI，再将三个入口 pin 指向该不可变提交。正式部署 payload 仍从稳定 Release 解析到不可变 commit；不安装 main 或预发布的业务代码。

v1.2.1 的 SHA256SUMS 校验两个 EXE。后续脚本版的 SHA256SUMS 校验该次 Actions 生成的 `TG2Cloud-vX.Y.Z-source.tar.gz`。当前在线向导仍使用 HTTPS 下载固定 commit 的源码，不读取这个资产校验清单；不能宣称已为在线向导增加包签名或额外内容校验。

## 桌面源码保留和备份

清理前应生成一个仓库外的完整公共源码 ZIP，包含两个部署器、共享模块、载荷、品牌、Windows 构建资源、固定依赖、测试、许可证、恢复说明和逐文件 SHA256 清单。不要包含本地凭据、虚拟环境或运行数据。

恢复时解压到新的空目录，先核对清单，再按备份中的 CONTRIBUTING 与 build.ps1 构建。源码备份仍需联网获取固定依赖，不是离线运行环境备份。不要直接解压覆盖较新工作树，也不要用旧 EXE 覆盖已升级的实例。

本阶段暂时保留桌面源码及相关回归测试，Windows 版本资源固定为 1.2.1。共享的 `deployer_products.py`、`domain_proxy.py`、`proxy_maintenance.py`、`vps_resources.py` 仍被脚本使用，不可按文件名删除。PySide6 等依赖目前仅为现有桌面兼容测试保留，Linux 安装向导不安装它们。

主分支后续整理已将桌面源码、依赖、构建脚本和版本资源归档到 `legacy/desktop/`，原根目录不再保留重复入口；测试和 CI 使用归档路径，资源仍从项目根目录读取。归档不等于删除实现，也不表示下方实机清理门槛已通过。已发布 v1.3.0 Tag 仍保持原目录布局。

## 后续验收和清理门槛

- 在专用测试环境分别验收 CloudDrive2/OpenList 的首次安装、保留配置升级、HTTPS 续做和 WebDAV 操作；另验收内网模式。
- 小磁盘推荐、手动不安全预算、独立 Docker 分区不足、确认前容量下降均应明确拒绝或引导重新选择；升级不得静默重算预算。
- 由 v1.2.1 EXE 安装的标准实例先 `--check`，身份和源码核对通过后才升级；自定义/部分实例不强制接管。升级后改用匹配的新脚本维护。
- 网关镜像 digest 变化仍停止自动升级；网关数据库迁移需要独立的备份、兼容性和回退验收。旧 EXE 不是这个限制的绕过方式。
- 更换域名、生产恢复等未提供的终端功能不能用菜单占位伪装完成；保持既有明确授权和数据保护边界。
- 脚本实机验收通过后，再分离桌面兼容测试与共享核心测试，清理专用源码和打包依赖；保留备份及历史 Release。

## 发布维护步骤

1. 更新 Bot/脚本版本源、安装入口版本、网站和 CHANGELOG/RELEASE_NOTES；不再同步 Windows 版本资源到新版本。
2. 提交辅助源码，经过 CI；再更新 `install.sh`、`install-lan.sh`、`uninstall.sh` 的固定 commit。被 pin 的所有辅助文件必须与最终 Tag 内容一致。
3. 执行离线测试、代码检查、两 Edition Docker/本地 WebDAV、网站检查及上述实机验收。未运行的检查明确保留待验收。
4. 创建新 Tag 后 Actions 打包一次，发布同一源码包及 SHA256。不覆盖已有版本，不上传本机产物。

若已有 Tag 的发布仅因工作流检查环境失败，修复主分支 Workflow 后，可在 Actions 的 release 工作流选择 main，填写 `release_tag` 为已有版本重试。实际源码、版本检查、Release Notes 与打包仍从 `refs/tags/<版本>` 读取，不从 main 取业务代码，不移动 Tag；已有 Release 继续拒绝覆盖。

发布授权不等于真实实例部署授权。v1.3.0 的真实 VPS／NAS 首次安装、升级和回退尚未执行；自动测试结果不能替代上述实机门槛。
