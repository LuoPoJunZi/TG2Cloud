# 外部 WebDAV（独立可选附加功能）

让手机文件管理器或播放器通过独立 HTTPS 域名，只读访问 Bot 已有上传目录。不复制数据、不重装网关、不重复挂载网盘、不新增 FUSE，也不是独立于 CloudDrive2/OpenList 的文件系统；底层网关和共享 Nginx/Certbot 必须继续可用。

本功能自 **v1.3.1** 提供，安装要求包含本功能的正式稳定源码包和 SHA256 清单；实际发布状态以 [GitHub Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/latest) 为准。已通过隔离 Nginx 认证、只读/编码路径、Range 和密码轮换回归；原生两版账号/目录、手机、公网 ACME 和 ARM64 尚未端到端实机验收。

## 独立入口

待发布开发版已适配[外部 Docker Nginx](DOCKER-NGINX.md)：自动识别 schema 3，经同一入口适配器管理独立只读站点、认证及证书，不创建第二套代理；撤销同步到真实持久化认证目录。已开始的读取可能持续至连接关闭，不通过停止外部 Nginx 强制中断。旧 schema 2 与当前稳定 v1.4.1 的原有管理代理流程保持原样；新增模式实机结果不能沿用上述旧回归结论。

v1.3.3 增加 `tg2cloud-webdav` 的“用户管理”（序号 10／`users`）：多个独立原生只读账号共同访问已确认的目录，不创建个人目录，不自动绑定 Bot 家人。单账号操作与整入口启停的区别、schema 兼容及验收步骤见[家庭共享](FAMILY-SHARING.md)。v1.3.2 及更旧版本尚无该菜单，需单独升级离线附加工具。

审阅源码后，在测试 Linux 主机从任意目录运行：

```bash
bash /path/to/TG2Cloud/install-webdav.sh --help
bash /path/to/TG2Cloud/install-webdav.sh install --edition clouddrive2
bash /path/to/TG2Cloud/install-webdav.sh install --edition openlist
```

无参数进入自己的向导，不进入主安装菜单；双 Edition 必须明确选择。自定义目录用 `--install-dir /opt/your-instance`，必须与 Compose 标签、持久化挂载和实例身份一致。不接管手工外部后端或部分实例。

### v1.3.2 交互优化

v1.3.2 向导改用中文编号菜单，选择网关后选择安装、状态、检查、启停、配置、卸载、升级或手机配置；`0` 退出。原英文子命令及参数保持兼容。已安装的离线代码不会自动更新，需从新正式入口显式执行附加功能升级；这与主实例的升级分开。

向导读取当前实例的 Bot 保存子目录；未设置时显示“使用账号根目录”。原生账号根目录仍须后台核对，只有实例、Bot 目录绑定和网关镜像均未改变时，才提供此前确认值供回车复用。计划、后台建号和手机配置均使用本次实际目录，没有固定网盘路径。

手动输入的密码不设最低长度或字符种类要求；仍拒绝空值、空白、控制字符、非 ASCII 和超过 128 位的输入，并给出不包含输入值的提示。回车生成 9 位大小写字母及数字随机密码。短密码保护较弱，建议使用生成密码或自行设置更长的独特密码。这里的输入规则不代替后端自身的密码要求。

确认安装计划后，建号说明和最后的手机配置各向当前私有终端显示本次密码，不再单独询问是否显示。请避免旁观、录屏或分享终端历史。密码不进入日志、命令参数或持久化记录；以后运行 status/print-config 不显示密码。安装计划简化内部文件列表，安装成功后提示运行 `tg2cloud-webdav` 重新打开离线管理菜单。主安装与 Bot 不变。

独立在线入口如下；正式 Release 缺少功能协议、源码包或校验清单时失败，不退回 main 业务代码。无需重新运行主安装向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

安装成功提供本地离线命令，不会每次 status 下载代码：

```bash
tg2cloud-webdav
tg2cloud-webdav status --edition openlist
tg2cloud-webdav print-config --edition openlist
tg2cloud-webdav check --edition openlist
tg2cloud-webdav check --edition openlist --sample-file '视频/现有视频.mp4'
tg2cloud-webdav disable --edition openlist
tg2cloud-webdav enable --edition openlist
tg2cloud-webdav configure --edition openlist
tg2cloud-webdav upgrade --edition openlist
tg2cloud-webdav uninstall --edition openlist
```

