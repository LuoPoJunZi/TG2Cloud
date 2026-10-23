# CloudDrive2 Edition 部署

使用 Linux 一键脚本部署，再在自己的 CloudDrive2 后台挂载云存储和设置专用 WebDAV 用户。115 只是可用存储的示例之一。

## 一、确认部署方式

先完成[部署前准备](/guide/prerequisites/)，确认 Debian / Ubuntu 原生 AMD64 / ARM64、root 权限及 `/dev/fuse` 可用。

按[从零开始部署](/guide/quick-start/)选择公网或可信内网入口，再选 **1. CloudDrive2**。首次安装按向导核对域名或私有 IP、磁盘建议及 Telegram 配置；标准安装目录为 `/opt/tg2cloud-clouddrive2`。

当前标准流程管理本机受管网关，不是给任意外部 CloudDrive2 填一个 URL 就能接管。未知容器、端口或目录冲突时停止，不静默覆盖。

## 二、填写 WebDAV

新装用户名回车默认 `tg2cloud`，密码可自行输入或留空生成。记下安装结束时在私有终端显示的凭据；之后需在 CloudDrive2 创建完全一致的用户。

受管 Bot 使用：

```text
http://tg2cloud-clouddrive2:19798/dav
```

这是 Docker 内部地址，由安装器配置，不是浏览器管理页。不要换成 Bot 容器里的 `127.0.0.1`，也不要换成公网管理域名。

CloudDrive2 账号、会员密码和云存储授权只在自己的网关后台输入，不用它们代替 Bot 的 WebDAV 凭据。

## 三、确认目录与预算

| 项目 | 操作 |
| --- | --- |
| 任务预算、磁盘保留 | 按实时资源推荐选择；手动数值仍需校验 |
| Bot 保存子目录 | 相对路径，可留空；根目录在 CloudDrive2 后台设置 |
| 时区 | 首次默认 `Asia/Shanghai`；升级保留已有值 |
| 已有实例 | 核对身份并保留原配置升级，不重新填写或覆盖凭据 |

确认计划后才执行安装；等待基础健康与管理入口结果。失败时按第一处错误排查，不把重试、重装和删除数据当成同一操作。

## 四、配置 HTTPS 并打开 CloudDrive2 管理页

公网实例使用自己的独立域名，例如 `https://cloud.example.com`；可信内网使用向导给出的 `http://内网IP:19798`。示例地址必须替换为实际值。

日常通过 `tg2cloud` → **7. HTTPS 与管理** 检查对应入口。公网 NAT、80/443 归属和已有 Docker Nginx 接入见[HTTPS 指南](/deploy/domain-https/)。

管理域名只代理页面，`/dav` 和 `/dav/` 被拒绝是预期策略。手机只读读取需另装[外部 WebDAV](/deploy/external-webdav/)，不能借用管理域名开放 Bot 账号。

## 五、启用 WebDAV 与正确权限

1. 在自己的管理页登录 CloudDrive2，添加并授权云存储，确认能浏览目标目录。
2. 开启 WebDAV，创建与安装时保存值一致的专用用户。
3. 设置用户根目录，取消只读，并确认实际列表、读取、写入、改名和删除能力。
4. 只给任务需要的目录权限，不使用管理员或匿名账号代替。

目录只组合一次，下面是示例，不是固定路径：

| 用户根目录 | Bot 相对子目录 | 最终位置 |
| --- | --- | --- |
| `/MyCloud/Telegram` | 留空 | `/MyCloud/Telegram/文件名` |
| `/MyCloud` | `Telegram` | `/MyCloud/Telegram/文件名` |

## 六、执行真实验收

运行 `tg2cloud`，选 CloudDrive2，再选 **11. WebDAV 验收**。确认随机测试文件的创建和清理，检查上传、大小、改名、复验及清理结果：

```text
TG2CLOUD_DESTINATION=OK
```

验收失败先看具体阶段。401、只读权限、网盘未登录与网络解析失败不是同一种问题，不能靠公开端口或重复重装解决。详见[WebDAV 排查](/troubleshooting/webdav/)。

## 七、发送测试文件

按[第一次文件转存](/usage/first-transfer/)发送一个小文件，在云存储官方客户端检查位置、大小和可打开性。WebDAV 大小复验不是内容哈希或云盘官方最终完成证明。

需要查看保存的凭据时，使用 `tg2cloud` → **6. WebDAV 凭据**，每项在私有终端确认。两版都可在 **13. 数据备份管理** 创建实例快照；快照会暂停所选服务，范围和隔离预检见[备份说明](/operations/backup/)。
