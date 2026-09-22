# CloudDrive2 Edition 部署

适用于使用 CloudDrive2 挂载云存储，并通过其 WebDAV 接口接收文件的用户。115 仅作为路径示例。

## 一、确认部署方式

先按 [部署前准备](/guide/prerequisites/) 备齐信息，下载 `TG2Cloud-CloudDrive2-Deployer.exe`，测试 SSH，并检查 VPS 具有受管 CloudDrive2 所需的 `/dev/fuse`。

同机受管部署一般保持“在 VPS 上安装并管理 CloudDrive2 容器”勾选。已有外部 CloudDrive2 时，可以取消这一项，但需要提供 **Bot 容器实际能访问** 的 WebDAV 地址。

## 二、填写 WebDAV

同机受管安装保持以下默认值：

```text
http://tg2cloud-clouddrive2:19798/dav
```

这里的主机名是 Docker 内网服务，不是浏览器应该打开的网址。不要替换为 `127.0.0.1`；在 Bot 容器内，它会指向 Bot 自己。

预先确定一个 TG2Cloud 专用 WebDAV 用户名与密码。部署后需要到 CloudDrive2 管理页创建完全一致的用户。不要填 CloudDrive2 会员密码或云盘登录密码。

## 三、确认目录与预算

| 项目 | 操作 |
| --- | --- |
| 安装目录 | 通常保持 `/opt/tg2cloud-clouddrive2` |
| 任务预算 | 检测 VPS 后，主动应用均衡或流式优先建议 |
| 磁盘保留 | 采用资源检测结果，不盲目降低安全线 |
| 子目录 | WebDAV 根目录已指向目标文件夹时留空 |
| 时区 | 按自己的实际用途设置；项目默认 `Asia/Shanghai` |

然后点击“一键部署基础环境”。日志构建期间不要反复点击其他操作，等明确部署成功再继续。

## 四、打开 CloudDrive2 管理页

点击“打开 CloudDrive2 管理页”，部署器通过 SSH 隧道访问：

```text
http://127.0.0.1:19798
```

这个地址属于当前 Windows 电脑上的隧道入口。网关端口默认不公开给互联网；不需要为了开管理页把 19798 暴露到公网。

在管理页登录 CloudDrive2，添加并授权自己的云存储，确认可以浏览目标目录。

## 五、启用 WebDAV 与正确权限

开启 WebDAV，创建与部署器中完全一致的专用用户。取消“只读”，确认用户实际能够列目录、读取、写入、改名和删除。

两种目标目录写法二选一：

| WebDAV 用户根目录 | 部署器子目录 | 最终位置 |
| --- | --- | --- |
| `/115open/Telegram` | 留空 | `/115open/Telegram/文件名` |
| `/` 或上层目录 | `115open/Telegram` | `/115open/Telegram/文件名` |

路径是示例，应替换为你的实际挂载名称。不要在两处重复写一段路径，造成 `Telegram/Telegram` 一类重复目录。

## 六、执行真实验收

点击“WebDAV 验收”，测试必须能完成上传、大小检查、改名、复验和清理，并出现：

```text
TG2CLOUD_DESTINATION=OK
```

只有报错确实属于 CloudDrive2 容器网络问题时，才使用“修复 CloudDrive2 网络”。这个按钮不能修复密码错误、只读权限、云盘未登录或空间不足。

## 七、发送测试文件

按 [第一次文件转存](/usage/first-transfer/) 发送一个小文件，并在云存储官方客户端核实位置、大小和内容。CloudDrive2 WebDAV 接收成功不等于上游云盘最终状态已被 TG2Cloud 证明。

:::warning 已有安装与备份
重复部署默认保留 VPS 当前 `.env`。CloudDrive2 没有手动“创建安全备份”UI，也没有正式自动 Restore。升级前先读 [备份边界](/operations/backup/)。
:::
