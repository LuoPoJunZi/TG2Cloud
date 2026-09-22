# SSH 与管理页问题

先区分连接层、服务器身份、用户认证和端口转发，错误发生的位置决定了下一步。

## 连接超时或拒绝连接

检查 VPS 是否在线，IP/域名、SSH 端口和安全组是否正确。通过服务商控制台确认 SSH 服务运行。

超时不能单凭现象归因为密码错误，也不要为了测试直接关闭全部防火墙。

## Host key 不匹配

常见于重装、恢复快照或服务器变更，也可能连错主机。先从独立控制台核对：

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
sudo ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub -E sha256
```

核对实际使用的密钥类型。确认新指纹正确后，再在部署器选择“更新并重新连接”。原因不明或指纹不同，取消操作。

不要清空所有 `known_hosts` 或关闭 Host Key 检查。

## 身份认证失败

在主机身份已经确认后，检查用户名、密码、私钥内容和私钥口令。私钥口令不是 VPS 登录密码，sudo 密码也不是 SSH 主机指纹。

主机密钥更新成功不意味着登录凭据也正确。

## 本机 19798 或 5244 端口占用

在 Windows PowerShell 中只读查看：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 19798,5244 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

根据进程 ID 确认占用者。不要直接结束未知系统进程；先正常关闭确认不再需要的应用，再重新点击管理页按钮。

## ERR_EMPTY_RESPONSE 或隧道无响应

检查对应网关是否运行、当前部署器连接是否有效，以及 SSH 服务是否允许 TCP 转发。

CloudDrive2 需要允许转发到 VPS 的 `127.0.0.1:19798`；OpenList 对应 `127.0.0.1:5244`。检查 `AllowTcpForwarding` 与 `PermitOpen` 的实际限制，不要直接扩大为不必要的公网监听。

:::danger 修改 SSH 服务配置前
保留当前可用会话与服务商控制台入口，先执行 `sshd -t` 验证配置，再按系统服务方式安全重载。错误修改可能把自己锁在服务器外。
:::

## 能打开管理页，但验收是 401

隧道层已经可用，下一步检查 WebDAV 用户和运行配置。它与管理页登录账号不是同一概念；参见 [WebDAV 排查](/troubleshooting/webdav/)。
