# 复用已有 Docker Nginx（v1.4.2）

本页对应已发布的 v1.4.2：辅助 A／固定入口 B 各五项 CI、[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39592291162)全部通过，实际下载的源码包、SHA256 和 GitHub 摘要已核验。正式在线入口已固定经过验证的辅助代码，不使用 moving-main 业务源码；真实 VPS／ACME／迁移仍须独立验收。

## 两种入口模式

| 模式 | 请求路径 | 生命周期 |
| --- | --- | --- |
| managed | TG2Cloud 自带 Nginx → 网关 | 保留原有 Compose / Certbot 行为；现有用户默认不变 |
| external_docker | 已有 Docker Nginx → 网关 | 只新增 TG2Cloud 站点，检查后 reload，不停止、重建或修改外部 Compose |

不会增加第二层 Nginx，不会为了腾出端口停止其他网站。只有显式授权后才向外部挂载目录写入专属文件。Bot、Telegram、命名、下载上传和数据库不改动；管理域名 `/dav`、`/dav/` 仍拒绝访问。外部只读 WebDAV 仍须单独安装、使用独立域名与账号。

## 支持条件

- Debian / Ubuntu、Python 3.10+、原生 AMD64 / ARM64、本机默认 rootful Docker daemon；不使用 QEMU、远端 daemon、rootless 或用户命名空间重映射。
- 普通 Nginx，有真实 master 进程和标准 `nginx -T` 输出；需完整配置检查及 `nginx -s reload`。
- 首版自动复用针对标准 `/opt/tg2cloud-clouddrive2`、`/opt/tg2cloud-openlist` 实例；自定义目录需导出方案人工接入，不在不明确归属时重配现有网关。
- 公网 TCP 80/443 确实属于所选容器。bridge 只自动支持宿主 80/443 到容器同端口的通配发布；不将 EXPOSE 当成发布。
- `http` 上下文中已有绝对路径 `*.conf` include，其目录映射到 root 所有、不可由其他用户写入的持久化 bind 目录，或本机 local named volume。支持容器只读挂载，由宿主写入；不能动态给运行容器添加卷。
- host 模式使用已验证的宿主 `127.0.0.1` 网关；bridge 模式要求外部项目有可验证的 Compose 文件、服务标签及已声明且已连接的自定义 bridge 网络。
- 需要宿主 curl、openssl、ss 和现有代理所需基础工具。TG2Cloud 管理新证书时，还要求已运行的系统 cron/crond；本功能不会自动安装、启动或重启它。

非 Compose 的 host 容器可在原容器 ID 不变时复用；同名重建不视为身份保证。Compose 重建仍须重新核对逻辑身份、镜像引用、挂载、网络和非受管配置指纹。

不自动接管 Nginx Proxy Manager、SWAG、控制器、面板生成配置、OpenResty/Tengine、默认 bridge、跨主机／内部网络、相对 include、非常规 prefix、路径带空格／链接或权限过宽的挂载。存在正则域名时保守拒绝冲突判断。上述情形可导出人工接入计划，不会输出安装成功。

## 从本地审阅源码使用

先在测试主机取得你已审阅的源码，以下命令均可从其他工作目录使用绝对路径调用。这里的 `edge-nginx`、域名和源码目录均须替换。

```bash
python3 -B /path/to/TG2Cloud/scripts/run_source.py proxy --help
python3 -B /path/to/TG2Cloud/scripts/run_source.py proxy detect
python3 -B /path/to/TG2Cloud/scripts/run_source.py proxy export --edition clouddrive2 --nginx-container edge-nginx --domain cloud.example.com --output /root/tg2cloud-proxy-plan
```

`detect` 只读。导出目录必须不存在；导出的 JSON 不是安装成功证明，不含密码或私钥。支持环境下还输出待审阅的专属站点候选；不支持的环境只有阻塞原因和人工准备步骤，不生成猜测可用的配置。

主安装向导在端口冲突时列出候选及编号，推荐复用；多个候选不会随机选择。显示容器、网络、域名、站点目录、证书责任与新增资源后请求授权；原有执行确认仍保留。显式参数为：

```bash
python3 -B /path/to/TG2Cloud/scripts/run_source.py install --edition clouddrive2 --proxy-mode external_docker --nginx-container edge-nginx --authorize-proxy
```

此命令仍是交互安装器，需要收集与确认配置；不是无人值守安装承诺。未授权、未指定目标、端口归属不明或尝试在占用端口上强行选 managed 时停止。

已有匹配网关可以显式配置入口（不运行主安装、不重启网关）：

```bash
python3 -B /path/to/TG2Cloud/scripts/run_source.py proxy configure --edition clouddrive2 --nginx-container edge-nginx --domain cloud.example.com --yes --authorize-proxy
```

