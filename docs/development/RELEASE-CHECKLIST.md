# 发布检查清单

本页面向维护者。用户安装、升级见[VPS 指南](../VPS-INSTALL.md)、[内网指南](../LAN-INSTALL.md)和[Compose 教程](../COMPOSE.md)。版本唯一来源为 `src/tg2cloud/version.py`；文档整理本身不提升版本。

## 1. 本地准备

- 确认分支、HEAD 和已有修改；保护私有配置、本地归档和用户数据。
- 描述本版实际改动、兼容边界、数据库迁移及回退；没有迁移就不宣称需要重建数据库。
- 核对前一正式版的可信升级基线、两 Edition 资源和递归清单。
- 更新 CHANGELOG、RELEASE_NOTES、安装入口版本和网站元数据；未实际发布时网站保持待发布状态。
- 新增能力补齐异常回归，运行[开发检查](DEVELOPMENT.md)，记录通过、失败、条件跳过与未执行项。

可生成审阅计划，下面的目标版本仅为示例，须高于当前版本：

```bash
python -B .github/scripts/prepare_release.py --version 1.5.5 --directory build/release-plan-155
python -B .github/scripts/maintenance_preflight.py --previous-tag v1.5.4 --json
```

工具不提交、不推送、不创建 Tag，也不安装到 VPS。候选目录必须全新，不为了通过预检放宽规则。

## 2. 辅助 A 与入口 B

1. 审阅并在授权后公开 helper 提交 A，使用真实不可变 SHA，记录其 CI 结果。
2. `prepare_bootstrap.py` 校验 `packaging/bootstrap-manifest.json`、`runtime-manifest.json`；新增模块时先审阅，再显式重新生成清单。
3. 生成入口候选，把公开入口 B 的 helper pin 指向经核验的 A；不可自指、伪造 SHA 或改为 moving main。
4. 检查两个入口的 helper 清单、字节内容和版本标识。过渡提交有失败时保留原结果，修复后使 B 全部适用 CI 通过，再建立正式 Tag。

```bash
python -B .github/scripts/prepare_bootstrap.py --directory build/bootstrap-candidate
python -B .github/scripts/release_metadata.py --tag v1.5.4
```

只生成候选或检查元数据不代表已经发布。当前 helper 身份及实际 A/B 结果见[当前发布记录](V154-ACCEPTANCE.md)。

## 3. 源码发布

- 明确授权后创建唯一版本 Tag，不移动已有 Tag；发布只从不可变 Tag 取源码。
- `release.yml` 等待同标签原生双架构的测试、依赖审计、两 Edition Docker／网关／FUSE 和隔离代理验证。
- 源码只打包一次，发布任务下载同一 artifact，核验后上传 `TG2Cloud-vX.Y.Z-source.tar.gz` 与 `SHA256SUMS.txt`。
- 不用本机重打包产物替换 Actions 资产，不覆盖历史 Release。

## 4. Compose 镜像与部署包

源码 Release 完整成功后，明确选择该正式稳定 Tag，人工触发 `compose-images.yml`：

- 同 Tag 分别原生构建两种架构，检查实际版本、revision、平台和非 root 运行。
- 发布／核验共享 GHCR index，确认可匿名读取；两 Edition 包固定同一真实镜像 digest。
- 附加两份 Compose 包与 `COMPOSE-SHA256SUMS.txt`，不替换源码原资产。
- 下载实际资产，比对清单、GitHub 资产 digest、Tag 源码、包内 helper 和镜像身份；校验和不是数字签名。

## 5. 文档与安装目标复核

资产验证后才把网站 `publishedVersion`、`releaseStatus`、下载链接和摘要改为实际发布状态；同步 README、docs 与网站，并运行网站构建和全部测试。

核对公开入口实际解析的新稳定 Release、Bot 与离线 CLI 版本，以及 Tag 和资产没有被移动或替换。历史下载可能被移除，历史版本事实留在 CHANGELOG；旧验收记录使用固定历史提交链接，不在现行教程中累积旧 pin。

## 6. 发布后实机验收

使用独立测试实例，分别验证新装、保留配置升级、CLI／Bot 实际版本、手动转存、监听、家庭共享、磁盘保护、两种网关及公网／内网入口。Compose 单独验收默认访问、HTTPS、已有代理导出、共享路由保护和移除。

真实 DNS／ACME、手机 Range、证书长期续期与生产恢复不能由 CI 推定通过。恢复演练使用隔离目录；未经授权不连接 VPS、不删除云端文件、不覆盖生产数据库。失败先保留现场、备份和脱敏日志，再按匹配版本制定恢复措施。
