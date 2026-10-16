**TG2Cloud v1.3.0** 转为 Linux 一键脚本优先维护，支持 CloudDrive2 和 OpenList。Windows 部署器最后版本为 v1.2.1，历史 EXE、Tag 与校验文件继续保留。

## 本次更新

- **首次安装磁盘推荐**：公网 VPS 和内网向导提供流式优先、均衡和手动配置，复用现有资源算法；显示实际磁盘、内存及可识别的 Docker 数据盘情况。任务预算不是分区，也不代表网关全部缓存受限。
- **执行前容量复检**：首次安装与升级在锁内重新检查容量，条件变化时停止；已有实例保留原预算、配置和运行数据。
- **源码发布**：GitHub Actions 从同一不可变 Tag 执行 Linux、Docker 和 WebDAV 回归，生成一次源码包与实际 SHA256；发布任务复用该 artifact，不再构建 Windows EXE。
- **入口一致性**：三个在线入口固定到已验证的辅助源码 commit；发布检查拒绝旧向导文件混入新版本。
- **文档同步**：区分脚本维护、v1.2.1 历史图形教程和不同资产的校验方式；保留许可证及上游致谢。

本版未更改 Telegram、队列、SQLite、rclone 或网关上传流程；除版本标识外，Bot 核心沿用 v1.2.1。本版不新增数据库迁移、环境变量或依赖。升级前仍应保存独立备份；自定义代码、部分实例、TG115 或网关镜像变化不会被自动接管。

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

发布前本地完整回归为 679 passed、26 skipped，另有 451 项子测试通过；网站构建及 15 项测试通过。缺少 Linux、rclone 或 Docker 环境的跳过不算通过，正式自动结果以本标签 Actions 为准。

此前 CloudDrive2 候选完成过数据库兼容、保留历史记录的启动及只读 WebDAV 检查。v1.3.0 的真实两 Edition 首次安装／升级、内网 NAS、Telegram 转存和长期运行仍需独立验收；自动测试和源码发布不替代这些验收。

更多说明：[VPS 安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/VPS-INSTALL.md) · [内网安装](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/LAN-INSTALL.md) · [升级边界](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/development/SCRIPT-FIRST.md) · [恢复指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.0/docs/RECOVERY.md)。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢。115 是示例之一，云存储授权由用户在自己的网关中完成。