bridge 模式须先由受管安装/升级载荷持久化网关网络；单独 configure 不会偷偷重建现有网关。不会用一次性 `docker network connect` 伪装持久化。现有 managed 用户需走下文的独立迁移，不通过 configure 隐式切换。

## 网络与文件

bridge 模式只调整 TG2Cloud 自己的规范 Compose：网关额外加入选中的既有外部网络，Bot 保持原网络。使用稳定容器 DNS 名称，Nginx 变量上游经 Docker DNS 重新解析；不缓存容器 IP，不开放网关公网端口。核验同网别名冲突和从 Nginx 内访问真正的网关页面；不把任意 HTTP 200 当作成功。

新站点使用 `tg2cloud-clouddrive2.conf`、`tg2cloud-openlist.conf`、`tg2cloud-webdav-*.conf` 及归属头；不改 `nginx.conf`、`default.conf` 或他人站点。资产目录为所选挂载下的 `tg2cloud-assets`，包含持久化 Webroot、认证哈希和本功能管理的证书。密码文件是目录挂载内的原子替换，不会因文件 inode 绑定继续使用旧密码。

共享状态 `/opt/tg2cloud-proxy/state/domains.json` 使用 **schema 3**，保存外部身份、站点摘要、网络、证书责任及加载记录；版本 1/2 继续用于 managed。未知状态拒绝覆盖。旧维护端遇到 schema 3 会拒绝操作；不要用旧 EXE、旧离线 runtime 或固定旧 helper 维护新入口。

基础安装后 HTTPS 失败时，私密 `external-pending-<edition>.json` 保留明确的网络计划，使后续源码基线核验能识别已授权的 Compose 变体。不删除数据库、Session 或重新创建实例来掩盖失败。

## 证书和真实续期

若已有持久化证书包含域名、信任链可验证、私钥匹配且有效期超过七天，可以复用。记录真实路径，但**不接管外部工具续期，也不把未知调度写成已验证**。用户必须确认原工具负责签发、续期和 reload。

否则在专属资产目录使用固定 Certbot 镜像的 Webroot：发布仅 ACME 的 HTTP 引导 → 完整 `nginx -t` → reload → 本机随机 challenge 映射复验 → 签发 → 域名／链／私钥验证 → HTTPS 配置 → reload → 真实页面、跳转、访问限制及服务证书复验。Certbot 不绑定公网端口、不挂 Docker Socket、不停止 Nginx。每个域名的签发尝试有五分钟冷却；失败先排查，不反复申请。

TG2Cloud 管理新证书时，创建唯一受管 `/etc/cron.d/tg2cloud-external-proxy`，每十二小时调用本地离线 `tg2cloud proxy maintain`。不会每次维护下载 main。安装前验证 cron/crond 处于活动状态，冲突的同名任务不覆盖。无该服务时明确停止，不声称已有自动续期。

维护比较续期前后叶证书摘要，只有更新或有待加载记录时才 reload；提交 pending-load 后再重载，并以带域名信任验证的真实 TLS 连接确认服务加载的叶证书。续期失败不删除有效证书，reload 失败保留待加载状态供后续重试。外部证书依旧由原管理器维护，不新增第二套签发任务。

```bash
tg2cloud proxy check --edition clouddrive2
tg2cloud proxy maintain --yes --authorize-proxy
tg2cloud proxy maintain --dry-run --yes --authorize-proxy
```

dry-run 会联系测试 ACME 并写测试账户／日志，不是只读；不等于正式续签或长期续期已验收。上述本地命令需要先安装当前离线管理代码；仅查看本地源码时使用 `python3 -B /path/to/TG2Cloud/scripts/run_source.py proxy ...`。

本机信任链、证书、网关页面与跳转通过不代表公网手机连通。DNS A/AAAA、CDN、NAT 与云安全组仍需独立核对；管理端口仍应只绑定回环。WebSocket 头保持，不将头部配置检查写成已完成真实应用握手。

## 事务、备份与修复

写入在现有共享入口锁内复核。逐文件记录原内容和候选，比较摘要后替换；检查失败只回滚本次文件，不能恢复整目录覆盖别人修改。普通中断尝试回滚；断电/强杀后保留私密 journal，阻止继续写入。原站点最多抽样八个精确域名的 HTTP 状态；这不是所有网站和功能的全量验收。

```bash
tg2cloud proxy recover --edition clouddrive2 --nginx-container edge-nginx --yes --authorize-proxy
```

恢复只接受同一目标和已登记范围；若站点被其他人并发修改，会保留恢复日志并拒绝覆盖。不要删除 journal、锁或修改摘要来绕过保护。

