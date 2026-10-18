# 外部 WebDAV（独立附加功能）

通过单独 HTTPS 域名，在手机文件管理器或播放器中只读访问 Bot 已有上传目录。共享原网关数据，不复制文件、不重新安装或挂载云盘；仍依赖 CloudDrive2/OpenList 和共享 Nginx/Certbot，不是完全独立的文件系统。

::: warning 验证范围
本功能自 v1.3.1 提供，要求对应正式稳定源码资产。隔离 Nginx 认证、只读、编码、密码轮换和 Range 已通过；原生两版账号/目录、手机、ARM64 与公网 ACME 尚未端到端实机验收。发布与资产状态以 GitHub Release 为准。
:::

## 与主安装的关系

不加入主安装向导，不默认询问或启用，不增加 Bot 命令和依赖，不改 Bot 账号、rclone、数据库、上传目录或网关监听。管理域名继续禁止 `/dav`；外部域名只服务 `/dav/`，不展示后台。不重启 Bot、网关或 Docker。

已有完整受管实例须通过 Compose 标签、目录、挂载、运行指纹核验；未知/部分实例、符号链接、未知共享状态、其他代理占 80/443 时停止，不自动接管。附加宿主代码接受 Debian/Ubuntu、root、Python 3.10+、x86_64/ARM64、本机 rootful Docker，ARM64 实机仍待验证。原主安装范围不因此扩大。

## 独立安装

审阅本地源码后，在测试 Linux 运行：

```bash
bash /path/to/TG2Cloud/install-webdav.sh install --edition clouddrive2
bash /path/to/TG2Cloud/install-webdav.sh install --edition openlist
```

两个 Edition 并存需明确选择，支持身份一致的 `--install-dir /opt/custom`；无参数为自己的向导。独立在线命令如下，不需要重新运行主安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

引导只执行正式稳定源码资产，核验同 Release SHA256 清单，不回退 main/RC。校验和不是数字签名。安装后提供离线 `tg2cloud-webdav`，status 不下载代码。

::: info v1.3.2 向导优化
新版采用中文编号菜单，保留原英文子命令，`0` 退出；已安装的离线代码需从新正式入口显式执行附加功能升级，不会自动变成新界面。安装后运行 `tg2cloud-webdav` 可重新进入独立管理菜单。
:::

新向导读取实际 Bot 保存子目录，未设置时显示“使用账号根目录”；账号根目录仍须后台核对。只有实例、目录绑定和网关镜像未变时，才建议复用此前确认值。计划、后台建号与完成页均使用本次实际目录，不固定任何网盘路径。

## 原生只读账号与目录

向导要求在后台核实 Bot 用户根目录，再与 Bot 相对子目录计算最终网关逻辑目录。例如 `/媒体` 加 `Telegram` 才是 `/媒体/Telegram`，不是 VPS 暂存目录；不能仅从 Base64 相对子目录推测完整根。Base64 不是加密。拒绝暴露网关 `/`。

外部账号原生根目录直接等于最终目标，手机 `/dav/` 即此目录，不能用管理员加路径改写冒充隔离。

- CloudDrive2：先核实当前版本/会员支持独立 WebDAV 用户，新建专用只读用户并限制根目录；能力不够就取消，不借主账号邮箱密码、匿名或 Bot 用户。
- OpenList：新建普通用户，base path 限定最终目录，只授予 WebDAV 读取/列表，不授予 WebDAV 管理、上传、删除、改名或移动。

第一版采用人工后台建号、输入完整目录并确认原生只读的受支持流程，不猜 API/权限位、不修改后端数据库、不重置管理员、不保留管理令牌。程序随后验证新凭据、匿名拒绝、目录 XML/href 和 HTTPS，但不能声称自动审计了原生权限。后台改名的管理员也需人工排除。

新密码安全生成或隐藏输入，不在参数、日志或 URL 中传递；历史 v1.3.1 经单独确认可只在终端显示。v1.3.2 向导在确认计划后，直接于后台建号说明和最后手机配置中向当前私有终端显示本次密码，不再重复询问；请避免旁观、录屏或分享终端历史。后续查看配置不会显示密码，也不会为回显保存明文。

