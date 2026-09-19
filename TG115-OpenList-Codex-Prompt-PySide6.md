# TG115-OpenList：Codex 完整开发提示词

> 用途：将下面整段内容直接交给 Codex，在**当前尚未进行本次 OpenList 改造的 TG115 项目**基础上，沿用项目已经存在的**新版 PySide6 图形化部署器 UI**，开发独立的 OpenList 版本。
>
> 目标不是替换现有 CloudDrive2 中转方案，而是提供两个并列的 **PySide6 部署器**：
>
> - `TG115-CloudDrive2-Deployer.exe` → PySide6 UI → TG115 + CloudDrive2 + 115
> - `TG115-OpenList-Deployer.exe` → PySide6 UI → TG115 + OpenList + 115
>
> **最终构建和发布只保留以上两个部署器 EXE。原 CloudDrive2 的 Tkinter 轻量兼容版退出本轮新版本的使用、构建与发布，不再作为第三个程序提供。**
>
> 两套程序部署数据相互独立、互不覆盖，用户可以按自己的需要选择。共用源码与组件不等于合并为一个带后端选择器的 EXE。

---

## 零、本轮补充确认：UI 基线与最终产物（硬性要求）

### 0.1 当前基线

按项目维护者补充，当前 TG115 的 CloudDrive2 方案已经提供两个桌面程序：

```text
当前 CloudDrive2 方案
├── 新版 PySide6 图形化部署器
└── 原 Tkinter 界面的轻量兼容版
```

“尚未修改项目”是指**尚未进行本次 OpenList 改造**，不是说项目还没有 PySide6 UI。请先在当前工作区核实两套入口及其构建关系；不要跳过现有新版 UI，退回较旧上游版本重新开发。

### 0.2 本轮最终结果

```text
本次修改后的项目
├── TG115-CloudDrive2-Deployer.exe
│   └── 保留现有新版 PySide6 UI，继续使用 CloudDrive2
└── TG115-OpenList-Deployer.exe
    └── 从同一套现有 PySide6 UI 修改适配，使用 OpenList
```

**是“保留一个 PySide6 版 + 新增一个 PySide6 版”，不是“原来的两个 EXE + 新增第三个 EXE”。**

### 0.3 不可偏离的边界

1. OpenList 版必须以**项目现有新版 PySide6 图形化部署器**为 UI 基线，不以 Tkinter 轻量版为基线。
2. 不重新设计一套与现有项目无关的界面；延续现有页面结构、布局、主题、控件风格和交互习惯，仅对 OpenList 初始化、管理入口和 WebDAV 引导作必要适配。
3. CloudDrive2 的 PySide6 版继续保留，原有部署、隧道、网络修复、WebDAV 验收等已实现功能不能因本次改造被删减。
4. 原 Tkinter 轻量兼容版停止作为正式产品使用：从活动入口、打包目标、发布工作流、当前版本下载入口及使用说明中退出。
5. 若 Tkinter 入口文件还混有共用部署逻辑，先提取并保留必要逻辑，再退役旧 UI；不得因为删旧界面误删 SSH、配置生成或远端部署功能。
6. 最终交付的部署器 EXE 只有两个，均为 PySide6；不得新增 Tkinter/OpenList 兼容版，也不得用 Tkinter 作为 PySide6 启动失败时的备用入口。
7. OpenList 隧道仍固定为 `127.0.0.1:5244 → VPS 127.0.0.1:5244`。本地端口占用时提示处理，不自动切换端口。
8. 本章限定后文“保留原版”“复用现有 UI”“沿用打包方案”的含义；这些表述**不包含继续保留 Tkinter EXE**。

---

## 一、你的角色

你现在负责对当前 TG115 项目进行一次**保守式二次开发**：保留 CloudDrive2 的新版 PySide6 部署器，基于该 UI 新增独立的 `TG115-OpenList` PySide6 部署器，并退役原 Tkinter 轻量兼容版的活动入口和构建发布。

请先完整阅读、分析当前仓库，再开始修改。不要根据文件名或我下面的描述直接猜测现有实现。

开发原则：

1. **优先复用原 TG115 已经稳定工作的逻辑。**
2. 不要无意义重构 Telegram 下载、SQLite 队列、任务恢复、流式传输等成熟模块。
3. OpenList 版必须作为**独立 PySide6 版本**存在，不替换、不破坏 CloudDrive2 的 PySide6 版；Tkinter 轻量兼容版按本轮要求退役。
4. 所有涉及凭据的逻辑必须以“用户电脑 ↔ 用户自己的 VPS”为边界，不允许加入任何遥测、上传、回传或第三方收集逻辑。
5. 不要为了界面漂亮牺牲可靠性；先保证部署、隧道、WebDAV、任务和验收逻辑稳定。
6. 不得声称某功能已验证，除非实际测试过。
7. UI 复用、构建脚本、Release 产物、README 与测试清单必须一致落实“两个 PySide6 EXE、无 Tkinter 兼容版”。

---

# 二、项目目标

在保留 CloudDrive2 的 PySide6 部署器的前提下，新增一个独立的 Windows **PySide6 EXE 部署器**：

```text
TG115-OpenList-Deployer.exe
```

它必须从**当前项目新版 PySide6 图形化部署器 UI**适配而来，不从 Tkinter 版改造，也不重新搭建另一套不相干的 UI。

新链路为：

```text
Telegram
   ↓
私人 Telegram Bot
   ↓
TG115
   ↓
rclone
   ↓
OpenList WebDAV
   ↓
OpenList 115 Open 驱动
   ↓
115
```

现有 CloudDrive2 版逻辑仍然保留：

```text
Telegram
   ↓
私人 Telegram Bot
   ↓
TG115
   ↓
rclone
   ↓
CloudDrive2 WebDAV
   ↓
115
```

**本次不要把 CloudDrive2 和 OpenList 合并到同一个 EXE 中选择。**

最终要交付的产品只有以下两个：

| EXE | UI 技术与基线 | 中转方式 |
|---|---|---|
| `TG115-CloudDrive2-Deployer.exe` | 当前项目已有的新版 PySide6 图形化部署器 | CloudDrive2 |
| `TG115-OpenList-Deployer.exe` | 在同一套新版 PySide6 UI 上修改适配 | OpenList |

不再生成、维护或发布原 Tkinter 轻量兼容版 EXE。

OpenList 版是一个新的选择，主要面向不希望使用 CloudDrive2 会员方案的用户。

---

# 三、第一步：先审计现有仓库

在修改任何代码之前，请先完成以下工作：

