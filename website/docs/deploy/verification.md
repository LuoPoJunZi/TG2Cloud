# 真实 WebDAV 验收

“网页能打开”“目录能列出”“密码能登录”和“文件能完整写入”是不同的检查。正式转存前，必须从 Bot 的实际运行环境完成真实写入验收。

## 什么时候执行

首次挂载云存储、创建 WebDAV 用户后执行。修改用户名、密码、路径、权限，或者完成升级后，也应重新验证当前配置。

先完成基础部署，再完成网关登录和挂载。部署器尚在构建服务时，不要并发点击验收。

## CloudDrive2 验收路径

```text
Bot 当前配置
  → 创建 256 字节随机测试文件
  → WebDAV 上传临时文件
  → 检查远端大小
  → 改名为正式路径并复验
  → 删除远端及本地测试文件
```

## OpenList 验收路径

```text
Bot 与 OpenList 健康
  → 认证并访问目标目录
  → 写入预留最终路径
  → 检查大小与最终落盘
  → 删除测试文件并检查清理
```

OpenList v1.0.2 不依赖 WebDAV MOVE，因此两版的最终落盘步骤不同。

## 唯一明确的通过标记

```text
TG2CLOUD_DESTINATION=OK
```

只出现“认证通过”或 HTTP 201，不代表整体验收成功。OpenList 页面会把阶段分为“通过、失败、未执行”，应先定位第一处失败。

## 命令行入口

CloudDrive2：

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh verify
```

OpenList：

```bash
sudo /opt/tg2cloud-openlist/manage.sh verify
```

:::warning 这不是只读检查
`verify` 会在目标目录创建和删除小测试文件。只想查看健康状况时使用 Bot `/doctor` 或管理脚本 `check`，不要在不合适的目录执行真写验收。
:::

## 通过之后还要验证什么

先发一个小文件，确认网盘官方客户端中大小正确且可打开。之后测试普通模式、流式模式、重启恢复和测试任务取消。

WebDAV 的 256 字节验收不能替代真实大文件测试，也不能证明云盘官方最终入库状态。故障分类见 [WebDAV 错误排查](/troubleshooting/webdav/)。
