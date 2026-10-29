# 仓库结构与维护规范

当前公共仓库面向 Linux 一键脚本、独立 Docker Compose、共享 Telegram Bot 和两种存储网关。主分支只维护当前产品文档，不提供桌面部署器下载、构建和跨项目迁移教程。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `install.sh`、`install-lan.sh` | 公网、可信内网安装与管理；保留公开 URL 和受支持参数 |
| `src/tg2cloud/` | 共享 Bot、CLI、部署、传输、存储、持久化和监测 |
| `src/tg2cloud/compose/` | 独立 Compose 初始化、离线包和可选宿主 HTTPS |
| `src/tg2cloud/addons/external_webdav/` | 统一菜单内按需管理的只读附加功能 |
| `scripts/run_source.py` | 不依赖当前目录或 Bot 依赖的源码入口 |
| `packaging/` | Dockerfile、两 Edition Compose、部署钩子和必要薄入口 |
| `requirements/`、`pyproject.toml` | 唯一依赖定义、统一工具生成的锁文件及 Ruff 配置 |
| `tests/` | Bot、CLI、任务、恢复、资源、Docker、网关和协议回归 |
| `docs/` | 当前安装、使用、运维和开发教程 |
| `website/` | 独立静态文档站源码、文章及测试 |
| `assets/brand/` | 正式品牌资源唯一来源 |
| `.github/` | 工作流、检查工具、Dependabot、贡献与安全政策 |

根目录保留标准配置、README、许可证、版本记录和轻量入口；不为了目录美观移动稳定核心。两种部署方式互不接管，源码整理不迁移安装目录、容器、网络、数据库或 Session。

## 开发和测试

开发环境、模块边界、载荷组装、指纹和测试命令见[开发指南](DEVELOPMENT.md)，贡献要求见[贡献指南](../../.github/CONTRIBUTING.md)。不恢复桌面依赖，不引入无必要的大型框架；公共构建不能依赖维护者本地文件。

`pyproject.toml` 的 `[tool.ruff]` 统一配置，保留 Python 3.10 目标及原规则。`.editorconfig` 管编辑器，`.gitattributes` 管 Git 换行，两者职责不同。保留 Markdown 语义空白和品牌二进制，不做无关格式化。

`.github/scripts/check_repository.py` 枚举 tracked／未被忽略的新文件，检查公共输入、禁止产物和文档索引。强制跟踪的配置、数据库、Session 及旁文件即使被 ignore 仍应拒绝；检查不是完整秘密内容或 Git 历史扫描。完整回归使用干净公共副本，不依赖本地归档。

## 文档分工

README 保持简洁，详细导航指向[仓库文档目录](../README.md)。仓库文档应能独立阅读，网站也可覆盖同主题，不为跨入口去重删掉必要教程。

| 主题 | 当前正文 |
| --- | --- |
| 公网、内网、Compose 部署 | VPS-INSTALL、LAN-INSTALL、COMPOSE |
| 网关与首次转存 | STORAGE、BOT-USAGE |
| 命名、监听、家庭与可选设置 | NAMING、LISTENING、FAMILY-SHARING、FEATURE-ENHANCEMENTS |
| 维护、配置、故障恢复与备份 | OPERATIONS、CONFIGURATION、RECOVERY、BACKUP-RESTORE |
| HTTPS、外部只读入口与卸载 | DOCKER-NGINX、external-webdav、UNINSTALL |
| 版本事实、当前验证与发布步骤 | CHANGELOG、当前发布记录、RELEASE-CHECKLIST |

当前教程不逐版追加旧 pin、历史测试统计或旧 UI；更新实际步骤并保留必要兼容说明。TG2Cloud 的全版本功能记录保留在 CHANGELOG，旧验收证据使用固定历史提交链接，不能把它们当作当前版本验收。

删除或合并文章时，同步 README、文档索引、网站导航、来源映射、站内链接与测试。仍有效的书签可映射到对应当前章节，不保留指向已删除资源的下载按钮。新增公开 `docs/` Markdown 必须进入文档目录。

## 用户数据、品牌与许可

新装 `data/tg2cloud.db`；已有唯一 `data/tg115.db` 继续使用。旧变量只作兼容读取，不由文档整理自动重命名、迁移或删除。数据库、Session、网关账号和云端文件保护优先于命名统一。

保留 MIT 许可证、原版权与上游 TG115 致谢；移除旧产品教程不等于移除来源说明。正式 Logo／Icon 使用 `assets/brand/`，不重绘或覆盖。

本地 `.venv/`、私有配置、内部审计、工作记录、legacy 和恢复 ZIP 不作为公共依赖，也不作为清理目标。构建输出写入忽略的 `build/`、`website/dist/`，不提交用户数据或测试秘密。

## 发布边界

版本唯一来源、helper A／入口 B、源码资产、原生多架构镜像、两版 Compose 包和实际下载核验按[发布检查清单](RELEASE-CHECKLIST.md)执行。正式业务仍只取稳定 Release，不改为 moving main；不移动历史 Tag 或替换发布资产。

文档更新不代表已经更新用户 VPS 或上线网站。未经本轮明确授权，不提交、推送、创建 Tag、发布镜像或连接真实实例。缺少 Linux／Docker／网关条件时如实列出未执行项。
