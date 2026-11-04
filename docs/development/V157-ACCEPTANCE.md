# v1.5.7 发布与兼容记录

状态：2026-11-04，v1.5.7 已正式发布。同标签原生双架构、源码、共享镜像及两份 Compose 部署包已核验；真实用户 VPS 升级与转存尚未执行。

## 改动与兼容

监听短限流保留原分片等待；尚无远端记录的普通监听下载最多两次持久冷却恢复，并受既有 MAX_RETRIES 更低限制，重启不重置次数。重新排队从头下载，流式远端不确定现场不自动重排。来源空附件最多复核一次，诊断单列 source_access；升级摘要及故障报告核对实际日志轮转参数。

业务 schema 3、原配置、任务、两份 Session、旧数据库名、两网关提交策略和两种部署方式保留；无新增依赖、环境变量或数据库迁移。历史失败不批量自动重试，旧容器不自动重建。

已从原 v1.5.6 正式提交 `35d24a6e052d032543344f95567cf245274c9b1f` 计算并审阅两 Edition 载荷基线。保留此前支持版本，不仅凭版本文本接受未知代码。

## 本地验证

实现阶段完整检查1610项：1580通过、30既有环境跳过、0失败，371.007秒。首轮3处旧查询次数断言不兼容新增只读 inspect，已修正为精确对象、数量、参数和超时限制，保留不重启／不修改 HTTPS 保护；没有删测试、降低规则或新增 skip。

网站37项与34HTML构建、固定 Ruff0.17、Bandit、Bash／ShellCheck、Python3.10无 Bot 依赖入口及17项宿主回归、干净公共副本24项恢复／传输回归通过。5项真实本机 rclone 回环 WebDAV 通过，后端为隔离协议夹具，不是用户网关。

新增20项回归覆盖普通／高级等待、重启、并发 CAS、取消／账号撤销／来源删除、精确错误分类与日志配置。原生 Docker LogConfig 检查已在现有显式 opt-in 双架构 CI 通过；两 Edition 非 root、网关 HTTP／FUSE、共享／复用代理和外部只读 Range 在隔离原生资源中通过，不代表用户网关或 VPS 验收。版本与基线同步后完整检查1610项、1580通过、30既有环境跳过、0失败，368.699秒；Ruff、compileall、395个公共文件、网站37项和构建通过，两份依赖审计均未发现已知漏洞。

## A／B 与发布资产

- 辅助 A：`8a4d9b3b561a92d01a3597b513f5044086ea89eb`。67个宿主 helper 远端 Git blob 和关键匿名 raw 字节一致；五组 CI 全通过，包括[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41786267274)与[VPS installer checks](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41786267041)。
- 入口 B／正式 Tag commit：`0c71f9ee3f626510f00999ab2770beecf48cc029`。两个公开入口均固定 A，五组 B CI 全通过，包括[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41787326517)与[VPS installer checks](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41787326428)；PR #31 快进合入 main。main 五组复核通过，包括[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41787774204)。
- [同标签源码发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41787774081)与[原生镜像／Compose 发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41788284296)成功。源码395个文件逐字节匹配不可变 Tag；两份 Compose 包逐文件匹配同标签生成器。五资产 SHA256、GitHub digest 和清单一致，匿名镜像索引及两平台 digest 已核验；校验和不是数字签名。

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| `COMPOSE-SHA256SUMS.txt` | 215 | `47f8bba9cb2fea65d5078cb6168984857b8896f8ee71eca6da63ca87ec77e1ea` |
| `SHA256SUMS.txt` | 96 | `92c2ed55bf731fce0861e53b478085fa88be084874f03e9f7170966b16822655` |
| `TG2Cloud-v1.5.7-compose-clouddrive2.tar.gz` | 244438 | `8c1c397ce9c6a1865d3a0de63d95e68875ce0861f943199b82a7941e44271a31` |
| `TG2Cloud-v1.5.7-compose-openlist.tar.gz` | 244323 | `69db13f54fccc96d05867c5cfb5e139137ff2b11a3958bc7a1280509945d9a9e` |
| `TG2Cloud-v1.5.7-source.tar.gz` | 3924159 | `1018c0e7c2029d081393916c16347b798436c1b93b807dec186b9871a064915e` |

镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:e194d52aeca50ad1f28d0ed35704c11bc827849d1e30f8272f127f1b30cf40d1`。

- `linux/amd64`：`sha256:d3a7852b03a82c2c1abafcba19802c10faeb537ffbb5371edb4363d70182f695`。
- `linux/arm64`：`sha256:fa214643dd50ea36e613c5c0f740ab6ab7a6e209d1a8242acc2a80e7653d599f`。

不可变源码包中的文档保留发布前准备状态；main 补录实际发布结论及下载入口，不移动 Tag 或替换已发布资产。

## 发布后验收

真实用户 VPS 新装／升级、Telegram 监听限流恢复、两种网关转存、手机 Range、长期运行和灾难恢复尚未执行。发布后使用专用测试实例先备份，核对 Bot／CLI 版本、原配置／任务／授权保留、手动转存和监听；检查冷却后恢复、来源不可读提示，以及实际容器日志限额。

日志未采用时先确认中断影响，再按原部署方式更新创建相应容器；不会为检查而重启 Bot、网关或代理。历史失败经原入口人工确认恢复，远端不确定对象保留。回退前保护当前完整数据，在隔离目录核对匹配版本和一致性备份，不删除云端文件。

[安装与升级](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [运维](../OPERATIONS.md) · [备份与恢复](../BACKUP-RESTORE.md)
