# 仓库结构与维护规范

公共仓库以 Linux 一键脚本、共享 Telegram Bot、两 Edition Docker 资源和文档站为主。目录整理不改变现有 VPS 安装目录、数据库、配置或公开的一键命令 URL；历史 Tag 的布局保持不变。

## 目录职责

| 路径 | 职责与维护边界 |
| --- | --- |
| `install.sh`、`install-lan.sh`、`uninstall.sh` | 保留根目录的公开单行命令入口 |
| `src/tg2cloud/` | 共享 Bot、CLI、公共部署、存储、持久化及监测 |
| `scripts/run_source.py` | 不依赖当前目录或 Bot 依赖的受控源码入口 |
| `packaging/` | 共用 Dockerfile、两版 Compose、Shell 钩子和 `app.*` 兼容入口 |
| `requirements/`、`pyproject.toml` | 包元数据、依赖分组及同一 uv 工具生成的哈希锁文件 |
| `assets/brand/` | 正式 Logo／Icon 唯一来源，不自动重绘或覆盖 |
| `tests/` | Bot、Linux、资源、Docker、网关、备份和协议兼容回归 |
| `.github/` | Workflow、检查工具、Dependabot、贡献指南和安全政策 |
| `docs/` | 用户指南与公开开发规范，入口见[文档目录](../README.md) |
| `website/` | 独立静态文档站，沿用现有 Node 构建与部署方式 |

根目录只保留标准配置、README／英文版、许可证、版本记录及三个 Shell 入口。本轮重构不迁移运行数据或提升版本；兼容及未公开 helper 的发布步骤见[Linux 重构说明](LINUX-REFACTOR.md)。

## 桌面源码只在本地保留

Windows EXE 停留在 v1.2.1。main 不再跟踪旧部署器、PySide6 界面、桌面 SSH／Tunnel、Windows 资源、打包脚本或专用测试，公共 CI 不再安装 Qt、Paramiko、PyInstaller。

维护者本地的 `legacy/` 和独立恢复 ZIP 由 `.git/info/exclude` 排除，不作为公共依赖。恢复请使用完整备份或 [v1.2.1 Tag](https://github.com/LuoPoJunZi/TG2Cloud/tree/v1.2.1)，在新目录中校验和构建，不覆盖当前工作树。历史 Release、EXE、SHA256 和 Git 历史不重写。

混合测试中的非桌面检查必须保留。历史配置输出使用仅含合成数据的 `tests/fixtures/deployment-config.json` 固定协议快照回归，不再导入旧 GUI；载荷组装直接测试公开 Linux 接口。旧完整测试与代码保存在本地恢复归档，不能把本地专用测试算作当前公共 CI 已执行。

## 编辑与检查规范

`.editorconfig` 和 `.gitattributes` 约定 UTF-8、换行与缩进；不自动重绘品牌资源或破坏 Markdown 有语义的末尾空格。现有中英文文档不做无关批量重命名；新用户文档加入[文档目录](../README.md)。

`.ruff.toml` 保留原有隐式规则和文件发现策略。统一检查入口为 `.github/scripts/check_python.py`；环境准备见[贡献指南](../../.github/CONTRIBUTING.md)。`all` 依次运行公共文件检查、unittest、Ruff、compileall，不安装依赖、不构建 EXE、不部署或推送。CLI 范围继续在 Python 3.10／3.13 下只用标准库运行。

`.github/scripts/check_repository.py` 使用 Git 枚举 tracked／未被忽略的新文件，禁止构建产物、缓存、私有配置、内部记录及本地桌面归档进入公共集合。已跟踪文件不能仅通过 ignore 移除，必须取消跟踪。它不读取或显示凭据内容，不是完整 Secret／历史扫描。

输入检查保留三个入口、Linux 共用模块、两 Edition 资源及品牌资源，以 AST 读取 `src/tg2cloud/deployment/profiles.py` 静态清单并检查递归源码，不执行模块。公开 `docs/` Markdown 必须有有效索引链接；它不是动态依赖解析器，也不验证公网。公共检查需要完整 Git checkout；源码 ZIP 可运行测试和语法检查，但不能推断跟踪状态。

完整回归还应在不含本地 `legacy/` 的干净副本运行，确保新克隆可独立工作。缺少 Bash、rclone 或显式 Docker 条件时如实记录跳过；不增加 skip 来掩盖失败。

## 仓库文档与网站同步

| 事实来源 | 需要同步审阅的网页文章 |
| --- | --- |
| README、VPS 安装指南 | 下载、快速开始、升级 |
| 内网与卸载指南 | 下载页中的命令及安全边界 |
| 运维与恢复指南 | 维护、备份、升级及故障排查 |
| TG115 迁移指南 | 网站迁移文章 |
| 唯一版本源、CHANGELOG、RELEASE_NOTES | 网站版本、发布状态、下载与来源 |
| `assets/brand/` | 网站实际静态图标副本 |

网站仍执行 `npm run build` 和 `npm test`，不更改主题、导航、搜索或部署方式。文章可有不同篇幅，但命令、边界和发布事实必须一致。main 待发布行为与稳定 Release 必须区分。自动检查不替代浏览器、VPS／NAS 或真实网盘验收。

## 本地资料与发布边界

`build/`、`dist/`、`website/dist/`、测试缓存是可重建输出；`.venv/`、个人 AI 指令、内部审计、工作记录及恢复 ZIP 不属于可随意删除的垃圾。本地独有资料优先使用 `.git/info/exclude`，不作为公共文档；通用产物和秘密由 `.gitignore` 排除。

目录标准化不提升版本、不创建 Tag、不替换已有 Release。在线入口的下载白名单、包结构和不可变 helper pin 必须配套：先在隔离分支提交辅助代码并验证，再把三个入口固定到通过的同一提交。正式业务 payload 仍来自稳定 Release，不改用 main／RC。

Release 继续从同一 Tag 验证并打包源码一次，发布 Job 复用 artifact 和实际 SHA256。历史 Tag 的重试按历史布局验证，不要求本地桌面资料。更多边界见[脚本优先说明](SCRIPT-FIRST.md)。
