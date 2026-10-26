# v1.4.9 发布准备与发布后实机验收

## 发布决定与当前状态

按用户最新决定，目标是 **v1.4.9 正式版**，不发布 v1.5.0-rc.1。不把真实 VPS／Telegram 验收设为发布前必需条件，但必须明确它尚未完成；发布成功只表示已生成可安装资产。

当前本地基础为 `main` 的 `9caf007c5d48e20965c4f7c601e81ecbe6a1d02a`；远端最新稳定版 v1.4.8。v1.4.9 本地提交按下述 A／B 流程整理，尚未推送、打 Tag 或发布。代码和自动化通过后仍须用户授权远端操作。

## A／B 与远端计划

现有两个在线入口均固定真实辅助 A `f2c089aeccc1de1c17c43654dad35249236e6e14`；v1.4.8 Tag 指向入口 B `e24cddfa77fe76b90ea63ee9e7d88008066cb0a3`，文档后续提交未移动 Tag。v1.4.8 的两 Edition 指纹已从该原始提交核验并加入升级基线。

1. 在临时 `codex/release-1.4.9` 分支整理本次源码、测试、文档和版本为辅助提交 A；先不改 main 的入口。A 的实际 SHA 只能在提交后产生，不预填。
2. 授权后推送该分支，显式触发 tests、VPS installer checks、repository-quality、docs-quality、website-docs 五个现有工作流，核对它们的实际 head SHA 均为 A。失败先修复，新的 A 重新验收。
3. A 验证成功后，用现有 `prepare_bootstrap.py` 生成两个入口候选；B 只更新 helper 清单和 pin，固定真实、已公开的 A。再次运行清单、pin、打包检查及上述五项工作流，核对 B 的 SHA。
4. 检查远端 main 未被其他提交推进后，再更新 main 至已验证 B。创建不可变 `v1.4.9` Tag；现有 release workflow 从同一标签运行原生 AMD64／ARM64、两 Edition 及隔离集成，成功后创建非预发布 Release。
5. 核验唯一源码归档、SHA256 清单、Tag／源码版本和下载内容。成功后更新网站 publishedVersion 和发布事实，移除本次辅助分支。若远端 main 已变化，重新整合和验证，不强推覆盖。

新 helper 尚未发布时，`maintenance_preflight.py` 的 helpers 项应阻断，不能绕过它。默认稳定入口不执行本地未发布源码。Bot 镜像仍由安装器从已固定 Release 载荷在目标机原生构建，网关镜像继续使用已有固定 digest；本轮不增加镜像仓库发布。

## 本地审计范围

- 私聊／管理员校验、一次性用户绑定按钮、交互超时、源规则修订号和计划归属。
- 默认手动命名／下载／上传与既有去重保持；普通成员不能取得监听源／个人 Session。
- 内容保护与成员资格检查，任务开始前复核，限流持久化；无自动加入、评论抓取或全历史补抓。
- Schema 2 → 3、嵌套事务、配额、计划与任务入队的同事务性，以及匹配旧快照回退。
- 个人 Session 与 Bot Session 隔离；终端隐藏输入；日志无凭据；菜单实例快照和离线包均覆盖个人 Session。
- 源码／helper 清单、最低 Python 和两 Edition 原生容器入口。

本轮修复：长文件名／反馈按 Telegram UTF-16 长度分页，按钮只放最后一页；登录断开异常仍恢复 umask 并释放锁；迁移普通中断显式回滚；权限检查等待期间停用监听后不再登记计划；菜单快照补入个人 Session，拒绝非正常文件且不打包锁；增加显式正式 Release 选择以便准确安装本版。

## 发布后安装和升级

下面命令须在 GitHub v1.4.9 Release 发布并完成资产核验后使用。当前尚不可用；不要先运行，也不要通过修改 URL 到 main 假装固定了版本。

公网 CloudDrive2：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition clouddrive2 --release v1.4.9 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition clouddrive2 --release v1.4.9
```

公网 OpenList：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition openlist --release v1.4.9 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install.sh) --edition openlist --release v1.4.9
```

