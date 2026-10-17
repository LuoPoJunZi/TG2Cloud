**TG2Cloud v1.3.0** 转为 Linux 一键脚本优先维护，支持 CloudDrive2 和 OpenList。Windows 部署器最后版本为 v1.2.1，历史 EXE、Tag 与校验文件继续保留。

## 本次更新

- **首次安装磁盘推荐**：公网 VPS 和内网向导提供流式优先、均衡和手动配置，复用现有资源算法；显示实际磁盘、内存及可识别的 Docker 数据盘情况。任务预算不是分区，也不代表网关全部缓存受限。
- **执行前容量复检**：首次安装与升级在锁内重新检查容量，条件变化时停止；已有实例保留原预算、配置和运行数据。
- **源码发布**：GitHub Actions 从同一不可变 Tag 执行 Linux、Docker 和 WebDAV 回归，生成一次源码包与实际 SHA256；发布任务复用该 artifact，不再构建 Windows EXE。
- **入口一致性**：三个在线入口固定到已验证的辅助源码 commit；发布检查拒绝旧向导文件混入新版本。
- **Linux 源码模块化**：共享 Python 核心归入 `src/tg2cloud/`，部署资源归入 `packaging/`；宿主 CLI 支持 Python 3.10+ 且只依赖标准库，Bot 容器继续使用 Python 3.12。
- **视频命名增强**：优先本条消息的有效长描述和引用块，可替换包含频道推广的原名；过滤链接、话题和联系方式，不读取频道历史或评论区。
- **CI 与依赖修复**：适配新布局的 ShellCheck、Compose 和历史发布验证，更新已通过测试的 CI 工具、Bot Python 3.12 基础镜像及开发依赖；保留已验收的两版网关镜像。
- **文档同步**：区分脚本维护、v1.2.1 历史图形教程和不同资产的校验方式；保留许可证及上游致谢。

本版重组源码并增强命名，保留现有任务状态、SQLite 事务和两网关不同的上传／恢复策略；不新增数据库结构迁移或环境变量。现有安装目录、配置、`data/tg115.db`、Telegram Session 和运行身份保持兼容。升级前仍应保存独立备份；自定义代码、部分实例、TG115 或网关镜像变化不会被自动接管。

如果曾部署旧布局的同号 v1.3.0 实验实例，不能当作普通跨版本升级：源码基线不一致时脚本会停止，不自动覆盖。请保留数据并单独核对迁移，不要删除版本记录或数据库来绕过保护。

## Linux 一键安装与升级

公网 VPS，使用管理域名与 HTTPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网 Debian / Ubuntu x86_64 主机，手工填写内网 IPv4：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

入口先收集信息、预检并展示计划，最终确认默认取消。已有实例建议先追加 `--edition clouddrive2 --check` 或 `--edition openlist --check` 只读检查，再去掉 `--check` 确认升级；公网和内网入口不能混用。实际业务代码只取最新正式稳定 Release。

## 下载与校验

| 文件 | 用途 |
| --- | --- |
| `TG2Cloud-v1.3.0-source.tar.gz` | 同标签公共源码，包含两 Edition 的安装资源 |
| `SHA256SUMS.txt` | 核对本次 Actions 生成的源码包 |

下载上述两个文件后，在 Linux 中核对：

```bash
sha256sum -c SHA256SUMS.txt
```

校验失败时停止使用。在线向导通过 HTTPS 获取固定 commit 源码，目前不读取此资产校验清单。Windows 历史部署器请使用 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1) 与该版本自己的 SHA256SUMS，不用旧 EXE 覆盖已升级实例。

## 验证范围

新布局主分支已通过 Linux 全量回归、宿主 Python 3.10/3.13、两 Edition 非 root 镜像和隔离 LAN 网关检查。正式构建还会从本标签重新执行回归、Docker/WebDAV、安全及源码包检查；具体结果以本标签 Actions 为准。缺少环境而跳过的项目不算通过。

发布后补充（2026-10-17）：CloudDrive2 旧测试候选经授权、备份和人工核对后，使用正式 v1.3.0 原生流程迁移成功；用户确认升级后的使用验收完成。历史任务、配置和 Session 授权保留，运行指纹、健康、HTTPS、只读 WebDAV 及在线入口复检通过。本次不是脚本自动接管任意候选代码的证明。

OpenList 脚本实机验收暂缓；全新 VPS 安装、无需人工接管的正式版自动升级、故障回退、NAS、全部传输异常场景和长期续期仍需独立验证。详见[发布后验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。该补充只更新仓库文档，不替换已发布的 Tag、Release 正文或资产。

更多说明：[VPS 安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/VPS-INSTALL.md) · [内网安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/LAN-INSTALL.md) · [升级边界](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/development/SCRIPT-FIRST.md) · [恢复指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/RECOVERY.md)。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。115 是示例之一，云存储授权由用户在自己的网关中完成。
