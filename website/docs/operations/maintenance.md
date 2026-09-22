# 状态、日志与重启

先用只读检查定位问题，再决定是否重启或执行会写文件的验收。路径要与安装的 Edition 一致。

## CloudDrive2 常用命令

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh status
sudo /opt/tg2cloud-clouddrive2/manage.sh logs
sudo /opt/tg2cloud-clouddrive2/manage.sh check
```

`status` 查看状态，`logs` 查看近期 Bot 日志，`check` 核对配置、代码指纹和基础心跳。输出可能含个人信息，分享前仍需自行审查脱敏。

## OpenList 常用命令

```bash
sudo /opt/tg2cloud-openlist/manage.sh status
sudo /opt/tg2cloud-openlist/manage.sh logs
sudo /opt/tg2cloud-openlist/manage.sh check
```

部署器的 OpenList 日常管理区也提供状态、脱敏日志和分别重启服务的操作。不要用另一 Edition 的路径处理当前实例。

## 重启 Bot

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh restart
```

OpenList 对应替换为 `/opt/tg2cloud-openlist/manage.sh`。`restart` 仅用于重启，不负责把你在电脑上刚改的表单应用到 VPS。

停止或启动时使用对应脚本的 `stop`、`start`；会影响服务可用性，操作前留意当前任务。

## 两种健康检查的区别

| 操作 | 是否真写目标文件 |
| --- | --- |
| Bot `/doctor` | 否，面向只读诊断 |
| `manage.sh check` | 不用于真写验收 |
| `manage.sh verify` | 是，会上传并删除小测试文件 |

不要把 `/doctor` 通过当作写权限已经验收。完整步骤见 [WebDAV 验收](/deploy/verification/)。

## 发现旧 TG115

桌面状态会把旧 TG115 独立提示，不会把它当作 TG2Cloud 已安装。当前管理脚本仅面向本 Edition 的 TG2Cloud 命名空间，不会替你升级或删除旧实例。

## 提交问题前

记录 Edition、版本、最后一次成功操作、第一处错误和是否刚改过配置。提供经过自己复核的脱敏日志，而不是完整 `.env`、数据库或备份。见 [安全说明](/reference/security/)。
