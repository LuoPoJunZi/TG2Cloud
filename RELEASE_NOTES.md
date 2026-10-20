## TG2Cloud v1.4.0 · 原生 AMD64 / ARM64

Linux 一键脚本增加原生 ARM64 支持，继续维护 AMD64；两个 Edition 共用 Python + Bash 核心，不提供新版 Windows EXE。Oracle Cloud／真实 VPS 的安装、升级和转存由用户在发布后验收，不能将自动化检查写成实机通过。

## 本次更新

- 将 x86_64／amd64、aarch64／arm64 统一为 linux/amd64、linux/arm64；核对 Linux 发行版、64 位 Python、dpkg 用户态、本机 rootful Docker 与实际镜像平台，不配置 QEMU。
- 公网、内网、管理、卸载及独立外部 WebDAV 共用检测。拒绝远端 daemon、异平台镜像，以及进程／候选 .env 中的平台或构建器覆盖。
- 两 Edition 在停止旧 Bot 前检查原生基础和网关候选，启动后核对容器实际 Image ID，保留既有健康、备份、配置保留、升级和回退保护。
- 保留 Python、CloudDrive2、OpenList 的固定多架构索引摘要及原 Nginx／Certbot 版本，不升级依赖或改成 latest。
- 新增原生 AMD64／ARM64 CI、CLI Python 3.10／3.13 检查、原生扩展及 rclone 运行检查、隔离网关 HTTP／FUSE 与代理测试；发布等待两个平台通过，仅打包和上传一次源码。
- 同步仓库及网站的安装、支持范围、镜像证据和 Oracle 验收说明；保留原命名、家庭共享、外部只读账号及任务恢复能力。

## 安装与升级

同一入口自动识别原生平台：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

已有实例建议先执行只读预检，OpenList 将 Edition 改为 openlist：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

预检通过后，运行不带 --check 的入口并确认安装／升级。可信内网仍用 install-lan.sh，外部只读功能仍独立使用 install-webdav.sh，不加入主安装向导。详见[安装指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)、[双架构与 Oracle 验收](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/ARCHITECTURES.md)。

## 兼容与数据

要求 Debian / Ubuntu、原生64位用户态、root、宿主 Python 3.10+、本机默认 rootful Docker；内网仍要求 Docker Engine 28+。CloudDrive2 仍需 /dev/fuse 及原网关权限，OpenList 不新增 FUSE 要求。不支持其他 CPU、32位 ARM、远端 Docker 或 Docker Desktop。

无需数据库迁移或调整普通用户配置。保留 .env、data/tg115.db、Telegram Session、rclone 配置、下载、日志、网关数据、容器身份与备份；不要卸载重装，不用旧 EXE 覆盖。若使用了自定义 Docker 平台／构建器覆盖，需先人工核对，程序会安全停止，不隐式模拟执行。

## 发布资源与校验

GitHub Actions 从同一不可变 v1.4.0 Tag 验证、打包 Linux 源码；Release 复用同一次构建产物，包含 TG2Cloud-v1.4.0-source.tar.gz 和 SHA256SUMS.txt。下载后执行 sha256sum -c SHA256SUMS.txt；校验和不是数字签名，不混用旧版本清单。

在线辅助代码遵循先公开并验证 A、后固定入口 B 的流程，业务代码只取正式稳定 Release，不以 moving main 或预发布代替。不覆盖历史 Tag／Release，历史 Windows EXE 保留于 v1.2.1。

## 验证边界

发布前本地 Python 3.13 完整回归880项：853执行成功、27条件跳过、0失败；Python 3.10 CLI408项：396执行成功、12条件跳过、0失败。新增架构15项、部署脚本21项及网站19项检查通过。远端原生双架构、Docker／WebDAV 与同标签发布检查必须成功后才会发布。

**Oracle Ubuntu 24.04／26.04、Debian ARM64、真实 Telegram／云存储、网关挂载传播、手机、ACME 及升级故障回退尚未实机验收。** 发布后请核对架构、Docker／Compose、FUSE、HTTPS、WebDAV，再执行小文件／视频／大文件、取消与重启恢复测试，并在云盘官方客户端确认。大小复验不是内容哈希校验或云盘官方最终完成。

历史范围分别见 [v1.3.3 用户转存确认](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V133-ACCEPTANCE.md)与 [v1.3.0 历史迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)，不扩大为本版实机结论。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权和必要致谢；网盘授权仍由用户在自己的网关完成。