1. 阅读仓库目录结构。
2. 分别找出**新版 PySide6 部署器**与**原 Tkinter 轻量兼容版**的真实入口，确认哪些业务逻辑由两者共用。不要仅凭 `installer.py` 等文件名猜测 UI 类型。
3. 找出当前 PySide6 EXE 的实际构建方式、打包脚本、spec 文件及发布工作流，并识别所有会生成 Tkinter 兼容版的目标。
4. 找出远端 VPS 安装脚本。
5. 找出 Docker Compose 文件。
6. 找出 TG115 Bot 的主程序。
7. 找出 rclone/WebDAV 配置生成逻辑。
8. 找出 CloudDrive2 健康检查与修复逻辑。
9. 找出 `manage.sh verify` 或等效的目的端验收逻辑。
10. 找出配置文件、SQLite、下载目录、日志目录的实际位置。
11. 找出当前 Telegram Bot 支持的全部命令与任务状态机。
12. 确认当前“大文件超过本地预算后采用流式模式”的实际实现，不要凭描述自行重写。
13. 找出现有 PySide6 的主窗口、导航、表单、主题、图标、资源文件、日志面板、任务线程和信号/槽组织方式，形成 OpenList 页面适配清单。
14. 搜索 Tkinter 兼容版在代码入口、依赖、构建脚本、持续集成、Release、README、下载页中的引用，记录每项退役方式。
15. 先记录 CloudDrive2 PySide6 版的功能基线，确保新增 OpenList 后原部署流程不回归。

如果当前工作区找不到维护者所说的新版 PySide6 部署器，请说明缺少哪个分支或文件，并请求提供正确基线；**不得自行改用 Tkinter 版，不得凭想象重建所谓“现有新版 UI”。**

审计完成后，在仓库中建立一份开发记录，例如：

```text
docs/OPENLIST_IMPLEMENTATION.md
```

至少记录：

- 当前 TG115 架构；
- 实际采用的新版 PySide6 入口、UI 组件和构建目标；
- Tkinter 兼容版入口与构建发布退役清单；
- 两个 PySide6 EXE 的入口、资源、产品标识和产物名称对应表；
- CloudDrive2 相关耦合点；
- 哪些代码可以复用；
- 哪些位置必须为 OpenList 新增适配；
- 本次实际修改的文件；
- 已完成测试；
- 尚未测试内容；
- 已知限制。

如果仓库已经有类似开发日志，请沿用现有规范，不要重复创建无意义文件。

---

# 四、命名规范

请统一使用下面的命名。

## 4.1 CloudDrive2 版

保留的正式桌面程序为：

```text
TG115-CloudDrive2-Deployer.exe
```

UI：**当前项目已有的新版 PySide6 图形化部署器**，不再提供 Tkinter 轻量兼容版。

窗口标题：

```text
TG115 · CloudDrive2 部署器
```

容器统一命名为：

```text
tg115-clouddrive2-bot
tg115-clouddrive2
```

Docker Network 推荐：

```text
tg115-clouddrive2-net
```

安装目录推荐：

```text
/opt/tg115-clouddrive2
```

> 注意：当前已有项目如果仍然使用旧名字，本次 OpenList 开发不要为了统一名字而强行改坏现有生产版。可以把这作为后续 CloudDrive2 版维护事项记录下来。

## 4.2 OpenList 版

必须使用：

```text
tg115-openlist-bot
tg115-openlist
```

Docker Network：

```text
tg115-openlist-net
```

VPS 安装目录：

```text
/opt/tg115-openlist
```

Windows EXE：

```text
TG115-OpenList-Deployer.exe
```

UI：**从项目现有新版 PySide6 图形化部署器修改适配**。

窗口标题建议：

```text
TG115 · OpenList 部署器
```

首个正式版本：

```text
v1.0.0
```

---

# 五、两套程序必须完全隔离

OpenList 版不能覆盖 CloudDrive2 版的：

- Docker 容器；
- Docker Network；
- 安装目录；
- SQLite 数据库；
- 下载目录；
- `.env`；
- rclone 配置；
- 日志；
- 配置备份。

OpenList 版建议目录结构类似：

```text
/opt/tg115-openlist/
├── docker-compose.yml
├── .env
├── manage.sh
├── bot/
├── data/
├── downloads/
├── config/
├── backups/
└── openlist-data/
```

具体结构优先服从原 TG115 项目实际设计，但必须实现**完整隔离**。

用户即使在同一台 VPS 同时安装：

```text
TG115 + CloudDrive2
```

和：

```text
TG115 + OpenList
```

也不能发生容器名、端口、网络、目录、任务数据库冲突。

---

# 六、OpenList 的部署方式

OpenList 由 EXE 自动部署到用户自己的 VPS。

建议 Docker 服务：

```text
tg115-openlist
```

OpenList 管理端口使用默认内部端口：

```text
5244
```

**不要默认把 OpenList 管理后台直接暴露到公网。**

优先绑定：

```text
127.0.0.1:5244:5244
```

或者采用等效的仅本机可访问方案。

TG115 Bot 与 OpenList 加入同一个 Docker Network：

```text
tg115-openlist-net
```

因此 Bot 访问 OpenList WebDAV 时优先使用 Docker 内部地址：

```text
http://tg115-openlist:5244/dav/
```

不要让 Bot 为了访问同机 OpenList 而绕公网域名、Cloudflare 或 Nginx。

---

# 七、OpenList 管理后台：必须提供 SSH 隧道

OpenList 版 EXE 必须像现有 CloudDrive2 版一样，为普通用户隐藏 SSH 隧道细节。

提供按钮：

```text
[打开 OpenList]
```

点击后：

1. 检查 VPS 上 `tg115-openlist` 是否运行；
2. 检查 Windows 本地 `5244` 端口是否被占用；
3. OpenList SSH 隧道的**本地端口固定使用官方默认端口 `5244`**，不要自动随机选择其他端口；
4. 建立：

```text
Windows 127.0.0.1:5244
        ↓
SSH Tunnel
        ↓
VPS 127.0.0.1:5244
        ↓
OpenList
```

5. 自动打开系统默认浏览器：

```text
http://127.0.0.1:5244
```

6. 如果 Windows 本地 `5244` 已被其他程序占用，不要自动切换为 `15244`、随机端口或其他备用端口。应明确提示用户：

```text
❌ 无法打开 OpenList 管理后台

本地端口 5244 已被占用。
请先关闭占用该端口的程序，然后重新点击“打开 OpenList”。

[重新检测]
```

这样可以保证部署器、教程、截图和用户访问地址始终统一为 OpenList 官方默认端口 `5244`。

用户不需要自己执行：

```bash
ssh -L ...
```

也不需要理解端口转发。

EXE 关闭隧道时应正确释放资源，不留下僵尸 SSH 连接。

---

# 八、OpenList 首次管理员密码：这是和 CloudDrive2 最大的 UX 区别

CloudDrive2 是用户进入网页后登录自己的 CloudDrive2 账号。

OpenList 不同：

```text
部署 OpenList
↓
VPS / 容器首次生成管理员初始化信息
↓
用户需要管理员账号/密码才能进入后台
```

因此 OpenList 版 EXE 必须专门优化首次使用体验。

