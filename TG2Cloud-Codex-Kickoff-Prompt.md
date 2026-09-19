# TG2Cloud v1.0.0 — Codex 新项目整合与品牌化开发提示词

> 本文件用于 **Codex 新对话的主开发提示词**。
>
> 当前前提：新的 `TG2Cloud` 目录中已经放入两套**分别调试成功**的代码：
>
> - CloudDrive2 版本；
> - OpenList 版本。
>
> TG2Cloud 的正式 Logo、Icon 等品牌资源也已经准备完成，并放在仓库：
>
> ```text
> assets/brand/
> ```
>
> 因此本次开发不是从零重写，也不是重新设计 Logo，而是把已经稳定工作的两套代码正式整合成 **TG2Cloud v1.0.0**。

---

# 一、项目正式定位

项目名称：

```text
TG2Cloud
```

一句话定位：

> TG2Cloud 是一个将 Telegram 中提交的文件自动转存到用户自有云存储的自托管工具。

TG2Cloud 不再绑定 115。

最终支持的云盘取决于用户在：

```text
CloudDrive2
或
OpenList
```

中实际挂载的存储。

115 可以继续作为：

- 主要测试场景；
- README 示例；
- 教程示例；
- FAQ 示例；

但不能再把项目描述成“115 专用”。

当前项目中原 UI 的：

```text
CloudDrive2/115
```

已经改成：

```text
CloudDrive2
```

这个修改已经完成，本次不要重复修改已经正确的 UI，只检查其他用户可见位置是否还有“仅支持 115”的旧文案。

---

# 二、产品架构

TG2Cloud 统一架构：

```text
Telegram
   ↓
Private Bot
   ↓
TG2Cloud Transfer Core
   ↓
rclone
   ↓
Storage Gateway
   ├── CloudDrive2 WebDAV
   └── OpenList WebDAV
   ↓
用户自行挂载的云存储
```

CloudDrive2 Edition：

```text
Telegram
→ TG2Cloud Bot
→ rclone
→ CloudDrive2 WebDAV
→ 用户挂载的云存储
```

OpenList Edition：

```text
Telegram
→ TG2Cloud Bot
→ rclone
→ OpenList WebDAV
→ 用户挂载的云存储
```

两个 Edition 是同一 TG2Cloud 品牌下的两个独立发行方案。

---

# 三、最终只发布两个 PySide6 EXE

旧 TG115 项目曾经存在：

```text
PySide6 图形化部署器
Tkinter 轻量兼容版
```

TG2Cloud v1.0.0 开始：

```text
Tkinter 版停止开发
Tkinter 版停止正式构建
Tkinter 版停止进入 Release
```

最终正式发布：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

两者都必须使用：

```text
PySide6
```

要求：

- CloudDrive2 版继续基于当前已调试成功的 PySide6 新 UI；
- OpenList 版继续基于同一套 PySide6 UI 体系；
- 两个 EXE 必须明显属于同一产品系列；
- 不要为 OpenList 重新设计一套完全不同的 UI；
- 不要新增 OpenList Tkinter 版；
- 不要继续构建 CloudDrive2 Tkinter 兼容版。

如果 Tkinter 源码仍然包含共享功能，先提取或保留必要逻辑，再停止其构建，不要粗暴删除导致功能回归。

---

# 四、版本从 1.0.0 开始

TG2Cloud 是新的项目品牌。

版本统一从：

```text
1.0.0
```

开始。

统一更新：

- VERSION 或等效版本源；
- PySide6 窗口；
- About；
- README；
- CHANGELOG；
- PyInstaller；
- EXE 元数据；
- Release；
- Bot 用户可见信息；
- 文档。

不要沿用 TG115 的旧版本号。

---

# 五、TG2Cloud 品牌资源：已经存在，禁止重新设计

TG2Cloud 的正式 Logo / Icon 已经放在：

```text
assets/brand/
```

这是 TG2Cloud v1.0.0 的**品牌资源唯一来源（Source of Truth）**。

开始品牌迁移前，先检查该目录实际文件。

预期结构类似：

```text
assets/brand/
├── tg2cloud-logo.svg
├── tg2cloud-icon.svg
├── tg2cloud-icon.png
├── tg2cloud-icon-32.png
├── tg2cloud-icon-64.png
├── tg2cloud-icon-128.png
├── tg2cloud-icon-256.png
├── tg2cloud-icon-512.png
├── tg2cloud.ico
├── tg2cloud-logo-preview.png
└── README.md
```

具体以仓库实际内容为准。

## 5.1 禁止事项

不要：

