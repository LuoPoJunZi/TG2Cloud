from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

from tg2cloud.cli import terminal
from tg2cloud.cli.presentation import InstallerLog, edition_menu
from tg2cloud.deployment import (
    architecture,
    configuration,
    install,
    instances,
    preflight,
    releases,
    runtime,
)
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import PRODUCTS


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="TG2Cloud 可选 VPS 向导：稳定 Release 安装 / 保留配置升级")
    result.add_argument("--release", help="显式选择已发布正式 vX.Y.Z；默认仍为最新稳定版，不接受 RC")
    result.add_argument("--edition", choices=["clouddrive2", "openlist", "both"], help="both 仅用于两套已有完整实例")
    result.add_argument("--install-dir", help="仅支持单 Edition 的 /opt 下目录；不搬迁现有实例")
    result.add_argument("--check", action="store_true", help="只读实例/版本/HTTPS检查；不收集秘密，不执行安装")
    result.add_argument("--proxy-mode", choices=("managed", "external_docker"), help="显式选择 HTTPS 入口；不隐式迁移已有模式")
    result.add_argument("--nginx-container", help="明确授权复用的外部 Docker Nginx 容器")
    result.add_argument("--authorize-proxy", action="store_true", help="授权修改目标容器专属站点；仍需最终计划确认")
    result.add_argument("--configure-https", action="store_true", help="显式续做/修复 HTTPS；已有域名不切换")
    result.add_argument("--verify", action="store_true", help="另行确认 WebDAV 写入验收；默认不会在升级中运行")
    result.add_argument("--show-credentials", action="store_true", help="仅经确认在私有终端显示已有凭据；不安装、升级或改密")
    return result


