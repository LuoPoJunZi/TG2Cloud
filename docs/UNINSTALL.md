# TG2Cloud 独立卸载脚本

`uninstall.sh` 适用于标准目录下的 CloudDrive2 / OpenList 受管 Docker 部署，包括公网 VPS 的 HTTPS 和独立内网管理入口。它独立于 `install.sh`、`install-lan.sh` 和两个 Windows EXE，不改动安装器或 Bot 业务流程。

> 当前源码版本为 v1.2.0。在线引导固定到已审查且通过 Windows/Linux、Python 3.10/3.13 CI 的不可变提交 `5b85703a2a484788d4b51428032d20f61c55cd4d`。**真实 VPS / NAS 卸载尚未验收**；请先结束任务、独立备份并只读预检，模拟测试不代表生产删除已验证。正式 EXE 由 GitHub Actions 构建，不从本机上传。

## 在线一键入口

先以只读方式检查；要求信任本仓库，可以先下载检查脚本：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh) --edition all --check
```

实际卸载命令会询问 Edition 并展示范围，再等待默认 N 的确认：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/uninstall.sh)
```

## 本地源码运行

在目标 Linux 的 TG2Cloud 源码根目录中以 root 执行。要求 Debian / Ubuntu x86_64、Python 3.10+、Bash、本机默认 Docker；涉及 HTTPS 路由时需要现有 Docker Compose 及 `flock`。不会替你安装、升级、重启或卸载系统软件。

先只读查看范围：

```bash
bash ./uninstall.sh --edition all --check
```

卸载全部 TG2Cloud 运行资源，默认保留本地配置、业务数据和历史备份：

```bash
bash ./uninstall.sh --edition all
```

只卸载一个 Edition：

```bash
bash ./uninstall.sh --edition clouddrive2
bash ./uninstall.sh --edition openlist
```

不指定 `--edition` 时，向导询问卸载 `clouddrive2`、`openlist` 或 `all`。只读 `--check` 必须明确指定 Edition。实际执行前列出容器、网络、数据目录和共享代理处理方式，确认默认 **N**；没有 `--yes` 或无人值守强制删除。

## 删除本地实例数据

需要删除本地配置与数据时，先备份，再预检：

```bash
bash ./uninstall.sh --edition all --purge-data --check
bash ./uninstall.sh --edition all --purge-data
```

`--purge-data` 除普通卸载确认外，还要求输入 `DELETE all`；单个 Edition 对应 `DELETE clouddrive2` 或 `DELETE openlist`。任一确认取消或不匹配，均不执行卸载。

| 项目 | 默认卸载 | `--purge-data` |
| --- | --- | --- |
| 所选 Bot、云网关容器 | 停止并移除 | 停止并移除 |
| 所选项目网络 | 无外部连接且归属正确时移除 | 同左 |
| 所选 HTTPS 路由 / LAN 容器与入口配置 | 移除；另一 Edition 的路由保留 | 同左 |
| TG2Cloud 共享 Nginx / Certbot 容器 | 没有剩余 HTTPS 路由时移除 | 同左 |
| `.env`、Session、SQLite、下载、日志、云网关账号授权配置 | 保留 | 删除所选标准实例目录，不可自动恢复 |
| 共享代理配置、证书私钥与日志 | 保留 | 没有剩余路由和另一 Edition 容器时才删除 |
| Edition 历史备份 / 共享代理历史备份 | 保留 | 仍保留 |
| Docker 镜像缓存 / CLI 与代理锁文件 | 保留 | 仍保留 |
| 系统 Docker、Nginx、其他容器、旧 TG115、云端已有文件 | 不操作 | 不操作 |

标准实例目录仅为 `/opt/tg2cloud-clouddrive2` 和 `/opt/tg2cloud-openlist`。自定义目录、同名外部容器、额外服务、未知挂载或使用中的网络都会停止，不通过文件名前缀猜测归属。标准部署使用宿主机 bind mount，没有需要删除的命名卷；不会清理其他 Docker 卷或使用全局 `prune`。

项目网络为 `tg2cloud-clouddrive2-net`、`tg2cloud-openlist-net`；共享代理的 Certbot 使用 `tg2cloud-proxy_default`，仅在没有剩余 HTTPS 路由且没有外部容器连接时一起移除。Nginx 和 LAN 入口使用 host 网络，绝不删除 Docker 的 `host`、`bridge`、`none` 网络。

共享代理历史备份在 `/opt/tg2cloud-proxy-backups`，Edition 备份在各自 `/opt/tg2cloud-<edition>-backups`。备份可能包含凭据或证书私钥；保留不表示可以公开上传。锁文件为并发协调所需的少量元数据，不是仍在运行的服务；卸载中不会删掉正在持有的锁再创建新 inode。

## 安全与部分失败

- 先结束进行中的 Telegram / 云盘传输。停止容器最多等待 60 秒，超时后 Docker 可能终止进程，不能据此保证任务完成。
- 先核对 Compose 标签、安装目录、固定容器名称和挂载，再按不可变容器 / 网络 ID 移除。确认期间资源变化时停止；不执行手改 Compose 的 `down --remove-orphans`。
- 移除单个 HTTPS 路由复用现有事务和剩余路由自检。另一 Edition 的自检失败时恢复原路由，并在移除 Bot / 云网关前停止。
- CloudDrive2 数据目录可能包含真实云盘 FUSE 挂载。数据删除预检和删除前都会检查挂载；发现挂载即拒绝递归删除，也不会执行强制 / lazy 卸载。可先用不带 `--purge-data` 的命令移除运行资源，再确认挂载已释放后重新预检删除残留数据。
- 不删除云端文件，不读取 / 显示 `.env`、`rclone.conf`、密码或容器环境变量；异常原始输出不回显。
- 与一键安装 / 升级使用相同 Edition 锁，并使用共享 HTTPS 事务锁。**不能同时通过 EXE 或其他终端操作相同实例**；EXE 基础部署没有这个 CLI 锁。
- 失败、取消或连接中断可能部分完成。不会自动重装、删除更多数据或假装回滚全部容器；重新运行 `--check` 核对，确认剩余范围后再执行。
- 默认保留的安装目录不能当作全新目录被安装器覆盖；如需全新安装，可在明确备份后使用本脚本 `--purge-data` 清理可识别的标准残留，再运行安装向导。未知残留停止并要求人工核对。

结果：`TG2CLOUD_UNINSTALL_CHECK=OK` 仅表示预检；`TG2CLOUD_UNINSTALL_RESULT=OK` 表示所选运行资源和路由的卸载后复检通过，数据 / 备份是否保留以计划为准。`CANCELLED` 不执行计划；`FAILED` / `INTERRUPTED` 不等于卸载完成。
