## TG2Cloud v1.4.7 · 统一管理与可靠性维护

继续维护 Linux Python + Bash、CloudDrive2 / OpenList 和原生 AMD64 / ARM64，不生成 Windows EXE。

## 本次更新

- `tg2cloud` 主菜单新增 **15. 外部 WebDAV**，按当前 Edition 和已核验目录进入安装、检查、配置、启停、用户、升级及卸载子菜单。主安装不默认启用，不改变 Bot 上传配置。
- 根目录仅保留 `install.sh` 与 `install-lan.sh`，移除独立 `uninstall.sh`、`install-webdav.sh`。卸载仍使用菜单 **14. 卸载当前实例** 或 `tg2cloud uninstall`，保留 all、只读预检和各清理模式。
- 外部 WebDAV 以 API 2 明示新发布布局；旧 API 1 继续按原清单验证。旧工具在统一菜单确认后，仅迁移维护代码，保留账号、路由、文件及旧代码；拒绝可继续旧版离线访问。
- 修复运行代码准备晚于外部入口启用的问题：确认后先准备维护代码，再修改认证和路由；代码准备失败保留原状态，成功检查全部完成后才报告安装完成。
- 私密代码候选校验后发布，普通异常／中断清理本次候选，历史未知残留保留且不阻止新尝试；命令写入失败保留旧命令，重试复用已校验代码。
- 共享代理启动及健康检查复核 Certbot 实际挂载。仅对已核验归属、恰缺续期状态挂载且本次 Compose 摘要一致的情况单次重建 Certbot，再完整复验；其他异常继续停止。
- 补齐 v1.4.6 原正式提交升级基线，同步载荷、发布工具、CI 与文档；保留历史 Tag／Release 校验，不放宽权限或安全检查。

## 安装与升级

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

内网实例使用 `install-lan.sh`。已有主机按原模式升级并保留配置；重新打开 `tg2cloud` 后使用新菜单。外部 WebDAV 维护代码与 Bot 独立：旧布局迁移需确认，不自动启用账号或修改路由。

卸载先预览清理范围：

```bash
tg2cloud uninstall --edition all --check
```

实际卸载仍要求确认；完整清理会删除所选实例数据和可识别备份，需保留时使用 `--keep-data`。两个历史 Shell 文件只保留在原 Tag／提交，不再从 main 分发。

## 验证与兼容边界

发布准备前本地完整回归 1,198 项：1,166 通过、32 项按环境条件跳过；Python 3.10 最小宿主环境 146 项，143 通过、3 跳过，LAN help 和发布元数据不需要 Bot 依赖。Bash 语法、ShellCheck、Ruff、编译、定向 Bandit、历史布局与网站 37 项检查通过。版本同步后继续执行适用检查，正式发布必须等待辅助 A、入口 B 和同标签原生双架构 GitHub CI，再核验实际资产。

**升级前备份。** 不新增运行依赖、必填环境变量或数据库迁移；保留两 Edition 配置、数据库、Session、下载及网关数据。源码 API 2 不是数据库迁移；更旧业务 schema 的既有迁移及匹配代码／数据库回退规则继续适用。

本版未连接真实 VPS 或用户网盘；原生网关账号、手机播放／Range、公网 ACME、长期续期及完整灾难恢复仍需独立实机验收，不使用旧版本结果替代。SHA256 是完整性校验，不是数字签名。

详情见[外部 WebDAV](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/external-webdav.md)、[卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md)、[维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LOCAL-MAINTENANCE.md)与[更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

历史验收按原版本范围保留：[v1.3.0 人工迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3 用户日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)、[v1.4.4 双架构升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)、[v1.4.5 ARM64 升级与 WebDAV](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V145-ACCEPTANCE.md)。这些结果不替代 v1.4.7 实机验收。
