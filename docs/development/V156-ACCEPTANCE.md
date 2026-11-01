# v1.5.6 发布与兼容记录

状态：2026-11-01，v1.5.6 已正式发布。同标签原生双架构、源码、共享镜像与两份 Compose 部署包已核验；真实用户 VPS 新装、升级与转存尚未执行。

## 改动与兼容

rclone 凭据标准输入及私有候选配置，Bot Session／业务库权限加固，受管容器日志轮转，以及个人监听独立健康／有界临时异常观察。保留旧五项 Bot 基础就绪含义、首页、并发控制、任务恢复、两网关提交策略和两种部署方式。业务 schema 3 不变，不新增依赖包、环境变量或数据库迁移；已有 pyasn1 仅更新安全补丁，不清除或重建 Session。

已审阅原 v1.5.5 正式 Tag 对应提交 `30ffeefb76d20556d8e7dfcce8af1205d5371fbb` 的两 Edition 基线。历史结果见[v1.5.5 记录](V155-ACCEPTANCE.md)，不作为本版实机结论。日志选项需确认更新创建相应容器后生效；旧容器重启不会自动套用，外部复用代理不由本项目接管。

## 本地审计与验证

实现阶段完整检查 1590 项：1560 通过、30 环境跳过、0 失败，Ruff、compileall、固定 Ruff 0.17.0、定向 Bandit、Python 3.10 无 Bot 依赖导入和 7 项观察测试、35 项干净公共源码专项、13 发布包／13 布局回归、5 份 YAML 解析、Bash／ShellCheck 候选通过。网站构建及 37 项测试通过；391 公共候选文件。版本／基线同步后重新执行完整检查：1590 项、1560 通过、30 环境跳过、0 失败，520.333 秒；Ruff、compileall 及网站 37 项通过，392 公共候选文件。

17 项新增回归覆盖 stdin 不泄密、失败／取消保留配置、子进程回收、Session 授权与文件身份、权限拒绝、日志轮转、监听过期／冷却／缺口、旧快照未知状态和有界事件。没有删测试、降低规则或新增跳过；实际 POSIX 权限、两 Edition 非 root 候选、原生网关 HTTP／FUSE、共享／复用 Nginx、外部只读鉴权与 Range 已在原生 CI 隔离资源中通过，不等于真实用户网关或 VPS 验收。

## A／B、CI 与发布资产

- 辅助 A：`201e64fe789c981b47a611e643e8b3340b746bf5`。远端完整树与 raw 字节核对一致；[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41274869480)、[VPS installer checks](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41274869476)及仓库／文档／网站五组全部通过。
- 入口 B／不可变正式 Tag commit：`35d24a6e052d032543344f95567cf245274c9b1f`，两入口均固定上述 A；[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41275377717)、[VPS installer checks](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41275377663)及其余三组通过，PR #21 快进合入 main。main 的五组复核通过，其中[tests](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41275640758)。
- [同标签源码发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41275643612)、[原生镜像与 Compose 发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41275939793)成功。源码 392 个文件逐字节对应 Tag；两 Edition 包逐文件对应同标签生成器，五份资产 SHA256／GitHub digest／清单一致。匿名镜像索引及两平台 digest 已核验，校验和不是数字签名。
- 公网／内网公开 raw 入口与 B 一致。不移动 Tag、不替换资产、不使用 moving main 业务代码。

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| `COMPOSE-SHA256SUMS.txt` | 215 | `8a87b1a83bd5fb8145464fd279e80aab32fa7d5e69a2b7c11cdcad39da240d79` |
| `SHA256SUMS.txt` | 96 | `b75a12e2b6012ab779d475a670449a105096021c823d9115d8253e5e32af9aa8` |
| `TG2Cloud-v1.5.6-compose-clouddrive2.tar.gz` | 243005 | `3c493b12cd0cae05974ba7006e0e004879847b1c889b19756ec8bce00a024174` |
| `TG2Cloud-v1.5.6-compose-openlist.tar.gz` | 242811 | `d467bbaa7eac939ea0bf5ec70c9627bc1d00469a0555371b298f6fb29abef84c` |
| `TG2Cloud-v1.5.6-source.tar.gz` | 3910710 | `c0ad969fd4e6c52051cff1e73a52d15cdf77b0fa5fe560781289d510b30180d9` |

镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:f521b9b9d2c082a655bdbbecf520f1af3717dcb73b3c17259f2ab5e58f547152`。

- `linux/amd64`：`sha256:b096d39a422dca9278162e7242fd298f6e1420a42fa9aebd54e7391a3e4763ba`。
- `linux/arm64`：`sha256:c46efd595c46b3e0bd1f0157c48e1f590e326174510bf21565564b21f402e66b`。

不可变源码包内文档保留发布前准备状态；当前 main 已同步实际发布结论及下载入口。Tag、代码、镜像和 Compose 包均为 v1.5.6，不通过修改历史快照补录发布结果。

## 发布后实机与回退

真实用户 VPS、Telegram、CloudDrive2／OpenList 实际升级与转存、手机 Range、自动证书续期、灾难恢复及长期吞吐尚未执行。后续在专用测试实例先备份，再核对 Bot／CLI 版本、原配置／任务／授权保留、文件权限、日志选项及两网关读写；监听启停、冷却、旧快照与诊断另行核验。一次大小复验不等于云存储官方最终入库或内容哈希校验。

回退先停止任务并保留当前完整数据，保护匹配版本与一致性快照，在隔离目录预检后决定恢复；不让两个实例同时使用同一 Token，不删除云端文件。本轮不自动部署或操作真实 VPS。

[安装与升级](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [运维](../OPERATIONS.md) · [备份与恢复](../BACKUP-RESTORE.md)

## 发布前依赖安全补丁

初始辅助提交的两项原生运行 CI 因 pyasn1 0.6.4 的四项新披露漏洞未通过依赖审计，未忽略审计结果。经用户授权，将已有包限定更新为 0.6.5，由统一工具重新生成 Bot／开发锁文件，逐包核对其他版本不变；补丁后完整检查 1590 项、1560 通过、30 环境跳过、0 失败，620.195 秒；固定 Ruff 0.17.0、Bandit、网站 37 项、Python 3.10 无依赖入口与两份依赖审计通过。Windows 审计缓存的跨盘写入提醒不影响成功退出；未忽略漏洞。补丁后的最终 A／B、main 和同标签原生 CI 全通过，结果见上。
