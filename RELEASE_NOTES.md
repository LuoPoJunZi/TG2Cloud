**TG2Cloud v1.3.1** 增加独立的只读「外部 WebDAV」附加功能，可通过专用 HTTPS 域名访问 Bot 已有上传目录。两个 Edition 继续使用 Linux 一键脚本；Windows 部署器停留在 v1.2.1。

## 本次更新

- **独立入口**：新增 `install-webdav.sh` 与离线 `tg2cloud-webdav`，支持安装、状态、检查、启停、配置、升级和卸载。主安装不默认安装或询问此功能，Bot 菜单和运行依赖不变。
- **独立只读账号**：引导在原生网关后台创建专用账号，将根目录直接限定为最终上传目录；不复用 Bot、管理员或网盘凭据。原生权限由用户确认，程序验证认证与目录响应。
- **HTTPS 读取**：单账号哈希门禁与原生只读权限共同约束，允许 GET、HEAD、OPTIONS、PROPFIND，支持中文文件名和 Range；禁止写方法、危险编码和越界路径，不展示网关管理后台。
- **共享代理兼容**：proxy schema 2 保留管理与附加路由，续期和私密备份覆盖新增资源；禁用时拒绝访问，主卸载会提示附加依赖，独立卸载不删除云文件或 Bot 数据。
- **Nginx 边界修复**：方法检查提前到 server 层，修正反斜杠正则的配置转义；隔离 Docker 测试覆盖两版认证、只读拦截、编码路径、密码轮换和视频 Range。
- **可信引导**：主入口仍固定到通过 CI 的不可变 helper，附加入口只执行已核对源码包及 SHA256 的正式稳定 Release，不回退执行 main 业务代码。

不新增数据库迁移或 Bot 环境变量，不更换 Bot 业务、两版网关镜像、现有 Session、任务记录、rclone 配置和上传策略。现有 v1.3.0 实例按原升级流程保留配置；安装附加功能是单独操作，不必为此重新挂载云存储。

## Linux 安装与升级

公网 VPS：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

可信内网：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-lan.sh)
```

已有完整实例先追加 `--edition clouddrive2 --check` 或 `--edition openlist --check` 只读预检，再去掉 `--check` 确认升级；公网与内网入口不要混用。保留独立备份，未知或修改过的源码不会被自动接管。

## 独立外部 WebDAV

本 Release 发布完成后，单独执行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install-webdav.sh)
```

要求完整受管实例、可用的原生独立只读账号、专用域名和 HTTPS 签发条件。使用原网关和共享代理，不复制数据；原生账号能力不足、目录不明或身份不符时停止。完整步骤见[外部 WebDAV 指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/v1.3.1/docs/external-webdav.md)。

手机参数为 HTTPS、你的专用域名、443、根路径 `/dav/`，使用新外部账号与新密码。管理域名仍禁止 `/dav`。停用使用 `tg2cloud-webdav disable --edition openlist`，独立卸载使用 `tg2cloud-webdav uninstall --edition openlist`；CloudDrive2 改为 `--edition clouddrive2`。

## 下载与校验

| 文件 | 用途 |
| --- | --- |
| `TG2Cloud-v1.3.1-source.tar.gz` | 同标签公共源码与两 Edition 资源 |
| `SHA256SUMS.txt` | 本次 Actions 源码包的实际校验清单 |

下载两个文件到同一目录，执行 `sha256sum -c SHA256SUMS.txt`。校验和不是数字签名；不用于历史 EXE。Windows 历史资产仍见 [v1.2.1 Release](https://github.com/LuoPoJunZi/TG2Cloud/releases/tag/v1.2.1)。

## 验证与兼容范围

主分支已通过 Linux 全量回归、宿主 Python 3.10/3.13、Compose、两版非 root 候选镜像及真实隔离 Nginx 测试。同标签 Actions 会重新验证并只打包一次，Release 复用该产物；具体结果以本标签工作流为准。

**尚未执行本版原生 CloudDrive2/OpenList 账号与目录权限、手机实际播放、公网 DNS/ACME 或 ARM64 的端到端实机验收。** 附加宿主预检允许 ARM64，不等于主安装器新增 ARM64 支持。隔离测试使用合成后端，不能代替网关会员能力或原生 ACL 审计。

附加功能启用后代理状态升级到 schema 2；旧 v1.3.0 严格写入工具会拒绝维护，禁止用更旧脚本或桌面恢复包覆盖新代理。主卸载前先独立卸载附加入口，仅 disable 不解除依赖。CloudDrive2 历史迁移范围见 [v1.3.0 原验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)，不扩展为本版实机通过结论。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权及必要致谢；云存储授权由用户在自己的网关完成。
