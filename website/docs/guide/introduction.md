# 认识 TG2Cloud

把文件交给自己的 Telegram Bot，把存储留在自己选择的云端。

TG2Cloud 是个人自托管的文件转存工具。你在 Telegram 中手动挑选有权保存的文件，转发给私人 Bot；VPS 负责排队、传输、目的端大小检查和本地清理。文件最终写入你在 **CloudDrive2** 或 **OpenList** 中挂载的云存储。

:::info 先了解项目来源
本项目基于原作者 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 二次开发，并保留 MIT 许可证和上游版权。TG2Cloud 扩展为双存储网关、多云目标；115 是主要测试场景和文档示例之一，不是唯一目标。
:::

## 一条清楚的传输链路

```text
Telegram 一对一私聊
        ↓
私人 Bot → SQLite 持久任务队列
        ↓
普通模式：VPS 完整下载 → rclone 上传
流式模式：Telegram → rclone 管道
        ↓
CloudDrive2 / OpenList WebDAV
        ↓
你自行挂载、授权的云存储
```

CloudDrive2 与 OpenList 在这里充当“存储网关”：TG2Cloud 面向网关的 WebDAV 接口，不直接接管各家云盘的登录和授权。

## 可以做什么

| 能力 | 实际作用 |
| --- | --- |
| Windows 图形化部署 | 配置 SSH、Telegram 和 WebDAV，部署 VPS 基础服务 |
| 持久任务队列 | 将任务保存在 SQLite 中，支持重启后恢复处理 |
| 资源保护 | 检查安装盘、Docker 数据盘、inode、内存与磁盘安全线 |
| 普通与流式传输 | 根据文件大小和本地任务预算选择传输方式 |
| 日常运维 | 查询队列、暂停调度、重试、只读诊断和临时文件巡检 |
| 两个独立版本 | 分别部署 CloudDrive2 Edition 或 OpenList Edition |

## 使用前必须知道的边界

**不是频道爬虫。** 当前只接受配置用户的一对一私聊，不自动监听频道，也不批量抓取频道历史。手动转发文件与后台自动处理是两件事。

**不是云盘官方完成接口。** “Bot 完成”表示 Bot 的 WebDAV 传输和大小检查流程完成，不等于网盘官方客户端已经完成最终入库校验。

**不是内容哈希校验。** 当前以远端文件大小为主要完整性依据；重要文件仍需自行验证内容。

**不是不占磁盘。** 流式模式不保留完整本地副本，但网关缓存、Docker 镜像、日志和备份仍会占空间。

## 应该从哪里开始

新用户先看 [版本选择](/guide/editions/) 和 [从零开始部署](/guide/quick-start/)。已有 TG115 的用户先看 [迁移说明](/operations/migration/)，不要直接覆盖旧目录。
