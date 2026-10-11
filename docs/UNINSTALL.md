# TG2Cloud 独立卸载脚本

`uninstall.sh` 适用于标准目录下的 CloudDrive2 / OpenList 受管 Docker 部署，包括公网 VPS 的 HTTPS 和独立内网管理入口。它独立于 `install.sh`、`install-lan.sh` 和两个 Windows EXE，不改动安装器或 Bot 业务流程。

> 当前正式版本为 v1.2.0。用户已反馈原保留数据卸载在其 VPS 验收通过，不据此标记两 Edition、NAS 或新增完整清理均通过。**本轮完整清理增强尚未发布，仍需新的实机验收**；在线引导仍固定到原不可变提交 `5b85703a2a484788d4b51428032d20f61c55cd4d`，在线命令暂保持原保留数据行为。下面的完整清理选项适用于修改后的本地源码，须先通过 CI / 审查并更新固定提交才能在线生效。两个 EXE 未修改。

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

修改后的本地向导默认完整清理所选 TG2Cloud 实例及可识别备份。先核对范围，执行时还需输入删除口令：

```bash
bash ./uninstall.sh --edition all
```

只卸载一个 Edition：

```bash
bash ./uninstall.sh --edition clouddrive2
bash ./uninstall.sh --edition openlist
```

不指定 `--edition` 时，向导询问卸载 `clouddrive2`、`openlist` 或 `all`。只读 `--check` 必须明确指定 Edition。实际执行前列出容器、网络、数据目录、备份目录和共享代理处理方式，先等待默认 **N** 的确认，再要求输入 `DELETE ALL all`；单 Edition 对应 `DELETE ALL clouddrive2` 或 `DELETE ALL openlist`。任一取消或不匹配均不执行卸载。没有 `--yes` 或无人值守强制删除。

## 清理模式

默认模式等同 `--purge-all`，包括配置、Session、SQLite、下载、日志、云网关授权配置以及所选 Edition 可识别的历史备份。没有其他 HTTPS 路由、另一 Edition 容器或保留实例目录时，也删除共享代理配置、证书和可识别的共享代理备份。**先把需要保留的备份复制到这些清理目录之外；这不是恢复操作，删除后不能靠原目录中的备份回退。**

```bash
bash ./uninstall.sh --edition all --purge-all --check
bash ./uninstall.sh --edition all --purge-all
```

只移除运行资源、保留配置和数据时，必须明确选择 `--keep-data`：

```bash
bash ./uninstall.sh --edition all --keep-data --check
bash ./uninstall.sh --edition all --keep-data
```

兼容原 `--purge-data`：删除实例数据，但保留历史备份：

```bash
bash ./uninstall.sh --edition all --purge-data --check
bash ./uninstall.sh --edition all --purge-data
```

`--purge-data` 仍使用 `DELETE all` / `DELETE clouddrive2` / `DELETE openlist`，与会删除备份的 `DELETE ALL …` 区分。三个模式互斥。

| 项目 | 默认 / `--purge-all` | `--purge-data` | `--keep-data` |
| --- | --- | --- | --- |
| 所选 Bot、云网关容器 | 停止并移除 | 同左 | 同左 |
| 所选项目网络 | 无外部连接且归属正确时移除 | 同左 | 同左 |
| 所选 HTTPS 路由 / LAN 容器与入口配置 | 移除；另一 Edition 路由保留 | 同左 | 同左 |
| TG2Cloud 共享 Nginx / Certbot 容器 | 没有剩余 HTTPS 路由时移除 | 同左 | 同左 |
| `.env`、Session、SQLite、下载、日志、云网关账号授权配置 | 删除所选标准实例目录 | 同左 | 保留 |
| 共享代理配置、证书私钥与日志 | 无剩余路由、其他 Edition 容器/保留目录时删除 | 同左 | 保留 |
| Edition 历史备份 | 删除所选可识别备份目录 | 保留 | 保留 |
| 共享代理历史备份 | 无剩余路由、其他 Edition 容器/保留目录时删除 | 保留 | 保留 |
| Docker 镜像缓存 / CLI 与代理锁元数据 | 保留 | 保留 | 保留 |
| 系统 Docker、Nginx、其他容器、旧 TG115、云端已有文件 | 不操作 | 不操作 | 不操作 |

