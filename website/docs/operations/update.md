# 升级与修改配置

“重启”“用当前 payload 重建”和“安装新版本”是三个不同操作。

## 后续脚本升级入口

Windows EXE 停留在 v1.2.1。后续公网实例使用 install.sh 先 --check，再确认升级；内网实例使用 install-lan.sh，不混用入口。安装目录、身份和原源码均可核验时，旧 EXE 创建的标准 VPS 实例也可保留配置升级。网关镜像变化、自定义代码或部分实例仍会停止，不能用旧 EXE 绕过检查。

v1.3.2 的默认公网／内网入口先选 Edition：已有实例打开管理菜单，选 `1. 安装 / 升级` 后核对计划并确认；未安装则确认进入安装向导。已有 LAN 实例按保存模式维护，不因入口名称变化而转为公网 HTTPS。只读 `--check` 不安装本地命令；确认安装后可运行 `tg2cloud`，同版本也可确认仅安装管理工具、不重启容器。完整边界见[本地管理菜单](/operations/maintenance/)。

管理命令、实例 Bot 与外部 WebDAV 的离线工具分别核对版本，不会自动同步更新。独立附加功能从其新正式入口显式选择升级，不能把主实例升级或容器重启当成附加工具升级。日常查看状态和日志不下载新代码，不需要卸载重装来升级。

v1.3.0 向导的磁盘推荐仅用于新安装，升级不静默改预算。CloudDrive2 本次旧候选已迁移到正式版，用户确认升级后使用验收通过；OpenList 脚本实机验收暂缓，不能把本次结果扩展成两 Edition 的全部流程均已实测。

## v1.4.2 人工升级验收与旧 Release 缺失

2026-10-21，专用 Debian13／原生 AMD64 测试机完成 CloudDrive2 v1.3.4 → v1.4.2 人工保留配置升级。原版 Release 和 Tag 已删除，在线向导查询基线返回 404 并先停止；经用户授权，核验原不可变提交与受管文件、备份后，调用正式 v1.4.2 原有升级核心完成切换，没有关闭指纹保护或添加强制覆盖。

`.env`、任务记录、Session 授权和暂存清单保留，Bot healthy、非 root，网关／OpenList／共享代理容器身份和启动时间未变。本机 HTTPS、只读 WebDAV 207，以及另一台电脑的 TLS、HTTP 跳转与管理域名 `/dav` 阻断通过。升级后的公开 `--check` 识别已是 v1.4.2、不重建；不代表旧 Release 缺失的自动升级路径已经修复。

此机继续使用 managed／schema 2；未执行实际 Telegram 转存、WebDAV 写入、external_docker 接入、ACME、回退或 OpenList 升级。完整备份范围、结果与限制见[独立验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V142-ACCEPTANCE.md)。遇到旧 Release 缺失时保留现有服务，先备份并单独审阅可信基线，不改版本标记、不卸载重装或照搬人工处理脚本。

## v1.3.0 本次升级验收

2026-10-17，在专用测试 VPS 完成 CloudDrive2 旧测试候选到正式 v1.3.0 的迁移。原实例与官方旧版源码不一致，在线预检先安全停止；经授权人工核对、备份后，调用正式版原生安装流程完成切换。没有给脚本加入强制覆盖，也没有伪造旧版本。

历史任务、原配置及 Session 授权保留，运行指纹、健康、HTTPS 和只读 WebDAV 检查通过，在线 `--check` 复检识别为最新且不重建。用户随后确认使用验收完成。首次安装、标准正式版自动升级、故障回退、NAS 和全部传输异常场景不属于本次结论，详见[验收记录](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)。

## v1.2.1 历史图形升级流程

1. 阅读新版本 Release 说明和已知限制。
2. 查看队列，安排维护窗口，保存必要备份与失败保留文件。
3. 从正式 Release 下载同一 Edition 的新版部署器并校验。
4. 连接到已有 TG2Cloud 实例，确认安装目录正确。
5. 保持默认保留 VPS 当前 `.env`，重新执行“一键部署基础环境”。
6. 受管网关检查 HTTPS 状态；已有实例用新版部署器重新配置同一正常域名，以更新续期容器与记录能力，不需要移除旧路由或切换域名。
7. 查看部署器与 VPS Bot 的实际版本，执行 WebDAV 验收，再发送小文件验证。
8. 确认稳定后再评估旧回退点的保留策略。

不要用更新 TG2Cloud 的操作直接覆盖旧 TG115。跨项目前身迁移见 [迁移说明](/operations/migration/)。

## 下载新版不等于 VPS 已更新

本机 EXE、VPS Bot 和 HTTPS 续期容器分别需要核对。仅下载新版 EXE 不会更改 VPS；只重启也不会安装新版 payload。部署器“查看运行状态”显示正在运行的 Bot 版本，无法获取时不当作最新版，不自动升级或降级。

