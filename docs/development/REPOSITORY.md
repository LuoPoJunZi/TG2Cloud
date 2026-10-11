# 仓库结构与维护规范

本仓库同时维护两个 PySide6 部署器、共享 Bot 运行代码、Linux 安装 / 卸载入口及静态文档站。目录标准化不意味着迁移运行代码或改变现有安装路径。

## 目录职责

| 路径 | 职责与维护边界 |
| --- | --- |
| 根目录 `installer*.py` 与公共 Python 模块 | 两个部署器入口及共享实现；构建、导入和在线向导依赖现有路径，不随意搬入 `src/` |
| `build.ps1`、`requirements-build.txt` | Windows EXE 的正式构建入口和固定构建依赖 |
| `install.sh`、`install-lan.sh`、`uninstall.sh` | 公开单行命令入口；下载白名单与不可变源码固定值需经过审查和 CI 验证，不为整理目录而改写 |
| `scripts/` | 独立 Linux 向导和本机执行适配；不得默认操作真实服务器 |
| `payload_clouddrive2/` | 共享 Bot 应用和 CloudDrive2 Docker / Shell 资源 |
| `payload_openlist/` | OpenList 专用运行资源；复用共享 Bot 应用，不复制第二套业务核心 |
| `packaging/windows/` | 两个正式 EXE 的版本资源，属于构建输入 |
| `assets/brand/` | 正式品牌资源唯一来源，不自动重绘或覆盖 |
| `tests/` | 自动回归测试与模拟工具，保留公开 |
| `.github/workflows/`、`.github/scripts/` | 全仓库 CI、发布与开发检查工具；不在网站子目录再放一套 Workflow |
| `docs/`、`docs/development/` | 用户文档与公开开发规范；入口见 [文档目录](../README.md) |
| `website/` | 独立静态文档站，使用自己的 Node 构建与测试，不改变主程序构建方式 |

根目录保留 README、许可证、版本历史、正式入口和必要模块。新增用户文档先加入文档目录；新文档优先使用清楚的英文大写短横线文件名，网站文章沿用现有小写短横线与分类目录。现有中英文文件名不批量重命名，避免破坏链接。

## 编辑与检查规范

`.editorconfig` 约定 UTF-8、空格缩进、文件末尾换行；Shell 为 LF，PowerShell 为 CRLF，与 `.gitattributes` 保持一致。Markdown 不自动删除有语义的末尾双空格，不强制将自然段折成多行。正式 SVG / PNG / ICO 不作为格式化输入。

`.ruff.toml` 统一文件发现与忽略策略，保持现有 Ruff 的隐式默认规则，不额外设置 `select` / `ignore` 或批量格式化。显式列出规则组可能启用原默认没有启用的规则，因此不为标准化调整规则范围。全仓库检查通过 `ruff check .` 自动发现 Python 源文件，遵守 Git 忽略规则；CLI 检查使用独立范围，保持 Python 3.10 / 3.13 无桌面依赖测试。

统一 Python 检查入口为 `.github/scripts/check_python.py`；具体环境准备和命令见 [贡献指南](../../CONTRIBUTING.md)。`all` 依次运行仓库约束、测试、Ruff 和 compileall，不安装依赖，不打包 EXE，不部署，不提交或推送。缺少依赖或检查失败直接返回非零退出码。

`.github/scripts/check_repository.py` 是只读约束检查，可独立运行，不需要第三方 Python 依赖。它通过 Git 获取已跟踪文件与未被忽略的新文件，检查常见产物 / 缓存 / 私有配置 / 内部记录是否混入候选公共文件集合；已经跟踪的文件不能仅靠 `.gitignore` 消除报错。只在本地忽略的资料不属于候选集合，不会被扫描内容或自动清理。

构建约束保留正式入口、共享模块、Windows 资源及品牌输入，并以 AST 读取 `deployer_products.py` 中两 Edition 的 payload 字面量路径，不导入或执行运行代码。它验证文件存在、是仓库内普通文件且未被排除，但不是所有动态依赖的解析器，也不能代替 `build.ps1` 的实际打包自检。文档约束检查索引中的本地文件链接，并要求每个公开 `docs/` Markdown 文件被索引收录；不检查网页链接是否在线，不自动修改文章或导航。

这些检查需要完整 Git checkout，不能在源码 ZIP 中推断跟踪状态。公共文件 Workflow 对 main 的 Push / PR 全部运行；Release 的 prepare 阶段也在 Windows 构建前检查。检查只显示问题路径 / 索引行号及原因，不读取或打印凭据文件内容，不扫描 Git 历史；通过不代表不存在真实 Secret。

网站继续使用 `npm run build` 与 `npm test`。文档 CI 检查索引链接和仓库规范；网站测试检查公开命令、版本和品牌副本。自动检查只验证明确列出的约束，不能代替语义审阅、浏览器检查和真实 VPS/NAS 验收。

## 仓库文档与网站同步

| 事实来源 | 需要同步审阅的网页文章 |
| --- | --- |
| `README.md`、`README_EN.md`、`docs/VPS-INSTALL.md` | `website/docs/download.md`、`guide/quick-start.md`、`operations/update.md` |
| `docs/LAN-INSTALL.md`、`docs/UNINSTALL.md` | `website/docs/download.md`；内网与卸载命令、安全边界必须一致 |
| `docs/OPERATIONS.md` | `website/docs/operations/maintenance.md`、`backup.md`、`update.md`及相关故障排查 |
| `docs/MIGRATION_FROM_TG115.md` | `website/docs/operations/migration.md` |
| 唯一版本源、CHANGELOG 与 RELEASE_NOTES | `website/site.config.json`、包版本、下载页、更新日志与资料来源 |
| `assets/brand/` | `website/public/assets/` 中的正式图标副本，以及 `website/public/favicon.ico` |

网页文章是面向浏览器的整理版，不要求全文逐字相同。修改安装、升级、卸载或安全行为时，同时审阅对应来源和摘要；发布状态与 main 分支行为不同必须明确区分，不能仅统一版本数字。

网站品牌副本需要独立静态部署，因此保留实际文件而非符号链接。测试逐字节比较五个正式图标副本；更新品牌时手动复制已有正式资源，不生成新图形。

## 本地文件与生成产物

`build/`、`dist/`、`website/dist/`、Python / 测试缓存是生成或本地工作目录，不提交到 Git。`.venv/` 是开发环境，不属于应自动删除的垃圾。现有 `.gitignore` 已排除这些内容及秘密、运行数据库和日志。

`build/` 下的依赖验证副本、回归检查缓存、历史发布辅助文件应先确认是否仍需复用，再逐项清理。不能仅凭目录名就递归删除整个工作区或删除可能用于未完成验收的材料；本轮标准化不执行清理。

个人 AI 指令、内部审计与开发记录继续由 `.git/info/exclude` 本地排除，不加入公共开发文档。内部记录不替代 CHANGELOG；不要把账号、密码、Token、生产配置或实际数据库写入任何文档。

## 发布边界

整理规范和文档不提升产品版本、不创建 Tag、不替换已有 Release。正式 EXE 仍只由 GitHub Actions Windows Runner 执行 `build.ps1` 生成，Release 复用同次构建并自检的两个 EXE 及实际 SHA256，不重复构建或上传本机产物。
