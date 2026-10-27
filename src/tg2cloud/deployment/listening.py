"""Host entry is stdlib-only; login runs inside the verified existing Bot container."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404
from contextlib import ExitStack


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="可选监听账号终端授权；不重启 Bot 或网关"
    )
    parser.add_argument("action", choices=("login", "status", "disable"))
    parser.add_argument("--edition", required=True, choices=("clouddrive2", "openlist"))
    parser.add_argument("--install-dir")
    args = parser.parse_args(argv)
    from pathlib import Path

    from tg2cloud.deployment import instances, preflight, runtime
    from tg2cloud.deployment.host import LocalSession, SafeLog, edition_lock
    from tg2cloud.deployment.profiles import PRODUCTS

    log = SafeLog()
    stage = "Linux 与 Docker 环境检查"
    try:
        preflight.validate_host()
        # Do not let root's docker CLI context silently target another host.
        from tg2cloud.deployment.architecture import check_environment

        check_environment()
        root = Path(__file__).resolve().parents[3]
        stage = "本地管理工具完整性检查"
        if (root / "installation.json").exists():
            runtime.verify(root)
        docker = shutil.which("docker")
        if not docker:
            raise ValueError("Docker 不可用")
        product = PRODUCTS[args.edition]
        session = LocalSession(log)
        from tg2cloud.deployment.architecture import check_docker

        stage = "本机 Docker 检查"
        check_docker(session)
        stage = "实例身份与运行版本检查"
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (product.key + ".lock")):
            item = instances.discover(
                product,
                instances.docker_inventory(session),
                session,
                log,
                install_dir=args.install_dir,
            )
            if not item.present or not item.running:
                raise ValueError("请先安装并启动所选 Edition")
            command = [
                docker,
                "exec",
                *(["-it"] if args.action == "login" else []),
                product.bot_container,
                "python",
                "-B",
                "-m",
                "tg2cloud.listening.account",
                args.action,
            ]
            stage = "个人监听账号操作"
            with ExitStack() as stack:
                options = {}
                if args.action == "login" and (not os.isatty(0) or not os.isatty(1)):
                    stage = "交互终端检查；请从自己的 SSH 终端运行 tg2cloud"
                    # Online Bash launches the wizard asynchronously, so stdin may
                    # be /dev/null even though Terminal's /dev/tty menu works.
                    tty = stack.enter_context(open("/dev/tty", "r+b", buffering=0))
                    if not os.isatty(tty.fileno()):
                        raise ValueError("无法取得控制终端")
                    options = {"stdin": tty, "stdout": tty, "stderr": tty}
                # Inherit/reopen only the private terminal, never capture secrets.
                return subprocess.run(command, check=False, **options).returncode  # nosec B603
    except (ValueError, RuntimeError, OSError):
        log("监听操作未完成：" + stage + "未通过；未显示凭据或内部异常。")
        return 1


def manage(manager, instance):
    """The selected Edition's terminal menu reuses the verified CLI operations."""
    from tg2cloud.cli.management import choose
    from tg2cloud.cli.presentation import numbered_menu

    actions = {"1": "login", "2": "status", "3": "disable"}
    while True:
        instance = manager.recheck(instance)
        manager.heading("监听管理", instance)
        manager.log("登录只保存个人账号授权；在 Bot 监听管理中启用。停用保留来源、任务和 Session。")
        manager.log(numbered_menu(((1, "登录监听账号"), (2, "查看监听状态"),
                                   (3, "停用监听功能"), (0, "返回主菜单"))))
        selected = choose(manager.ui, "选择操作", ("0", *actions), "0")
        if selected == "0":
            return
        result = main([actions[selected], "--edition", instance.product.key,
                       "--install-dir", str(instance.directory)])
        if result:
            manager.log("监听操作未完成，请核对上方结果。")
        manager.log(numbered_menu(((0, "返回监听管理"),)))
        choose(manager.ui, "选择操作", ("0",), "0")


if __name__ == "__main__":
    raise SystemExit(main())
