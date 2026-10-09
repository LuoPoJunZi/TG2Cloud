# 升级与修改配置

“重启”“用当前 payload 重建”和“安装新版本”是三个不同操作。

## 推荐升级流程

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

已有 TG2Cloud 重复部署默认保留 VPS 当前完整 `.env`，以及 SQLite、`rclone.conf` 和持久化数据。只有明确勾选“使用本页配置覆盖 VPS 当前 .env”，才会应用本次表单。

因此，单纯在 Windows 界面改密码但没有应用配置，不会改变正在运行的 Bot。

## `manage.sh update` 做什么

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh update
```

它使用 VPS 已安装的 payload 重建 Bot，**不自动从 GitHub 下载新源码，也不替换 `.env`**。

OpenList 对应脚本还会拉取当前 Compose 已固定的 OpenList 镜像并核验服务，但这同样不等于获取任意最新 TG2Cloud 源码。

## 没有 Windows：保留配置升级

v1.1.3 源码新增可选 VPS 向导。先做只读预检：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2 --check
```

核对计划、备份和维护窗口后，用同一入口启动交互向导：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh) --edition clouddrive2
```

它只获取正式稳定 Release 的源码，并核验已有实例的官方基线与运行指纹。已有完整受管实例保留 `.env`、rclone、SQLite 和持久化数据；仅重启或本机源码升级不等于 VPS 更新。不自动降级，不静默覆盖旧 TG115、部分安装或自定义配置，也不隐式切换 HTTPS 域名。

当前 CloudDrive2 已完成真实 VPS 只读预检，但首次安装、实际跨版本升级及回退仍未验收；OpenList 脚本实机验收暂缓。完整边界见 [VPS 脚本指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md)。两个 EXE 仍是主力入口，切勿与脚本同时操作同一实例。

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
当前 v1.1.3 只有有限内部失败回退机制，不提供正式自动 Restore 或 Uninstall。共享代理隔离解包也不是在线恢复；不能因为升级脚本有保护，就省略独立备份。
:::

## 升级后检查清单

检查 Edition、版本、服务健康、目的路径和凭据是否符合预期；再看 `TG2CLOUD_DESTINATION=OK` 与真实小文件结果。只看到容器运行中，不足以确认升级完全成功。
