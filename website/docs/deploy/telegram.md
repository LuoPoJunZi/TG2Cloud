# Telegram 配置

TG2Cloud 使用你自己的 Bot，而不是让你向文档站登录 Telegram 私人账号。

## Bot Token

在 Telegram 中找到官方 `@BotFather`，按其流程创建 Bot，保存返回的 Token。不要在公共频道、Issue、截图或网页里暴露它。

Token 是 Bot 的控制凭据，不是 Bot 用户名。复制时注意不要混入空格或换行。

## API ID 与 API Hash

在 [my.telegram.org](https://my.telegram.org) 的 API 应用管理页面创建应用，获取配套的 API ID 和 API Hash。

它们与 BotFather 的 Token 不同，三个字段都应分别填写。私人账号密码或短信验证码不需要交给 TG2Cloud 部署器。

## 允许使用的数字 ID

Allowed User 填写你本人的 Telegram **数字 ID**，不是电话号码，也不是 `@username`。请通过自己信任的方式确认 ID，避免把凭据交给来历不明的网站。

安装时只填写这一个固定管理员 ID；管理员可在安装后的 `tg2cloud` → **5. Bot 用户管理** 授权可信家人，共用保存目录并各自管理任务。详见[Bot 使用与家庭共享](/usage/commands/)。管理员与已授权成员都必须通过与 Bot 的一对一私聊提交，加入群组或频道不会启用群组批量转存。

## 第一次与 Bot 对话

部署和 WebDAV 验收结束后，在 Telegram 打开自己的 Bot，发送：

```text
/start
/help
/status
```

再发一个测试文件，按 [第一次文件转存](/usage/first-transfer/) 检查全链路。

## 同一个 Token 只交给一个活动实例

其他 Edition 或另一台主机上的 Bot 若仍在使用相同 Token，可能争抢 updates。不要把这种冲突误判为“Bot 偶尔失灵”。

切换实例前应在自己的维护计划中停止旧实例，或给新实例创建独立 Bot。部署器不会扫描整个网络来替你查找 Token 冲突。

## Token 泄露怎么办

在 BotFather 撤销或更新 Token，之后按[修改配置](/operations/update/)将新配置应用到 VPS，再验证服务。不要只更换本地记录或重启容器而不应用运行配置，也不要把旧 Token 贴到问题报告中。