标准实例目录仅为 `/opt/tg2cloud-clouddrive2` 和 `/opt/tg2cloud-openlist`。自定义目录、同名外部容器、额外服务、未知挂载或使用中的网络都会停止，不通过文件名前缀猜测归属。标准部署使用宿主机 bind mount，没有需要删除的命名卷；不会清理其他 Docker 卷或使用全局 `prune`。

项目网络为 `tg2cloud-clouddrive2-net`、`tg2cloud-openlist-net`；共享代理的 Certbot 使用 `tg2cloud-proxy_default`，仅在没有剩余 HTTPS 路由且没有外部容器连接时一起移除。Nginx 和 LAN 入口使用 host 网络，绝不删除 Docker 的 `host`、`bridge`、`none` 网络。

共享代理历史备份在 `/opt/tg2cloud-proxy-backups`，Edition 备份在各自 `/opt/tg2cloud-<edition>-backups`。只识别现有工具生成的普通文件名及私密归属；遇到手工文件、子目录、链接、外部引用或挂载点即停止，不读取备份中的凭据。确认后备份清单或元数据变化也停止。备份可能包含凭据或证书私钥；保留不表示可以公开上传。锁文件为并发协调所需的少量元数据，不是仍在运行的服务；卸载中不会删掉正在持有的锁再创建新 inode。

“完整清理”是清除上述可验证的 TG2Cloud 实例数据与备份，**不等于把 VPS 逐字节还原到安装前**：安装 / 升级过程中 APT 软件包的变化、Docker 镜像及构建缓存、系统日志、锁元数据，以及你在 Cloudflare 添加的 DNS 记录不会回滚。无法判断镜像 / 系统配置是否早已存在或被其他项目复用，因此不执行全局 prune，也不卸载系统软件。

## 安全与部分失败

- 先结束进行中的 Telegram / 云盘传输。停止容器最多等待 60 秒，超时后 Docker 可能终止进程，不能据此保证任务完成。
- 先核对 Compose 标签、安装目录、固定容器名称和挂载，再按不可变容器 / 网络 ID 移除。确认期间资源变化时停止；不执行手改 Compose 的 `down --remove-orphans`。
- 移除单个 HTTPS 路由复用现有事务和剩余路由自检。另一 Edition 的自检失败时恢复原路由，并在移除 Bot / 云网关前停止。
- CloudDrive2 数据目录可能包含真实云盘 FUSE 挂载。数据删除预检和删除前都会检查挂载；发现挂载即拒绝递归删除，也不会执行强制 / lazy 卸载。可先明确使用 `--keep-data` 移除运行资源，再确认挂载已释放后重新预检完整清理。仅去掉 `--purge-data` 已不再表示保留数据。
- 不删除云端文件，不读取 / 显示 `.env`、`rclone.conf`、密码或容器环境变量；异常原始输出不回显。
- 与一键安装 / 升级使用相同 Edition 锁，并使用共享 HTTPS 事务锁。**不能同时通过 EXE 或其他终端操作相同实例**；EXE 基础部署没有这个 CLI 锁。
- 失败、取消或连接中断可能部分完成。不会自动重装、删除更多数据或假装回滚全部容器；重新运行 `--check` 核对，确认剩余范围后再执行。
- `--keep-data` 保留的安装目录不能当作全新目录被安装器覆盖；如需全新安装，可在明确备份后使用本脚本清理可识别的标准残留，再运行安装向导。未知残留停止并要求人工核对。即使原容器已卸载，可识别的备份也可再次预检清理。

结果：`TG2CLOUD_UNINSTALL_CHECK=OK` 仅表示预检；`TG2CLOUD_UNINSTALL_RESULT=OK` 表示所选运行资源和路由的卸载后复检通过，数据 / 备份是否保留以计划为准。`CANCELLED` 不执行计划；`FAILED` / `INTERRUPTED` 不等于卸载完成。