CloudDrive2 改用 `--edition clouddrive2`。status/print-config 仅显示登记信息，check 才验证实际实例、代理、认证和目录。可选样本只做 HEAD、OPTIONS、单字节 Range，不下载完整视频、不写入或删除。密码只从控制终端隐藏输入，没有密码参数。

## 前置条件与只读预检

附加功能宿主检查接受 Debian/Ubuntu、Linux root、Python 3.10+、原生 64 位 AMD64 或 ARM64、本机默认 rootful Docker daemon。事先准备 Bash、OpenSSL、curl、ss/ip、getent、flock、timeout 和 Docker Compose。正式 v1.4.1 与主安装共用平台检查及公网 NAT 的人工确认预检，不改变独立账号或代理边界；既有离线工具需显式 upgrade。两架构的隔离 Nginx／认证／Range 检查已通过，原生网关账号、Oracle 和手机仍需端到端实机验收，见[双架构说明](ARCHITECTURES.md)。

不自动安装依赖、重装/重启 Docker、调用主安装器、停其他代理或开放防火墙。Bot 配置、rclone、数据库、上传目录和原账号不变；不重启 Bot 或网关。安装/检查/启用要求网关运行，关闭/卸载允许网关已停，但仍核验身份。

19798/5244 必须继续仅发布在 127.0.0.1，不改成公网 0.0.0.0。80/443 必须空闲或属于受管共享代理；其他 Nginx/Caddy、未知容器/挂载、缺状态、未知 schema、符号链接、目录重叠和域名冲突均停止，不自动修复。

全部 A/AAAA 直接指向当前主机，首次签发 Cloudflare 使用“仅 DNS”，安全组/防火墙允许 80/443。纯内网无法通过公网 HTTP-01 的 NAS 不适用，不降级为 HTTP 认证。写入前展示实例、目标目录、账号、域名、文件和共享代理变更，用户确认后锁内复核；新增挂载可能重建 Nginx，短暂影响管理入口。

## 真实目录与独立原生账号

必须区分 Bot 用户原生根目录、Bot 相对子目录、最终网关逻辑目录、VPS 本地目录。用户在后台确认根目录为 `/媒体`、Bot 子目录为 `Telegram`，最终目录才是 `/媒体/Telegram`，不是 `/opt/.../downloads`。仅凭 `WEBDAV_TARGET_PATH_B64` 不能确定完整根目录；Base64 是编码，不是加密。

向导要求先核对并输入 Bot 原生根目录，再计算目标。新外部用户原生根目录必须直接限定为最终目标；手机 `/dav/` 即此目录。第一版拒绝暴露网关 `/`；宽权限账号加 Nginx 路径替换不算隔离。

第一版不使用未经核实的管理 API，不编辑后端数据库、不重置管理员、不读取或长期保存管理员凭据。采用完整人工流程：生成/隐藏输入新凭据 → 用户后台建号 → 输入完整目录并确认独立、隔离、原生只读 → 本地认证/XML 检查 → 发布 HTTPS。用户须核实新用户名也不是改过名称的管理员。

### CloudDrive2

后台核对当前版本及会员支持独立 WebDAV 用户。新建专用用户，根目录为最终目标，开启只读。不能使用主账号邮箱密码、管理员、匿名或 Bot 用户。能力不足取消，不提供高权限替代。

### OpenList

新建普通用户，base path 限定最终目标，只开 WebDAV 读取/列表；不要授予 WebDAV 管理、上传、删除、移动、改名、复制等写权限。不改管理员和 Bot 用户。按当前后台实际权限说明核实，不从未知数字权限位猜测。

### 验证边界

程序验证新凭据 PROPFIND、匿名拒绝、UTF-8 XML/href、TLS、入口账号及尾斜杠；**独立用户能力、原生只读和目录 ACL 由用户确认，不冒充自动审计**。不会对真实用户目录发写方法测试。

后端须能安全代理 WebDAV 读取；内部 href/远程重定向不受支持。程序不将 Authorization 发给其他地址；代理拒绝上游 30x，返回 502。若适配必须改影响 Bot 的全局设置，停止，不为方便改动 Bot 配置。真实播放/拖动用独立样本与外部手机验收。

## 手机参数与 HTTP 边界