## 8.1 新安装时

部署成功后，EXE 自动：

1. 获取 OpenList 容器首次启动日志或使用 OpenList 当前版本提供的官方初始化方式；
2. 解析首次管理员信息；
3. 在 EXE 中清晰显示；
4. 提供：

```text
[显示密码]
[隐藏密码]
[复制密码]
[打开 OpenList]
```

界面示意：

```text
OpenList 初始化

OpenList              ✅

初始管理员账号： admin
初始管理员密码： ••••••••••••

[显示] [复制密码] [打开 OpenList]
```

不要让普通用户自己 SSH 到服务器执行：

```bash
docker logs tg115-openlist
```

再手工在日志里找密码。

## 8.2 已初始化过的 OpenList

如果检测到这是已有实例：

```text
检测到 OpenList 已初始化
```

只显示：

```text
[打开 OpenList]
```

并提示：

```text
请使用您之前设置的管理员账号登录。
```

**严禁每次启动部署器都自动重置管理员密码。**

## 8.3 管理员密码恢复

如需要提供恢复功能，只允许放到：

```text
高级工具
```

而且必须：

- 明确说明影响；
- 二次确认；
- 不作为正常部署流程的一部分。

## 8.4 兼容 OpenList 版本差异

不要硬编码某个版本固定日志格式。

如果不同 OpenList 版本初始化方式不同：

1. 优先使用官方支持的命令/API；
2. 其次兼容日志解析；
3. 如果无法可靠获得初始密码，要给出清晰提示和一键复制的官方命令，不要静默失败。

---

# 九、OpenList 中的 115 配置全部由用户自己完成

部署器**不负责收集或代填**：

```text
115 账号
115 密码
115 Cookie
115 Access Token
115 Refresh Token
115 OAuth 凭据
```

流程应当是：

```text
EXE 部署 OpenList
        ↓
EXE 建立 SSH Tunnel
        ↓
用户打开自己的 OpenList 后台
        ↓
用户自行添加 115 Open
        ↓
用户自行完成授权/Token 配置
        ↓
用户自行创建 Telegram 目标目录
```

EXE 不解析 OpenList 中的 115 Token，也不需要知道这些内容。

请在 UI/README 明确说明：

> 115 相关授权全部由用户直接在自己 VPS 上的 OpenList 后台完成，部署器不会读取、上传或收集这些信息。

---

# 十、WebDAV 用户配置：重点优化用户体验

这是 OpenList 版最重要的交互设计之一。

我们不希望出现下面这种麻烦流程：

```text
用户进入 OpenList
↓
自己想用户名
↓
自己想密码
↓
回来 EXE
↓
再次输入用户名
↓
再次输入密码
```

应改成：

```text
EXE 本地生成推荐 WebDAV 凭据
↓
用户复制到 OpenList
↓
回来直接点击测试
```

## 10.1 推荐用户名

默认：

```text
tg115
```

提供按钮：

```text
[复制用户名]
```

允许高级用户修改，但普通用户无需修改。

## 10.2 推荐密码

EXE 在**用户本地电脑**随机生成强密码，例如：

- 长度建议 24～32 字符；
- 使用密码学安全随机源；
- 避免容易在表单中产生歧义或转义问题的字符组合；
- 不要使用固定密码；
- 不要上传到任何服务器。

UI：

```text
WebDAV 密码：••••••••••••••••••••••••

[显示]
[复制密码]
[重新生成]
```

## 10.3 不要求用户重复输入

EXE 已经生成了用户名和密码，因此在当前部署会话中应继续保留这些值。

用户在 OpenList 中创建用户后，只需要返回 EXE 点击：

```text
[测试 WebDAV]
```

无需再次填写。

如果用户关闭 EXE 后重新进入，应提供：

```text
使用已有 WebDAV 配置
```

高级入口，允许手动填写已有用户名/密码，而不是强行覆盖远端用户。

## 10.4 目标基本路径

建议引导用户在 OpenList 中创建：

```text
/115/Telegram
```

其中：

```text
/115
```

只是示例挂载名称，实际应允许用户根据自己的 OpenList 挂载路径调整。

推荐做法是：

```text
OpenList 用户：tg115
基本路径：用户实际的 Telegram 目标目录
```

这样 WebDAV 用户登录后看到的：

```text
/
```

就是最终 TG115 上传目录。

因此 TG115 端：

```text
TARGET_PATH=
```

可以保持为空。

## 10.5 提供复制按钮

界面至少提供：

```text
推荐用户名：tg115
[复制]

随机密码：••••••••••••••••••••
[显示] [复制] [重新生成]

建议基本路径：/115/Telegram
[复制]
```

---

# 十一、OpenList 操作向导

在 EXE 中加入一个清晰的“请在 OpenList 中完成以下设置”区域。

例如：

```text
① 使用初始管理员账号登录 OpenList
② 添加 115 Open 存储
③ 在 115 中准备 Telegram 目标目录
④ 在 OpenList 中创建普通用户 tg115
⑤ 把该用户基本路径设置为 Telegram 目标目录
⑥ 给该用户开启 WebDAV 所需文件权限
⑦ 返回部署器，点击「测试 WebDAV」
```

不要假装这些步骤已经自动完成。

可以提供可视化勾选项供用户自行确认，但不要把手动勾选状态冒充为自动检测结果。

---

# 十二、OpenList WebDAV 权限提示

部署器需要明确提醒用户：WebDAV 账号至少需要完成 TG115 验收所需权限。

包括：

- 读取/列目录；
- 上传/创建文件；
- 创建目录（如果 TG115 会用到）；
- 重命名；
- 删除；
- WebDAV 相关权限。

不要只写一句“开启 WebDAV”。

如果当前 OpenList 版本权限名称与上面不同，请根据实际 OpenList UI/文档调整提示。

---

# 十三、WebDAV URL 不让普通用户填写

因为：

```text
tg115-openlist-bot
```

和：

```text
tg115-openlist
```

在同一个 Docker Network 中，内部 URL 可以由程序固定为：

```text
http://tg115-openlist:5244/dav/
```

因此普通 UI 不应该再显示一个复杂的：

```text
WebDAV URL：________
```

高级设置中可以允许覆盖，但默认隐藏。

这能显著减少用户配置错误。

---

# 十四、TG115 原有功能必须尽量完整保留

OpenList 版不是重写 TG115。

以下能力如果原项目已经存在，必须保留：

- Telegram Bot 登录；
- 只允许指定 Telegram 数字 ID；
- SQLite 持久化队列；
- 重启恢复；
- 排队机制；
- 任务状态；
- 下载进度；
- 上传进度；
- 失败重试；
- 取消任务；
- 磁盘保护；
- 本地任务预算；
- 超预算大文件的流式处理；
- 目的端验证；
- 本地文件清理；
- 原有 Bot 命令。

包括但不限于原项目实际存在的：

