# TG2Cloud v1.0.0 Release Checklist

状态说明：`[x]` 表示已有源码、自动化、冻结程序或本机产物证据；`[ ]` 表示尚未执行。
带“自动化”说明的项目不等同于真实 VPS 验收。

## A. 项目身份

- [x] 项目名统一为 `TG2Cloud`
- [x] 版本统一为 `1.0.0`
- [x] 多云存储定位清晰
- [x] 115 仅作为示例/主要测试场景
- [x] `CloudDrive2/115 → CloudDrive2` 已确认完成
- [x] 没有重复修改已经正确的 CloudDrive2 UI
- [x] 上游 TG115 关系透明

## B. 品牌资源

- [x] 仓库中存在 `assets/brand/`
- [x] 使用现有正式 Logo，而不是重新设计
- [x] `tg2cloud-logo.svg`
- [x] `tg2cloud-icon.svg`
- [x] `tg2cloud-icon.png`
- [x] `tg2cloud-icon-32.png`
- [x] `tg2cloud-icon-64.png`
- [x] `tg2cloud-icon-128.png`
- [x] `tg2cloud-icon-256.png`
- [x] `tg2cloud-icon-512.png`
- [x] `tg2cloud.ico`
- [x] `tg2cloud-logo-preview.png`
- [x] EXE 使用正式 ICO（关联图标已从两个最终 EXE 提取并目视核对）
- [x] PySide6 使用正式 Icon
- [x] README 使用正式 Logo
- [x] About 使用正式 Logo（两个 frozen EXE 已截图验证）
- [x] 两个 Edition 共用同一主品牌
- [x] 未产生未经确认的新 Logo

## C. 正式 Windows 构建

- [x] `TG2Cloud-CloudDrive2-Deployer.exe`
- [x] `TG2Cloud-OpenList-Deployer.exe`
- [x] 两者均为 PySide6
- [x] 正式 Tkinter EXE 数量 = 0
- [x] Release 中无旧 TG115 EXE
- [x] Release 中无 debug/test EXE

## D. CloudDrive2 Edition

- [x] `tg2cloud-clouddrive2-bot`（源码/自动化）
- [x] `tg2cloud-clouddrive2`（源码/自动化）
- [x] `tg2cloud-clouddrive2-net`（源码/自动化）
- [x] `/opt/tg2cloud-clouddrive2`（源码/自动化）
- [x] Tunnel：`127.0.0.1:19798`（源码/自动化）
- [x] 本地 19798 占用时明确报错（自动化）
- [x] 不自动切换其他端口（自动化）
- [ ] CloudDrive2 管理页可打开 — 未测试（需授权 VPS）
- [ ] 用户可以自行登录和挂载网盘 — 未测试（需测试网盘）
- [ ] WebDAV 认证正常 — 未测试（真实环境）
- [ ] 列目录正常 — 未测试（真实环境）
- [ ] 上传正常 — 未测试（真实环境）
- [ ] 重命名正常 — 未测试（真实环境）
- [ ] 删除正常 — 未测试（真实环境）
- [ ] Telegram 实际转存正常 — 未测试（真实环境）

## E. OpenList Edition

- [x] `tg2cloud-openlist-bot`（源码/自动化）
- [x] `tg2cloud-openlist`（源码/自动化）
- [x] `tg2cloud-openlist-net`（源码/自动化）
- [x] `/opt/tg2cloud-openlist`（源码/自动化）
- [x] Tunnel：`127.0.0.1:5244`（源码/自动化）
- [x] 本地 5244 占用时明确报错（自动化）
- [x] 不自动切换其他端口（自动化）
- [x] 首次管理员信息 UX 正常（frozen UI/自动化；真实登录未测试）
- [x] 已初始化实例不会自动重置（自动化）
- [ ] OpenList 管理页可打开 — 未测试（需授权 VPS）
- [ ] 用户可以自行挂载网盘 — 未测试（需测试网盘）
- [x] WebDAV 凭据 UX 正常（frozen UI/自动化）
- [ ] WebDAV 认证正常 — 未测试（真实环境）
- [ ] 列目录正常 — 未测试（真实环境）
- [ ] 上传正常 — 未测试（真实环境）
- [ ] 重命名正常 — 未测试（真实环境）
- [ ] 删除正常 — 未测试（真实环境）
- [ ] Telegram 实际转存正常 — 未测试（真实环境）

## F. TG2Cloud Core

- [ ] Bot 登录 — 未测试（真实 Bot/VPS）
- [x] Allowed User 限制（自动化）
- [x] SQLite（自动化）
- [x] Queue（自动化）
- [x] Restart Recovery（自动化）
- [x] `/start`（自动化）
- [x] `/help`（自动化）
- [x] `/queue`（自动化）
- [x] `/status`（自动化）
- [x] `/performance`（自动化）
- [x] `/task`（自动化）
- [x] `/confirm`（自动化，业务语义未改）
- [x] `/retry`（自动化）
- [x] `/cancel`（自动化）

## G. 磁盘

