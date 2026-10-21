## TG2Cloud v1.4.1 · 公网 NAT HTTPS 预检修复

修复 Oracle 等公网 IPv4 映射到私有网卡的主机在 HTTPS 前置检查时被误判为 DNS 错误的问题。继续支持 Linux 原生 AMD64／ARM64、CloudDrive2 和 OpenList，使用现有 Python＋Bash 架构。

## 本次修复

- 单一公网 A、所有已解析 AAAA 均匹配本机、没有其他公网 IPv4 网卡且端口归属安全时，新增云控制台公网 IPv4 人工确认。地址须独立输入并匹配域名 A，确认默认否；不会从 DNS 自动填值或查询第三方出口 IP。
- 确认只用于当前操作，绑定域名、DNS 和原有网卡地址；写入前重新检测。地址变化时停止，新增 Docker 网桥可继续；写入锁内不会重新索取 NAT 确认。
- 首次安装、tg2cloud 的 HTTPS 显式修复和独立外部 WebDAV 共用此能力。错误 AAAA、多 A、未确认或不一致地址、其他服务占用及未知端口仍停止；ACME、TLS 自检和失败回退继续执行。
- 分别显示 DNS、80 和 443 的检查结果。拒绝用本地执行地址 127.0.0.1 作为公网域名身份。
- 新增14项 NAT 回归，覆盖两 Edition、取消确认、错误地址、DNS／网卡变化、端口归属和证书失败回退。同步安装、FAQ、双架构说明与网站。
- 发布审计发现的两项开发依赖漏洞通过更新 uv 与 certifi 修复，统一重新生成哈希锁；不忽略漏洞或关闭安全检查，Bot 运行依赖不变。

## 安装与验收

继续使用原安装命令：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)
```

出现 NAT 提示时，请填写云控制台分配给本机的公网 IPv4，并确认已配置对应映射和80／443入站规则；不要把公网 A 改成私有 IP。此确认不证明入站可达，最终仍须通过证书签发、HTTPS 自检及外部网络验收。完整说明见[公网安装指南](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/VPS-INSTALL.md#公网-nat-的已知限制与待发布修复)。

已有实例建议先追加 --edition clouddrive2 --check（OpenList 使用 openlist），只读检查不执行升级。需要安装／升级时重新运行入口并确认；内网仍使用 install-lan.sh，外部只读访问仍独立使用 install-webdav.sh。现有离线管理工具需显式更新，重启旧容器不会更新向导。

## 兼容与发布资源

无需数据库迁移或新增用户配置；镜像与 Bot 运行依赖版本不变，仅更新两项开发工具依赖。保留配置、数据库、Telegram Session、网关数据及现有备份。公网管理后端仍仅回环监听，NAT 确认不改变端口暴露、只读账号或代理归属规则。Windows 部署器保留历史 v1.2.1，本版不构建 EXE。

GitHub Actions 从同一不可变 v1.4.1 Tag 完成原生 AMD64／ARM64 验证后，打包并发布一次 TG2Cloud-v1.4.1-source.tar.gz 与 SHA256SUMS.txt。在线 helper 先验证辅助 A，再固定入口 B；业务只取正式稳定 Release，不用 moving main 替代。下载后使用同版本清单执行 sha256sum -c SHA256SUMS.txt；校验和不是数字签名。

## 验证边界

本地完整回归894项：867成功、27环境条件跳过、0失败；Python3.10的21项宿主／NAT专项及不加载Bot依赖的CLI帮助通过。全范围Ruff、语法检查、Bandit、网站构建及19项网站测试通过。正式发布还须通过对应提交与同标签的原生双架构检查。

真实 Oracle NAT 的入站映射、ACME、网关挂载、Telegram 转存、手机和故障回退仍待用户发布后实机验收。大小复验不等于内容哈希或云盘官方最终完成。历史范围见[v1.3.3 用户转存确认](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V133-ACCEPTANCE.md)与[v1.3.0 历史迁移](https://github.com/LuoPoJunZi/TG2Cloud/blob/main/docs/development/V130-ACCEPTANCE.md)，不外推为本版结果。

TG2Cloud 从 [whyhhh20/TG115](https://github.com/whyhhh20/TG115) 演进，保留 MIT 许可证、版权与必要致谢；用户在自己的存储网关管理云账号授权。
