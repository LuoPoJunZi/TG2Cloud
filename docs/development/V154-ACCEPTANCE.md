# v1.5.4 发布与兼容记录

状态：2026-10-30，v1.5.4 已正式发布。本地回归、同标签原生双架构、源码与镜像／Compose 发布流程通过；五份实际资产已下载核验。修复后的真实用户 VPS、Telegram 下载、两种网关转存与长期运行尚未执行。

## 范围与兼容

短时间 Premium 下载限速继续当前分片；普通限流及超限持久化冷却。临时服务错误进入有限重试，真实授权失效停止；迟到错误不得影响替换后的账号。监听新任务按限速信号退让并逐步恢复，不取消在途任务或改变手动任务资源窗口。普通／流式失败记录保留脱敏原因。

业务 schema 3 不变，没有新依赖、配置或数据迁移；保留数据库、Session、下载、用户配置和历史任务。新增 v1.5.3 正式提交 `2e6f06f09e1e2ac9fe8ae2d9c6e1d83cc7a3bee1` 的可信升级基线。一键脚本与 Compose 仍使用不同实例身份，互不接管。

## 本地验证

`python -B .github/scripts/check_python.py all`：1537 项，1501 通过、36 条件跳过、0 失败；Ruff 与 compileall 通过。额外 Ruff 0.17.0、Bandit、Python 3.10 标准库 CLI help、源码清单检查与网站 37 项测试通过。未执行的本机原生 Linux／Docker／rclone 检查交由远端 CI；真实服务验收单独记录。

## 发布链与实际资产

- 辅助 A：`9fe6695f7881f4994b9dde99144e94ea3a0886ef`；5 组检查全部通过，PR #19 已快进合入。
- 入口 B：`8705a892e1265b6296dee959f1f2b7a2d75ecdf8`；两入口固定 A。安装器及运行检查通过；网站因三处旧文档 SHA 未同步而失败，保留原结果。后续仅修正文档，未改生产规则或测试预期。
- 文档修复及正式 Tag：`7d3a56ff3cb7b9d9f8d994930904c1749677c69b`；仓库、文档、网站全部通过。[同标签发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41000641181)及[镜像／Compose 发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/41001030144)全部成功。
- 源码 382 个文件按 Git 原始 LF 字节逐项对应 Tag；两 Edition 部署包完整内容对应同标签生成器。五份资产 SHA256 与清单、GitHub 资产摘要一致，镜像可匿名读取，平台及子镜像身份通过发布工作流核验。
- 不移动 Tag，不覆盖旧资产；校验和不等于数字签名。当前线上入口的业务仍取正式稳定 Release，不执行 moving main 业务代码。

| 资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| `COMPOSE-SHA256SUMS.txt` | 215 | `e5108c64748328a47e62e3ebc634823b08f23349c46cf15ddd20d12d38178e08` |
| `SHA256SUMS.txt` | 96 | `fa8d23a6cd52712d5fd97ba11c2d32f3bfc3f39057622872c15110e39b5bf802` |
| `TG2Cloud-v1.5.4-compose-clouddrive2.tar.gz` | 240043 | `e4ac71f898742d69597b0cac056f11acc61ad95894c54afaa89a5a2b9c54e0a8` |
| `TG2Cloud-v1.5.4-compose-openlist.tar.gz` | 239850 | `2b5c3125e8739fb8abae3b290ac1732582b8eaa28b29318182139880ad18d20c` |
| `TG2Cloud-v1.5.4-source.tar.gz` | 3871581 | `5903e94859102f8a1a322aaf42de231e36e0db1334f8db8961150e6181067dbf` |

镜像：`ghcr.io/luopojunzi/tg2cloud@sha256:6e84db4eda2b00997a42390d28a417a095bfadad4e3966f18d0cd279c1550aca`。

- `linux/amd64`：`sha256:ca27122014ef70b0ca252125ef4a05d0229c932636a351d1f8642e6781b6054c`。
- `linux/arm64`：`sha256:58f9939dc4ee37214bb7367b5f4c97122dbafcb0a3d715546fda3482e28be21b`。

## 已知文档限制

不可变 v1.5.4 源码及 Compose 包随附 README 的下载示例仍引用 v1.5.3；包内程序、镜像和 HTTPS helper 的版本均已核验为 v1.5.4。当前[Compose 教程](../COMPOSE.md)已更新到正确的 v1.5.4 命令；安装和升级请以在线教程及本次实际资产为准，不混用旧版文件。本次不通过移动 Tag 或替换资产修改历史快照。

## 发布后验收与回退

1. 先按原部署方式生成一致性备份；确认两组件版本及数据库路径，不同时启动使用同一 Token 的实例。
2. 少量重试已失败的监听任务，核对短限速等待后继续、长冷却提示、临时错误重试与最终脱敏原因；不批量强制重传。
3. 分别核对手动转存、监听普通／流式传输、两种网关目的端大小验证、磁盘保护、重启与 Session 保留。
4. 对账号替换和真实权限拒绝验证隔离；不要使用用户云端文件测试删除或覆盖。
5. 如需回退，先停止任务并保护现场，使用匹配源码／镜像和升级前一致性备份在隔离目录核验；不要直接覆盖生产数据库或删除 SQLite 旁文件。

[升级说明](../VPS-INSTALL.md) · [Compose](../COMPOSE.md) · [监听说明](../LISTENING.md) · [备份与恢复](../BACKUP-RESTORE.md)
