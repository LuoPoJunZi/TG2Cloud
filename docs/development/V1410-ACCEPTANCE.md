# v1.4.10 发布与交互验收

## 当前状态

2026-10-26：按用户授权已发布 [v1.4.10 正式版](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.4.10)。A／B、main、[同标签双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40287434283)及实际资产核验全部通过。真实 VPS、Telegram 和用户网关验收尚未执行，不自动连接用户主机。

## 本版范围

- Telegram 监听规则、命名、目录、历史与审批使用按钮、逐项文字和草稿，不增加 Web 管理服务。
- 输入多项时放在同一条消息中分行发送；输入成功回复更新后的设置页，错误保留输入机会。规则最后明确保存，单项改名仍待确认转存。
- 终端主菜单 16 集成监听登录／状态／停用，手机号与验证码回显，只有两步验证密码隐藏。
- 外部 WebDAV 维护代码升级不依赖后端账号已配置完成；安全状态无法确认时不开放路由，不修改 Bot 或后台账号。
- 计划中文状态、默认目录和返回导航；纳入 v1.4.9 原正式提交升级基线。

## 安装与升级（发布后）

升级前主菜单 13 创建并核验快照，另存所需下载文件、程序／镜像身份与代理／附加配置。监听个人 Session 含授权能力，停用并等待释放后私密备份，不作为日志上传。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.10/install.sh) --edition clouddrive2 --release v1.4.10 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.10/install.sh) --edition clouddrive2 --release v1.4.10
```

OpenList 替换 Edition 为 `openlist`。内网使用同标签 `install-lan.sh`，保持已安装模式。不存在的正式 Tag 或 Release 不应使用。重新打开 `tg2cloud` 核对版本与菜单；升级 Bot 才能更新 Telegram 按钮，主机工具与外部维护工具也须各自更新。

## 发布后人工检查

| 检查 | 操作与预期 | 问题处理 |
| --- | --- | --- |
| 升级与数据 | 备份、预检、升级；确认原配置、任务和两个 Session 保留，网关与管理入口可用 | 收集脱敏升级摘要，不反复卸载 |
| 管理入口 | 主菜单 16 登录／查看状态／停用；仅两步验证密码隐藏；原 listen 命令兼容 | 不把验证码发送给 Bot，登录不自动启用来源 |
| 监听权限 | 管理员打开监听管理；普通家人无法使用命令、旧按钮或编号越权 | 不公开个人 Session、聊天 ID 或原始凭据日志 |
| 规则填写 | 多行关键词和后缀、类型、大小、范围、组合条件；填写后显示更新页，取消不保存，保存才生效 | 过期重新打开；不使用真实敏感文件测试 |
| 测试与命名 | 样例和最近消息测试不建任务；命名预览与实际说明相符 | 对照规则、原名和必要的脱敏说明，避免上传用户内容 |
| 目录与历史 | 选择授权别名、撤权拒绝提交；历史预览后确认；返回按钮可用 | 不扩大网关根目录，不自动改已入队路径 |
| 审批与批次 | 单项改名／目录／忽略、批次主题／目录／审批；重复点击不重复入队 | 核对失败项仍待确认、额度与权限 |
| 原转存 | 两 Edition 分别验证小文件、流式、重启、取消恢复与去重 | WebDAV 大小通过不等于云盘官方完成或哈希校验 |
| 外部入口恢复 | 测试实例未完成后台建号时先升级工具，再继续只读账号配置；失败时入口仍关闭 | 不借用 Bot／管理员凭据，不重启网关或删除云端数据 |
| 手机读取 | 正确专用账号、错误账号拒绝、目录范围、Range 播放与证书 | 仅在自己隔离数据上检查，不对真实目录做写操作负测 |

每项结果由用户在发布后确认；自动化、构建、代码升级不能替代真实账号、网关或公网验收。安全日志只包含版本、阶段、固定错误分类与脱敏结果。

## 数据库与回退

v1.4.9 → v1.4.10 沿用 schema 3，无新增迁移；v1.4.8 及更早仍经过已有 2 → 3 事务迁移，不删旧任务。从本版回退也先停用监听／Bot，保留当前可用数据，使用匹配代码和一致性快照；不要把旧代码直接接到不兼容 schema，不启动两个共用 Bot Token 的实例。完整步骤见[备份恢复](../BACKUP-RESTORE.md)与[监听指南](../LISTENING.md)。

## 自动验证与发布证据

本地及远端结果在实际执行后追加；未执行的 Linux／Docker、Telegram、VPS、真实网关或生产恢复不得记为通过。

### 本地验证与辅助 A

最终干净公共副本 369 文件与工作树逐字节一致。`check_python.py test`：1317 项，1283 通过、34 环境跳过、0 失败；Python 3.10 无 Bot 依赖的 `all --scope cli`：734 项，722 通过、12 跳过、0 失败。网站 37 项通过，34 HTML／4306 本地引用／285 搜索条目；Ruff、编译、Bandit、ShellCheck、两 Edition 组装与两份依赖审计通过。Windows 跳过 Linux UID／flock／PTY、rclone 或 opt-in Docker，后者由远端原生 CI 单独验证。

辅助 A：`cff370d597f1fd78dc7b081ae95300beb27cd974` 已公开，五项检查全部通过：[原生 AMD64／ARM64 与两 Edition 隔离运行](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40284157038)、[Python 3.10／3.13 四组合](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40284153686)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40284149685)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40284145808)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40284142319)。入口 B 固定该真实提交，不自指，不改写旧 Tag。A 的成功不代表 B、正式资产或真实 Telegram／VPS 已通过。

### 正式发布核验

- 已验证 A：`cff370d597f1fd78dc7b081ae95300beb27cd974`；最终 B／Tag：`39386ce8c4901727362e7d22ff4676922ad25052`，入口不自指。66 个实际公开辅助文件与候选逐字节一致。
- 初次入口 B 的内网 pin 赋值格式被 ShellCheck 拒绝；仅修正一行 Bash 赋值，完整 Shell 与 LAN 回归通过，未降低检查。最终 B 五项全部通过：[原生两架构](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40286961930)、[四组 CLI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40286958586)、[网站](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40286955676)、[文档](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40286952587)、[仓库](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40286949434)。
- main 同一提交的五项 CI 及正式标签工作流成功；[发布工作流](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40287434283)的 prepare、AMD64、ARM64、release 全部成功，原生两 Edition、隔离网关与代理检查通过，不等于真实账号或 VPS 验收。
- 实际源码资产 `TG2Cloud-v1.4.10-source.tar.gz`：3822084 字节，SHA256 `e657ce1f0017b70f498b07048ab9feb38d4b881855548c5dabbc94f81d348d35`。`SHA256SUMS.txt` 的 SHA256 为 `60419198837e6121ee3557bf79e253a6f54184ee94a88a34c08a30417b49beb7`。
- 正式验证器、GitHub digest 与下载字节一致；按 Linux LF 归档规则核对不可变 Tag 的全部 369 个文件，逐文件相同。未使用本机重新打包替代正式资产，未改写旧 Tag／Release。
- 版本、构建与隔离 CI 均不代表真实 Telegram 登录、监听来源、实际云端转存、手机播放或生产恢复已验收；这些项目仍按上表执行。
