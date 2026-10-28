# Docker Compose 部署

本功能正在本地开发，**尚未随正式版本发布镜像或部署包**。当前稳定版的一键脚本仍是可用入口。下面的镜像与 Release 资产步骤须待对应版本正式发布后使用；不要把版本示例当成已经存在的下载。

## 适用范围

适合已有 Docker 的 Linux／NAS 用户，宿主机不需要安装 Python。要求 Docker Compose **2.24.0 或以上**，支持原生 Linux AMD64 和 ARM64；真实硬件、FUSE 和网关能力仍需验收。CloudDrive2 需要 `/dev/fuse` 及其现有高权限配置；OpenList 不使用这些权限。

两版使用同一个 Bot 镜像，每份部署包含 Bot 和一个对应网关。网关镜像及其权限从现有正式清单生成；第一版不接管外部网关。每个 Edition 保留独立的 SQLite、Bot Session、个人监听 Session、暂存、日志和网关配置。

Compose 安装与一键脚本安装分别维护。不要把部署包解压到已有脚本安装目录，也不要让两个实例同时使用同一个 Bot Token 或数据库。默认容器与网络身份保持两 Edition 的标准命名，因此同一主机不能直接同时启动同 Edition 的两套部署。`tg2cloud` 目前不接管直接 Compose 安装；完整交互管理和自动 HTTPS 请继续使用一键脚本。

## 获取正式部署包（发布后）

从对应 GitHub Release 下载同版的文件：

- `TG2Cloud-v<版本>-compose-clouddrive2.tar.gz`，或 OpenList 对应包。
- `COMPOSE-SHA256SUMS.txt`。

在只包含这些下载文件的目录执行 `sha256sum --ignore-missing -c COMPOSE-SHA256SUMS.txt`，必须看到所选文件 `OK`，再解压。校验和用于完整性核对，不是数字签名。镜像是公开的 `ghcr.io/luopojunzi/tg2cloud`；部署包将其固定到实际多架构 manifest digest，不默认跟随 latest。

以下 Docker Compose 管理命令在 root 管理终端执行（或逐条加 `sudo`），因为生成的 `.env` 归 root 所有且权限为 600。先进入解压后的目录，可放在例如 `/opt/tg2cloud-compose-clouddrive2`。确认目录确实属于新实例；备份、旧 Session 和未知数据不会被初始化覆盖。

## 交互初始化

```bash
docker compose run --rm setup
```

首次会收集 Telegram API ID、API Hash、Bot Token、一个管理员 ID、WebDAV 用户及密码、保存子目录、暂存预算和保留空间。密码隐藏输入，留空生成；不要求手工填写 Base64。Base64 是兼容配置编码，不是加密。

默认暂存预算 20GB、至少保留 8GB，支持修改；初始化检查部署目录所在文件系统是否容纳预算及保留空间。这里不自动安装 Docker，也不提供一键脚本的完整宿主机资源推荐／FUSE 预检。容器侧空间检查不能覆盖所有网关缓存、其他文件系统或 NAS 宿主机限制，须同时检查宿主存储池。

管理端口默认仅绑定 `127.0.0.1`。需要从可信内网访问时，在向导填写这台 NAS／Linux 的实际内网 IPv4，例如 `192.168.26.5`；不接受 `0.0.0.0` 或公网 IPv4。填写后仍需核对本机确实拥有该地址及防火墙策略。第一版不支持直接绑定 IPv6。

初始化服务以 root 短暂运行，只挂载本部署目录和本地备份目录，没有网络、Docker Socket 或宿主机根目录。它只准备本实例的权限；Bot 始终 UID/GID 10001，OpenList 网关为 1001，CloudDrive2 保留自身必要权限。NFS／SMB 共享目录若不支持这些权限，应改用本地受支持目录，不用 chmod 777。

重复执行会检查并保留已有配置，不再生成密码或重置管理员。初始化中断后，可重试已知空目录；发现未知内容或不完整私有配置时停止，先检查文件，不覆盖用户数据。

## 启动网关并配置云存储

CloudDrive2：

```bash
docker compose up -d clouddrive2
```

OpenList：

```bash
docker compose up -d openlist
```

可信内网管理地址分别为 `http://<本机内网IPv4>:19798`、`http://<本机内网IPv4>:5244`。若保持回环绑定，需要通过自己的 SSH 隧道或已有反向代理访问。

在网关后台挂载自己的云存储，创建与向导一致的专用 WebDAV 用户，授予上传所需的权限并限定账号根目录。Bot 保存子目录是在这个账号根目录下面的相对目录；留空表示使用账号根目录。OpenList 的初始化管理员密码由向导生成，只在确认后的私有终端显示，不等于外部 WebDAV 手机凭据。

忘记向导中填写的值，可重新在私有终端查看：

```bash
docker compose run --rm setup python -m tg2cloud.compose credentials
```

这只显示本地保存值；后台已修改的管理员密码不会被重置。

## 启动和检查 Bot

CloudDrive2：

```bash
docker compose up -d tg2cloud-clouddrive2-bot
docker compose logs --tail=100 tg2cloud-clouddrive2-bot
```