- 重新设计 TG2Cloud Logo；
- 调用 AI/绘图程序生成另一套 Logo；
- 用临时图标替换正式资源；
- 从 TG115 Logo 自动派生另一套主 Logo；
- 为 CloudDrive2 / OpenList 分别制作完全不同的主品牌；
- 覆盖 `assets/brand/` 里的正式资源。

## 5.2 正确任务

本次工作是：

```text
读取 assets/brand/
        ↓
确认正式 TG2Cloud 品牌资源
        ↓
替换旧 TG115 品牌引用
        ↓
应用到两个 PySide6 部署器
        ↓
应用到 PyInstaller / EXE
        ↓
应用到 README / About / 文档
```

## 5.3 如果缺少某种尺寸

如果代码实际需要额外尺寸：

1. 优先使用现有 SVG；
2. 可以从现有 SVG/PNG 派生新尺寸；
3. 保持原设计不变；
4. 不重新设计 Logo；
5. 在 `docs/WORKLOG.md` 记录派生资源。

---

# 六、品牌资源使用规则

Windows EXE：

```text
assets/brand/tg2cloud.ico
```

PySide6 主窗口可使用：

```text
assets/brand/tg2cloud-icon.svg
assets/brand/tg2cloud-icon-256.png
assets/brand/tg2cloud-icon-512.png
```

README / 文档优先：

```text
assets/brand/tg2cloud-logo.svg
```

如果平台不方便显示 SVG：

```text
assets/brand/tg2cloud-logo-preview.png
```

两个 Edition 共用同一主品牌：

```text
TG2Cloud · CloudDrive2
TG2Cloud · OpenList
```

---

# 七、运行时命名空间

TG2Cloud 不应静默覆盖旧 TG115。

## CloudDrive2 Edition

```text
容器：
tg2cloud-clouddrive2-bot
tg2cloud-clouddrive2

Docker Network：
tg2cloud-clouddrive2-net

安装目录：
/opt/tg2cloud-clouddrive2
```

## OpenList Edition

```text
容器：
tg2cloud-openlist-bot
tg2cloud-openlist

Docker Network：
tg2cloud-openlist-net

安装目录：
/opt/tg2cloud-openlist
```

如果现有调试成功代码仍使用：

```text
tg115-...
/opt/tg115-...
```

不要直接全局替换。

先审计：

- Python；
- Compose；
- Shell；
- rclone；
- SQLite；
- healthcheck；
- backups；
- repair；
- update；
- uninstall；
- Tunnel；
- 日志解析；
- 文档。

然后再一致性迁移。

---

# 八、第一阶段：只审计，不大规模修改

先完整阅读当前 TG2Cloud 目录。

识别：

1. CloudDrive2 版代码；
2. OpenList 版代码；
3. 两套 PySide6 入口；
4. Tkinter 旧入口；
5. build.ps1 / spec / PyInstaller；
6. Telegram Bot；
7. SQLite；
8. Telegram 下载；
9. rclone；
10. WebDAV；
11. 流式大文件；
12. 磁盘预算；
13. verify；
14. CloudDrive2 Tunnel；
15. OpenList Tunnel；
16. OpenList 首次管理员密码；
17. WebDAV 用户引导；
18. update/repair/backup/uninstall；
19. Logo/Icon 引用；
20. TG115 品牌残留；
21. 115-only 文案；
22. LICENSE / NOTICE / 致谢。

创建：

```text
docs/AUDIT.md
docs/WORKLOG.md
```

完成审计后先向我汇报：

- 当前结构；
- 两版差异；
- 可以共享的内容；
- 不应重构的稳定模块；
- 品牌替换位置；
- 运行时命名迁移风险；
- 构建方式；
- 正式改造计划。

然后再继续修改。

---

# 九、稳定优先

两套代码已经调试成功。

遵循：

```text
稳定 > 重构
最小改动 > 大规模迁移
可回滚 > 一步到位
回归测试 > 猜测
```

禁止无理由重写：

- Telethon / Bot；
- Telegram 下载；
- SQLite；
- 队列；
- 重启恢复；
- rclone；
- WebDAV；
- 流式大文件；
- 磁盘保护；
- verify；
- 清理。

如果需要提取公共模块：

1. 先建立回归基线；
2. 一次只提取一个；
3. 两个 Edition 都测试；
4. 测试通过再继续。

---

# 十、CloudDrive2 Edition

CloudDrive2 版已经调试成功。

流程：

```text
EXE 部署 CloudDrive2
↓
固定 SSH Tunnel
↓
用户登录自己的 CloudDrive2
↓
用户自行挂载云盘
↓
配置 WebDAV
↓
TG2Cloud 验收
↓
Telegram 实际转存
```

TG2Cloud 不收集用户的网盘账号、Cookie、Token、OAuth 凭据。

