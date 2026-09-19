# TG2Cloud v1.0.0 人工验收清单

本清单用于 Release Candidate 的真实 VPS、Telegram、Storage Gateway 和云存储验收。
请只使用本人控制的测试 VPS、测试 Bot 和测试云存储；不要把真实密码、Token、Cookie、私钥、
`.env`、`rclone.conf` 或日志提交到仓库、Issue、聊天或截图。

建议记录每项的日期、测试人员、VPS 系统、Edition、结果和不含秘密的错误摘要。占位符示例：
`<YOUR_VPS>`、`<YOUR_BOT_TOKEN>`、`<YOUR_WEBDAV_PASSWORD>`。

## 0. Windows 与发布文件

1. 在干净的 Windows 10/11 64 位环境核对 `SHA256SUMS.txt`。
2. 分别启动两个 EXE，确认名称、窗口标题、TG2Cloud Logo、Edition 和版本 `1.0.0`。
3. 打开 About，确认正式 Logo、`From Telegram to Your Cloud`、Edition 和版本。
4. 检查 Explorer、窗口标题栏、任务栏和 Alt-Tab 图标。
5. 分别在 100%、125%、150% 缩放下检查文本、Logo、按钮、密码控件和日志区。
6. 记录 SmartScreen、Microsoft Defender 和其他安全软件结果；未知发布者提示与恶意软件告警
   必须分开记录。

## 1. CloudDrive2 Edition

### Fresh Install

1. 启动 `TG2Cloud-CloudDrive2-Deployer.exe`，使用本人控制的 `<YOUR_VPS>` 测试 SSH。
2. 使用没有 `/opt/tg2cloud-clouddrive2` 的测试环境；旧 TG115 资源如存在，只记录提示，
   不允许部署器自动停止、删除或迁移。
3. 填写测试 Telegram/WebDAV 信息，确认默认预算 `20GB`、安全线 `8GB`、TARGET_PATH 为空。
4. 执行一键部署，确认目录 `/opt/tg2cloud-clouddrive2`。
5. 确认容器 `tg2cloud-clouddrive2`、`tg2cloud-clouddrive2-bot`，Network
   `tg2cloud-clouddrive2-net`，Bot health 正常。
6. 建立固定 `127.0.0.1:19798 → VPS 127.0.0.1:19798` Tunnel，打开管理页；关闭部署器后
   确认 Tunnel 失效，再重新建立。占用本地 19798 后重试，必须明确失败且不换端口。
7. 由本人在 CloudDrive2 中挂载测试云存储并创建专用 WebDAV 用户；不要向 TG2Cloud
   开发者提供云存储凭据。
8. 分别以 TARGET_PATH 空值、`Telegram`、`Media/Telegram` 验证路径；如果输入
   `/Telegram`，确认规范化后没有 `//` 或 `remote://`。
9. 执行 WebDAV 验收，逐项确认 auth/list/upload/size/rename/recheck/delete/cleanup，最终出现
   `TG2CLOUD_DESTINATION=OK`。
10. 向私人 Bot 发送测试文件，确认 Telegram → TG2Cloud → rclone → CloudDrive2 WebDAV
    → 测试云存储完整成功，并在云存储官方客户端核对大小和可打开性。

### Existing / Update / Repair

11. 在 VPS 手工把 TARGET_PATH、预算或安全线改为一个非敏感测试值，保存 `.env` 哈希或仅记录
    非敏感字段；不要输出 Bot Token、API Hash 或密码。
12. 默认不勾选覆盖选项再次部署，确认 `.env` 非敏感自定义值、SQLite、`rclone.conf`、
    CloudDrive2 配置和挂载数据保持。
13. 备份后明确勾选覆盖选项，使用新的非敏感测试值再次部署，确认只有此时表单配置生效。
14. 执行 `/opt/tg2cloud-clouddrive2/manage.sh update`，确认成功才输出
    `TG2CLOUD_UPDATE=OK`，上述配置和数据不被删除。
15. 正常环境重复执行 CloudDrive2 Repair；若可安全模拟 Network 缺失，再执行一次修复。
    确认修复只操作 TG2Cloud Network/容器、不删除数据，并再次通过 WebDAV 验收。
