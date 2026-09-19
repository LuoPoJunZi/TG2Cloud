# AGENTS.md — TG2Cloud

## 项目身份

项目名称：

```text
TG2Cloud
```

定位：

> 将 Telegram 中提交的文件自动转存到用户自有云存储的自托管工具。

架构：

```text
Telegram
→ Private Bot
→ TG2Cloud
→ rclone
→ CloudDrive2 / OpenList WebDAV
→ 用户挂载的云存储
```

TG2Cloud 不再是 115 专用项目。

115 可以作为示例和主要测试场景，但用户可见文案不得暗示它是唯一目标网盘。

当前：

```text
CloudDrive2/115 → CloudDrive2
```

已经修改完成，不要重复改动。

---

## 版本

TG2Cloud 从：

```text
1.0.0
```

开始。

不要继承 TG115 版本号。

---

## 正式 Windows 应用

只发布：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

两者都使用：

```text
PySide6
```

Tkinter 版不再：

- 开发；
- 构建；
- 发布。

---

## 运行命名

CloudDrive2：

```text
tg2cloud-clouddrive2-bot
tg2cloud-clouddrive2
tg2cloud-clouddrive2-net
/opt/tg2cloud-clouddrive2
```

OpenList：

```text
tg2cloud-openlist-bot
tg2cloud-openlist
tg2cloud-openlist-net
/opt/tg2cloud-openlist
```

不要静默覆盖旧 TG115。

---

## 固定 Tunnel

CloudDrive2：

```text
127.0.0.1:19798 → VPS 127.0.0.1:19798
```

OpenList：

```text
127.0.0.1:5244 → VPS 127.0.0.1:5244
```

固定端口被占用时：

- 不自动换端口；
- 明确提示；
- 提供重新检测。

---

## UI

使用当前已经调试成功的 PySide6 新 UI。

两个 Edition 必须看起来属于同一产品。

复用：

- 主题；
- 导航；
- 卡片；
- 表单；
- 日志；
- 状态；
- 进度；
- 对话框；
- 密码控件；
- 复制控件；
- SSH；
- Tunnel；
- About；
- Logo/Icon。

不要为 OpenList 重新设计完全不同的 UI。

---

## 正式品牌资源

TG2Cloud Logo / Icon 已经准备完成。

唯一正式来源：

```text
assets/brand/
```

必须先读取实际文件。

不要：

- 重新设计 Logo；
- 重新生成另一套 Logo；
- 覆盖正式资源；
- 为两个 Edition 制作完全不同主 Logo。

Windows EXE 优先使用：

```text
assets/brand/tg2cloud.ico
```

README 优先使用：

```text
assets/brand/tg2cloud-logo.svg
```

PySide6 优先从：

```text
assets/brand/
```

选择合适的正式图标。

如果缺少代码需要的尺寸，只允许从现有正式 SVG/PNG 派生，并记录到 `docs/WORKLOG.md`。

---

## 稳定核心规则

两套代码已经调试成功。

不要无理由重写：

- Telegram Bot；
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

原则：

```text
稳定 > 重构
最小修改 > 大迁移
回归测试 > 猜测
```

---

## 默认磁盘

```text
LOCAL_TEMP_BUDGET_GB=20
MIN_FREE_DISK_GB=8
```

20GB 是任务预算，不是磁盘分区。

---

## OpenList 特殊 UX

必须保留：

- 首次管理员密码自动获取；
- PySide6 显示；
- 显示/隐藏；
- 复制；
- 已初始化实例不自动重置；
- WebDAV 凭据方便复制；
- 用户不需要重复输入。

推荐 WebDAV 用户：

```text
tg2cloud
```

---

## 隐私

禁止加入：

```text
遥测
埋点
凭据回传
第三方统计
```

敏感信息只允许在必要时用于：

```text
用户本机 ↔ 用户自己的 VPS
```

日志必须脱敏。

不得公开输出：

- SSH 密码/私钥；
- Bot Token；
- API Hash；
- WebDAV 密码；
- OpenList 管理员密码；
- `.env`；
- `rclone.conf`；
- 网盘 Token；
- Cookie。

---

## 网盘配置边界

用户的网盘账号、OAuth、Token 等配置全部在：

```text
CloudDrive2
或
OpenList
```

中自行完成。

TG2Cloud 不收集这些数据。

---

## 上游

TG2Cloud 从 TG115 演进而来。

必须保留许可证、版权、NOTICE 和必要的 README 致谢。

---

## 工作方式

先审计，再修改。

维护：

```text
docs/AUDIT.md
docs/WORKLOG.md
```

未执行的测试不能写成“通过”。

---

## v1.0.0 暂不做

不要加入：

- Telegram 用户账号频道监听；
- tdata；
- 自动频道订阅；
- 内容保护绕过；
- rclone crypt；
- SaaS；
- 在线账号系统；
- 遥测；
- 开发者侧凭据收集。

目标是稳定完成：

```text
TG2Cloud v1.0.0
```
