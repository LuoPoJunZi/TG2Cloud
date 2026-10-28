## TG2Cloud v1.5.2 · Compose 部署与监听恢复

## 本次改动

- 增加独立 Docker Compose 部署包，两 Edition 共用一个 Bot 镜像；交互初始化生成私有配置及目录权限，支持配置检查、凭据查看与停机离线备份。默认回环端口，可显式选择可信内网地址；第一版通过已有反向代理提供 HTTPS。
- 镜像发布工作流只接受已发布的稳定 Tag，在 Linux AMD64、ARM64 原生构建并执行两版隔离测试，部署包固定实际镜像 digest；一键升级和卸载拒绝接管直接 Compose 实例。
- 修复监听临时网络／服务器故障导致永久停用：30 秒连接／身份查询超时、5～300 秒退避重试、断开客户端重建；失效授权继续停止，旧请求不覆盖新授权或手动停用。
- 历史维护每类每批最多处理 500 行，保持原保留期、待确认保护及事务回滚；schema 3 下幂等补充查询索引。整理当前指南与历史验收导航，保留旧文件及链接。
- 补充原正式 v1.5.1 的不可变升级基线，保留两版配置、数据库、Session、下载及既有存储提交策略。

## 安装与升级

本版提供保留配置升级与独立 Compose 部署；实际 CI、helper 与资产证据见本版记录。已有脚本实例先在菜单 13 备份，再执行所选 Edition 的预检和升级；不需要卸载。

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.2/install.sh) --edition clouddrive2 --release v1.5.2 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.5.2/install.sh) --edition clouddrive2 --release v1.5.2
```

OpenList 改为 `--edition openlist`；内网使用同标签 `install-lan.sh`。升级后退出旧菜单，再运行 `tg2cloud` 核对 Bot 与 CLI 均为 1.5.2。Compose 新安装的资产、root 管理命令及范围见[部署指南](docs/COMPOSE.md)，镜像／部署包发布核验单独记录。

## 验证与兼容

沿用业务 schema 3，增加三个可重复创建的辅助索引，不改表字段、不增加运行依赖或必填配置；首次大库建索引可能增加启动时间。回退须先停机并保护现场，按版本恢复匹配代码和一致性备份；仅切换旧镜像不能替代数据库回退。

Compose 管理端口保持受控，Bot 非 root；CloudDrive2 保留 FUSE 专用权限。直接 Compose 暂不提供一键脚本的完整管理菜单、自动证书、外部 WebDAV 或个人监听终端登录等价入口，不自动迁移已有脚本实例。

本地回归和实际 CI／资产证据见[本版发布与验收](docs/development/V152-ACCEPTANCE.md)。**真实 VPS、NAS、Telegram、两种网关转存、小时级负载及生产恢复尚未执行。** 合成历史维护的单批耗时只说明单次占用，不代表总清理时间或传输提速。

历史验收按当时范围保留：[v1.3.0](docs/development/V130-ACCEPTANCE.md)、[v1.4.3](docs/development/V143-ACCEPTANCE.md)、[v1.4.4](docs/development/V144-ACCEPTANCE.md)、[v1.5.1](docs/development/V151-ACCEPTANCE.md)。
