"""Shared local/CI checks; never build, deploy, or install dependencies."""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI_TESTS = (
    "test_compose.py",
    "test_architecture.py",
    "test_vps_installer.py", "test_lan_installer.py", "test_uninstaller.py",
    "test_proxy_host_compat.py", "test_repository.py", "test_storage_wizard.py", "test_source_release.py", "test_layout_contracts.py",
    "test_feature.py", "test_http.py", "test_scope.py", "test_management.py", "test_family_management.py", "test_users.py", "test_external_proxy.py",
    "test_upgrade_baselines.py", "test_instance_backup.py", "test_readiness.py", "test_naming_preview.py",
    "test_host_bundle.py", "test_feature_settings.py", "test_install_feedback.py",
    "test_notifications.py", "test_diagnostic_report.py", "test_classification.py", "test_member_quotas.py",
    "test_progress_metrics.py",
    "test_restore_rehearsal.py",
    "test_management_pages.py",
    "test_release_preparation.py",
    "test_proxy_rendering.py",
    "test_proxy_certbot_startup.py",
    "test_webdav_entry.py",
    "test_listening_host.py", "test_webdav_upgrade.py", "test_listening_login.py",
)
CLI_PATHS = (
    "src/tg2cloud/compose", ".github/scripts/compose_release.py",
    "src/tg2cloud/cli", "src/tg2cloud/deployment", "src/tg2cloud/addons", "src/tg2cloud/__init__.py",
    "src/tg2cloud/version.py", "src/tg2cloud/config.py", "scripts",
    ".github/scripts/check_python.py", ".github/scripts/check_repository.py",
    ".github/scripts/source_release.py",
    ".github/scripts/baseline_metadata.py", "src/tg2cloud/domain/naming.py",
    ".github/scripts/maintenance_preflight.py", "src/tg2cloud/persistence/rehearsal.py",
    ".github/scripts/prepare_release.py", ".github/scripts/linux_validation.py",
    "src/tg2cloud/persistence/backup.py", "src/tg2cloud/persistence/bundle.py", "src/tg2cloud/monitoring/readiness.py",
    "src/tg2cloud/monitoring/progress.py",
    *(f"tests/{name}" for name in CLI_TESTS if name not in {"test_feature.py", "test_http.py", "test_scope.py", "test_users.py", "test_naming_preview.py"}),
    "tests/naming/test_naming_preview.py",
    "tests/addons",
    "tests/test_lan_gateway_docker.py",
)


def source_paths(scope: str) -> tuple[str, ...]:
    if scope == "cli":
        return CLI_PATHS
    return (
        *(path.name for path in sorted(ROOT.glob("*.py"))),
        ".github/scripts", "src", "packaging/compat", "scripts", "tests",
    )


def commands(task: str, scope: str) -> list[list[str]]:
    tasks = ("repository", "test", "lint", "compile") if task == "all" else (task,)
    result: list[list[str]] = []
    for selected in tasks:
        if selected == "repository":
            result.append([sys.executable, "-B", ".github/scripts/check_repository.py"])
        elif selected == "test":
            patterns = CLI_TESTS if scope == "cli" else ("test*.py",)
            result.extend(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]
                for pattern in patterns
            )
        elif selected == "lint":
            paths = CLI_PATHS if scope == "cli" else (".",)
            result.append([sys.executable, "-m", "ruff", "check", *paths])
        elif selected == "compile":
            # Keep development bytecode out of the payload/PyInstaller inputs.
            result.append([
                sys.executable, "-X", f"pycache_prefix={ROOT / 'build/check-pycache'}",
                "-m", "compileall", "-q", *source_paths(scope),
            ])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("all", "repository", "test", "lint", "compile"))
    parser.add_argument("--scope", choices=("all", "cli"), default="all")
    args = parser.parse_args(argv)
    for command in commands(args.task, args.scope):
        print("+ " + " ".join(command), flush=True)
        # Commands use the current Python, fixed module names and validated choices;
        # no user-provided command text is executed by a shell.
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(command, cwd=ROOT, check=False, shell=False, env=environment)  # nosec B603
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
