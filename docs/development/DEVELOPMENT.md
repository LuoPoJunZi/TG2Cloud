# Linux 开发与测试

TG2Cloud 采用 Python 主体、Bash 轻量入口和 Docker Compose。CloudDrive2 与 OpenList 共享 Bot，部署配置、容器身份和持久化目录分开；不依赖维护者的本地归档。

## 源码与职责

| 模块 | 职责 |
| --- | --- |
| `src/tg2cloud/cli/` | 参数解析、终端交互和本地管理菜单 |
| `src/tg2cloud/deployment/` | 实例核验、配置、安装升级、备份卸载和共享代理 |
| `src/tg2cloud/telegram/` | 鉴权、消息／媒体组、按钮、交互草稿和展示 |
| `src/tg2cloud/transfer/` | 任务、调度、下载、上传、流式与恢复 |
| `src/tg2cloud/domain/` | 状态、错误、命名等领域规则 |
| `src/tg2cloud/persistence/` | SQLite 事务、迁移、路径解析与一致性备份 |
| `src/tg2cloud/storage/` | rclone 与两种网关的提交、校验和恢复策略 |
| `src/tg2cloud/monitoring/` | 资源、进度和健康检查 |
| `src/tg2cloud/compose/` | 独立 Compose 初始化、部署包和可选宿主 HTTPS |
| `src/tg2cloud/addons/external_webdav/` | 按需启用的外部只读入口 |

## 本地入口与依赖

完整克隆仓库；历史兼容回归会读取固定 Git 对象，因此测试环境需要完整历史。宿主 CLI 支持 Python 3.10+，使用标准库；包初始化不提前加载 Bot 依赖。源码入口不依赖当前工作目录：

```bash
python3 /path/to/TG2Cloud/scripts/run_source.py install --help
python3 /path/to/TG2Cloud/scripts/run_source.py lan --help
python3 /path/to/TG2Cloud/scripts/run_source.py manage --help
python3 /path/to/TG2Cloud/scripts/run_source.py uninstall --help
python3 /path/to/TG2Cloud/scripts/run_source.py webdav --help
```

这些帮助命令不执行部署。真正安装、升级或卸载必须核对实例并确认；不要把生产 VPS 当作单元测试夹具。

Bot 镜像使用 Python 3.12，完整本地回归使用 Python 3.12 / 3.13。`pyproject.toml` 是依赖定义，`requirements/` 的两份锁文件由统一工具生成，不手改独立版本：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/dev.lock.txt
python -m pip install --no-deps -e .
python -B .github/scripts/check_python.py all
```

只验证宿主 CLI 时，使用不含 Bot 依赖的 Python 3.10 / 3.13 环境；需要现有固定版本的 Ruff 才能执行 lint：

```bash
python -B .github/scripts/check_python.py all --scope cli
```

依赖确需变化时才运行 `python .github/scripts/lock_dependencies.py`，按其固定 uv 和 Bot Python 下限生成并审阅哈希锁文件。

## 组装、检查与测试

```bash
python -B .github/scripts/prepare_bootstrap.py
python -B .github/scripts/build_payload.py --edition all --directory build/local-contexts
PYTHONPATH=src:tests python -B -m unittest discover -s tests/naming -v
python -B .github/scripts/check_repository.py
python .github/scripts/validate_release_notes.py RELEASE_NOTES.md
git diff --check
```

`build_payload.py` 组装 Docker 上下文；不要直接把 `packaging/` 当完整运行目录。候选目录用全新路径，不覆盖已有实例数据。

Linux CI 共用以下阶段：

```bash
python -B .github/scripts/linux_validation.py shell
python -B .github/scripts/linux_validation.py test
python -B .github/scripts/linux_validation.py quality
```

Shell 阶段需要 Bash 和 ShellCheck；真实回环 WebDAV 需要 rclone。Docker、网关／FUSE、Nginx 和 Range 集成有显式开关，按现有 workflow 在隔离资源运行；条件不足必须记录未执行。CI 原生区分 AMD64 / ARM64，不使用 QEMU 冒充原生通过。

性能测量只创建合成数据库，不读取运行实例：

```bash
python -B .github/scripts/benchmark_runtime.py
python -B .github/scripts/benchmark_runtime.py --tasks 100000 --duration-seconds 60 --interval-ms 10
```

合成结果不等于真实吞吐或长期稳定性。网站另在 `website/` 执行 `npm run build` 和 `npm test`，不改品牌或部署框架。

## 运行兼容与代码指纹

程序组装为实例的 `app/tg2cloud/`，外层 `app/` 及必要的 `app.healthcheck`、`app.backup_database` 等薄入口保持兼容。安装目录、容器、网络、`.env`、rclone、Session 和下载路径不随源码整理迁移。

数据库路径使用 `persistence/paths.py`：新装 `data/tg2cloud.db`，已有唯一 `data/tg115.db` 原地使用；双库、链接和无主旁文件拒绝操作。详情见[配置参考](../CONFIGURATION.md)和[备份恢复](../BACKUP-RESTORE.md)，不要为统一名字重建数据库或 Session。

`deployment/fingerprints.py` 的 `tg2cloud-code-v2:sha256:` 递归覆盖受管 Python 源码，按完整相对路径排序；嵌套同名文件、增加、删除和修改均会改变摘要。旧平铺布局只接受对应旧协议，未知无标记的嵌套代码不认作可信旧版。指纹不替代正式源码基线核对。

`deployment/compatibility.py` 静态读取版本和历史布局，不执行下载的旧代码；保留已支持的换行兼容、文件清单、镜像身份与失败回退顺序。存储提交策略分别保留：CloudDrive2 临时对象改名复验，OpenList 预留正式路径直接写入；不承诺两个后端都具有原子 MOVE。

## 发布工具边界

清单、helper A／入口 B、正式 Tag、双架构镜像与实际资产核验按[发布检查清单](RELEASE-CHECKLIST.md)执行。所有远端操作和真实实例变更均需明确授权；本地候选不是线上可安装版本。