v1.3.2 向导回车生成 9 位大小写字母及数字随机密码；手动密码不设最低长度或字符种类要求，但拒绝空值、空白、控制字符、非 ASCII 和超过 128 位的输入，提示不包含输入值。短密码保护较弱，建议生成或设置更长的独特密码；后端自身规则仍需满足。

入口单账号 Basic Auth 哈希门禁仅接受新用户，同一组凭据再由本地网关认证；其他后端有效用户、Bot、管理员都不能通过新域名。

## HTTPS 与手机

全部 DNS A/AAAA 直接指向此主机，首次签发 Cloudflare 用“仅 DNS”，安全组允许 80/443。复用共享代理，无代理且端口空闲才建立受管代理；19798/5244 仍只在 127.0.0.1 发布。不支持纯内网 HTTP 降级，不跳过证书校验。

```text
名称：TG2Cloud 文件
协议：HTTPS
服务器：你设置的外部域名
端口：443
根路径：/dav/
用户名：新外部专用用户名
密码：使用新设置的外部专用密码
```

仅 GET/HEAD/OPTIONS/PROPFIND，其他写方法拒绝；Depth 仅空值/0/1。中文、空格、正常编码和 Range 保留，流式读取不完整落盘。危险点段/重复编码、反斜杠、查询参数拒绝；上游重定向返回 502，不把凭据送往其他主机。限流兼容常规播放，但大量并发枚举仍可能 429。网关须支持安全的本地 WebDAV 读取代理，不能为兼容修改影响 Bot 的全局设置。

## 检查、维护和卸载

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

CloudDrive2 换 edition。status 仅登记信息；check 输入密码做只读实际检查，样本只读一个字节验证 Range。外部网络播放/拖动仍独立验收。

disable 撤销认证，入口 HTTPS 403，保留配置/证书并继续续期；enable 重新核验原生账号和目录。configure 先关闭旧入口再改域名/账号，失败不恢复匿名或借 Bot 密码；后端人工改密不具备原子回滚。Bot 目录/账号/URL 或网关镜像变化要求显式 configure，不扩大范围；后台私自改账号根目录仍需人工发现。

uninstall 只移除本功能路由、活动哈希和记录，不删云文件、Bot 数据、人工后端账号或仍引用的证书，不整体 compose down。先卸载附加入口再卸载底层网关，仅 disable 不解除依赖。仍有外部路由时，移除最后管理域名不会停共享代理。

独立元数据/代码/私密回退点在 `/opt/tg2cloud-webdav/`，共享认证哈希为 `/opt/tg2cloud-proxy/external-auth/`，共享备份含证书和认证资料，不能公开。元数据 0600/0700，认证目录 0750、哈希 0640，以实际 worker 组读取。目录只读挂载解决密码轮换旧 inode 问题；校验容器实际读取的摘要。备份校验/隔离解包不等于完整服务恢复；恢复还要原生账号、密码、证书和权限匹配，先关闭再恢复，不盲目覆盖生产。

## 排查与版本兼容

| 状态 | 方向 |
| --- | --- |
| 401 | 新域名/专用账号/密码；旧 Bot 和管理员被拒绝是预期 |
| 403 | disable、原生权限不足、Depth infinity；不能放开全权限 |
| 404 | 根路径 `/dav/` 与原生 base path；其他路径无后台 |
| 405 | 第一版只读，客户端在发写方法 |
| 429 | 降低并发/枚举，等冷却 |
| 502 | 网关/回环端口/认证、本地读取能力或上游重定向被拒绝 |

代理升级为 schema 2；未知版本拒绝覆盖，不自动降级。原 v1.3.0 严格旧工具会停止，使用 v1.3.1 起的匹配工具维护；更旧无校验脚本或桌面恢复包禁止覆盖。主入口先公开验证 helper A，再由 B 固定；附加入口只执行包含本功能完整源码与协议的正式资产。历史 Tag 不变。

实际开放前核对原生权限、外网手机播放、续期 dry-run、所用架构、配置失败/中断、启停/轮换/升级、共享路由保留及备份隔离恢复；这些实机项不因版本发布而写成通过。写操作负面验证仅用模拟后端或明确隔离对象，绝不对真实目录 `DELETE /dav/`。
