# 备份与恢复边界

先明确哪些数据被包含，哪些没有被包含。备份包本身可能含敏感凭据，不能公开上传。

## CloudDrive2 Edition

当前没有手动“创建安全备份”UI。重新部署前的内部备份包含程序和配置、现有 `rclone.conf`，并在可用时创建 SQLite 一致性快照。

它**不包括**下载目录、日志以及 CloudDrive2 状态目录；也不备份云端实际文件。需要完整灾难恢复时，应另行保护这些必要数据，不能只保留升级回退点。

## OpenList Edition

日常管理中的安全备份包含程序配置（含 `.env`、`rclone.conf`）、可用的 SQLite 快照及已初始化的 OpenList 状态，排除网关临时文件与日志。

为了避免复制不一致的 OpenList 数据，操作会短暂停止 Bot 和 OpenList，结束后重新启动并检查健康。它也不包含下载文件、TG2Cloud 日志或云端文件。

## 共享 HTTPS 代理需要独立备份

两个 Edition 的现有备份都**不包含** `/opt/tg2cloud-proxy`。强制 HTTPS 之后，仅恢复 Edition 数据仍不足以恢复管理入口。

独立保护以下内容：

- `state/domains.json`：两个 Edition 的域名与后端端口映射；
- `docker-compose.yml`、`nginx/nginx.conf` 和 `nginx/conf.d/`：共享代理与续期配置；
- `certbot/letsencrypt/` 完整目录：包括 `live/`、`archive/`、`renewal/` 和账户信息，保留符号链接及其目标，不能只复制 `live/` 下的链接。

先安排维护窗口，禁止两个部署器同时修改代理配置，并暂停 Certbot 续期后再以 root 或必要的 sudo 权限备份；完成后恢复续期并检查状态。无需停止 Bot 传输来备份代理，但如果还要备份 Edition 数据，应遵循其一致性要求。

私钥与账户信息属于敏感数据。目录限制为 700、备份文件限制为 600，传出 VPS 使用安全传输并考虑加密；不要上传公共仓库或 Issue。锁文件和 ACME 临时 challenge 不是需要恢复的业务状态。

恢复时先在隔离环境检查归档、权限、状态版本和域名映射，再确认 80/443 归属及两个后端仍只监听回环地址。复用有效证书，依次验证 Nginx 配置、本机 HTTPS、外部网络访问和续期。不要将整包直接解压覆盖生产 `/opt`，也不要删除现有证书强迫重新签发。当前没有一键代理 Restore，以上恢复流程仍需要管理员独立演练。

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

v1.1.1 没有正式自动 Restore。旧 TG115 的队列/数据库迁移也未被声明完成真实环境验收。

备份可读取不等于恢复已验证。重要部署应在受控环境制定恢复步骤，并保留独立可恢复副本；不要边猜数据库位置边覆盖生产实例。

## 私密保存

备份含 Token、密码和网关状态。放在自己控制的受限目录，传出 VPS 时使用安全传输并考虑加密，不要把完整包附到公开 Issue。