```text
名称：TG2Cloud 文件
协议：HTTPS
服务器：用户设置的外部域名
端口：443
根路径：/dav/
用户名：新外部专用用户名
密码：使用新设置的外部专用密码
```

v1.3.2 向导在本次建号及完成页的私有终端显示密码；后续查看配置只提示使用已设置的密码，不存储明文用于回显。

没有默认生产域名。Nginx Basic Auth 文件只含本功能登记且启用的主账号与家人账号，不接受所有后端用户；使用随机盐、SHA512-crypt、200000 rounds。同一组凭据再交给本地后端，不替换为 Bot 凭据。其他后端有效用户、Bot、管理员也不能通过新域名。依据 [Nginx 支持的 crypt 格式](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html)，实际镜像由隔离集成和发布前实机确认。

仅 `/dav`、`/dav/` 下允许 GET/HEAD/OPTIONS/PROPFIND；其他路径 404、写方法 405、危险路径或查询参数 400。中文、空格和普通 URL 编码保留；禁止编码分隔符、点段穿越、重复危险编码、反斜杠。Depth 仅空值/0/1，不支持 infinity 或带令牌查询链接。Range 保留，响应流式、不落盘缓存。每 IP 每域名普通请求 30/s（burst 90）、PROPFIND 2/s（burst 10）、连接上限 32；不能替代后端只读权限。

管理域名 `/dav` 继续禁止，不用于手机。外部域名不展示后台，不记录访问 URL/Authorization/Cookie；日志和状态脱敏，认证仅 HTTPS，不跳过证书校验。

## 状态、事务与维护

- 元数据：`/opt/tg2cloud-webdav/<edition>/config.json`；原单账号 schema 1 兼容读取，使用 v1.3.3 家庭账号后为 schema 2，不存明文密码。
- 离线代码及来源：`/opt/tg2cloud-webdav/runtime/<摘要>/`。
- 该 Edition 的主账号及已启用家人账号哈希：`/opt/tg2cloud-proxy/external-auth/<edition>.htpasswd`。
- 元数据回退点：本 Edition `backups/`；共享代理备份：`/opt/tg2cloud-proxy-backups`。

元数据/备份 0600/0700；认证目录 0750、哈希 0640，组取固定镜像实际 worker GID。仅认证目录只读挂载，不挂整个私密状态目录。目录 bind mount 识别原子替换的新 inode，成功前核对容器实际读取的摘要。

锁顺序 Edition → 共享代理。写前备份、生成候选、Nginx 校验后激活，锁内复核 revision/实例绑定，冲突不覆盖。变更失败或普通中断保持拒绝/needs_repair，不退回匿名或 Bot 密码。后端手工改密无法原子回滚，不能声称入口哈希回退等于后端密码已回退。

- disable 先撤销认证再变为 HTTPS 403，保留配置/证书并继续续期；旧读取连接重载后最多约 10 秒退出。
- enable 重新认证、人工复核原生只读/目录后启用。Bot 用户、目录、URL 或网关镜像变化要求 configure，不扩大范围；后台单独改原生根目录不能靠 Bot 配置摘要感知，仍须人工复核。
- configure 先关闭旧入口，再引导账号、目录/域名变更；失败重新执行，不手工关闭鉴权。
- upgrade 仅从正式稳定源码资产核对 SHA256、Tag、版本/协议，运行候选校验后切换离线代码；不升级 Bot/网关。旧代码保留，失败不切换离线入口，但外部访问可能安全关闭。
- uninstall 只移除本功能路由、活动哈希和配置，不执行共享 compose down，不删除云文件、上传目录、Bot 数据或人工后端账号，不盲目删除证书。保留私密回退点和离线代码；后端用户需自行确认后手动删除。

共享备份包含 Nginx/Compose/状态、认证哈希、证书和 ACME 数据，都敏感，不能上传。校验/隔离解包仅证明结构和摘要，不代表服务已恢复。恢复还需匹配元数据、原生账号/密码、证书和 worker 权限；隔离解包的 0600 文件不能直接宣称已恢复生产挂载。回退先 disable 并保留当前记录，从审阅过的源码重新 configure/enable；不提供危险的一键生产恢复。

主卸载发现被引用网关或活动附加记录会停止；即使 disable 也须先独立 uninstall。删除最后一个管理路由时，外部路由仍在就保留 Nginx/Certbot。disable 的域名继续续期；卸载该路由后退出续期集合但不删除证书。schema 2 不自动降级，空共享资源留给主卸载受管清理。

