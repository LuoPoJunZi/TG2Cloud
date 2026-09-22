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

## 容器内 WebDAV 地址

CloudDrive2：

```text
http://tg2cloud-clouddrive2:19798/dav
```

OpenList：

```text
http://tg2cloud-openlist:5244/dav/
```

这些是 Bot 访问受管网关的地址。管理页浏览器入口使用 Windows 本机 SSH 隧道，不能把两者混用。

## 已明确的任务预算变量

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `LOCAL_TEMP_BUDGET_GB` | `20` | Bot 本地任务预算 |
| `MIN_FREE_DISK_GB` | `8` | 磁盘最少保留 |

完整运行配置应以部署器和当前源码为准。本页不提供可以直接覆盖生产实例的空白 `.env` 模板，避免误清已有凭据或默认项。

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

修改表单后必须明确重新部署并选择应用，或使用 `apply-config`。`restart` 与 `update` 不等于从 Windows 自动同步所有新输入值。