```text
/start
/help
/queue
/status
/performance
/task <id>
/confirm <id>
/retry <id>
/cancel <id>
```

请以仓库实际实现为准。

不要因为 OpenList 适配而删除已有成熟功能。

这里保留的是 TG115 的业务能力及 CloudDrive2 的 PySide6 部署体验，**不要求保留 Tkinter UI 或其 EXE**。如果某项必要功能目前只存在于 Tkinter 入口，应迁移到对应 PySide6 部署器或共用业务层，再退役旧入口。

---

# 十五、默认磁盘参数

OpenList 版建议默认：

```text
LOCAL_TEMP_BUDGET_GB=20
MIN_FREE_DISK_GB=8
TZ=Asia/Shanghai
```

这些值应在 EXE 中可配置。

但要清楚：

```text
LOCAL_TEMP_BUDGET_GB=20
```

代表本地任务预算，不是划出固定 20GB 分区。

如果原 TG115 有更复杂的资源控制逻辑，请保留原有计算方式。

---

# 十六、rclone / WebDAV 适配

OpenList 版应继续使用现有成熟的 rclone 传输逻辑，而不是为了换 OpenList 重新写一套 HTTP 上传器。

建议 remote 的逻辑语义改成中性名称，例如：

```text
webdav
storage
remote
```

不要在新的 OpenList 项目中到处残留：

```text
CD2_...
clouddrive2_...
```

但不要为了“名字好看”而大规模改动 TG115 核心代码。

优先把真正与 CloudDrive2 强耦合的部分抽离出来。

OpenList WebDAV remote 应由：

```text
URL
用户名
密码
```

生成。

其中 URL 默认内部固定：

```text
http://tg115-openlist:5244/dav/
```

用户主要只需要处理 WebDAV 用户名/密码。

---

# 十七、部署状态不能因为“还没配置 115”就报失败

这是非常重要的 UX 要求。

用户点击：

```text
[一键部署基础环境]
```

完成后，OpenList 里还没有添加 115 是正常状态。

不要显示：

```text
部署失败
```

正确状态应类似：

```text
Docker              ✅
TG115 Bot            ✅
OpenList             ✅
Docker Network       ✅

目标存储             ⏳ 等待用户在 OpenList 中配置
WebDAV               ⏳ 等待用户创建 tg115 用户
```

部署和“最终目的端验收”必须分成两个阶段。

---

# 十八、完整的 EXE 交互流程

以下五步是**业务操作顺序与信息组织要求，不是要求重新设计一套五页 UI**。必须把这些内容映射到项目现有新版 PySide6 部署器的页面、分区、卡片或导航结构中。

如果当前 PySide6 UI 已采用分区表单、侧边栏或其他布局，应保留该结构，不得为了机械对应下面的 Step 1～5 而重做界面。CloudDrive2 版延续原操作路径，OpenList 版只适配必要的中转配置区。

两版的共用操作沿用相同控件与交互方式；OpenList 特有的首次管理员密码、复制按钮和 WebDAV 指引放入现有风格的组件。

## Step 1 / 5：连接 VPS

```text
服务器地址
SSH 端口
SSH 用户名
SSH 密码 / SSH Key

[测试连接]
```

要求：

- 清晰显示连接结果；
- 不把 SSH 密码输出到日志；
- 支持已有项目的认证方式；
- 超时后给明确提示。

---

## Step 2 / 5：Telegram

```text
Bot Token
API ID
API Hash
允许使用的 Telegram 数字 ID

本地任务预算：20 GB
最低磁盘空间：8 GB
时区：Asia/Shanghai
```

要求：

- 密码/Token 类字段默认遮罩；
- 可以显示/隐藏；
- 日志中脱敏；
- 不发送到第三方。

---

## Step 3 / 5：部署 OpenList

按钮：

```text
[一键部署基础环境]
```

完成后显示：

```text
OpenList             ✅
TG115 Bot            ✅
Docker Network       ✅
```

如果为首次初始化，显示：

```text
初始管理员密码：••••••••••••

[显示]
[复制]
[打开 OpenList]
```

用户此时进入 OpenList，自行配置 115 Open。

---

## Step 4 / 5：配置 WebDAV

显示 EXE 本地生成的：

```text
推荐用户名：tg115
[复制]

推荐密码：••••••••••••••••••••••
[显示] [复制] [重新生成]

建议基本路径：/115/Telegram
[复制]
```

同时显示配置步骤。

按钮：

```text
[打开 OpenList]
[测试 WebDAV]
```

用户无需再次输入 EXE 已生成的用户名/密码。

---

## Step 5 / 5：最终验收

建议显示：

```text
Telegram Bot        ✅
OpenList            ✅
OpenList WebDAV     ✅
目标目录            ✅
上传                ✅
重命名              ✅
删除                ✅

TG115_DESTINATION=OK
```

按钮：

```text
[完成]
[查看状态]
[查看日志]
[打开 OpenList]
```

---

# 十九、WebDAV 验收逻辑必须保留并增强

现有 TG115 如果已经有：

```bash
manage.sh verify
```

优先复用和改造。

OpenList 版建议完整验证：

```text
1. OpenList 容器健康
2. Docker 内部 WebDAV 可访问
3. WebDAV 用户认证成功
4. 可以列目录
5. 上传一个很小的随机测试文件
6. 获取远端文件信息/大小
7. 远端重命名
8. 再次检查
9. 删除测试文件
10. 确认清理成功
```

最后输出机器可解析的状态，例如：

```text
TG115_STORAGE_BACKEND=openlist
TG115_OPENLIST=OK
TG115_WEBDAV=OK
TG115_UPLOAD=OK
TG115_RENAME=OK
TG115_DELETE=OK
TG115_DESTINATION=OK
```

如果中间失败，应保留明确错误码/阶段。

不要把“HTTP 连接成功”错误地当成“115 最终写入成功”。

---

# 二十、错误信息必须面向普通用户

不要把：

```text
401 Unauthorized
```

直接作为主提示。

例如 WebDAV 登录失败时，主界面显示：

```text
❌ 无法登录 OpenList WebDAV

可能原因：
1. 尚未创建 tg115 用户
2. OpenList 中填写的密码与部署器推荐密码不一致
3. 该用户没有 WebDAV/上传相关权限
4. 用户基本路径配置错误

[复制用户名]
[复制密码]
[打开 OpenList]
[再次测试]
```

然后提供：

```text
[查看详细日志]
```

高级用户才能看到完整：

```text
HTTP 401 Unauthorized
rclone ...
```

其他错误同理，例如：

- 403 → 权限不足；
- 404 → WebDAV 路径/基本路径问题；
- Connection refused → OpenList 未运行；
- timeout → 网络/容器异常；
- No space left → VPS 磁盘不足。

---

# 二十一、OpenList 大文件可靠性：必须谨慎

本项目主要传输 Telegram 视频，大文件可能为：