def main(argv: list[str] | None = None, *, friendly: bool | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(arguments)
    friendly = (not arguments or bool(args.release) and not args.check) if friendly is None else friendly
    log = InstallerLog(SafeLog(), friendly=friendly)
    ui = None
    try:
        if args.show_credentials and (args.check or args.configure_https or args.verify):
            raise ValueError("--show-credentials 必须单独使用，不能与检查、HTTPS 修复或验收组合")
        if args.show_credentials and not args.edition:
            raise ValueError("查看凭据请显式指定 --edition，不进入安装/升级选择向导")
        preflight.validate_host(log=log)
        if args.install_dir and (not args.edition or args.edition == "both"):
            raise ValueError("--install-dir 必须搭配单个 --edition")
        session = LocalSession(log)
        architecture.check_docker(session, allow_missing=True)
        inventory = instances.docker_inventory(session)
        if not args.edition:
            if args.check:
                raise ValueError("只读检查请显式指定 --edition")
            ui = terminal.Terminal()
            ui.friendly = friendly
            detected = [product for product in PRODUCTS.values()
                        if {product.bot_container, product.storage_container} & inventory]
            for product in detected:
                log("发现 " + product.display_name + " 容器；选择后仍需核对完整性和实际版本")
            default_choice = "2" if len(detected) == 1 and detected[0].is_openlist else "1"
            chosen = edition_menu(ui, log, default=default_choice, both=True)
            args.edition = {"1": "clouddrive2", "2": "openlist", "3": "both"}.get(chosen)
            if not args.edition:
                raise ValueError("Edition 选择无效")
        keys = list(PRODUCTS) if args.edition == "both" else [args.edition]
        selected_instances = [instances.discover(PRODUCTS[key], inventory, session, log, install_dir=args.install_dir) for key in keys]
        if args.edition == "both" and not all(item.present for item in selected_instances):
            raise ValueError("both 只升级两套已有完整实例；首次安装请分别选择 Edition")
        if args.show_credentials:
            if not all(item.present for item in selected_instances):
                raise ValueError("尚无完整实例，不生成凭据、不启动安装")
            if ui is None:
                ui = terminal.Terminal()
            for instance in selected_instances:
                terminal.show_credentials(ui, instance.product, instance.config, log)
            log("TG2CLOUD_CLI_RESULT=NO_CHANGE；凭据查看结束，未修改实例或配置")
            return 0
        client = releases.ReleaseClient()
        bootstrap = Path(os.environ.get("TG2CLOUD_SOURCE_ROOT", Path(__file__).resolve().parents[3])) / ".bootstrap-release.json"
        pinned = json.loads(configuration.regular_private(bootstrap)) if bootstrap.exists() else None
        release = client.resolve(args.release or (pinned["tag"] if pinned else None))
        if pinned and not args.release and release.commit != pinned["commit"]:
            raise ValueError("引导之后 Release Tag 发生变化；停止，重新下载入口")
        log("正式 Release：" + release.tag + "；固定源码 commit：" + release.commit)
        with tempfile.TemporaryDirectory(prefix="tg2cloud-cli-source-") as private:
            root = Path(private)
            source = client.download(release, root)
            baselines = {release.tag: source}
            plans = []
            for instance in selected_instances:
                old_source = None
                if instance.present:
                    tag = "v" + instance.version
                    if tag not in baselines:
                        old_dir = root / ("baseline-" + tag)
                        old_dir.mkdir(mode=0o700)
                        baselines[tag] = releases.download_baseline(client, tag, old_dir, log)
                    old_source = baselines[tag]
                if not args.check and ui is None:
                    ui = terminal.Terminal()
                    ui.friendly = friendly
                extra = {}
                if args.proxy_mode or args.nginx_container or args.authorize_proxy:
                    extra["proxy_options"] = {"proxy_mode": args.proxy_mode, "nginx_container": args.nginx_container,
                                              "authorize_proxy": args.authorize_proxy}
                plan = install.make_plan(instance, release, source, old_source, session, log, ui,
                                         configure_https=args.configure_https, **extra)
                terminal.preview(plan, release, log)
                plans.append((plan, old_source))
            if args.check:
                log("TG2CLOUD_CLI_CHECK=OK；只读预检，不等于部署/WebDAV/公网验收通过")
                return 0
            actionable = [(plan, baseline) for plan, baseline in plans if plan.action in {"install", "upgrade"} or plan.configure_https or args.verify]
            if not actionable:
                if friendly:
                    runtime.check_destination()
                    if ui.confirm("实例无需安装/升级；是否仅安装本地管理命令 tg2cloud？不重启容器"):
                        with runtime.lifecycle_lock():
                            for selected in selected_instances:
                                current = instances.discover(selected.product, instances.docker_inventory(session), session, log, install_dir=str(selected.directory))
                                if not current.present or current.raw_config != selected.raw_config or current.version != selected.version:
                                    raise ValueError("确认期间实例已移除或变化；不重新创建管理命令")
                            runtime.install()
                        log("本地管理命令已安装：tg2cloud")
                log("TG2CLOUD_CLI_RESULT=NO_CHANGE")
                return 0
            if friendly:
                runtime.check_destination()
                log("\n── 执行确认 ──\n将安装本地管理命令 tg2cloud；备份含敏感配置，仅保存在本机。请勿同时运行其他安装器。")
            else:
                log("备份含敏感配置，仅保存在 VPS；失败可能需人工恢复。请勿同时运行其他安装器。")
            if not ui.confirm("确认执行上述所选计划？所选 Bot 可能短暂中断"):
                log("TG2CLOUD_CLI_RESULT=CANCELLED；未执行安装/升级/HTTPS变更")
                return 0
            with runtime.lifecycle_lock() if friendly else nullcontext():
                if friendly:
                    runtime.install()
                    log("本地管理命令已安装：tg2cloud（后续操作失败时可用于检查）")
                for plan, baseline in actionable:
                    install.execute_plan(plan, release, source, baseline, session, log, ui, verify=args.verify)
            log("TG2CLOUD_CLI_RESULT=BASE_HTTPS_OK；WebDAV 是否验收请以独立结果为准")
        return 0
    except KeyboardInterrupt:
        log("TG2CLOUD_CLI_RESULT=INTERRUPTED；请核对安装器回退日志；不假定状态已恢复")
        return 130
    except (ValueError, RuntimeError, TimeoutError, ZoneInfoNotFoundError) as exc:
        log("TG2CLOUD_CLI_RESULT=FAILED：" + str(exc))
        return 1
    except Exception:  # noqa: BLE001 - secret-safe terminal boundary
        # Never dump a traceback containing parsed configuration or raw API data.
        log("TG2CLOUD_CLI_RESULT=FAILED：检查/操作发生异常；未输出配置或凭据，请核对实例状态后重试")
        return 1
    finally:
        if ui is not None:
            ui.close()


def interrupted(_signum: int, _frame) -> None:
    raise KeyboardInterrupt
