## TG2Cloud v1.4.8 · 外部 WebDAV 交互与输入维护

## 本次改动

- 本地管理和外部 WebDAV 不再重复展示环境检测表、启动横幅和多层相同标题；全部平台、实例和 Docker 归属检查保留，异常继续停止并说明原因。
- 控制终端逐字节读取当前行，避免父菜单缓存子进程后续答案；普通字段恢复回显，密码输入隐藏，并在异常／中断后恢复原终端状态。支持完整的括号粘贴封装。
- 域名、邮箱和目录正常显示输入；邮箱回车可跳过，普通字段提示固定具体原因，密码及未知校验异常不复述秘密。
- 已核验实例优先读取 Bot 账号目录：CloudDrive2 仅接受可精确匹配的已识别用户配置，OpenList 使用本机当前用户接口；无法读取时自动复用绑定未变的历史确认值，否则仅首次补录。未知／加密结构不猜测、不解密。
- 安装计划、后台建号及手机配置使用同一实际目录；显示当前 Edition 的管理页地址，取消第二次手打路径，保留计划确认、独立账号及原生只读权限确认。
- 新模块纳入运行与引导清单，补入 v1.4.7 固定升级基线，并扩充终端、目录、权限、错误脱敏及最低 Python 回归。

## 安装与升级

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

内网使用 `install-lan.sh`。已有实例按原公网／内网模式升级并保留配置，随后重新打开 `tg2cloud`。外部 WebDAV 位于 **15. 外部 WebDAV**，其离线工具需单独选择 **8. 升级附加功能** 才能加载新向导；主项目升级不自动替换这套工具。首次打开仅经确认下载正式稳定管理组件，不默认启用访问。

## 验证与兼容

版本同步后本地完整回归 1,216 项：1,183 通过、33 项因平台或工具条件跳过；最低 Python 3.10 标准库环境 121 项：119 通过、2 跳过。Ruff、语法、Bandit、ShellCheck、清单、仓库、网站 37 项及链接检查通过。已完成本版 A／B 各五项 CI、[同标签原生 AMD64／ARM64 发布验证](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40175950235)及实际源码资产核验。原生 Linux PTY、权限与隔离集成由对应 CI 执行；不将本地跳过写成已通过。

不新增运行依赖、必填配置或数据库迁移；不更改 Bot 账号、rclone、数据库、Session、网关监听和转存流程。目录读取不等于原生权限自动审计，仍须创建独立只读账号。**升级前备份。** 更早业务 schema 的原有迁移和匹配代码／数据库回退规则继续适用。

本版未连接真实 VPS、Telegram 或用户网盘；真实 SSH／Web 终端、原生两网关账号目录、手机播放／Range、公网 ACME、长期续期及完整恢复仍需独立验收。源码校验和不是数字签名，不使用旧版实机结论代替本版。

详情见[外部 WebDAV](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/external-webdav.md)、[维护记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/LOCAL-MAINTENANCE.md)和[更新记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/CHANGELOG.md)。历史验收保留原范围：[v1.3.0](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)、[v1.4.3](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V143-ACCEPTANCE.md)、[v1.4.4](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V144-ACCEPTANCE.md)、[v1.4.5](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V145-ACCEPTANCE.md)。

## 发布核验

Tag 固定入口 B `e24cddfa77fe76b90ea63ee9e7d88008066cb0a3`，两个入口固定已验证辅助 A `f2c089aeccc1de1c17c43654dad35249236e6e14`。源码包 SHA256：`6282058970c09e05e0b74cab1df7d775373464b8c3b40bbfc90e3ae4cd57ee69`。后续文档提交不移动 Tag、不替换资产。