```text
500 MB
1 GB
2 GB
5 GB
甚至更大
```

因此不能只验证 1KB 测试文件就宣布生产可用。

开发完成后至少设计并记录下面的手动测试方案：

```text
10~100 MB
500 MB
1 GB
2 GB
5 GB
```

记录：

- Telegram 下载是否完成；
- rclone 上传是否完成；
- OpenList 是否正确返回完成状态；
- 115 中是否最终出现文件；
- 文件大小是否正确；
- 本地临时文件是否按预期清理；
- 失败后重试是否会重复生成错误副本；
- 容器重启后任务是否恢复；
- 流式模式是否仍然正常。

如果本地环境无法实际完成 GB 级测试，请在开发日志中明确写：

```text
未完成真实 GB 级文件实测，需要人工验收。
```

不要伪造“已验证”。

---

# 二十二、不要改变 TG115 对大文件的成熟策略

如果原 TG115 已经实现：

```text
文件在本地预算内
→ 普通本地任务
```

和：

```text
单文件超过本地预算
→ 流式传输
```

OpenList 版继续沿用。

不要因为换 OpenList 就把所有文件强制落盘，也不要强制所有文件流式传输。

只在 OpenList WebDAV 兼容性确实要求改变时，才进行最小必要修改，并记录原因。

---

# 二十三、隐私与安全要求

这是必须满足的硬性要求。

## 23.1 禁止收集

程序不得上传、遥测、回传或收集：

```text
SSH 密码
SSH 私钥
Telegram Bot Token
Telegram API Hash
Telegram 登录信息
OpenList 管理员密码
OpenList WebDAV 密码
115 Access Token
115 Refresh Token
115 Cookie
115 OAuth 数据
```

## 23.2 日志脱敏

普通日志、诊断包、错误上报文本中必须脱敏：

```text
Bot Token: ********
API Hash: ********
WebDAV Password: ********
SSH Password: ********
```

不得把完整 `rclone.conf` 直接显示给用户或写入公开日志。

## 23.3 本地生成 WebDAV 密码

使用安全随机源。

生成过程只在用户本地电脑进行。

## 23.4 VPS 配置文件权限

保存敏感配置的文件应限制权限，例如：

```bash
chmod 600
```

具体以 Linux 实际文件结构为准。

## 23.5 不默认公网开放管理后台

OpenList 管理后台默认只通过 SSH Tunnel 访问。

不要默认：

```text
0.0.0.0:5244
```

直接暴露公网。

---

# 二十四、隐私说明文案

在 EXE 和 README 中加入类似说明：

> 所有 SSH、Telegram、WebDAV 与网盘相关凭据仅用于您的电脑与您自己的 VPS 之间的配置和连接。部署器不包含凭据遥测或第三方回传功能。115 账号及 115 Open 授权由用户直接在自己的 OpenList 后台完成，部署器不会读取或收集这些内容。

文案可以优化，但含义必须保留。

---

# 二十五、管理功能

OpenList 版 EXE 至少提供：

```text
[测试 SSH]
[一键部署基础环境]
[打开 OpenList]
[测试 WebDAV]
[最终验收]
[查看状态]
[查看日志]
[重启 TG115 Bot]
[重启 OpenList]
[备份配置]
```

如果原项目已经有更新、修复、卸载等功能，应尽量保留对应能力。

但删除/卸载功能必须二次确认。

不要默认删除用户 OpenList 数据。

---

# 二十六、manage.sh 建议

OpenList 版建议保留一个统一管理脚本：

```text
/opt/tg115-openlist/manage.sh
```

支持至少：

```bash
manage.sh status
manage.sh logs
manage.sh restart
manage.sh verify
manage.sh backup
```

如果原项目已有命令体系，沿用原体系即可。

不要为了符合本提示词而破坏当前成熟的 CLI。

---

# 二十七、备份与迁移

OpenList 版应优先使用容易备份的宿主机目录绑定，而不是把所有关键数据藏在匿名 Docker Volume 中。

用户应能够通过备份：

```text
/opt/tg115-openlist
```

覆盖主要配置、数据库和 OpenList 持久化数据。

但如果 OpenList 官方推荐的数据目录结构不同，请正确适配。

备份功能必须避开临时大文件，避免把几十 GB 下载缓存一起打包。

建议备份内容：

- docker-compose；
- `.env`；
- TG115 数据库；
- rclone 配置；
- OpenList 持久化配置；
- 其他必要配置。

不建议默认备份：

- 临时下载；
- 巨型缓存；
- 可重建镜像。

---

# 二十八、EXE UI：必须沿用现有新版 PySide6 部署器

## 28.1 唯一 UI 基线

本项目已有新版 **PySide6 图形化部署器**。本次应在这套 UI 上开发，不是泛泛地“任意复用一个现有界面”。

必须保留并复用仓库中实际存在的：

- 主窗口与页面/分区组织；
- 主题、配色、字体、间距、按钮和状态样式；
- 图标、品牌资源及资源加载方式；
- VPS、Telegram、存储、运行参数等共用表单；
- 日志区域、状态反馈、错误对话框及高级工具入口；
- 已实现的 SSH、隧道、后台任务与进度更新交互。

不得把本提示词中的文本示意图当成新 UI 设计稿，推倒当前新版界面重做。不要以旧 Tkinter 界面、网页套壳或另一套 GUI 技术替代现有 PySide6。

## 28.2 两版 UI 如何复用

建议保留一个可复用的 PySide6 UI/业务基础层，再提供两个明确的产品入口或构建目标：

```text
现有 PySide6 UI + 共用部署/隧道/日志逻辑
                 │
        ┌────────┴────────┐
        │                 │
CloudDrive2 产品入口    OpenList 产品入口
        │                 │
CloudDrive2 PySide6 EXE OpenList PySide6 EXE
```

具体文件组织服从仓库实际结构，不强行新增上述名称的目录。

允许在内部用产品配置驱动标题、容器名、端口、资源和存储适配；**不允许在用户界面里合并成一个 EXE 后再选择 CloudDrive2/OpenList**。应避免把整套 PySide6 UI 复制成两份长期分叉的重复代码。

## 28.3 OpenList 版的必要差异

在现有 PySide6 UI 中，仅对以下内容作必要适配：

```text
CloudDrive2 登录/管理入口
    ↓
OpenList 首次管理员信息 + 打开后台

CloudDrive2 WebDAV 提示
    ↓
OpenList 普通用户、基本路径及权限指引

CloudDrive2 网络与目的端检查
    ↓
OpenList 网络、WebDAV 与目的端检查
```

增加 OpenList 初始管理员密码的遮罩、显示/隐藏和复制按钮；保留“已有实例不自动重置密码”的边界。

WebDAV 推荐用户名、随机强密码和复制操作应嵌入现有表单；只生成一次并在当前部署会话中复用，不要求用户在网页配置后再回 EXE 重复输入。重新生成密码必须由用户明确操作，不能因切换页面或重绘控件触发。