本次主要做：

```text
TG2Cloud 品牌迁移
v1.0.0
Logo/Icon 接入
运行命名迁移
多云文案检查
统一构建
Release
```

不要改变已经稳定的传输行为。

---

# 十一、OpenList Edition

OpenList 版也已经调试成功。

流程：

```text
EXE 部署 OpenList
↓
获取首次管理员信息
↓
固定 SSH Tunnel
↓
用户自行添加云存储
↓
创建/配置 WebDAV 用户
↓
TG2Cloud 验收
↓
Telegram 实际转存
```

## 11.1 首次管理员密码

首次部署时：

- 自动识别新实例；
- 自动获取 OpenList 当前官方支持的初始化信息；
- PySide6 中清晰显示；
- 提供显示/隐藏；
- 提供复制；
- 提供“打开 OpenList”。

不要让普通用户自己 SSH 查日志。

已有实例：

- 不自动重置；
- 不尝试读取用户之后修改的密码；
- 提示使用已有管理员账号。

## 11.2 WebDAV 用户体验

推荐：

```text
EXE 本地生成 WebDAV 用户名/密码
↓
用户复制到 OpenList
↓
返回 EXE 直接测试
```

推荐用户名：

```text
tg2cloud
```

密码：

- 24~32 字符；
- 安全随机源；
- 本地生成；
- 支持复制；
- 支持重新生成；
- 不上传给开发者；
- 不写入普通日志。

---

# 十二、固定 SSH Tunnel

CloudDrive2：

```text
Windows 127.0.0.1:19798
           ↓
SSH Tunnel
           ↓
VPS 127.0.0.1:19798
```

浏览器：

```text
http://127.0.0.1:19798
```

OpenList：

```text
Windows 127.0.0.1:5244
           ↓
SSH Tunnel
           ↓
VPS 127.0.0.1:5244
```

浏览器：

```text
http://127.0.0.1:5244
```

如果本地端口被占用：

- 不换随机端口；
- 明确提示；
- 提供重新检测。

---

# 十三、默认磁盘策略

默认：

```text
LOCAL_TEMP_BUDGET_GB=20
MIN_FREE_DISK_GB=8
```

20GB 是本地任务预算，不是分区。

要求：

- PySide6 可配置；
- 正确写入 VPS；
- 容器重建后实际生效；
- 超预算大文件保留现有流式逻辑。

---

# 十四、WebDAV verify

两个 Edition 都保留完整目的端验收：

```text
WebDAV 登录
→ 列目录
→ 上传测试文件
→ 获取远端信息
→ 重命名
→ 再检查
→ 删除
→ 确认清理
```

推荐输出：

```text
TG2CLOUD_STORAGE_GATEWAY=clouddrive2|openlist
TG2CLOUD_WEBDAV=OK
TG2CLOUD_UPLOAD=OK
TG2CLOUD_RENAME=OK
TG2CLOUD_DELETE=OK
TG2CLOUD_DESTINATION=OK
```

如旧输出格式被程序依赖，做兼容过渡。

---

# 十五、错误提示

普通用户主 UI 不要只显示：

```text
401 Unauthorized
```

应显示：

```text
无法登录 WebDAV
```

并给出原因和下一步。

详细日志再显示底层错误。

至少覆盖：

- 401；
- 403；
- 404；
- Connection refused；
- timeout；
- No space left；
- SSH failure；
- Docker unavailable；
- 19798 占用；
- 5244 占用；
- OpenList 未初始化；
- WebDAV 权限不足。

---

# 十六、正式构建

最终正式 Release 只允许：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

两者均为 PySide6。

正式 Release 中：

```text
Tkinter EXE = 0
旧 TG115 EXE = 0
Debug/Test EXE = 0
```

优先统一：

```text
build.ps1
```

默认一次构建两个 Edition。

---

# 十七、README

README 首屏要直接说明：

```text
Telegram
   ↓
TG2Cloud
   ↓
CloudDrive2 / OpenList
   ↓
Cloud Storage
```

推荐开头：

```markdown
# TG2Cloud

TG2Cloud 是一个将 Telegram 中提交的文件自动转存到用户自有云存储的自托管工具。

项目提供两个独立的 PySide6 部署版本：

- CloudDrive2 Edition
- OpenList Edition

最终可用的云盘取决于用户在 CloudDrive2 或 OpenList 中挂载的存储。
115 是主要测试和示例场景之一，并不是唯一目标网盘。
```

README 至少包括：

- 项目定位；
- 架构；
- 两个 Edition；
- 功能；
- 系统要求；
- CloudDrive2；
- OpenList；
- Telegram；
- WebDAV；
- 磁盘预算；
- 大文件；
- 隧道；
- 隐私；
- 安全；
- 备份；
- 更新；
- 迁移；
- 卸载；
- FAQ；
- 致谢；
- License。