## 状态兼容与发布步骤

最低写入端必须理解 **proxy schema 2 + external WebDAV API 1**，不能仅按相同产品版本号判断。首次安装从旧 schema 1 锁内迁移，未知版本/字段拒绝。本功能不改 Bot 数据库和环境变量。

| 状态／协议 | 版本含义 | 兼容注意 |
| --- | --- | --- |
| 共享代理 schema 2 | 管理与附加路由可共存。 | 旧 schema 1 写入端应拒绝，不能覆盖新路由。 |
| 附加配置 schema 1 | 原单账号配置。 | v1.3.3 工具兼容读取。 |
| 附加配置 schema 2 | 含家人账号记录。 | v1.3.2 及更旧附加工具不能操作；不要手动降 schema。 |
| External WebDAV API 1 | 附加功能的发布能力标记。 | 不等于上述两个状态文件必须都是 schema 1。 |

更新主 Bot 不会自动更新附加离线工具；先用正式入口升级对应工具，再按实际账号逐一检查。共享代理备份也不包含附加目录全部元数据，独立备份范围见[备份指南](BACKUP-RESTORE.md)。

旧 v1.3.0 helper 及严格版本检查的历史 Python 工具遇 schema 2 会拒绝操作，须使用 v1.3.1 起的匹配维护工具。更旧、没有状态版本校验的手工脚本/历史桌面工具无法保证安全，安装后禁止使用；不把旧恢复包覆盖到新代理，不手改 version 为 1。

发布与部署验收要求：

1. 实际开放前在自己的环境核实原生账号/目录只读权限、手机、ACME 及所用架构；本版这些实机项尚未执行，不因正式发布改写为通过。
2. v1.3.1 首次发布本功能；v1.3.2 更新交互，均单独创建 Tag/资产，不覆盖历史版本或 EXE。
3. 先公开并验证含 add-on 和共享模块的 helper 提交 A，再由入口 B 固定 A；严格发布校验阻挡不一致 helper，不能造 SHA 或自指提交。
4. 新源码资产包含本入口、`packaging/external-webdav.json`、全部模块及更新的显式清单。Release 生成/核验源码归档和 `SHA256SUMS.txt`，校验和不是数字签名。
5. 稳定 Release 发布后验证公开命令与资产下载；不新增 Windows 构建。CI 中合成后端不能代替原生账号/会员能力与权限审计。

## 排查

| 状态 | 排查方向 |
| --- | --- |
| 401 | 用外部域名、新专用账号和同一新密码；旧 Bot/管理员被拒绝是预期 |
| 403 | 已 disable、原生权限不足、Depth infinity；不放开全权限 |
| 404 | 根路径应为 `/dav/`，核实原生 base path；其他路径不展示后台 |
| 405 | 客户端发送写方法；第一版只读 |
| 429 | 降低目录枚举/并发，等待冷却，勿连续重试 |
| 502 | 网关/回环端口/认证及该版本本地代理读取能力；上游 30x 会被拒绝 |
| TLS/DNS | A/AAAA、80/443 归属、安全组、证书/续期；不忽略 TLS |
| needs_repair | 入口保持关闭，核实原生账号后 configure，不借用 Bot 凭据 |

## 自动与人工验收

```bash
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_feature.py -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test*.py' -v
bash -n install-webdav.sh
shellcheck install-webdav.sh
```

仅在一次性 Linux CI/隔离测试机、测试端口空闲时运行真实 Nginx + 合成 HTTP 后端（不是原生网关实机）：

```bash
TG2CLOUD_TEST_EXTERNAL_WEBDAV_DOCKER=1 PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_docker.py -v
```

实际开放前分别核实两版原生只读账号/会员/根目录；外部网络浏览中文、播放、拖动；无认证/错误密码/Bot/管理员拒绝；管理 DAV 仍拦截；轮换、启停、域名变更、失败/中断、升级回退、共享路由保留、私密备份隔离恢复和续期 dry-run；比对 Bot 配置、rclone、DB 和容器不变。上述是人工验收清单，不是已完成记录。写方法负面测试只在模拟后端或明确隔离对象进行，绝不发送 `DELETE /dav/` 到真实用户目录。