OpenList 本地隧道固定使用 `127.0.0.1:5244`，仍按第七章处理端口占用，不自动换端口。

## 28.4 CloudDrive2 的 PySide6 版不得功能倒退

保留原有 PySide6 部署器中的已实现功能，包括但不限于：

```text
一键部署基础环境
打开 CloudDrive2 管理页
修复 CloudDrive2 网络
WebDAV 验收
查看状态/日志
已有更新、备份及高级工具
```

以审计得到的真实功能清单为准。退役 Tkinter 不等于删除 CloudDrive2 方案，也不等于缩减新版 PySide6 部署器的功能。

## 28.5 Tkinter 轻量兼容版退役

必须检查并处理：

1. 旧 Tkinter 主入口和桌面启动说明；
2. 旧版 EXE 的构建脚本、spec 目标及持续集成任务；
3. 当前版本 Release 上传清单、下载页和 README 入口；
4. 专属于旧 UI 的资源和依赖；
5. 两版 PySide6 运行路径中可能残留的 Tkinter 导入或回退逻辑。

若旧 UI 文件含有共用业务逻辑，先提取、测试再清理。可通过 Git 历史保留旧实现；确需保留源码归档时，必须明确标注停用并排除在活动入口、构建、打包和发布之外。

不要自动删除用户电脑上已有的旧 EXE，也不要操作用户历史 Release；本次退役限定于**修改后项目的当前代码入口和新版本构建发布**。

## 28.6 交互可靠性

沿用现有 PySide6 的任务线程/信号机制，耗时 SSH、安装、日志读取和验收不能阻塞界面。不要为方便而退回 Tkinter 的消息循环或对话框。

两版都要验证：长任务时窗口可响应、进度和错误能正确显示、复制按钮不泄露到日志、重复点击不会创建重复任务或隧道、关闭窗口可按原有设计妥善处理后台操作。

普通用户不需要知道 Docker Network 名称、不需要填写内部 WebDAV URL、不需要 SSH 找初始密码，也不需要重复输入已生成的凭据；高级细节继续放在现有“高级设置/详细日志”区域。

---

# 二十九、不要加入本次范围之外的功能

本次明确**不做**：

- Telegram 用户账号登录；
- 自动监听频道；
- 绕过禁止转发/内容保护；
- 自动频道订阅；
- 读取 Telegram Desktop tdata；
- rclone crypt；
- CloudDrive2 与 OpenList 合并成一个后端选择器；
- 自动收集 115 Token；
- 远程遥测；
- SaaS 后台；
- 用户账号系统；
- 新的 Tkinter/OpenList 兼容版；
- 第三个轻量版、Legacy 版或混合后端 EXE；
- 与现有新版 PySide6 UI 无关的整套界面重做。

本次范围是：

```text
新增：TG115 Bot + OpenList WebDAV + 115
保留：CloudDrive2 的 PySide6 部署器及原有业务能力
退役：原 Tkinter 轻量兼容版的活动入口、构建与发布
交付：CloudDrive2 / OpenList 两个 PySide6 部署器 EXE
```

---

# 三十、与原作者项目关系

如果这是基于原 TG115 项目的二次开发：

1. 保留原许可证；
2. 保留原作者版权信息；
3. README 中明确致谢原项目；
4. 标明 OpenList 版为二次开发/衍生版本；
5. 不要删除上游作者信息。

如果许可证对衍生发布有特殊要求，严格遵守许可证。

---

# 三十一、README 必须补充

OpenList 版 README 至少包含：

## 项目简介

```text
Telegram Bot → TG115 → rclone → OpenList WebDAV → 115
```

## 两个正式程序与 UI 基线

明确当前版本只提供：

```text
TG115-CloudDrive2-Deployer.exe  → PySide6 图形化部署器
TG115-OpenList-Deployer.exe    → PySide6 图形化部署器
```

OpenList 版沿用项目已有新版 PySide6 UI；用户选择的是中转方案，不是“新版界面或轻量界面”。

说明原 CloudDrive2 的 Tkinter 轻量兼容版已退出当前版本使用、构建与发布。更新 README、当前下载入口、构建说明和截图，避免用户误以为还存在第三个推荐程序。引用旧界面时，只能标明为历史版本，不作为本轮使用入口。

## 和 CloudDrive2 版的区别

说明：

```text
CloudDrive2 版：使用 CloudDrive2 作为 115 WebDAV 中转。
OpenList 版：使用 OpenList 作为 WebDAV 中转，不依赖 CloudDrive2 会员。
两版 UI：均采用项目现有新版 PySide6 图形化部署器。
```

不要贬低任何一个方案。

## 部署流程

简化为：

```text
1. 准备 Telegram 信息
2. EXE 连接 VPS
3. 一键部署
4. 复制 OpenList 初始管理员密码
5. 打开 OpenList
6. 用户自行添加 115 Open
7. 按 EXE 提示创建 tg115 WebDAV 用户
8. 返回 EXE 测试 WebDAV
9. 最终验收
10. Telegram 实际转存测试
```

## 安全说明

明确说明凭据不上传。

## 备份与迁移

写清关键目录。

## 常见问题

至少包括：

- 找不到 OpenList 初始管理员密码；
- OpenList 已初始化；
- WebDAV 401；
- WebDAV 403；
- 目标目录错误；
- VPS 磁盘不足；
- OpenList 后台打不开；
- 5244 本地端口被占用；
- 上传 100% 但远端仍在处理；
- 如何查看日志；
- 如何重新执行目的端验收。

---

# 三十二、建议的错误状态

尽量为部署器定义机器可识别的状态，而不是依赖日志字符串猜测。

例如：

```text
SSH_OK
DOCKER_OK
OPENLIST_CONTAINER_OK
OPENLIST_INIT_REQUIRED
OPENLIST_READY
BOT_OK
WEBDAV_AUTH_OK
WEBDAV_WRITE_OK
WEBDAV_RENAME_OK
WEBDAV_DELETE_OK
DESTINATION_OK
```

UI 根据状态给用户友好文案。

如果现有 TG115 已有统一状态输出格式，请优先兼容。

---

# 三十三、测试要求

至少覆盖：

## 本地 Windows 部署器（两个 PySide6 版本分别测试）