- [x] `LOCAL_TEMP_BUDGET_GB=20`（源码/自动化/frozen UI）
- [x] `MIN_FREE_DISK_GB=8`（源码/自动化/frozen UI）
- [x] PySide6 可修改（frozen UI）
- [ ] VPS 配置正确 — 未测试（真实 VPS）
- [ ] 容器实际生效 — 未测试（真实 Docker）
- [x] 超预算文件策略未破坏（自动化）
- [x] 清理逻辑正常（自动化；真实大文件未测试）

## H. verify

以下仅表示机器协议与模拟流程通过；真实 WebDAV 验收仍未测试。

CloudDrive2：

- [x] `TG2CLOUD_STORAGE_GATEWAY=clouddrive2`
- [x] `TG2CLOUD_WEBDAV=OK`
- [x] `TG2CLOUD_UPLOAD=OK`
- [x] `TG2CLOUD_RENAME=OK`
- [x] `TG2CLOUD_DELETE=OK`
- [x] `TG2CLOUD_DESTINATION=OK`

OpenList：

- [x] `TG2CLOUD_STORAGE_GATEWAY=openlist`
- [x] `TG2CLOUD_WEBDAV=OK`
- [x] `TG2CLOUD_UPLOAD=OK`
- [x] `TG2CLOUD_RENAME=OK`
- [x] `TG2CLOUD_DELETE=OK`
- [x] `TG2CLOUD_DESTINATION=OK`

## I. 文件传输测试

- [ ] 10～100 MB — 未测试
- [ ] 500 MB — 未测试
- [ ] 1 GB — 未测试
- [ ] 2 GB — 未测试
- [ ] 5 GB — 未测试
- [ ] 失败重试 — 未进行真实传输测试
- [ ] 重启恢复 — 未进行真实传输测试
- [ ] 本地临时清理 — 未进行真实传输测试
- [ ] 远端最终文件大小确认 — 未测试

## J. 隐私

- [x] 无遥测（静态审计）
- [x] 无第三方统计（静态审计）
- [x] 无凭据回传（静态审计）
- [x] SSH 密码脱敏（自动化/静态审计）
- [x] Bot Token 脱敏（自动化/静态审计）
- [x] API Hash 脱敏（自动化/静态审计）
- [x] WebDAV 密码脱敏（自动化/静态审计）
- [x] OpenList 管理员密码脱敏（自动化/静态审计）
- [x] `.env` 不进入公开诊断（自动化/静态审计）
- [x] `rclone.conf` 不进入公开诊断（自动化/静态审计）
- [x] 网盘 Token 不进入日志（静态审计）

## K. 安全

- [x] CloudDrive2 默认不公网暴露（源码/自动化）
- [x] OpenList 默认不公网暴露（源码/自动化）
- [x] 使用 SSH Tunnel（源码/自动化；真实隧道未测试）
- [x] 敏感配置权限合理（脚本静态审计/自动化）
- [x] 已有有影响操作有明确确认；v1.0.0 不新增 uninstall（已知限制）
- [x] 默认不删除 Gateway 持久化数据（脚本静态审计/自动化）
- [x] 源码中无真实 Token（扫描命中仅为明确测试 fixture）
- [x] Git 中无真实凭据（当前跟踪文件扫描）

## L. 文档

- [x] `README.md`
- [x] `CHANGELOG.md`
- [x] `RELEASE_NOTES.md`
- [x] `AGENTS.md`
- [x] `docs/AUDIT.md`
- [x] `docs/WORKLOG.md`
- [x] `docs/MIGRATION_FROM_TG115.md`
- [x] `docs/MANUAL_ACCEPTANCE.md`
- [x] CloudDrive2 文档
- [x] OpenList 文档
- [x] Tunnel 文档
- [x] WebDAV 文档
- [x] Backup（已有能力）；restore 不在 v1.0.0 范围内（已知限制）
- [x] Update
- [x] Uninstall 不在 v1.0.0 范围内（已知限制，非发布阻断项）
- [x] FAQ
- [x] LICENSE
- [x] NOTICE 判定：MIT/当前上游材料未要求独立 NOTICE，未虚构文件
- [x] TG115 上游致谢

## M. Release

- [ ] Windows 干净环境构建 — 未测试（当前开发机完成构建）
- [x] 正式 EXE 数量 = 2
- [x] SHA256 已生成并复核
- [x] Release Notes 已完成
- [ ] `v1.0.0-rc.1` Tag 已创建并推送 — 发布准备中
- [ ] GitHub Pre-release `TG2Cloud v1.0.0 RC1` 已发布 — 发布准备中
- [ ] 三个正式 Release assets 已上传并核对 — 发布准备中
- [x] Stable `v1.0.0` 未创建
- [x] Release 中无 Tkinter
- [x] Release 中无旧 TG115 构建

## 最终发布条件

当前状态：

```text
RELEASE CANDIDATE — MANUAL ACCEPTANCE PENDING
```

源码、自动测试、正式构建、冻结资源、品牌、隐私、安全静态审计和文档已完成。真实 VPS、
Tunnel、WebDAV、Telegram 端到端、大文件以及 Windows Taskbar/Alt-Tab/干净机验收仍须按
`docs/MANUAL_ACCEPTANCE.md` 执行；这些项目未勾选，不得视为通过。