16. 检查 Running、Stopped、Not Installed 和 Legacy TG115 detected 状态；旧 TG115 Running
    不得被显示为 TG2Cloud Running。

## 2. OpenList Edition

### Fresh Install

1. 启动 `TG2Cloud-OpenList-Deployer.exe`，使用本人控制的测试 VPS 测试 SSH。
2. 使用没有 `/opt/tg2cloud-openlist` 的测试环境，确认默认 WebDAV 用户 `tg2cloud`、
   TARGET_PATH 空、预算 `20GB`、安全线 `8GB`。
3. 检查首次管理员密码默认隐藏，可显示、复制；普通日志中不得出现明文。执行 Fresh Install。
4. 确认目录 `/opt/tg2cloud-openlist`，容器 `tg2cloud-openlist`、
   `tg2cloud-openlist-bot`，Network `tg2cloud-openlist-net` 和 Bot health。
5. 建立固定 `127.0.0.1:5244 → VPS 127.0.0.1:5244` Tunnel；验证打开、关闭、重建和本地
   5244 冲突，端口冲突时不得自动换端口。
6. 使用首次管理员信息登录 OpenList。由本人添加测试云存储，创建普通 WebDAV 用户
   `tg2cloud`，测试 WebDAV 密码的显示/隐藏、复制和重新生成。
7. 分别验证 TARGET_PATH 空值、`Telegram`、`Media/Telegram` 和 `/Telegram` 规范化。
8. 执行完整 WebDAV 验收并确认 `TG2CLOUD_DESTINATION=OK`。
9. 向私人 Bot 发送测试文件，确认 Telegram → TG2Cloud → rclone → OpenList WebDAV
   → 测试云存储完整成功，并在云存储官方客户端复验。

### Existing / Update / Backup

10. 再次部署已有 OpenList，确认不会自动重置管理员密码，界面提示使用已有凭据。
11. 修改一个非敏感 VPS 配置后，默认重复部署并确认完整 `.env`、SQLite、`rclone.conf` 和
    `openlist/data` 保留；再备份后测试显式覆盖选项。
12. 执行 `/opt/tg2cloud-openlist/manage.sh update`，确认成功标记、两个服务健康和数据保留。
13. 在 PySide6 中创建手动安全备份，确认服务暂停/恢复行为、SQLite snapshot、`.env`、
    `rclone.conf`、OpenList state 和文件权限；失败情境不得报告成功。
14. 检查 Running、Stopped、Not Installed 和 Legacy TG115 detected 状态。

## 3. Telegram、文件规模和磁盘策略

1. 验证 `/start`、`/help`、`/queue`、`/status`、`/performance`、`/task <id>`、
   `/confirm <id>`、`/retry <id>`、`/cancel <id>`，品牌必须为 TG2Cloud；`/confirm` 不得改变
   原有业务语义。
2. 两个 Edition 分别测试并记录：10～100MB、500MB、1GB、2GB、5GB。无法执行的项目写
   “未测试”，不要推测通过。
3. 至少验证一个小文件、一个中等文件和一个大于常规缓存/自定义预算的文件；确认流式传输、
   失败重试、重启恢复、本地临时清理和最终云端文件大小。
4. 确认 VPS `.env` 和容器实际环境为默认 `LOCAL_TEMP_BUDGET_GB=20`、
   `MIN_FREE_DISK_GB=8`，并确认用户显式自定义值在更新后继续生效。

## 4. Legacy 与发布判定

1. 在安全测试环境分别模拟旧目录、旧停止容器、旧运行容器、19798 冲突和 5244 冲突。
2. Legacy presence 只提示；真实端口或目标资源冲突必须停止。TG2Cloud 不得删除、停止、迁移
   旧 TG115，也不得自动换端口。
3. 确认两个 Edition 均完成 Fresh Install、Tunnel、WebDAV、Telegram E2E、重复部署和 Update；
   CloudDrive2 完成 Repair，OpenList 完成 Manual Backup。
4. 把真实结果更新到 `TG2Cloud-v1.0.0-RELEASE-CHECKLIST.md` 和 `docs/WORKLOG.md`。
5. 只有所有 Release Blocker 均关闭后才把状态从
   **Release Candidate — Manual Acceptance Pending** 改为 **READY**。
