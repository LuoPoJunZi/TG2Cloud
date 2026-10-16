# 冻结的 Windows 部署器源码

Windows EXE 最后发布版本为 **v1.2.1**。此目录集中保留原 PySide6 界面、两个产品入口、Windows 构建脚本、固定依赖、版本资源及旧构建输入检测器，供兼容回归和历史恢复使用；当前 CI／Release 不构建新 EXE。

当前 main 已将文件从仓库根目录归档到这里，GitHub 首页主要保留 Linux 一键入口和共享运行代码。归档只调整 Python 导入和资源定位；没有重写界面、SSH、Tunnel 或部署流程。共享的 `deployer_products.py`、`domain_proxy.py`、`proxy_maintenance.py`、`vps_resources.py` 仍在根目录，Linux 向导继续依赖它们。

## 恢复正式 v1.2.1 桌面版

从新的空目录获取 [v1.2.1 Tag](https://github.com/LuoPoJunZi/TG2Cloud/tree/v1.2.1)，或解压事先保存的完整桌面源码备份并核对清单。该版本仍使用原根目录布局和 `build.ps1`。不要把旧源码直接覆盖较新工作树，也不要用旧 EXE 覆盖已升级实例。

当前归档的构建脚本仍拒绝将较新 Bot 版本打包成 Windows 产品。恢复历史产品应使用完整旧版源码，不只复制几个 UI 文件。

## 当前兼容检查

在仓库根目录安装本目录的 `requirements-build.txt` 与 `payload_clouddrive2/requirements.txt` 后，运行统一回归检查，或只执行不联网的依赖检查：

```bash
python -m legacy.desktop.installer --check-deps
python .github/scripts/check_python.py all
```

品牌唯一正式来源仍为根目录 `assets/brand/`；不在归档目录复制另一套 Logo。数据库、Telegram Session、真实配置和 EXE 不属于本目录。