已有 HTTPS 的续期记录需要用新版部署器重新配置同一域名才能生效；旧实例没有记录并不代表 HTTPS 已失效。不要为了获得维护功能卸载重装、重置管理员或覆盖云存储挂载。说明见 [域名访问与 HTTPS](/deploy/domain-https/)。

## 哪些配置会保留

Linux 升级保留 VPS 当前 `.env` 原始字节，以及 SQLite、Session 授权和持久化数据。rclone 可能重新混淆同一 WebDAV 密码，使 `rclone.conf` 字节变化；应在私有环境核对实际配置，不凭 hash 变化直接断言改密，也不公开解混淆结果。混淆不是加密，配置和备份仍是敏感文件。

历史 v1.2.1 图形部署器仅在明确勾选“使用本页配置覆盖 VPS 当前 .env”时应用表单；单纯在旧 Windows 界面改密码但没有应用配置，不会改变正在运行的 Bot。不要用旧 EXE 覆盖已升级实例。

## `manage.sh update` 做什么

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh update
```

它使用 VPS 已安装的 payload 重建 Bot，**不自动从 GitHub 下载新源码，也不替换 `.env`**。

OpenList 对应脚本还会拉取当前 Compose 已固定的 OpenList 镜像并核验服务，但这同样不等于获取任意最新 TG2Cloud 源码。

## Linux 脚本：保留配置升级

v1.1.3 源码新增可选 VPS 向导。CloudDrive2 先做只读预检：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

核对计划、备份和维护窗口后，用同一入口启动交互向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

OpenList 先做只读预检，不安装／升级：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --check
```

检查通过并核对备份和维护窗口后，运行 OpenList 安装／升级向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist
```

它只获取正式稳定 Release 的源码，并核验已有实例的官方基线与运行指纹。已有完整受管实例保留 `.env`、rclone、SQLite 和持久化数据；仅重启或本机源码升级不等于 VPS 更新。不自动降级，不静默覆盖旧 TG115、部分安装或自定义配置，也不隐式切换 HTTPS 域名。

CloudDrive2 本次实际迁移及用户使用验收已完成，但不能据此跳过官方源码基线核对；自定义或旧候选实例仍需单独审阅。OpenList 脚本实机验收暂缓。完整边界见 [VPS 脚本指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。从 v1.3.0 起只维护 Linux 脚本，Windows EXE 停留在 v1.2.1，切勿与脚本同时操作同一实例。

v1.1.4 修复向导的交互终端与候选镜像源码权限：公开程序可供非 root Bot 读取，秘密仍保持私有；镜像内程序和日志统一为 TG2Cloud。数据库、Session、UID/GID 与 HTTPS 路由保持不变。遇到旧 `Permission denied` 不要删除数据或重新授权云盘，使用包含修复的正式版本重试；原版本 Tag 缺失时脚本仍安全停止。

## HTTPS 续做与已有凭据

v1.1.5 在首次基础安装成功、HTTPS 未完成的实例上，续做成功后再次提供逐项确认的已有凭据展示。取消配置会尝试有限回退；回退失败或 SSH 断连时必须重新核对状态，不代表业务数据已经恢复。

仅查看已保存信息时，不需要再次部署。按已安装的 Edition 在私有交互终端选择一条命令：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --show-credentials
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition openlist --show-credentials
```

每项默认不显示；此模式不安装、升级或改密，不能与 `--check`、`--configure-https`、`--verify` 组合。OpenList 显示的是保存的初始化管理员密码，可能不是你后来修改的当前密码。缺少的保存值不会被重新生成；不要将输出公开分享。

## 单独应用配置

把新配置保存在安装目录之外的、仅你可访问的绝对路径，再执行：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh apply-config /absolute/new-config.env
sudo /opt/tg2cloud-clouddrive2/manage.sh check
sudo /opt/tg2cloud-clouddrive2/manage.sh verify
```

`/absolute/new-config.env` 是待替换的示例路径，不是系统自带文件。OpenList 使用其 Edition 的脚本路径。

应用过程先备份和预检，再重建并检查实际环境；失败时按脚本机制恢复旧配置。改变目的账号或路径前，应先处理完队列及失败保留任务。

:::warning 自动保护不是通用恢复产品
v1.3.0 沿用有限内部失败回退机制，不提供正式自动 Restore；本次升级成功不等于故障回退已经实测。独立卸载不是升级步骤：完整清理会在双重确认后删除所选数据及可识别备份，保留数据需明确使用 `--keep-data`；未知归属与新增完整清理未实机验收的边界见 [卸载指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/UNINSTALL.md)。共享代理隔离解包也不是在线恢复；不能因为升级脚本有保护，就省略清理范围之外的独立备份。
:::

## 升级后检查清单

检查 Edition、版本、服务健康、目的路径和凭据是否符合预期；再看 `TG2CLOUD_DESTINATION=OK` 与真实小文件结果。只看到容器运行中，不足以确认升级完全成功。
