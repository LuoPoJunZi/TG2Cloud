# 脚本优先维护与桌面版冻结

从 v1.3.0 起以 Linux 一键脚本为主入口，CloudDrive2 和 OpenList 两个 Edition 继续维护。最后一个 Windows 部署器版本为 v1.2.1，历史 Tag、Release、EXE 和原校验文件保留。

## v1.4.0 原生双架构

正式稳定源码与在线 helper 统一支持 Debian／Ubuntu 原生 AMD64／ARM64，不使用 QEMU。A／B 各五项 CI、同标签双架构发布与真实下载资产校验通过；Oracle／真实 VPS、云盘、手机及故障回退由用户发布后验收。配置、数据库、Session、实例身份与现有传输策略不变，详见[双架构说明](../ARCHITECTURES.md)。以下版本段落保留各自历史范围。

## v1.3.4 命名维护版本（待发布）

v1.3.4 已正式发布既有命名流程的兼容增强：媒体斜杠说明、标题／元数据边界、网址污染原名、图片自身说明，以及一图一视频且真实后缀不同的同标题规则。多成员／未知后缀继续编号，原名记录、鉴权、去重、无说明兜底和远端冲突保护保留；不改主安装、共享传输策略、依赖、数据库结构或历史 Windows 资源。辅助 A、固定入口 B 与同标签 CI 均通过，正式源码包及 SHA256 已核对；本版未进行真实 VPS／Telegram／网关升级验收。标题中的“待发布”仅为兼容原链接，实例仍需显式升级才生效。

## v1.3.3 家庭共享与命名增强

v1.3.3 已发布 Linux 源码与 SHA256 清单，增加安装后的家庭授权、独立外部只读账号管理和 Unicode 标题候选增强；主安装仍只有一个管理员 ID，不新增个人目录。现有 Bot 与两套离线工具需显式升级，操作及兼容边界见[家庭共享](../FAMILY-SHARING.md)。自动 CI 与资产核验通过不代表真实 Telegram、两版网关、手机或 VPS 验收完成。

## v1.3.2 安装与离线管理

公网／内网的默认入口先选择 Edition，缺失时确认安装，已有实例进入管理菜单。确认安装管理命令后可在主机运行 `tg2cloud`，不依赖 Windows；显式参数和原 `manage.sh` 仍兼容。最后一套完整卸载只在无依赖且归属核验通过时清理管理代码，独立卸载 URL 保留救援。菜单、权限及未验收边界见[运维指南](../OPERATIONS.md#本地管理菜单)。

新装 WebDAV 密码回车生成 8 位、默认时区 Asia/Shanghai；升级保留已有配置、Session、数据库和预算。独立外部 WebDAV 使用自己的编号向导与 9 位默认密码，仍不加入主安装或 Bot。主安装支持范围没有扩大；真实两 Edition 安装／升级／卸载和 NAS 仍需独立验收。

## v1.3.1 独立附加功能

v1.3.1 沿用 Linux Python + Bash 架构，新增独立 `install-webdav.sh`，不加入公网/内网主安装或 Bot 菜单。主入口 helper 必须包含兼容 proxy schema 2 的共享代码；旧工具拒绝或禁止维护新状态，详见[外部 WebDAV](../external-webdav.md)。原生两版账号、手机、ACME 和 ARM64 尚未端到端实机验收。发布授权仍不包含部署真实实例。

## v1.3.0 发布核对

2026-10-17 重新准备 v1.3.0，包含新 Linux 源码布局、命名增强及已验证的依赖修复。发布前重新核对 GitHub，远端当时没有 v1.3.0 Tag 或 Release；此前旧布局的构建记录不能作为本次发布结果。实际源码和资产以[正式 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.3.0) 及其对应 Tag 为准，不覆盖其他历史版本。

发布工作流从同一 Tag 验证并生成一次 `TG2Cloud-v1.3.0-source.tar.gz` 与 `SHA256SUMS.txt`；发布 Job 复用此 artifact。下方真实 VPS／NAS 验收门槛仍保留，桌面恢复归档保存在本地。

曾安装旧布局的同号 v1.3.0 实验实例需单独核对迁移；版本号相同不表示源码相同。脚本遇到基线不一致会停止，不会自动覆盖或重建数据库。不要删除版本标识、配置或 Session 来绕过此保护。

## v1.3.0 实现与历史上线边界

- Linux 重构见[模块与兼容说明](LINUX-REFACTOR.md)；产品版本为 v1.3.0，旧源码验证后本地归档，公共 CI 不依赖归档。
- VPS 与 LAN 首次安装复用 `src/tg2cloud/deployment/resources.py` 的均衡／流式优先推荐，用户明确选择或手动输入；手动输入不能绕过资源校验。
- 安装目录与 Docker 数据盘分别检查；任务预算不是分区、扩容，也不代表网关全部缓存受限。
- 已有实例保留原始配置；新安装和升级在执行前再次探测，磁盘条件变化时中止。
- 分支 CI 保留回归测试，停止自动构建 EXE；Release 改为同一 Tag 的 Linux 验证、源码打包和 SHA256，再由发布任务复用 artifact。
- 源码包检查 Tag 身份、两 Edition 载荷、Python 语法、路径安全、实际 SHA256，以及三个在线入口的辅助源码 pin。

公开单行命令由入口中固定的 commit 决定使用哪版向导；仅修改本地 Python 不会更新在线命令。v1.3.0 发布流程先提交向导、验证 CI，再将三个入口 pin 指向该不可变提交。正式部署 payload 仍从稳定 Release 解析到不可变 commit；不安装 main 或预发布的业务代码。

v1.2.1 的 SHA256SUMS 校验两个 EXE。后续脚本版的 SHA256SUMS 校验该次 Actions 生成的 `TG2Cloud-vX.Y.Z-source.tar.gz`。当前在线向导仍使用 HTTPS 下载固定 commit 的源码，不读取这个资产校验清单；不能宣称已为在线向导增加包签名或额外内容校验。

### 手动下载文件的校验

从同一个正式 Release 下载源码归档和 `SHA256SUMS.txt`，保存在同一目录后，在 Linux 中检查：

```bash
sha256sum -c SHA256SUMS.txt
```

这校验手动下载的文件是否与该清单一致，不是数字签名，也不替代对仓库来源的信任。不要把 v1.3.0 的源码校验清单用于 v1.2.1 EXE。

历史 Windows EXE 只从 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) 获取。下载对应 Edition 和该版本自己的清单，在下载目录用 PowerShell 计算所选文件的 SHA256 并逐字核对清单：

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

