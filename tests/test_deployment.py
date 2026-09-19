from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
git = shutil.which("git")
git_bash = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
BASH = os.getenv("TG115_TEST_BASH") or (
    str(git_bash) if os.name == "nt" and git_bash and git_bash.is_file()
    else shutil.which("bash") if os.name != "nt" else None
)


def bash_path(path: Path) -> str:
    value = path.as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


@unittest.skipUnless(BASH, "需要 Bash；Linux CI 必须运行脚本故障测试")
class DeploymentShellTests(unittest.TestCase):
    def run_openlist_admin_reset(
        self, command_output: str
    ) -> subprocess.CompletedProcess[bytes]:
        command = (
            'realpath() { printf "%s\\n" /opt/tg115-openlist; }; '
            'cd() { :; }; '
            'docker() { printf "%s\\n" "$TG115_TEST_ADMIN_OUTPUT"; }; '
            'export INSTALL_DIR=/opt/tg115-openlist; '
            'source "$1" reset-random I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD'
        )
        return subprocess.run(
            [
                BASH,
                "-c",
                command,
                "--",
                bash_path(SOURCE / "payload_openlist/openlist_admin.sh"),
            ],
            env=os.environ | {"TG115_TEST_ADMIN_OUTPUT": command_output},
            capture_output=True,
            timeout=20,
            check=False,
            **(
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if os.name == "nt"
                else {}
            ),
        )

    def test_openlist_admin_reset_parses_plain_and_prefixed_output(self) -> None:
        for command_output in (
            "admin user has been updated:\nusername: admin\npassword: Reset_2345",
            """INFO[2026-09-18] username: admin
INFO[2026-09-18] password: Reset_2345""",
        ):
            with self.subTest(command_output=command_output):
                result = self.run_openlist_admin_reset(command_output)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertIn(b"TG115_OPENLIST_ADMIN_RESET=OK", result.stdout)
                self.assertIn(
                    b"TG115_OPENLIST_ADMIN_PASSWORD=Reset_2345", result.stdout
                )

    def test_openlist_upgrade_preserves_existing_webdav_without_logging_secrets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate.env"
            existing = root / "existing.env"
            candidate.write_text(
                "WEBDAV_URL_B64=new-url\n"
                "CD2_WEBDAV_URL_B64=new-url\n"
                "WEBDAV_USERNAME_B64=new-user\n"
                "CD2_WEBDAV_USERNAME_B64=new-user\n"
                "WEBDAV_PASSWORD_B64=new-password\n"
                "CD2_WEBDAV_PASSWORD_B64=new-password\n"
                "WEBDAV_TARGET_PATH_B64=new-target\n"
                "CD2_TARGET_PATH_B64=new-target\n"
                "OPENLIST_ADMIN_PASSWORD=new-admin\n"
                "TG115_PRESERVE_WEBDAV=true\n",
                encoding="utf-8",
            )
            existing.write_text(
                "CD2_WEBDAV_URL_B64=old-url\n"
                "CD2_WEBDAV_USERNAME_B64=old-user\n"
                "CD2_WEBDAV_PASSWORD_B64=old-password\n"
                "CD2_TARGET_PATH_B64=old-target\n"
                "OPENLIST_ADMIN_PASSWORD=old-admin\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    BASH,
                    "-c",
                    'source "$1"; tg115_preserve_existing_webdav_config "$2" "$3"',
                    "--",
                    bash_path(SOURCE / "payload_openlist/preserve_webdav_config.sh"),
                    bash_path(candidate),
                    bash_path(existing),
                ],
                capture_output=True,
                timeout=20,
                check=False,
                **(
                    {"creationflags": subprocess.CREATE_NO_WINDOW}
                    if os.name == "nt"
                    else {}
                ),
            )
            merged = candidate.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"TG115_WEBDAV_CONFIG=PRESERVED\n")
        self.assertNotIn(b"old-password", result.stdout + result.stderr)
        self.assertIn("WEBDAV_PASSWORD_B64=old-password", merged)
        self.assertIn("CD2_WEBDAV_PASSWORD_B64=old-password", merged)
        self.assertIn("OPENLIST_ADMIN_PASSWORD=old-admin", merged)
        self.assertNotIn("new-password", merged)

    def run_backup_action(
        self, root: Path, action: str, keep: str = "2"
    ) -> subprocess.CompletedProcess[bytes]:
        command = (
            'source "$1"; '
            'backup_dir="$(cd "$2" && pwd -P)" || exit 1; '
            'if [[ "$3" == inventory ]]; then '
            'tg115_backup_inventory "$backup_dir"; '
            'else tg115_prune_backups "$backup_dir" "$4"; fi'
        )
        return subprocess.run(
            [
                BASH,
                "-c",
                command,
                "--",
                bash_path(SOURCE / "payload_clouddrive2/backup_retention.sh"),
                bash_path(root),
                action,
                keep,
            ],
            capture_output=True,
            timeout=20,
            check=False,
            **(
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if os.name == "nt"
                else {}
            ),
        )

    def run_apply(self, mode: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env").write_text("old", encoding="utf-8")
            candidate = root / "candidate.env"
            candidate.write_text("new", encoding="utf-8")
            (root / "app").mkdir()
            (root / "app" / "placeholder.py").write_text("# test fixture\n", encoding="utf-8")
            shutil.copyfile(
                SOURCE / "payload_clouddrive2/backup_retention.sh",
                root / "backup_retention.sh",
            )
            env = os.environ | {
                "TG115_TEST_DIR": bash_path(root), "TG115_TEST_MODE": mode,
                "TG115_TEST_SCRIPT": bash_path(
                    SOURCE / "payload_clouddrive2/manage.sh"
                ),
                "TG115_TEST_CANDIDATE": bash_path(candidate),
            }
            result = subprocess.run(
                [BASH, (SOURCE / "tests/manage_harness.sh").as_posix()],
                env=env, capture_output=True, timeout=20, check=False,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
            )
            calls = (root / "calls").read_text(encoding="utf-8")
            return result.returncode, (root / ".env").read_text(encoding="utf-8"), calls

    def test_invalid_config_restores_old_file_without_restarting(self) -> None:
        code, config, calls = self.run_apply("invalid")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertNotIn("compose up", calls)

    def test_unhealthy_new_container_restores_previous_configuration(self) -> None:
        code, config, calls = self.run_apply("unhealthy")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertEqual(calls.count("compose up -d --no-deps tg115-bot"), 2)

    def test_interrupt_restores_previous_configuration(self) -> None:
        code, config, calls = self.run_apply("interrupt")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertNotIn("compose up", calls)

    def test_valid_config_is_applied_without_restarting_clouddrive(self) -> None:
        code, config, calls = self.run_apply("ok")
        self.assertEqual(code, 0)
        self.assertEqual(config, "new")
        self.assertNotIn("clouddrive2", calls)
        self.assertIn("--expected-code", calls)

    def test_unsafe_install_path_is_rejected_before_commands(self) -> None:
        result = subprocess.run(
            [
                BASH,
                (SOURCE / "payload_clouddrive2/manage.sh").as_posix(),
                "status",
            ],
            env=os.environ | {"INSTALL_DIR": "/opt/tg115;false"},
            capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 2)

    def test_backup_inventory_and_retention_keep_newest_per_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expected: set[str] = {"notes.txt"}
            (root / "notes.txt").write_text("unrelated", encoding="utf-8")
            for prefix, suffix in (
                ("config", ".tar.gz"),
                ("database", ".db"),
                ("env", ".env"),
            ):
                for index in range(4):
                    path = root / f"{prefix}-{index:02d}{suffix}"
                    path.write_bytes(bytes([index + 1]) * (index + 1))
                    os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
                    if index >= 2:
                        expected.add(path.name)
            inventory = self.run_backup_action(root, "inventory")
            self.assertEqual(inventory.returncode, 0, inventory.stderr.decode())
            self.assertIn(b"TOTAL_COUNT=12", inventory.stdout)
            pruned = self.run_backup_action(root, "prune", "2")
            self.assertEqual(pruned.returncode, 0, pruned.stderr.decode())
            self.assertIn(b"DELETED_TOTAL=6", pruned.stdout)
            self.assertEqual({path.name for path in root.iterdir()}, expected)

    def test_backup_retention_rejects_invalid_keep_without_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            backup = root / "database-00.db"
            backup.write_bytes(b"database")
            result = self.run_backup_action(root, "prune", "0")
            self.assertEqual(result.returncode, 2)
            self.assertTrue(backup.is_file())
            self.assertIn("1 到 50", result.stderr.decode("utf-8"))


class DeploymentStructureTests(unittest.TestCase):
    def test_linux_ci_runs_qt_tests_with_offscreen_platform(self) -> None:
        workflow = (SOURCE / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        linux_job = workflow.split("  linux-products:", 1)[1]
        self.assertIn("QT_QPA_PLATFORM: offscreen", linux_job)

    def test_windows_build_isolates_dll_dependency_search_path(self) -> None:
        script = (SOURCE / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-Tg115IsolatedPath", script)
        self.assertIn('"$env:SystemRoot\\System32"', script)
        self.assertIn("$env:Path = Get-Tg115IsolatedPath", script)
        self.assertIn("$env:Path = $originalPath", script)

    def test_windows_build_supports_only_two_pyside_products(self) -> None:
        script = (SOURCE / "build.ps1").read_text(encoding="utf-8")
        self.assertFalse((SOURCE / "installer_classic.py").exists())
        self.assertFalse((SOURCE / "payload").exists())
        self.assertTrue((SOURCE / "payload_clouddrive2").is_dir())
        self.assertTrue((SOURCE / "payload_openlist").is_dir())
        self.assertFalse((SOURCE / "一键部署-Telegram到115.cmd").exists())
        self.assertFalse(
            (SOURCE / "一键部署-Telegram到115-OpenList.cmd").exists()
        )
        self.assertIn("[ValidateSet('All', 'CloudDrive2', 'OpenList')]", script)
        self.assertIn("TG115-CloudDrive2-Deployer", script)
        self.assertIn("TG115-OpenList-Deployer", script)
        self.assertIn("installer_clouddrive2.py", script)
        self.assertIn("installer_openlist.py", script)
        self.assertIn("payload_clouddrive2;payload_clouddrive2", script)
        self.assertNotIn("Source = 'installer_classic.py'", script)
        self.assertNotIn("import tkinter", script)
        self.assertIn("payload_openlist;payload_openlist", script)
        for stale_name in (
            "TG115-Deployer.exe",
            "TG115-Deployer-Modern.exe",
            "TG115-Deployer-Classic.exe",
        ):
            self.assertIn(stale_name, script)

        workflow = (SOURCE / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "$env:TG115_BUILD_PYTHON = (Get-Command python -ErrorAction Stop).Source",
            workflow,
        )
        self.assertIn("timeout-minutes: 20", workflow)
        self.assertIn("WaitForExit(120000)", workflow)
        self.assertNotIn('foreach ($edition in @("Modern", "Classic"))', workflow)

    def test_windows_deploy_reprobes_resources_before_remote_mutation(self) -> None:
        source = (SOURCE / "installer.py").read_text(encoding="utf-8")
        deploy = source.split("        def deploy(self, values:", 1)[1].split(
            "        def open_clouddrive(self, values:", 1
        )[0]
        self.assertLess(
            deploy.index("_probe_and_recommend"), deploy.index("mkdir -m 700")
        )
        self.assertIn("assess_storage_choice", deploy)

    def test_backup_failure_is_fatal_before_program_replacement(self) -> None:
        script = (SOURCE / "payload_clouddrive2/remote_install.sh").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            script.index('tar -tzf "$BACKUP"'),
            script.index('log "提交已预检的程序和配置"'),
        )
        self.assertIn('. || fail "配置备份失败', script)

    def test_upgrade_is_preflighted_and_has_database_rollback(self) -> None:
        script = (SOURCE / "payload_clouddrive2/remote_install.sh").read_text(
            encoding="utf-8"
        )
        commit = script.index('log "提交已预检的程序和配置"')
        self.assertLess(script.index("-m app.deployment_check --validate-only"), commit)
        self.assertIn("-m app.backup_database", script)
        self.assertIn('install -m 600 "$DATABASE_BACKUP" "$INSTALL_DIR/data/tg115.db"', script)
        self.assertIn("docker tag \"$OLD_IMAGE_ID\" \"$OLD_IMAGE_TAG\"", script)
        self.assertIn("已自动恢复升级前版本", script)
        self.assertIn("INT TERM HUP", script)
        self.assertIn("tg115_backup_inventory /opt/tg115-backups", script)
        self.assertNotIn("tg115_prune_backups /opt/tg115-backups", script)

    def test_docker_filesystem_is_rechecked_after_docker_start(self) -> None:
        script = (SOURCE / "payload_clouddrive2/remote_install.sh").read_text(
            encoding="utf-8"
        )
        docker_ready = script.index("docker compose version >/dev/null 2>&1 || fail")
        storage_check = script.index("DOCKER_ROOT_DIR=", docker_ready)
        candidate_build = script.index('docker build --tag "$CANDIDATE_TAG"')
        self.assertLess(docker_ready, storage_check)
        self.assertLess(storage_check, candidate_build)
        self.assertIn("Docker 数据文件系统空间不足", script)

    def test_configuration_is_not_executed_as_shell(self) -> None:
        for name in ("remote_install.sh", "repair_clouddrive_network.sh"):
            self.assertNotIn(
                'source "$INSTALL_DIR/.env"',
                (SOURCE / "payload_clouddrive2" / name).read_text(
                    encoding="utf-8"
                ),
            )


if __name__ == "__main__":
    unittest.main()
