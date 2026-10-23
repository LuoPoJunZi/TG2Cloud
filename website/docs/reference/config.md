# 配置与路径速查

下面按当前产品定义整理，用于核对而不是让你全局搜索替换旧名称。

## 两个 Edition 的资源

| 项目 | CloudDrive2 | OpenList |
| --- | --- | --- |
| 安装目录 | `/opt/tg2cloud-clouddrive2` | `/opt/tg2cloud-openlist` |
| 备份目录 | `/opt/tg2cloud-clouddrive2-backups` | `/opt/tg2cloud-openlist-backups` |
| Bot 容器 | `tg2cloud-clouddrive2-bot` | `tg2cloud-openlist-bot` |
| 网关容器 | `tg2cloud-clouddrive2` | `tg2cloud-openlist` |
| Docker 网络 | `tg2cloud-clouddrive2-net` | `tg2cloud-openlist-net` |
| 本机管理端口 | `19798` | `5244` |
| FUSE 要求 | 受管安装需要 | 产品配置不要求 |

## 共享 HTTPS 代理资源

| 项目 | 两个 Edition 共用 |
| --- | --- |
| 受管代理运行目录 | `/opt/tg2cloud-proxy`；外部代理模式按登记责任维护 |
| 代理私密备份目录 | `/opt/tg2cloud-proxy-backups` |
| managed 模式 Nginx 容器 | `tg2cloud-proxy-nginx` |
| managed 模式 Certbot 容器 | `tg2cloud-proxy-certbot` |
| 公网入口 | TCP 80/443，两个 Edition 使用不同域名 |

Edition 业务备份不包含此目录。代理归档含证书私钥与 ACME 账户，目录权限 700、文件权限 600；维护和历史清理使用 [HTTPS 工具](/deploy/domain-https/)，不是业务 `manage.sh prune-backups`。[备份边界](/operations/backup/)。

## 容器内 WebDAV 地址

CloudDrive2：

```text
http://tg2cloud-clouddrive2:19798/dav
```

OpenList：

```text
http://tg2cloud-openlist:5244/dav/
```

这些是 Bot 访问受管网关的 Docker 内网地址。管理页浏览器入口使用当前 Edition 的 HTTPS 域名，不能把两者混用；公网 `/dav` 与 `/dav/` 会被固定拒绝。

## 已明确的任务预算变量

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `LOCAL_TEMP_BUDGET_GB` | `20` | Bot 本地任务预算 |
| `MIN_FREE_DISK_GB` | `8` | 磁盘最少保留 |

完整运行配置以当前 Linux 向导、已保存实例和源码为准。本页不提供可以直接覆盖生产实例的空白 `.env` 模板，避免误清已有凭据或默认项。

## 常见状态标记

| 标记 | 含义 |
| --- | --- |
| `TG2CLOUD_DESTINATION=OK` | 当前真实 WebDAV 验收完成 |
| `TG2CLOUD_UPDATE=OK` | 管理脚本更新检查通过后的成功标记 |
| `TG115_*` | 仅在必要旧脚本输出读取中保留兼容，不代表应使用旧目录 |

## 不应手动替换的内部兼容项

SQLite 文件名 `tg115.db` 和一些历史前缀仍可能保留。保留名字是为了兼容稳定状态，不表示自动导入旧数据库。

不要把整个部署目录的 `TG115` 字符串全部替换为 `TG2Cloud`。改变内部状态格式需要代码和迁移验证。

## 配置生效方式

升级默认保留原 `.env`，不会因重新输入或重启自动改密。显式变更使用经过检查的 `apply-config` 流程；`restart` 和 `manage.sh update` 不等于下载新版本或应用新配置，见[配置变更](/operations/update/#单独应用配置)。