只下载一个 Edition 时运行对应一行。历史 EXE 没有商业代码签名，SmartScreen／安全软件可能提示未知发布者；不要为运行它关闭系统安全防护，不运行来源不明或校验不一致的文件。当前实例已升级时不要用旧 EXE 覆盖部署；历史界面见[旧版教程](../README-小白使用说明.md)。

## 桌面源码保留和备份

清理前应生成一个仓库外的完整公共源码 ZIP，包含两个部署器、共享模块、载荷、品牌、Windows 构建资源、固定依赖、测试、许可证、恢复说明和逐文件 SHA256 清单。不要包含本地凭据、虚拟环境或运行数据。

恢复时解压到新的空目录，先核对清单，再按备份中的 CONTRIBUTING 与 build.ps1 构建。源码备份仍需联网获取固定依赖，不是离线运行环境备份。不要直接解压覆盖较新工作树，也不要用旧 EXE 覆盖已升级的实例。

按用户后续明确授权，main 已将桌面源码、构建脚本、Windows 资源和专用 Qt／桌面 SSH 测试从 Git 跟踪中移除，本地文件与独立 ZIP 保留。混合测试中的 Bot、Linux、资源、Docker、网关和备份检查继续公开；原桌面配置输出另存为仅含合成数据的协议快照，Linux 配置继续与它逐项对照。公共 CI 不再安装 PySide6、Paramiko 或 PyInstaller。

共用部署逻辑由此前 `scripts/lib/` 进一步分入 `src/tg2cloud/deployment/`，不是删除 Linux 能力。在线清单与启动命令已切换新布局，pin 指向已公开且通过 CI 的辅助提交 A；后续入口提交 B 不改变 A 的辅助文件。目录整理和自动检查不表示实机验收已完成。

## 后续验收和清理门槛

- 在专用测试环境分别验收 CloudDrive2/OpenList 的首次安装、保留配置升级、HTTPS 续做和 WebDAV 操作；另验收内网模式。
- 小磁盘推荐、手动不安全预算、独立 Docker 分区不足、确认前容量下降均应明确拒绝或引导重新选择；升级不得静默重算预算。
- 由 v1.2.1 EXE 安装的标准实例先 `--check`，身份和源码核对通过后才升级；自定义/部分实例不强制接管。升级后改用匹配的新脚本维护。
- 网关镜像 digest 变化仍停止自动升级；网关数据库迁移需要独立的备份、兼容性和回退验收。旧 EXE 不是这个限制的绕过方式。
- 更换域名、生产恢复等未提供的终端功能不能用菜单占位伪装完成；保持既有明确授权和数据保护边界。
- 公共仓库清理已按用户授权先完成专用测试分离；桌面源仍本地保留，不物理销毁。脚本实机验收、版本回退和数据保护门槛不因此降低。

## 发布维护步骤

1. 更新 Bot/脚本版本源、安装入口版本、网站和 CHANGELOG/RELEASE_NOTES；不再同步 Windows 版本资源到新版本。
2. 提交辅助源码，经过 CI；再更新 `install.sh`、`install-lan.sh`、`uninstall.sh` 的固定 commit。被 pin 的所有辅助文件必须与最终 Tag 内容一致。
3. 执行离线测试、代码检查、两 Edition Docker/本地 WebDAV、网站检查及上述实机验收。未运行的检查明确保留待验收。
4. 创建新 Tag 后 Actions 打包一次，发布同一源码包及 SHA256。不覆盖已有版本，不上传本机产物。

若已有 Tag 的发布仅因工作流检查环境失败，修复主分支 Workflow 后，可在 Actions 的 release 工作流选择 main，填写 `release_tag` 为已有版本重试。实际源码、版本检查、Release Notes 与打包仍从 `refs/tags/<版本>` 读取，不从 main 取业务代码，不移动 Tag；已有 Release 继续拒绝覆盖。

发布授权不等于真实实例部署授权。2026-10-17，CloudDrive2 旧测试候选经授权、备份和人工核对后迁移到正式 v1.3.0，用户确认升级后使用验收完成。已有任务、配置、Session 授权和域名保留，官方入口复检通过；见[本次验收范围](V130-ACCEPTANCE.md)。首次安装、正式版自动升级、OpenList、NAS、故障回退及长期恢复仍需独立验证，不能用自动测试或这一次迁移替代。
