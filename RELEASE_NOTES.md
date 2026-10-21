## TG2Cloud v1.4.2 · 复用已有 Docker Nginx

新增显式授权的 external_docker 入口：不关闭原有 Docker Nginx，不启动第二层代理，将 TG2Cloud 管理站点接入可核验的现有持久化配置。原 managed 模式继续默认使用，已有实例不会自动迁移。

## 本次更新

- 新增只读检测、配置导出、显式配置、维护、漂移复核、事务恢复与受限迁移命令。核对真实端口占用、容器／Compose 身份、挂载与网络，不把 EXPOSE 当成公网发布。
- host 模式使用受控回环后端；bridge 模式连接经过核验的持久化 Compose 网络，使用稳定别名与 Docker DNS，Bot 保持原网络，不公开网关后端端口。
- 对 TG2Cloud 专属文件执行逐文件比较后写入、私密备份与故障恢复；先 nginx -t，再 reload，实际检查 HTTPS、跳转、证书及管理域名 /dav 阻断。不修改外部 Compose，不停止或重建外部代理。
- 支持核验后复用已有证书，或以 Webroot 方式签发并建立调用离线代码的宿主续期任务。新证书自动化要求系统 cron/crond 已运行；Certbot 不挂载 Docker Socket，不使用 standalone 抢占端口。
- 共享状态升级至 schema 3，兼容独立外部 WebDAV 的认证资源、禁用与卸载保护；不会将管理域名的 /dav 放开。
- 卸载只移除所选实例拥有的站点；不删除外部 Nginx、Compose 或网络。最后路由移除后撤销本功能续期任务，默认保留外部证书、私密恢复状态及离线维护命令。

## 使用与兼容边界

安装命令保持不变：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

复用外部代理不是自动接管。先按[Docker Nginx 说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/DOCKER-NGINX.md)执行只读检测和计划导出，核实后显式授权。首次自动接入只支持标准实例目录、普通 Nginx、可验证的持久化挂载和原生本机 rootful Docker；不接管 Nginx Proxy Manager、SWAG、面板生成配置或 OpenResty。自定义目录提供人工方案，不假报自动成功。

现有证书的外部续期工具仍由原工具负责，程序不会假定其已可自动续期。managed → external_docker 迁移需要人工安排维护窗口并先完成端口切换，不承诺零中断或自动回滚外部项目。未知资源、配置漂移与未恢复事务均安全停止。

无需数据库迁移或调整 Bot 环境变量；保留配置、任务、Telegram Session、网关数据和上传策略。Bot 依赖、固定镜像与内网入口不变。schema 3 只能由本版及兼容的新工具写入；请更新离线管理工具，旧助手不应操作新状态。历史 Windows EXE 保持 v1.2.1，不生成新版 EXE。

## 发布与验证

发布工作流从同一不可变 v1.4.2 Tag 进行原生 AMD64／ARM64 验证，新增隔离 Nginx 单层代理、原站保留与 reload 回归，所有门禁通过后才发布 TG2Cloud-v1.4.2-source.tar.gz 和 SHA256SUMS.txt。helper 先验证辅助提交 A，再在 B 固定真实提交；业务只使用正式稳定 Release，不在失败时退回 moving main。校验和用于完整性检查，不是数字签名。

本地完整回归949项：921执行通过、28因环境条件跳过、0失败；随后对最后的参数／认证保护调整复跑 Python 3.10 新代理52项、外部 WebDAV55项和HTTP1项，通过。Ruff、Bandit、源码清单、双 Edition 载荷组装、Shell 语法及文档构建／19项测试通过。本地没有 Docker，隔离 Docker 验证交由本次双架构 CI，不把跳过写成已通过。

未连接真实 VPS，未操作用户网盘。真实 ACME 签发、长期续期、现有网站业务、迁移／回退、卸载及手机外网仍需独立实机验收。历史 CloudDrive2 验收范围见[v1.3.0 记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)和[v1.4.1 ARM64 NAT 记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V141-ACCEPTANCE.md)，不外推为本次新模式通过。
