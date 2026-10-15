**TG2Cloud v1.2.1** 完善任务恢复、视频命名与备份保护。两个 PySide6 Windows 部署器继续由 GitHub Actions 从同一标签测试、构建和自检，校验值来自本次实际产物。

## 下载选择

| 文件 | 用途 |
| --- | --- |
| `TG2Cloud-CloudDrive2-Deployer.exe` | CloudDrive2 Edition |
| `TG2Cloud-OpenList-Deployer.exe` | OpenList Edition |
| `SHA256SUMS.txt` | 核对同一 Release 的 EXE |

下载新版 EXE 不会自动更新 VPS Bot。已有实例请备份后使用保留配置升级，无需卸载重装。

## 本次更新

- **安全恢复**：已取消任务经确认可重新转存，保留编号、去重和历史记录；远端文件大小不一致或结果不确定时暂停自动恢复，确认后换名重传，保留原文件。
- **视频命名**：数字或默认名称可从消息说明提取标题，过滤链接、话题和常见推广；整组图片/视频共用说明并分别编号。没有说明时保留原名，不回查频道或评论区。
- **失败计数**：首页保持 `❌ 数字`，按 Bot 时区每周一切换统计范围；历史失败记录和恢复操作继续保留。
- **扫描与验证**：遗留清单增量读取，超时或截断明确显示未完成；删除范围和数量保护不变。记录远端大小验证及时间，不宣称内容哈希验证。
- **备份与回退**：完善两版 DB 快照复验、停止失败保护和镜像回退；新增可选离线业务快照清单及隔离恢复预检，保留独立 HTTPS 备份。
- **容量与诊断**：按文件系统显示资源，保护并发预留；补充任务查询、失败分类和错误脱敏。未增加依赖、环境变量、端口或 Compose 权限。
- **完整卸载**：纳入此前 main 的双确认完整清理；`--keep-data` 保留数据。默认完整清理会删除所选配置、数据库、下载及可识别备份，请先只读预检并保存独立备份。

CloudDrive2 保留临时上传、改名及大小复验；OpenList 保留预留无冲突路径后直接写最终文件的兼容策略。存储授权仍由用户在自己的网关中配置。

## Linux 一键入口

公网 VPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网 Debian / Ubuntu x86_64 主机：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

两个入口先收集信息、预检并确认，业务 payload 只取最新正式稳定 Release。完整且可核验的已有实例复用配置；内网入口要求手工指定私有 IPv4，公网 VPS 继续使用强制 HTTPS。

卸载先只读检查；实际清理会另行要求双重确认：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

卸载不是升级步骤，不卸载系统 Docker/Nginx，不清理云端文件或其他项目，也不承诺撤销所有系统变化。完整清理增强仍待新的实机验收。

## 升级与验收范围

数据库以兼容的增量字段和表保留历史任务，通常无需手工迁移；升级前仍须备份。新增冲突保护和恢复记录不应直接交给旧程序继续处理，回退须核对对应代码、数据库与任务状态。

专用 VPS 的候选回归最终 263 项通过、1 项 Qt 界面测试跳过，含 5 项真实 rclone 本地 WebDAV 测试。CloudDrive2 候选代码已完成旧版数据库副本迁移与兼容检查、保留 465 条历史任务的启动核验，以及真实 WebDAV 只读访问；原网关、OpenList 与 HTTPS 未变。

真实 Telegram 转存、不同客户端媒体组转发、远端冲突恢复、完整安装脚本升级/回退、OpenList 新版实例及长期运行仍待用户验收。上述候选检查不等于正式 EXE 或所有部署流程已通过实测；公开验收清单保留未完成项目。

## 构建与校验

Release Job 复用已经通过自检的 Windows artifact，不重复构建，不上传本机 EXE、build 或 dist。请使用本次 v1.2.1 Release 的 `SHA256SUMS.txt`，不要套用旧版本校验值。

Windows EXE 尚未商业代码签名；请核对仓库、标签、文件名和 SHA256。TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。

更多说明：[恢复指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.1/docs/RECOVERY.md) · [验收清单](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.1/docs/development/RELIABILITY-ACCEPTANCE.md) · [VPS 安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.1/docs/VPS-INSTALL.md) · [卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.2.1/docs/UNINSTALL.md)。
