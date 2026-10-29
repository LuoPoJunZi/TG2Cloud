## TG2Cloud v1.5.3 · 项目命名统一与 Compose HTTPS

本版统一全新安装的 TG2Cloud 命名，并为独立 Compose 部署增加可选 HTTPS 向导。原有一键安装流程和已有实例数据保持兼容。

## 本次改动

- 全新安装使用 `data/tg2cloud.db`；已有唯一旧库继续使用，不重命名、不重建。Bot、监听、管理、诊断、备份及恢复统一解析路径；双库、链接和无主旁文件拒绝操作。
- 新配置不再输出 `TG115_*` 项目变量；兼容读取、旧实例隔离、历史证据、版权和上游致谢保留。日志、验收临时对象与内部 Shell 函数采用 TG2Cloud 命名。
- 两 Edition 一键升级／回退按实际数据库文件名保护数据；增加 v1.5.2 的真实不可变升级基线。
- Compose 初始化增加可选访问方案；完整 format 2 部署包提供离线宿主 HTTPS 向导，复用 Nginx／Certbot、共享锁、续期与备份。已有其他代理只导出候选，不自动修改原站点。
- Compose 保持独立初始化与容器标识，不给公网／内网一键安装增加步骤，不接管已有脚本实例；共享代理的写入、迁移和卸载检查 Compose 依赖。

## 使用与兼容

使用步骤见 [Compose 指南](docs/COMPOSE.md)、[一键安装](docs/VPS-INSTALL.md)及[发布与兼容记录](docs/development/V153-ACCEPTANCE.md)。在线安装仍只使用正式稳定 Release；Compose 请使用同版镜像、完整 format 2 部署包及校验清单，不混用旧版资源。v1.5.2 历史资产不替换。

沿用业务 schema 3，不增加必填环境变量或依赖，不清理数据库、Session、凭据、下载及云端文件。已有唯一旧库保留原名；全新实例使用新名，旧版本可能无法识别，禁止直接换旧镜像造成空库。回退应使用匹配的一致性备份，在隔离目录验证后再规划恢复。

## 验证状态

本地完整检查退出 0：1508 项中 1473 通过、35 条件跳过、0 失败；Python 3.10 宿主 CLI 共 845 项（833 通过、12 条件跳过），网站 37 项通过。详细命令及范围见[发布与兼容记录](docs/development/V153-ACCEPTANCE.md)。[同标签原生双架构发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40844895202)及[镜像与部署包发布](https://github.com/LuoPoJunZi/TG2Cloud/actions/runs/40845397585)通过；五份实际下载资产的 SHA256、源码与 Tag、两版部署包与镜像摘要已核验，详细证据见发布记录。真实 DNS／ACME、Telegram、两网关转存和生产恢复仍需发布后验收。

入口固定真实辅助 A `9dbae452c81c170fe74e03a4a52afecb6e60d721`；正式 Tag 对应 `2e6f06f09e1e2ac9fe8ae2d9c6e1d83cc7a3bee1`。不移动历史 Tag、不覆盖旧 Release，不自动连接或升级 VPS。

历史验收范围保留：[v1.3.0](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V130-ACCEPTANCE.md)、[v1.4.3](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V143-ACCEPTANCE.md)、[v1.4.4](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V144-ACCEPTANCE.md)、[v1.4.5](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V145-ACCEPTANCE.md)、[v1.5.1](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V151-ACCEPTANCE.md)、[v1.5.2](https://github.com/LuoPoJunZi/TG2Cloud/blob/c7e0b4b7497fbfa258c752dcff4666d1e2011eae/docs/development/V152-ACCEPTANCE.md)。它们不代表本版实机验收。