- CloudDrive2 与 OpenList 两个 EXE 均从正确的 PySide6 入口启动；
- OpenList 沿用当前新版 PySide6 布局、主题、组件与日志/状态交互；
- CloudDrive2 的原有 PySide6 功能清单回归通过，尤其是部署、打开后台、网络修复与 WebDAV 验收；
- 不加载 Tkinter UI，不触发旧轻量版入口或 Tkinter 回退路径；
- 部署、隧道、日志、验收等耗时操作不会阻塞 UI；
- 两版标题、图标、产品标识、配置与资源不会串用；
- 在项目支持的 Windows 环境实际启动打包产物，确认 Qt 插件和资源加载；不能实测则标明待验收；
- SSH 成功；
- SSH 失败；
- 密码认证；
- 如果已有 Key 支持则测试 Key；
- 本地 5244 可用；
- 本地 5244 被占用时明确报错且不得自动切换其他端口；
- 隧道固定绑定 `127.0.0.1:5244`；
- 隧道建立；
- 隧道关闭；
- 浏览器打开；
- OpenList 初次管理员信息解析；
- 已初始化 OpenList；
- WebDAV 凭据生成；
- 凭据复制；
- 日志脱敏。

## 构建与发布产物

- 两个明确构建目标分别生成 CloudDrive2 与 OpenList 的 PySide6 部署器；
- 本轮最终发布清单恰好包含两个部署器 EXE；
- 不再生成或上传 Tkinter、Lite、Legacy 等兼容版 EXE；
- 构建脚本、spec、持续集成、README 和下载页对产物的描述一致；
- 不依赖残留的旧 `dist` 产物充当成功构建；
- 在可能的测试环境中确认两版独立启动、独立配置且不会互相覆盖。

## VPS

- 干净环境首次安装；
- 重复运行安装器不破坏已有数据；
- OpenList 容器重启；
- Bot 容器重启；
- VPS 重启后自动恢复；
- Docker Network 正确；
- 关键目录持久化；
- `manage.sh verify`。

## WebDAV

- 正确账号；
- 错误密码；
- 权限不足；
- 错误基本路径；
- OpenList 未启动；
- 上传；
- 重命名；
- 删除。

## TG115

- 小文件；
- 正常本地任务；
- 超预算任务；
- 失败重试；
- 重启恢复；
- 本地清理。

无法自动测试的内容必须明确列入“人工验收”。

---

# 三十四、构建 EXE：只生成两个 PySide6 部署器

## 34.1 沿用当前 PySide6 打包基线

先审计并复用项目**新版 PySide6 部署器**已经采用的 Windows 打包方案。若使用 PyInstaller，则调整其现有脚本/spec；不要照搬旧 Tkinter 兼容版的打包入口，不要为了本次需求擅自更换打包工具。

UI 技术已经确定为 PySide6，不属于待选方案；打包工具与具体文件名以当前仓库实际实现为准。

## 34.2 两个且仅两个正式 EXE

最终交付的部署器程序必须是：

```text
TG115-CloudDrive2-Deployer.exe
TG115-OpenList-Deployer.exe
```

两者均为 PySide6。构建脚本和持续集成必须显式区分两个产品入口、产品标识与各自的部署 payload。

不得再生成或发布：

```text
原 Tkinter 轻量兼容版
新增的 OpenList Tkinter 版
Lite / Legacy / Classic 等额外部署器
一个运行后再选择两种中转的混合版 EXE
```

这里的“两个 EXE”指最终向用户分发的两个部署器产品，不把构建工具自身或临时目录里的内部文件计作第三个产品；不得以此名义另增用户可见的辅助部署器。

## 34.3 构建配置同步修改

必须同步检查：

- Python 程序入口；
- PySide6 共用 UI 与产品配置；
- 打包脚本与 spec 文件；
- Qt 资源、图标、样式及所需插件打包；
- Windows 持续集成构建目标；
- Release 上传清单和产物校验；
- README、下载页与本地构建说明。

两版可以共用内部业务代码，但应各自指向正确的 VPS 安装目录、容器名、网络、管理端口及部署资源；不得把 OpenList 产品打包成仍部署 CloudDrive2 的改名 EXE。

从专用构建输出目录发布，显式列出两个产物，防止旧 Tkinter EXE 被通配符一起上传。不得为了清理构建目录而删除用户数据或任意路径。

## 34.4 构建、验证与汇报

给出可复现的构建入口：可以一次生成两版，也应能单独指定构建其中一版。具体命令服从仓库现有脚本，不在审计前臆定入口文件名。

在可用的 Windows 构建环境执行打包，并分别启动两个 EXE，检查窗口、资源、输入、日志、隧道和后台操作。缺少 Windows 环境时，仍应完成构建配置与可运行测试，并明确列出尚未执行的 Windows 打包/启动验收；不得声称已生成或验证不存在的 EXE。

不允许将 Token、密码、私钥、测试服务器、个人域名或旧兼容版入口打包进正式产物。

---

# 三十五、版本和发布

首个 OpenList 版本建议为：

```text
TG115-OpenList v1.0.0
```

CloudDrive2 版版本号沿用项目现有发布策略，不随意倒退到历史版本。版本号可按原有规范加入文件名，但不改变两个产品的身份及数量。

**修改后项目的本轮正式 EXE 发布清单只有：**

```text
TG115-CloudDrive2-Deployer.exe
TG115-OpenList-Deployer.exe
```

同时提供相应的：

```text
README.md
CHANGELOG.md
构建与人工验收说明
```

沿用项目现有 releases 流程，但必须删除旧 Tkinter 兼容版的构建/上传目标，并检查旧产物不会混入本轮发布。

CHANGELOG 明确区分：

```text
保留：CloudDrive2 的 PySide6 图形化部署器
新增：基于同一 PySide6 UI 的 OpenList 图形化部署器
退役：原 CloudDrive2 Tkinter 轻量兼容版
```

这里的退役针对新版本；不要自动删除用户旧文件或修改历史 Release。

---

# 三十六、最终验收标准

只有满足下面条件，才认为 OpenList v1.0.0 及本轮两个 PySide6 部署器的交付达到可发布状态。

## UI 与构建产物

```text
✅ CloudDrive2 版保留项目已有的新版 PySide6 UI
✅ OpenList 版在同一套现有 PySide6 UI 上修改适配
✅ 没有把五步业务流程误做成推倒重来的全新界面
✅ CloudDrive2 原 PySide6 部署、隧道、修复与验收功能无回归
✅ 最终仅交付 CloudDrive2 和 OpenList 两个 PySide6 部署器 EXE
✅ Tkinter 轻量兼容版已退出活动入口、构建和本轮发布
✅ 两版 PySide6 运行与构建不依赖 Tkinter UI 回退
✅ README、构建脚本、Release 与下载入口均只指向上述两版
✅ 两个 Windows EXE 的实际构建/启动状态如实记录
```

## 部署

```text
✅ Windows EXE 可启动
✅ 可连接 VPS
✅ 可部署 tg115-openlist
✅ 可部署 tg115-openlist-bot
✅ Docker Network 正确
✅ 两个容器可重启恢复
```

## OpenList

```text
✅ 默认不直接暴露公网后台
✅ EXE 可建立 SSH Tunnel
✅ 浏览器可打开 OpenList
✅ 首次管理员信息可方便获得
✅ 已初始化实例不会被自动重置密码
```

## WebDAV

