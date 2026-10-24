# v1.4.6 维护与发布准备

本文说明 v1.4.6 的外部 WebDAV 界面与维护改动，当前正在执行正式发布流程。下面的新工具和新界面须等待辅助 A、入口 B 与同标签门禁后才能进入在线命令；不是新增 Windows 支持或运行数据库迁移。

## 外部 WebDAV 界面

本地源码运行：

```bash
python3 -B scripts/run_source.py webdav
```

沿用原有 10 项中文菜单及英文子命令。状态／连接检查页面执行后停留，1 刷新或重新检查，0 返回功能菜单；重新检查仍需输入本次认证密码，不保存明文。状态仅为本地登记信息，不能代替实际连接检查。修改操作没有“刷新执行”按钮。

用户管理显示所选 Edition／工具版本、共同目录与账号状态，返回文字区分功能菜单和用户管理。卸载或升级操作后退出当前进程，避免继续读取已删除或替换的运行代码。明确子命令仍执行一次后退出；权限、锁、账号隔离、后端人工只读配置及确认规则不变。

安装主流程、Bot 菜单和传输流程保持原行为。主项目升级不会代替独立附加功能升级。

## 发布准备工具

完整源码 checkout 中执行；`--version` 是计划目标，必须高于当前版本。以下 1.4.7 只是演示，不表示已确定下个版本号：

```bash
python3 -B .github/scripts/prepare_release.py --version 1.4.7
python3 -B .github/scripts/prepare_release.py --version 1.4.7 --directory build/review-release-147
```

第一条只输出计划；第二条只向 `build/` 下全新的目录写入 `plan.json` 和 `version.patch`。不修改工作树版本、依赖、CHANGELOG、Release Notes 或 pin，不执行 Git、网络、部署或发布操作。拒绝已有候选目录、链接路径、同版／降版和异常元数据。

补丁覆盖唯一版本源、安装入口展示版本和网站版本元数据；网站保持旧的实际发布版本，将候选状态标为未发布。维护者必须审阅实际变更说明、兼容性、文档与下载链接，再决定是否应用候选补丁。

继续执行已有的 `maintenance_preflight.py`。新代理模块使当前 helper 一致性按预期阻断，不能忽略或改成通过：

已核对本地 v1.4.5 原正式 Tag 提交，使用现有工具静态生成并复核两 Edition 载荷摘要，补入受支持的历史基线。已有历史 Git 对象重生成测试继续核对，不能用当前工作树的新代码替代旧正式源码。

1. 本地审阅源码和载荷清单，运行回归。
2. 获得发布授权后，先公开辅助提交 A 并等待其 CI。
3. 用 `prepare_bootstrap.py --directory build/<新的候选目录>` 生成入口候选；入口提交 B 只固定已公开、通过验证的 A，不固定自身。
4. 等 B 的 CI 通过后，再按授权创建不可变版本 Tag，同标签原生双架构校验与发布。
5. 下载并核对实际资产；此后再更新网站的已发布状态。校验和不等于数字签名。

## 测试与 CI 组织

`tests/naming/` 集中四组命名质量、增强、接入边界和预览测试，保留原测试文件名和全部断言。混合测试及共享夹具暂留原位置，不为目录整齐搬动整套测试。移动前后，标准化模块前缀后的 1,121 项测试发现集合摘要一致；之后再独立计入新增维护测试。

完整发现仍使用 `python3 -B -m unittest discover -s tests -v`。直接按子目录运行接入类测试时，需让共享夹具可导入：

```bash
PYTHONPATH=src:tests python3 -B -m unittest discover -s tests/naming -v
```

日常原生运行测试与正式 Tag 的当前布局验证共用 `.github/scripts/linux_validation.py`：

```bash
python3 -B .github/scripts/linux_validation.py shell
python3 -B .github/scripts/linux_validation.py test
python3 -B .github/scripts/linux_validation.py quality
```

`shell` 逐个检查四个入口并执行原 ShellCheck 范围；`test` 沿用完整测试入口；`quality` 保留 Ruff、编译、版本／清单、Bandit 及两份依赖审计，任一步失败即停止。Docker、双架构、隔离 WebDAV、网关／FUSE、打包与发布门槛继续由现有工作流执行。历史布局的旧校验分支保留，不改写旧 Tag。

## 小范围模块整理

`deployment/proxy/rendering.py` 承载纯 Nginx／Compose／续期循环文本生成。`manager.py` 保留宿主操作、锁、激活和回退，并重新导出旧渲染接口，现有调用不必改导入。生成内容、镜像、权限与状态协议保持原行为；新模块进入 bootstrap 和 runtime 显式清单。

暂不拆分 SQLite 事务、上传提交顺序或所有 Telegram 命令。后续随实际维护需求逐项抽离，每次保持事务／锁边界并补回归。

## 发布准备前的本地验证结果（2026-10-24）

- Python 3.13 完整检查：1,137 项测试，1,106 执行通过、31 项按现有环境条件跳过，0 失败／错误；仓库检查、Ruff 和 compileall 完成。另用 CI 固定的 Ruff 0.17.0 检查通过。
- Python 3.10：发布工具 8、外部结果页 6、纯代理渲染 2、干净宿主管理包 2 项通过；WebDAV `--help` 无 Bot 依赖运行通过。
- 额外尝试在裸 Python 3.10 跑完整旧代理组时，有 3 个夹具错误：缺少开发用 cryptography，且两处旧测试使用 datetime.UTC。完整代理组按现有规范在 Python 3.13 验证通过（75 项中 4 项环境跳过）；未修改生产能力、删除测试或新增 skip 掩盖此次额外尝试。
- 四个入口 Bash 语法、原受管 ShellCheck 范围、Bandit 通过；Bandit 的既有 nosec 无匹配提示不当作新增漏洞。
- 两 Edition 构建上下文在新目录组装成功，递归代码指纹一致；7 个纯渲染函数的函数体与重构前相同，四组移动测试除包定位和文档字符串外 AST 一致。
- 网站构建、36 项测试及 4,081 个站内链接／资源／锚点检查通过，33 HTML、266 条本地搜索记录；未部署网站。
- 版本、显式清单和 7 个旧版基线预检通过。helper 一致性仍按预期阻断：须以后经授权公开 A／更新 B／远端 CI 后才能发布。正式版本仍为 1.4.5，未创建 Git 提交或改动远端。

本轮没有 Docker daemon、Linux PTY／flock／原生 FUSE 或本机 rclone 集成条件，相应已有跳过不计为通过；未执行远端 CI、实际 VPS／网盘、手机播放、公网 ACME 或生产恢复。用户提供的旧代码验收与本地候选测试分别记录。
