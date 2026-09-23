# 开发与贡献

这里介绍 TG2Cloud 主项目的开发入口。本文档网站本身的维护方法见 [文档来源与维护](/reference/sources/)。

## 获取主项目源码

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
git checkout v1.0.3
```

对固定版本复现问题时使用对应标签；跟随主分支开发时，记录提交号，避免把未发布修改当成 Release 行为。

## 关键目录与入口

| 路径 | 用途 |
| --- | --- |
| `installer.py` | 共享部署器界面与逻辑 |
| `installer_clouddrive2.py` | CloudDrive2 产品入口 |
| `installer_openlist.py` | OpenList 产品入口 |
| `deployer_products.py` | 两版产品名、版本、路径和资源定义 |
| `payload_clouddrive2/` | CloudDrive2 部署脚本与共享核心文件来源 |
| `payload_openlist/` | OpenList 部署脚本 |
| `tests/` | 自动化回归 |
| `build.ps1` | Windows 打包与自检 |

## 执行自动测试

按仓库 CONTRIBUTING 的命令：

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

真实本地 WebDAV 集成测试需要 `rclone` 在 PATH 中；Shell 回归需要 Bash。缺少依赖时的跳过不能写成“所有集成测试均通过”。

仓库说明中 Linux CI 使用 Python 3.12，Windows 使用 Python 3.13；具体以当前 CI 配置为准。

## 构建两个部署器

```powershell
.\build.ps1 -Edition All
```

公共行为和版本号变更应同时检查两个产品入口及产品定义。不要只构建一个 Edition，就认为另一个必然不受影响。

## 提交规范

不提交账号、Token、密码、Cookie、私钥、用户 ID、服务器地址、下载文件、日志、数据库、缓存或本地配置。

涉及安装脚本、远程命令、路径处理时，补充异常输入与恶意输入测试。变更传输策略时，同时保护 CloudDrive2 与 OpenList 的不同落盘语义。

不要把 WebDAV 接收成功改写成云盘官方最终完成，也不要把模拟测试当作真实 VPS 端到端验收。

## 截图与文档

只提交实际界面的脱敏截图，注明版本与 Edition。本次文档首页展示的是 HTML/CSS 流程示意，不是伪造的部署器运行截图。
