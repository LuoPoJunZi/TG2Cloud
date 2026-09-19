# TG2Cloud v1.0.0 Release Checklist

## A. 项目身份

- [ ] 项目名统一为 `TG2Cloud`
- [ ] 版本统一为 `1.0.0`
- [ ] 多云存储定位清晰
- [ ] 115 仅作为示例/主要测试场景
- [ ] `CloudDrive2/115 → CloudDrive2` 已确认完成
- [ ] 没有重复修改已经正确的 CloudDrive2 UI
- [ ] 上游 TG115 关系透明

---

## B. 品牌资源

- [ ] 仓库中存在 `assets/brand/`
- [ ] Codex 使用现有正式 Logo，而不是重新设计
- [ ] `tg2cloud-logo.svg`
- [ ] `tg2cloud-icon.svg`
- [ ] `tg2cloud-icon.png`
- [ ] `tg2cloud-icon-32.png`
- [ ] `tg2cloud-icon-64.png`
- [ ] `tg2cloud-icon-128.png`
- [ ] `tg2cloud-icon-256.png`
- [ ] `tg2cloud-icon-512.png`
- [ ] `tg2cloud.ico`
- [ ] `tg2cloud-logo-preview.png`
- [ ] EXE 使用正式 ICO
- [ ] PySide6 使用正式 Icon
- [ ] README 使用正式 Logo
- [ ] About 使用正式 Logo
- [ ] 两个 Edition 共用同一主品牌
- [ ] 未产生未经确认的新 Logo

---

## C. 正式 Windows 构建

- [ ] `TG2Cloud-CloudDrive2-Deployer.exe`
- [ ] `TG2Cloud-OpenList-Deployer.exe`
- [ ] 两者均为 PySide6
- [ ] 正式 Tkinter EXE 数量 = 0
- [ ] Release 中无旧 TG115 EXE
- [ ] Release 中无 debug/test EXE

---

## D. CloudDrive2 Edition

- [ ] `tg2cloud-clouddrive2-bot`
- [ ] `tg2cloud-clouddrive2`
- [ ] `tg2cloud-clouddrive2-net`
- [ ] `/opt/tg2cloud-clouddrive2`
- [ ] Tunnel：`127.0.0.1:19798`
- [ ] 本地 19798 占用时明确报错
- [ ] 不自动切换其他端口
- [ ] CloudDrive2 管理页可打开
- [ ] 用户可以自行登录和挂载网盘
- [ ] WebDAV 认证正常
- [ ] 列目录正常
- [ ] 上传正常
- [ ] 重命名正常
- [ ] 删除正常
- [ ] Telegram 实际转存正常

---

## E. OpenList Edition

- [ ] `tg2cloud-openlist-bot`
- [ ] `tg2cloud-openlist`
- [ ] `tg2cloud-openlist-net`
- [ ] `/opt/tg2cloud-openlist`
- [ ] Tunnel：`127.0.0.1:5244`
- [ ] 本地 5244 占用时明确报错
- [ ] 不自动切换其他端口
- [ ] 首次管理员信息 UX 正常
- [ ] 已初始化实例不会自动重置
- [ ] OpenList 管理页可打开
- [ ] 用户可以自行挂载网盘
- [ ] WebDAV 凭据 UX 正常
- [ ] WebDAV 认证正常
- [ ] 列目录正常
- [ ] 上传正常
- [ ] 重命名正常
- [ ] 删除正常
- [ ] Telegram 实际转存正常

---

## F. TG2Cloud Core

- [ ] Bot 登录
- [ ] Allowed User 限制
- [ ] SQLite
- [ ] Queue
- [ ] Restart Recovery
- [ ] `/start`
- [ ] `/help`
- [ ] `/queue`
- [ ] `/status`
- [ ] `/performance`
- [ ] `/task`
- [ ] `/confirm`
- [ ] `/retry`
- [ ] `/cancel`

---

## G. 磁盘

- [ ] `LOCAL_TEMP_BUDGET_GB=20`
- [ ] `MIN_FREE_DISK_GB=8`
- [ ] PySide6 可修改
- [ ] VPS 配置正确
- [ ] 容器实际生效
- [ ] 超预算文件策略未破坏
- [ ] 清理逻辑正常

---

## H. verify

CloudDrive2：

- [ ] `TG2CLOUD_STORAGE_GATEWAY=clouddrive2`
- [ ] `TG2CLOUD_WEBDAV=OK`
- [ ] `TG2CLOUD_UPLOAD=OK`
- [ ] `TG2CLOUD_RENAME=OK`
- [ ] `TG2CLOUD_DELETE=OK`
- [ ] `TG2CLOUD_DESTINATION=OK`

OpenList：

- [ ] `TG2CLOUD_STORAGE_GATEWAY=openlist`
- [ ] `TG2CLOUD_WEBDAV=OK`
- [ ] `TG2CLOUD_UPLOAD=OK`
- [ ] `TG2CLOUD_RENAME=OK`
- [ ] `TG2CLOUD_DELETE=OK`
- [ ] `TG2CLOUD_DESTINATION=OK`

---

## I. 文件传输测试

- [ ] 10~100 MB
- [ ] 500 MB
- [ ] 1 GB
- [ ] 2 GB
- [ ] 5 GB
- [ ] 失败重试
- [ ] 重启恢复
- [ ] 本地临时清理
- [ ] 远端最终文件大小确认

无法执行的测试必须标记“未测试”。

---

## J. 隐私

- [ ] 无遥测
- [ ] 无第三方统计
- [ ] 无凭据回传
- [ ] SSH 密码脱敏
- [ ] Bot Token 脱敏
- [ ] API Hash 脱敏
- [ ] WebDAV 密码脱敏
- [ ] OpenList 管理员密码脱敏
- [ ] `.env` 不进入公开诊断
- [ ] `rclone.conf` 不进入公开诊断
- [ ] 网盘 Token 不进入日志

---

## K. 安全

- [ ] CloudDrive2 默认不公网暴露
- [ ] OpenList 默认不公网暴露
- [ ] 使用 SSH Tunnel
- [ ] 敏感配置权限合理
- [ ] 删除/卸载有二次确认
- [ ] 默认不删除 Gateway 持久化数据
- [ ] 源码中无真实 Token
- [ ] Git 中无真实凭据

---

## L. 文档

- [ ] `README.md`
- [ ] `CHANGELOG.md`
- [ ] `AGENTS.md`
- [ ] `docs/AUDIT.md`
- [ ] `docs/WORKLOG.md`
- [ ] `docs/MIGRATION_FROM_TG115.md`
- [ ] CloudDrive2 文档
- [ ] OpenList 文档
- [ ] Tunnel 文档
- [ ] WebDAV 文档
- [ ] Backup / Restore
- [ ] Update
- [ ] Uninstall
- [ ] FAQ
- [ ] LICENSE
- [ ] NOTICE（如需要）
- [ ] TG115 上游致谢

---

## M. Release

- [ ] Windows 干净环境构建
- [ ] 正式 EXE 数量 = 2
- [ ] SHA256 已生成
- [ ] Release Notes 已完成
- [ ] `v1.0.0` Tag 已准备
- [ ] Release 中无 Tkinter
- [ ] Release 中无旧 TG115 构建

---

# 最终发布条件

达到以下条件后才发布：

```text
CloudDrive2 PySide6 ✅
OpenList PySide6 ✅
TG Core ✅
Brand ✅
Privacy ✅
Security ✅
Docs ✅
```

所有未实际测试项目必须明确标记，不得伪造通过。