OpenList 使用 `tg2cloud-openlist-bot`。不要公开完整日志或 `docker compose config` 输出；它们可能含凭据。只检查 Compose 结构时使用 `docker compose config --quiet`。

```bash
docker compose ps
docker compose run --rm setup python -m tg2cloud.compose check
```

配置检查只验证本地版本、实例标记与配置，不代表 Telegram 登录、网关权限、实际上传或公网访问通过。最后向 Bot 提交一个小文件，确认任务完成、远端大小复验和本地清理，再从自己的云盘核对文件。

## 已有反向代理与 HTTPS

第一版不占用 80/443，不自动配置 Nginx、签发或续期证书。可以由现有 HTTPS 反向代理转发管理页到受控回环端口；代理若在另一容器内，需自行建立经过确认的网络连接，不能把容器自己的 127.0.0.1 当成宿主机。证书与续期由该代理维护。

公网管理域名必须继续拒绝 `/dav` 和 `/dav/` 下的访问；不要把管理端口直接开放公网。可信内网 HTTP 也不要通过路由器端口映射暴露公网。第一版没有把外部只读 WebDAV、家庭授权管理或监听终端登录整合到 Compose 工具中；Bot 核心已有功能仍由原有权限控制，但相关宿主维护入口须等后续适配，不宣传为与一键脚本全部等价。

## 备份与升级

先暂停调度并等待任务结束，再停止此 Compose 项目的 Bot 和网关：

```bash
docker compose stop
docker compose run --rm setup python -m tg2cloud.compose backup --offline-confirmed
```

确认参数表示你已经停止它们；工具没有 Docker Socket，不能替你证明服务已停。备份放在本目录 `backups/`，包含 `.env`、Compose、实例／版本标记、业务数据库、Bot／个人 Session、rclone 配置和网关配置，复用现有清单、SHA256 和 SQLite 完整性检查。必须先实际运行过 Bot，形成数据库和 Session；缺失覆盖项、活跃 WAL 或不安全链接时停止。

不包含 `downloads`、`logs`、网关挂载的云端文件或独立 HTTPS 配置；有保留的失败暂存任务时，需在停机后另行备份 `downloads`。备份含秘密，权限 600；建议再复制到独立安全位置。工具不会自动恢复生产数据库。

备份成功后，保留旧部署包和镜像 digest，把新正式部署包的公开文件替换到当前目录，**保留 `.env`、tg2cloud-compose.json、data、config、downloads、logs、网关数据和 backups**。归档不包含实际 `.env`，但解压前仍应核对文件清单。

```bash
docker compose pull
docker compose run --rm setup python -m tg2cloud.compose check
docker compose up -d
```

检查 Bot 健康和日志，再做小文件转存验收。新包可能同时更新网关固定镜像，应先阅读该版说明；不能在有活动写入时直接切换。不要用 `down -v`、镜像自动更新工具或强制覆盖数据来升级。

回退前先停止新实例，保留故障现场。如果涉及数据库迁移，须恢复匹配旧代码的一致性数据库、配置和 Session；仅换回旧镜像不保证安全。备份包只做隔离恢复预检与人工恢复，不提供一键覆盖生产数据。原配置／数据库格式兼容时也须按该版说明判断，不把版本回退当成自动恢复保证。

## 停止使用

`docker compose stop` 仅停止，`docker compose down` 移除此项目容器和网络，目录挂载的数据保留。云端文件不会被删除。正式清除本地目录前先确认无共享引用、保留必要备份，再由自己处理；本指南不提供自动删除用户数据命令。若共享了网络或反向代理，需要先解除相应引用。

## 开发与发布前验证

本地生成候选包（不会构建／发布镜像）：

```bash
python3 .github/scripts/compose_release.py bundle --directory build/compose-candidate
```

候选仍指向当前源码版本的镜像名称，不表示该镜像存在。开发者可用已有 `build_payload.py` 生成上下文并本地构建，在隔离 Compose override 中替换 setup 与 Bot 的 image；不要修改生产部署。

先正常发布包含本功能的新稳定 Tag，完成同标签原生 Linux 检查和源码资产验证，再人工运行 Actions 的 **Compose images and bundles** 并填写该 Tag。工作流从相同不可变提交构建两架构、运行两版隔离初始化与非 root 配置检查，再发布版本 manifest 和固定 digest 的部署包。禁止从 moving main 发布，不改稳定 helper pin，也不替换历史源代码资产。

首次 GHCR 包可能默认私有。发布管理员需将其设为 public；匿名拉取检查未通过时不会发布用户部署包。修正可见性后可重跑：相同提交的版本 index 会复核并复用，已有资产逐字节相同才接受，不能通过 clobber 覆盖。

人工验收必须补充两架构安装、两种真实网关、已有反向代理、断网／重启、升级与隔离恢复；CI 成功不等于这些实机步骤通过。


## 官方参考

- [Docker Compose 可选 env_file 与最低版本](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)。
- [Docker 多架构 manifest 与注解](https://docs.docker.com/reference/cli/docker/buildx/imagetools/create/)。
- [GitHub Actions 发布镜像与权限](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)。
