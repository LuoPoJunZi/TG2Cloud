## TG2Cloud v1.4.6 · 外部 WebDAV 与维护体验

继续维护 Linux Python + Bash、CloudDrive2 / OpenList 与原生 AMD64 / ARM64，不生成 Windows EXE。

## 本次更新

- 外部 WebDAV 的状态和连接检查执行后停留，可刷新并返回功能菜单；用户管理统一 Edition／版本与返回提示。卸载或升级后退出当前进程，避免继续使用已替换的运行代码；显式子命令保持单次执行。
- 新增本地发布准备工具，只生成审阅计划和候选版本补丁，不自行修改源码、pin、Tag 或远端。
- 四组命名测试按目录分类，保留全部断言和命名行为；抽离 Nginx／Compose 纯渲染模块，兼容旧导入，锁、激活与回退顺序不变。
- 日常与正式发布的当前布局验证共用实现，保留双架构、Docker、安全审计和历史布局校验门槛。
- 补齐 v1.4.5 原正式源码升级基线，整理现行教程和历史菜单说明，保留历史版本记录。

## 安装与升级

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

内网实例继续使用 `install-lan.sh`。确认计划后才升级所选 Bot 和离线管理代码；主菜单编号与主安装流程不变。

外部 WebDAV 独立升级：运行 `tg2cloud-webdav`，选择“升级附加功能”，之后重新打开管理命令。主项目升级不会自动更新这套独立工具；不默认启用，不改变 Bot 上传账号或目录。

**升级前备份。** 本版不新增运行依赖、环境变量或数据库迁移，保留配置、任务、Session、下载及网关数据。继续使用 schema 2，更旧版本的既有迁移和回退边界不变；回退须匹配旧代码与数据库。

## 验证与兼容边界

发布准备前本地全量检查 1,137 项：1,106 执行通过、31 项按环境条件跳过；标准库新工具／页面／渲染与干净宿主管理包在 Python 3.10 验证通过。Ruff、语法、ShellCheck、Bandit、双 Edition 载荷及网站 36 项测试通过。

正式发布须等待辅助 A、入口 B 和同一不可变 Tag 的原生 AMD64／ARM64、隔离 Docker／WebDAV、安全及依赖审计全部通过，再发布源码包和 SHA256SUMS。SHA256 是完整性校验，不是数字签名。

本版未连接真实 VPS 或用户网盘；旧版用户验收不外推本版。真实升级、外部手机播放、ACME 续期与完整故障恢复仍需独立验收。

历史验收按原范围保留：[v1.3.0 人工迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3 用户日志](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)、[v1.4.4 双架构升级](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)和[v1.4.5 ARM64 升级及 WebDAV](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V145-ACCEPTANCE.md)。

详情见[本版维护说明](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LOCAL-MAINTENANCE.md)、[外部 WebDAV](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/external-webdav.md)、[运维指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/OPERATIONS.md)与[完整更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。

## 发布核验（2026-10-24）

v1.4.6 已于 2026-10-24 正式发布。辅助 A `56e5115e729356c40a10912bb7d7c000969e40df` 与入口 B／Tag `2e18eba718df83beec3a9d0784ca8037125bdd20` 各五项工作流全部通过；[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40089991036)的准备、AMD64、ARM64 与发布任务成功。实际下载源码包与 SHA256 清单通过正式验证器，并与 GitHub 资产摘要一致。

源码包 SHA256：`d06803e0c00b73086f2d19520230e660958784da373430002b42b618f38f73b4`。Tag 保持指向入口 B，后续文档提交不改写 Tag 或资产；校验和不是数字签名。本版真实 VPS、用户网盘、手机与完整恢复仍需独立验收。