---

# 十八、上游 TG115

TG2Cloud 是新品牌，但不能抹去代码来源。

必须：

- 保留 LICENSE；
- 保留原作者版权；
- 保留 NOTICE 要求；
- README 中说明 TG2Cloud 从 TG115 演进/二次开发而来。

---

# 十九、CHANGELOG

TG2Cloud 版本历史从：

```text
v1.0.0
```

开始。

v1.0.0 可记录：

- TG2Cloud 新品牌；
- 多云定位；
- CloudDrive2 Edition；
- OpenList Edition；
- PySide6 双部署器；
- Tkinter 退役；
- 20GB 默认本地预算；
- 8GB 安全线；
- 固定 Tunnel；
- OpenList 首次管理员 UX；
- TG2Cloud 品牌资源接入；
- 新容器/安装目录；
- 无遥测；
- 日志脱敏；
- verify。

---

# 二十、迁移

创建：

```text
docs/MIGRATION_FROM_TG115.md
```

TG2Cloud v1.0.0 默认新装，不自动覆盖 TG115。

说明：

- 新容器；
- 新 Network；
- 新目录；
- 可共存；
- 迁移前备份；
- 手动迁移建议；
- 敏感配置注意事项。

---

# 二十一、隐私与安全

硬性要求：

```text
无遥测
无凭据回传
无第三方统计
无埋点
```

日志必须脱敏：

```text
SSH Password       ********
Telegram Bot Token ********
Telegram API Hash  ********
WebDAV Password    ********
OpenList Admin     ********
```

禁止把完整：

```text
.env
rclone.conf
SSH 私钥
云盘 Token
Cookie
```

放入公开诊断。

Storage Gateway 管理端默认通过 SSH Tunnel，不默认公网暴露。

---

# 二十二、测试

两个 PySide6 EXE：

- 启动；
- v1.0.0；
- Logo/Icon；
- SSH 成功/失败；
- 部署；
- 重复部署；
- 日志；
- 状态；
- restart；
- repair；
- backup；
- update；
- uninstall；
- Tunnel；
- Tunnel 关闭；
- 端口占用；
- verify。

CloudDrive2：

```text
127.0.0.1:19798
```

OpenList：

```text
127.0.0.1:5244
```

传输测试：

```text
10~100 MB
500 MB
1 GB
2 GB
5 GB
```

无法实测的必须标记：

```text
未测试
```

不得伪造“已通过”。

---

# 二十三、本次不做

本次不要加入：

- Telegram 用户账号频道监听；
- tdata；
- 自动订阅频道；
- 内容保护绕过；
- rclone crypt；
- SaaS；
- 用户账号系统；
- 遥测；
- 在线后台；
- 自动收集网盘 Token。

---

# 二十四、执行顺序

```text
1. 阅读 AGENTS.md
2. 阅读本文件
3. 阅读 TG2Cloud-BRAND-GUIDE.md
4. 阅读 Release Checklist
5. 审计两套已调试代码
6. 创建 docs/AUDIT.md
7. 创建 docs/WORKLOG.md
8. 汇报审计结果
9. 确认两套代码仍能构建/运行
10. 读取 assets/brand/ 正式品牌资源
11. 应用 TG2Cloud 品牌
12. 运行时命名迁移
13. CloudDrive2 PySide6 回归
14. OpenList PySide6 回归
15. 停止 Tkinter 正式构建
16. 统一 build.ps1
17. README / CHANGELOG / MIGRATION
18. 测试
19. 构建两个 EXE
20. 生成 v1.0.0 验收报告
```

---

# 二十五、完成后汇报

最终必须输出：

1. 最终项目结构；
2. 两个 EXE 路径、大小、SHA256；
3. 正式 Tkinter 构建产物数量：`0`；
4. 品牌资源实际使用位置；
5. 容器 / Network / 安装目录；
6. Tunnel 地址；
7. 已自动测试；
8. 已人工测试；
9. 尚未测试；
10. 安全检查；
11. 已知问题；
12. v1.0.0 是否达到发布条件。

---

# 最重要原则

> TG2Cloud 不是简单把 TG115 改名。

它是把已经调试成功的 CloudDrive2 / OpenList 两套 Telegram → 云存储方案，正式整理为拥有：

- 新品牌；
- 多云定位；
- 两个统一 PySide6 部署器；
- 新版本体系；
- 新运行命名；
- 新文档和 Release；

的：

```text
TG2Cloud v1.0.0
```

同时：

> 不要为了证明它是新项目而重写已经稳定工作的传输核心。