已有内网实例保持原模式，使用相应 Edition（首次安装还需通过 `--lan-ip` 指定本机实际私有 IPv4）：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install-lan.sh) --edition clouddrive2 --release v1.4.9 --check
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/v1.4.9/install-lan.sh) --edition clouddrive2 --release v1.4.9
```

必须同时固定脚本 Tag 和 `--release`；只固定脚本 URL，其默认部署目标仍可能是以后最新稳定版本。`--check` 不写入，但会联网下载并核验正式源码。没有强制降级／覆盖未知实例开关。已有自定义公网目录额外传入 `--install-dir`，不能混用另一实例路径。

升级后关闭旧管理会话，重新执行 `tg2cloud`。确认显示 1.4.9，所选容器身份／网关／HTTPS 或 LAN 健康。新主机先完成原存储网关与专用 Bot WebDAV 账号设置，验证手动小文件转存，再启用监听。

## 升级前备份与隔离原则

1. 推荐专用测试 VPS、测试 Bot Token、测试个人来源及云目录。双 Edition 分别使用各自 Bot Token／实例目录，不把同一 Token 的两套服务同时运行。
2. 已有测试实例用 Bot `/pause` 暂停新调度，等待活动传输结束；暂停不等于停止正在进行的任务。
3. `tg2cloud` → 所选 Edition → **13. 数据备份管理** → **2. 创建实例快照**，确认维护窗口；随后 **3. 校验实例快照**。校验成功不等于生产恢复成功。
4. 快照含配置、业务 DB、Bot Session、存在时的个人 Session、所选网关状态；不含源码／镜像、downloads、共享代理、LAN／外部 WebDAV 全部状态或云端数据。另存匹配旧版本源码、容器镜像身份及下载文件；代理使用该菜单的代理备份，附加状态按备份专题单独保护。
5. 备份放私密目录并保留离机副本，不放 Git 仓库，不将归档／Session 上传给支持人员。不删除 WAL 旁文件或只复制运行中主数据库。

## 逐项验收记录

初始状态均为 **未执行**。每个条目分别记录 CloudDrive2／OpenList、AMD64／ARM64、日期及结果；未覆盖的平台／后端标未验证。使用自己创建的无敏感测试附件和测试频道。

| 项目 | 操作步骤 | 预期与通过判定 | 安全证据／异常恢复 |
| --- | --- | --- | --- |
| 1. 版本与基础升级 | 完成上述备份、只读预检和显式版本安装；打开主菜单 2、10 | 版本 1.4.9，原配置／任务保留，Bot 健康，入口按原模式可用 | 保存脱敏升级摘要及任务数量；失败先核对回退日志，不反复卸载 |
| 2. 事务迁移 | 读取下方 schema 命令，并核对升级前后已有任务／配额 | schema=3、quick_check=ok；旧任务 read_identity=bot，原配置与 Session 未重建 | 只记录版本／数量；失败停止所选 Bot，保护现场和升级前快照 |
| 3. 个人登录 | 运行下方 login，隐藏输入手机号／验证码／2FA；随后 status | 授权保存但监听仍停用；Bot 原手动转存正常 | 记录固定状态消息，不记录验证码或个人 Session；失败用 disable |
| 4. 管理员入口 | 管理员私聊 `/listen`，启用账号，添加已加入测试频道或群组 | 显示来源卡，来源默认暂停、确认模式；选择启用从当前时点开始 | 记录来源脱敏名称及状态；错误先暂停该来源 |
| 5. 成员隔离 | 家庭成员私聊 `/listen`、尝试他人按钮／计划，发送普通文件 | 拒绝监听／他人计划；成员原手动转存成功、只见自己的任务 | 只记录拒绝文案和测试任务号；出现越权立即停用监听并报告 |
| 6. 规则组合 | 逐组设置指南 JSON：视频+扩展名+包含名+关键词；切换 exact／glob、any／all、min/max；增加第二个 OR 组 | 同组 AND、组间 OR；全局排除和大小限制对所有组有效；测试规则不创建任务 | 使用自制匹配／不匹配文件矩阵记录结果；空或非法规则被拒绝，恢复默认规则 |
| 7. 权限与保护 | 使用开启保存保护的自建来源、未加入的自建私有来源；已启用后撤销读取权限 | 添加／启用拒绝或暂停；新下载停止，不借用 Bot 身份，不自动加入 | 记录固定原因，无邀请链接／用户列表；暂停来源并恢复测试权限 |
| 8. 自动转存 | 测试来源切换自动模式，发布符合规则的新附件 | 一次入队、一次额度记账、WebDAV 接收并大小复验；云端官方完成另查 | 对比任务号／原名候选名／大小；冲突保留现场，不自动删云文件 |
| 9. 审批与目录 | 切回确认，创建管理员授权目录别名，收新附件；确认前改名、换目录；测试媒体组批次审批 | 审批前未下载、未占额度；修改不换扩展名；只进授权目录；重复点击无重复任务 | 记录脱敏计划和任务号；过期／撤销目录授权应拒绝，失败项仍待确认 |
| 10. 暂停与恢复 | 暂停来源后发附件再启用；另在短时间测试重启 Bot；发送图文媒体组并编辑已登记消息 | 暂停间隔不补抓；重启最多 6 小时有界补拉；媒体组安全关联；重复编辑不重入队 | 记录接收游标与计数，超过窗口应提示缺口；必要时停用监听，不扩大历史扫描 |
| 11. CloudDrive2 | 在测试挂载执行普通落盘和流式小预算样本，使用新的测试文件名 | 沿用临时对象→验证→改名→最终复验；结果正确 | 只截测试任务状态／验证方式；不确定 MOVE 停止自动恢复，保留云端对象 |
| 12. OpenList | 使用独立测试 Bot／网关执行同样样本及模拟中断 | 沿用预留最终路径直接上传；冲突停止危险重试、可用本地副本保留 | 记录失败分类／验证状态；不要用删除真实目录测试恢复 |
| 13. 手动与资源 | 管理员／家人手动转发；重复提交、取消后按确认恢复；用测试额度触发队列等待 | 原去重／恢复不退化，下载身份=bot；监听受限不阻塞手动任务；无需故意填满宿主盘 | 菜单资源与脱敏错误；恢复正常额度后再调度，不删无关数据 |
| 14. 备份与隔离恢复 | 登录后再次创建菜单快照并校验；用下方工具在独立目录对升级前快照演练 | 两 Session 均被保护；旧 DB 在隔离副本迁移到3，原归档／实例未改动，未启动第二Bot | 只保存演练摘要；失败保留原快照，不覆盖生产库 |

规则用法、准确字段、JSON 示例及目录授权见[监听指南](../LISTENING.md)，避免凭表格猜测接口。短时间 FloodWait 不宜人为刷 Telegram 触发；自动化已模拟，实机遇到时记录实际冷却提示，不能宣称强制压测已完成。

## 登录与只读证据命令

```bash
tg2cloud listen login --edition clouddrive2
tg2cloud listen status --edition clouddrive2
tg2cloud listen disable --edition clouddrive2
```

OpenList 替换 Edition。只读数据库结果仅输出 schema 与完整性，不输出任务名称或凭据（OpenList 替换容器名）：

```bash
docker exec tg2cloud-clouddrive2-bot python -B -c 'import sqlite3; c=sqlite3.connect("file:/data/tg115.db?mode=ro", uri=True); print("schema="+str(c.execute("PRAGMA user_version").fetchone()[0])); print("quick_check="+str(c.execute("PRAGMA quick_check").fetchone()[0])); c.close()'
```

Session 位置为所选实例的 `data/bot.session` 与 `data/listener/personal.session`。只核对存在／权限，不 `cat`、不导出内容。日志从 `tg2cloud` → **12. 故障诊断报告** 获取白名单脱敏报告；另附菜单状态、任务编号、时间和可复现步骤。人工分享前再次检查，删除 Token／手机号／账号／域名／频道ID／敏感标题；不要发送 `.env`、rclone.conf、数据库、Session 或备份包。

## 隔离恢复与回退

使用已核验的 v1.4.9 源码和兼容 Python 环境；先 `--help`，只对已生成的快照与新私密目录操作。以下 `/srv/...` 为必须替换的测试路径，不能指向运行实例：

```bash
PYTHONPATH=src python3 -B -m tg2cloud.persistence.rehearsal --help
PYTHONPATH=src python3 -B -m tg2cloud.persistence.rehearsal /srv/private-backups/before-upgrade.tar.gz --scratch /srv/private-restore-check --edition clouddrive2 --json
```

工具仅在隔离临时副本打开／迁移 DB 并模拟重启恢复，不加载 Session、不连接 Telegram 或网关、不读取生产下载路径。schema=3 与成功报告仅证明演练范围，不等于实际恢复运行。

发现监听异常优先 `tg2cloud listen disable --edition ...`，原手动转存保持可用。必须回退时，先停用监听、暂停调度并等待活动任务结束，保护升级后 DB／Session／下载和云端对象，再停止所选实例，按[恢复指南](../RECOVERY.md)恢复匹配旧代码与升级前 DB。旧版不接受 schema 3；不要改 PRAGMA 降级标记，不要删除任务表来通过启动。新任务需单独核对去重与远端文件，不自动重放或删除。没有一键覆盖生产库的回退命令。

## 执行证据与未验证范围

2026-10-26 本地结果（测试使用合成数据，未连接用户 VPS／Telegram／网盘）：

| 检查 | 命令／范围 | 实际结果 |
| --- | --- | --- |
| 干净公共副本回归 | `python -B .github/scripts/check_python.py test`；364 个公共文件，不含 legacy／私有归档／用户数据 | 1282 项：1248 通过、34 跳过、0 失败；325.683 秒 |
| 最低宿主版本 | Python 3.10.20：`python -B -m unittest test_listening_host test_instance_backup test_repository.UserDocumentationTests -q`（`PYTHONPATH=src;tests`，Linux 使用冒号） | 25 项通过 |
| 静态及清单 | `ruff check --no-cache .`、`check_python.py compile`、`check_repository.py`、`prepare_bootstrap.py`、`validate_release_notes.py RELEASE_NOTES.md`、`release_metadata.py --tag v1.4.9` | 通过；正式版元数据 `is_prerelease=false` |
| Shell | `bash -n install.sh install-lan.sh`；`shellcheck install.sh install-lan.sh` | 通过 |
| 安全静态／依赖 | `python -m bandit -q -r src scripts .github/scripts/source_release.py`；分别 `python -m pip_audit -r requirements/bot.lock.txt`／`requirements/dev.lock.txt` | 无报告问题／无已知依赖漏洞；已有未命中规则的 nosec 提醒，不是安全保证 |
| 两 Edition 载荷 | `python .github/scripts/build_payload.py --edition all --directory <新的本地输出目录>` | 组装通过，共享 Bot 递归指纹一致；没有本地 Docker 构建 |
| 文档站 | 在 `website/` 运行 `node scripts/build.mjs`、`node --test`、`node scripts/check.mjs` | 37 项通过；34 HTML、4300 个本地引用、284 条搜索索引 |
| 发布预检 | `python .github/scripts/maintenance_preflight.py --previous-tag v1.4.8 --json` | 版本／清单／旧版基线通过；helpers **按预期阻断**，等待公开 A 和入口 B |

34 项跳过来自 Windows 环境下的 Linux UID／权限／符号链接／flock／PTY、缺少 rclone 和未启用隔离 Docker 等条件，未新增无依据的 skip。原生 AMD64／ARM64 两 Edition 容器与模拟 WebDAV 集成需由远端 CI 验证，不能以本地跳过代替通过。

以上是最终代码的干净副本结果；填写本段执行记录前，364 个公共文件与工作树逐字节一致。凭据模式扫描及人工复核未发现真实秘密；匹配项仅为合成测试值和读取配置的表达式，Session／数据库／本地私有文件不属于提交集合。扫描不等于对所有未知秘密的绝对保证。

远端 A／B CI、Tag、Release、实际下载校验、VPS／Telegram 与生产恢复均尚未执行。GitHub 自动化检查必须成功后才发布，实机失败后修复发布新维护版本，不覆盖既有不可变 Tag 或资产。