每次事务的私密元数据／专属站点备份位于 `/opt/tg2cloud-proxy/external-backups/`，清单含文件摘要；不复制整个外部目录、其他项目私钥或证书工具数据。离线管理菜单的创建备份、最近备份核验／隔离解包已适配此范围；不能当作完整灾难恢复包。证书仍保留原持久化存储，需要另行按原工具备份，所有私密材料禁止公开上传。

其他网站配置变化会触发保守漂移保护，自动操作停止；确认这些变化由自己实施、专属站点未变后，可显式更新基线：

```bash
tg2cloud proxy revalidate --edition clouddrive2 --nginx-container edge-nginx --yes --authorize-proxy
```

此操作不接受未知的 TG2Cloud 站点修改、镜像／项目／挂载／网络切换。后端网络失联应先核对 Compose 声明及真实连接；不能通过临时网络连接或公开 19798/5244 绕过。

## 已有 managed 模式迁移

普通安装和升级不自动切换模式。先导出 `migration-plan`，审阅全部管理域名和 WebDAV，备份原配置和证书，安排维护窗口。当前迁移要求**用户先完成端口切换、持久化网络和可供目标 Nginx 读取的有效证书准备**；不是自动停止旧入口或批量重新签发所有域名。

```bash
tg2cloud proxy migration-plan --edition clouddrive2 --nginx-container edge-nginx --output /root/tg2cloud-migration-plan
tg2cloud proxy migrate --edition clouddrive2 --nginx-container edge-nginx --yes --authorize-proxy
```

执行前原受管 Nginx 和旧 Certbot 应由用户在维护窗口停用，避免端口和双重续期；目标外部 Nginx 已运行、网络可达，所有域名有效证书位于其持久化挂载，并由用户确认原续期责任。条件不满足就停止。迁移会保留私密旧状态和旧资源，不承诺零中断；回切需要在维护窗口按备份人工恢复原入口和调度，不提供未经验证的一键全局回滚。

## 外部 WebDAV、卸载与保留

附加功能自动识别 schema 3，通过同一适配器写专属只读站点、同步认证与证书；不创建第二套 Nginx，不修改 Bot 的凭据或数据。停用／换密先撤销实际目录中的认证，再变更站点；失败不恢复 Bot 或管理员凭据。

主卸载仍先阻止删除有 WebDAV 依赖的网关；请先独立停用并卸载附加路由。删除一个 Edition 只移除其管理站点，其他路由保留。删除最后一个路由后撤掉 TG2Cloud 的续期任务，但不停止或删除外部 Nginx、外部 Compose 或网络。证书、私密状态和恢复材料默认保留，离线管理命令因此也保守保留；这与 managed 模式最后实例完整清理的规则不同。未实现自动彻底清理外部证书，需另行逐项确认归属和引用，不以主卸载参数强行删除。

## 发布与实机门槛

本轮本地验证（2026-10-21）：完整 unittest 949 项，921 执行成功、28 因 Windows／未启用 Docker 等环境条件跳过；参数边界收尾后，Python 3.10 标准库环境的 52 项新增测试、55 项附加功能和 1 项 HTTP 回归再次通过。Ruff、Bandit、compileall、仓库清单、Shell 语法、两 Edition 载荷组装及网站构建／19 项测试／内部引用检查通过。完整回归不以 skip 掩盖失败，具体模拟边界见测试代码。

```bash
python3 -B -m unittest discover -s tests -p 'test*.py' -q
python3 -B -m unittest discover -s tests -p test_external_proxy.py -v
python3 -B .github/scripts/check_repository.py
python3 -B .github/scripts/prepare_bootstrap.py
```

已添加仅操作独立网络、临时容器与测试证书的真实 Nginx 用例，显式开启方式如下；本机无 Docker，但辅助 A 已在[原生 AMD64／ARM64 CI](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/39591006899)执行通过，覆盖单层代理、原站保留、nginx -t 失败及 reload，不代替真实 ACME、用户网关或迁移验收。

```bash
TG2CLOUD_TEST_EXTERNAL_NGINX_DOCKER=1 python3 -B -m unittest discover -s tests -p test_external_nginx_docker.py -v
```

代码清单已纳入 bootstrap/runtime manifest；已公开且通过五项 CI 的辅助 A 为 `840472f919409531e99da55c62070ea262ebed6d`。入口 B／Tag 为 `42e2c372823a085c36a7a7597ce775441598aaf9`，逐文件清单与 A 一致；B 的五项 CI 和同标签双架构发布均通过，源码资产已实际下载核验。后续维护继续执行先 A 后 B 的流程，不能填写伪 SHA 或回退 moving main。

尚需专用测试环境覆盖：host/bridge 与 named volume、两 Edition 和 WebDAV 共存、实际证书签发/续期/加载、容器重建及网关 IP 变化、原网站与 WebSocket、迁移维护窗口、完整升级回退及安全卸载。离线测试和配置渲染不能代替这些验收。