```text
✅ EXE 本地生成推荐 tg115 用户名/强密码
✅ 用户无需重复输入该密码
✅ 内部 WebDAV URL 使用容器网络
✅ 可认证
✅ 可上传
✅ 可获取远端文件信息
✅ 可重命名
✅ 可删除
```

## TG115

```text
✅ Bot 可正常登录
✅ 指定用户限制正常
✅ 队列正常
✅ SQLite 持久化正常
✅ 重启恢复正常
✅ 原有命令正常
✅ 本地任务预算正常
✅ 磁盘安全线正常
✅ 大文件策略未被破坏
```

## 隐私

```text
✅ 无遥测
✅ 无凭据上传
✅ 日志脱敏
✅ 115 授权完全在用户自己的 OpenList 后台完成
```

## 共存

```text
✅ 不覆盖 CloudDrive2 版
✅ 容器名不冲突
✅ 网络不冲突
✅ 安装目录不冲突
✅ 数据库不冲突
```

---

# 三十七、开发过程要求

请按照下面顺序执行：

```text
1. 审计当前 TG115，核实新版 PySide6 与旧 Tkinter 两套入口
2. 记录现有 PySide6 UI/功能基线及两个产品的改造方案
3. 确认共用业务层，规划 OpenList 独立部署目录与产品入口
4. 保留 CloudDrive2 PySide6 功能，退役 Tkinter 活动入口及构建发布
5. 完成 Docker/OpenList 基础部署
6. 在现有 PySide6 UI 中适配 OpenList 首次初始化体验
7. 完成固定本地 5244 的 SSH Tunnel
8. 在同一 UI 中完成 WebDAV 凭据与操作指引
9. 完成 rclone/OpenList WebDAV 适配
10. 完成 verify，并验证 TG115 原有核心功能
11. 分别回归两个 PySide6 产品的界面与部署流程
12. 完成日志脱敏
13. 同步修改 README、CHANGELOG、下载入口和发布工作流
14. 完成自动测试、静态检查及产物数量检查
15. 构建两个 PySide6 EXE，并如实记录 Windows 启动验收
16. 输出两版结果及未完成的人工测试清单
```

每完成一个重要阶段，都更新开发记录。

---

# 三十八、不要做的事情

严禁：

```text
❌ 删除 CloudDrive2 的 PySide6 正式版或其已有业务能力
❌ 以 Tkinter 轻量版而不是现有新版 PySide6 UI 为 OpenList 基线
❌ 给现有两个 EXE 再追加第三个 OpenList EXE，而不退役 Tkinter
❌ 在新版本继续生成/发布 Tkinter、Lite、Legacy 等兼容部署器
❌ 以缺少 PySide6 源码为由自行回退到旧 UI 或重新虚构一个新版 UI
❌ 为了照搬五步示意而推倒现有 PySide6 页面结构
❌ 把 OpenList 版覆盖到 /opt/tg115 原目录
❌ 默认公开 0.0.0.0:5244
❌ 自动读取并导出 115 Token
❌ 在日志中输出完整密码
❌ 把测试凭据写死在源码
❌ 每次启动 EXE 自动重置 OpenList 管理员密码
❌ 把 OpenList 初始化失败伪装成成功
❌ 只测试 1KB 文件就宣称大文件稳定
❌ 重写成熟的 TG115 下载/队列逻辑而不给理由
❌ 添加本次没有要求的 Telegram 频道监听功能
❌ 添加绕过 Telegram 内容保护的逻辑
```

---

# 三十九、完成开发后向我汇报

完成后不要只说“已经完成”。

请输出：

## 1. 架构变化

说明 OpenList 版最终架构，以及两个 PySide6 产品如何复用现有新版 UI 与共用业务逻辑。列出实际沿用的 PySide6 入口和关键组件，不要只写“使用 PySide6”。

## 2. 修改文件

列出：

```text
新增文件
修改文件
删除文件（如有）
```

以及各文件用途。

## 3. 容器与目录

明确：

```text
tg115-openlist-bot
tg115-openlist
tg115-openlist-net
/opt/tg115-openlist
```

## 4. EXE 与旧兼容版退役

分别给出：

```text
TG115-CloudDrive2-Deployer.exe
TG115-OpenList-Deployer.exe
```

的真实构建结果、构建命令、使用的 PySide6 入口以及 Windows 启动测试结果。

明确说明：

- 本轮最终交付是否只有两个部署器 EXE；
- Tkinter 活动入口、打包目标、发布任务与文档入口分别如何退役；
- 是否仍有仅供历史归档的旧源码，以及为何不会进入运行或发布；
- CloudDrive2 的 PySide6 功能如何验证未被破坏。

没有实际构建/启动的项目必须标明“未执行”，不得用另一个产品的测试结果代替。

## 5. 测试结果

分成：

```text
已自动测试
已人工测试
尚未测试
```

不允许混在一起。

## 6. 已知问题

如实列出。

## 7. 用户部署流程

用最短步骤说明普通用户如何：

```text
EXE → VPS → OpenList → 115 Open → tg115 WebDAV 用户 → 验收 → Telegram 转存
```

## 8. 安全检查

确认：

```text
没有遥测
没有凭据回传
日志已脱敏
OpenList 仅通过 SSH Tunnel 管理
```

---

# 四十、最终产品定位

请始终记住：这个项目不是为了替代 CloudDrive2 版。

TG115 最终形成两个并列方案，**两者均采用当前项目新版 PySide6 图形化部署器 UI**：

```text
                 TG115 系列
                     │
          ┌──────────┴──────────┐
          │                     │
  CloudDrive2 方案          OpenList 方案
          │                     │
tg115-clouddrive2       tg115-openlist
          │                     │
tg115-clouddrive2-bot   tg115-openlist-bot
          │                     │
CloudDrive2 WebDAV      OpenList WebDAV
          │                     │
          └─────────115─────────┘
```

用户根据自己的情况选择：

```text
CloudDrive2 版
或
OpenList 版
```

最终产品只有：

```text
TG115-CloudDrive2-Deployer.exe  [PySide6]
TG115-OpenList-Deployer.exe    [PySide6]
```

两套程序：

- 共用当前新版 PySide6 的 UI 基线，操作风格一致；
- 中转程序不同；
- 部署数据完全隔离；
- 可以在同一台 VPS 共存；
- 不向开发者收集或回传用户的 115/Telegram/SSH 敏感信息；
- 不再附带原 Tkinter 轻量兼容版作为第三个产品。

本次开发重点是：

> 在保留 CloudDrive2 PySide6 部署器及 TG115 已成熟核心功能的前提下，从现有新版 PySide6 UI 适配出同样易用的 OpenList 部署器，解决首次管理员密码、固定 5244 隧道、WebDAV 用户配置与验收体验；同时退役 Tkinter 轻量兼容版，最终只构建和发布两个 PySide6 EXE。

