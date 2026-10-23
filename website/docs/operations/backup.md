# 备份与恢复边界

先确认备份包含什么、怎样校验，以及哪些数据需要另存。备份包可能含 Token、Session 和证书私钥，只放在自己的受限目录，不公开上传。

## 当前入口与数据库兼容

运行 `tg2cloud`，选择对应 Edition，再选 **13. 数据备份管理**。两版都支持实例快照；**7. HTTPS 与管理** 用于入口检查 / 修复和续期演练，不是创建备份的菜单。

业务数据库从 v1.4.3 使用 schema 2。升级前保存与旧代码匹配的一致性快照；旧 Bot 不直接打开 schema 2，不能只降级镜像。回退前要保护当前数据，再核验旧数据库与代码，不能删表“降级”。

## 三类备份不要混用

| 类型 | 包含 | 不包含 |
| --- | --- | --- |
| 升级回退点 | 所选 Edition 的程序 / 配置、可用的一致性业务 DB；网关范围按脚本 | 不能假设包含 Session、downloads、完整网关状态或共享代理 |
| 实例快照 / 导出 | 配置、业务 DB、Telegram Session、rclone 与限定网关配置 | downloads、日志、共享 HTTPS、附加功能状态和云端文件 |
| 共享代理备份 | 受管代理状态 / 路由、配置、证书 / ACME 信息及所含认证资源 | Bot 业务 DB、Session、下载、完整附加私密目录和云端文件 |

网关配置备份不等于复制所有网盘数据或网关缓存。外部 WebDAV 的私密目录要单独保护；external_docker 还需按其登记责任保护外部代理的网络、证书及配置，不假设 TG2Cloud 备份了整个其他项目。

## 创建实例快照

在 **13. 数据备份管理** 选择 **6. 创建实例快照／导出**，核对所选 Edition 与私密输出目录后确认。

为了获得一致状态，会短暂停止所选 Bot 和网关；同一网关的管理和外部 WebDAV 读取可能中断，其他 Edition 不停止。完成后恢复原有容器运行状态，并再次检查业务就绪。

菜单默认输出位置为 `/opt/tg2cloud-snapshots/<edition>`，不放进默认卸载清理范围；仍应准备私密离机副本。快照含敏感配置，不附到 Issue。

失败或中断时先看结果和服务状态，不把“恢复原容器运行状态”理解为“已从备份恢复了生产数据”。

## 实例快照隔离预检

选择 **7. 实例快照隔离预检**，指定归档绝对路径与新的私密测试目录。工具检查清单、SHA-256、SQLite 完整性及兼容性，不覆盖在线文件或自动启动恢复服务。

归档能解包、数据库能读取，不等于 Telegram、网关授权、网络和云端读写都已经恢复。完整运行恢复仍需独立演练。

## CloudDrive2 与 OpenList 的差异

CloudDrive2 升级回退点不应当作完整网关状态备份；需要限定实例状态时使用上面的快照 / 导出，不再寻找旧桌面的“安全备份”按钮。

OpenList 管理脚本的业务安全备份会短暂停止所选服务，以保护配置和数据库一致性；不包含云端文件、下载或共享代理。它与统一的实例快照、代理备份仍是不同产物，不按文件名猜范围。

更多清单、静止副本要求和兼容命令见[完整备份指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/BACKUP-RESTORE.md)。

## 共享 HTTPS 代理需要独立备份

在 **13. 数据备份管理** 选择 **2. 创建共享代理备份**。managed 模式的主要范围包括：

- `state/domains.json` 和已登记的管理 / 外部路由；
- Compose、Nginx 配置及认证资源；
- `certbot/letsencrypt/`，包括 live / archive / renewal 和 ACME 账户；不能只拷贝 live 符号链接；
- 域名续期记录，区分检查成功和实际证书变更。

工具使用共享事务锁。源文件在续期期间变化时，不把不一致归档当成有效快照；按提示稍后重试。通常无需停止运行中的 Bot。

归档放在 `/opt/tg2cloud-proxy-backups/`，私密目录 0700、归档 0600。external_docker 的备份与恢复责任见[代理专题](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/DOCKER-NGINX.md)。

## 校验、隔离解包与清理

同一备份菜单中：

| 子项 | 作用 |
| --- | --- |
| 3. 查看共享代理备份 | 查看已登记归档 |
| 4. 校验/隔离解包最近代理备份 | 核对摘要、清单及权限，不覆盖在线配置 |
| 5. 清理旧代理备份 | 先预览，再确认；固定保留最近 5 份有效备份 |

清理候选有变化或校验失败时重新预览；只处理明确清单中的受管归档及校验文件。删除后不能自动撤销，失败或中断可能已删除部分项目，应重新核对。

代理备份操作有执行时限。SSH / Docker 无响应或强制中断时，不能声称临时任务已清理完毕。隔离解包通过不等于完整服务恢复。

## Edition 升级回退点

只读查看各自历史备份数量与占用：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh backups
sudo /opt/tg2cloud-openlist/manage.sh backups
```

备份目录分别是 `/opt/tg2cloud-clouddrive2-backups`、`/opt/tg2cloud-openlist-backups`。超过提示容量需人工关注，升级不会自动清空历史点。

`manage.sh prune-backups 5` 是实际删除策略，不是查看命令，也没有代理菜单的同一预览流程。完成真实升级验收、确认有独立副本并核对范围后再考虑，不在新手流程中直接执行。

## 完整恢复仍需独立演练

没有覆盖生产数据的一键 Restore。正式恢复前需核对版本、数据库、Session、网关授权、资源与代理状态，保护当前可用配置，防止新旧 Bot 同时使用同一 Token。

不要把整包直接解压覆盖生产 `/opt`，也不要删除现有证书强迫签发。验收记录只证明各自执行过的范围：[v1.4.4 双架构升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)、[v1.4.2 人工升级与备份核验](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md)、[v1.3.3 升级与用户转存](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V133-ACCEPTANCE.md)。它们不等于灾难恢复已通过。

## 私密保存

快照、数据库、Session、配置、网关数据与证书都可能包含完整秘密。保存到卸载清理范围之外，限制属主和权限，离机传输时使用安全通道并考虑加密。完整范围见[备份指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/BACKUP-RESTORE.md)，升级前另读[升级说明](/operations/update/)。
