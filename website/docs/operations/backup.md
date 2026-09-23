# 备份与恢复边界

先明确哪些数据被包含，哪些没有被包含。备份包本身可能含敏感凭据，不能公开上传。

## CloudDrive2 Edition

当前没有手动“创建安全备份”UI。重新部署前的内部备份包含程序和配置、现有 `rclone.conf`，并在可用时创建 SQLite 一致性快照。

它**不包括**下载目录、日志以及 CloudDrive2 状态目录；也不备份云端实际文件。需要完整灾难恢复时，应另行保护这些必要数据，不能只保留升级回退点。

## OpenList Edition

日常管理中的安全备份包含程序配置（含 `.env`、`rclone.conf`）、可用的 SQLite 快照及已初始化的 OpenList 状态，排除网关临时文件与日志。

为了避免复制不一致的 OpenList 数据，操作会短暂停止 Bot 和 OpenList，结束后重新启动并检查健康。它也不包含下载文件、TG2Cloud 日志或云端文件。

## 默认备份目录

```text
/opt/tg2cloud-clouddrive2-backups
/opt/tg2cloud-openlist-backups
```

查看数量和占用属于只读操作：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh backups
sudo /opt/tg2cloud-openlist/manage.sh backups
```

部署会报告备份占用，超过 5GB 时提示人工关注，不在升级时自动清空历史回退点。

## 显式删除旧回退点

下面的命令会删除符合脚本规则的旧备份，每类保留最新 5 份：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh prune-backups 5
```

:::danger 删除前先确认
第一次升级后的真实文件验证完成前，不要急着运行清理。`prune-backups` 是有破坏性的保留策略，不是查看命令。确认 Edition、备份可用性和保留数量后再执行。
:::

脚本只处理当前 Edition 备份目录内特定命名的普通文件，不清理旧 TG115 备份。不要把这个范围扩大为手动递归删除整个 `/opt`。

## 恢复不是一键承诺

v1.0.3 没有正式自动 Restore。旧 TG115 的队列/数据库迁移也未被声明完成真实环境验收。

备份可读取不等于恢复已验证。重要部署应在受控环境制定恢复步骤，并保留独立可恢复副本；不要边猜数据库位置边覆盖生产实例。

## 私密保存

备份含 Token、密码和网关状态。放在自己控制的受限目录，传出 VPS 时使用安全传输并考虑加密，不要把完整包附到公开 Issue。
