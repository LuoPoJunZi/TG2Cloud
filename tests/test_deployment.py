from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from payload_fixture import payload

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
    def test_clouddrive_discovery_ignores_bot_but_detects_other_gateways(self) -> None:
        gateway = "tg2cloud-clouddrive2|cloudnas/clouddrive2:latest|127.0.0.1:19798->19798/tcp"
        bot = "tg2cloud-clouddrive2-bot|tg2cloud-clouddrive2-bot:latest|"
        legacy = "tg115-clouddrive2|cloudnas/clouddrive2:legacy|"
        other_gateway = "other-clouddrive2|cloudnas/clouddrive2:latest|"
        image_matched_gateway = "storage|cloudnas/clouddrive2:latest|"
        cases = (
            ("bot_only", (bot, legacy), ()),
            ("managed_gateway_and_bot", (gateway, bot, legacy), ("tg2cloud-clouddrive2",)),
            ("gateway_detected_by_image", (bot, image_matched_gateway), ("storage",)),
            (
                "multiple_real_gateways",
                (gateway, bot, legacy, other_gateway),
                ("tg2cloud-clouddrive2", "other-clouddrive2"),
            ),
        )
        for script_name in ("remote_install.sh", "repair_clouddrive_network.sh"):
            script = (SOURCE / "packaging/hooks/clouddrive2" / script_name).read_text(
                encoding="utf-8"
            )
            match = re.search(
                r"mapfile -t CD2_MATCHES < <\(\n(.*?)\n\s*\)", script, re.DOTALL
            )
            self.assertIsNotNone(match, script_name)
            discovery = match.group(1)
            harness = (
                'docker() { printf "%s\\n" "$TG2CLOUD_TEST_PS"; }\n'
                'BOT_CONTAINER="tg2cloud-clouddrive2-bot"\n'
                "mapfile -t CD2_MATCHES < <(\n"
                + discovery
                + '\n)\nif ((${#CD2_MATCHES[@]})); then '
                'printf "%s\\n" "${CD2_MATCHES[@]}"; fi\n'
            )
            for scenario, containers, expected in cases:
                with self.subTest(script=script_name, scenario=scenario):
                    result = subprocess.run(
                        [BASH, "-c", harness],
                        env=os.environ | {"TG2CLOUD_TEST_PS": "\n".join(containers)},
                        capture_output=True,
                        timeout=20,
                        check=False,
                        **(
                            {"creationflags": subprocess.CREATE_NO_WINDOW}
                            if os.name == "nt"
                            else {}
                        ),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(tuple(result.stdout.decode().splitlines()), expected)

    def test_clouddrive_diagnostic_logs_redact_secrets(self) -> None:
        script = (SOURCE / "packaging/hooks/clouddrive2/manage.sh").read_text(
            encoding="utf-8"
        )
        function = "redact_runtime_logs() {" + script.split(
            "redact_runtime_logs() {", 1
        )[1].split("\n}\n", 1)[0] + "\n}\n"
        secret_log = (
            "BOT_TOKEN=123456:abcdefghijklmnopqrstuvwxyzABCDE\n"
            "WEBDAV_PASSWORD=plain-secret\n"
            "endpoint=https://alice:private@example.invalid/dav\n"
        )
        result = subprocess.run(
            [BASH, "-c", function + "redact_runtime_logs"],
            input=secret_log.encode(),
            capture_output=True,
            timeout=20,
            check=False,
            **(
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if os.name == "nt"
                else {}
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(b"plain-secret", result.stdout)
        self.assertNotIn(b"abcdefghijklmnopqrstuvwxyzABCDE", result.stdout)
        self.assertNotIn(b"alice:private", result.stdout)
        self.assertIn(b"[REDACTED]", result.stdout)


    def test_redeploy_keeps_existing_config_unless_explicitly_replaced(self) -> None:
        secrets = (
            "BOT_TOKEN_B64=old-token\nALLOWED_USER_ID=123\n"
            "WEBDAV_USERNAME_B64=old-user\nWEBDAV_PASSWORD_B64=old-password\n"
            "WEBDAV_TARGET_PATH_B64=custom/target\n"
            "LOCAL_TEMP_BUDGET_GB=34\nMIN_FREE_DISK_GB=11\n"
            "OPENLIST_ADMIN_PASSWORD=old-admin\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            existing = root / "existing.env"
            candidate = root / "candidate.env"
            existing.write_text(secrets, encoding="utf-8")
            helper = bash_path(
                SOURCE / "packaging/hooks/clouddrive2/preserve_runtime_config.sh"
            )
            for apply_config, expected in (
                (False, secrets),
                (True, "NEW=true\nTG2CLOUD_REDEPLOY_APPLY_CONFIG=true\n"),
            ):
                with self.subTest(apply_config=apply_config):
                    candidate.write_text(
                        "NEW=true\nTG2CLOUD_REDEPLOY_APPLY_CONFIG="
                        + ("true" if apply_config else "false")
                        + "\n",
                        encoding="utf-8",
                    )
                    result = subprocess.run(
                        [
                            BASH,
                            "-c",
                            'source "$1"; tg2cloud_prepare_redeploy_config "$2" "$3"',
                            "--",
                            helper,
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
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(candidate.read_text(encoding="utf-8"), expected)
                    self.assertEqual(existing.read_text(encoding="utf-8"), secrets)
                    self.assertNotIn(b"old-token", result.stdout + result.stderr)
                    self.assertNotIn(b"old-password", result.stdout + result.stderr)
            candidate.write_text(
                "TG2CLOUD_REDEPLOY_APPLY_CONFIG=false\n", encoding="utf-8"
            )
            missing = root / "missing.env"
            result = subprocess.run(
                [
                    BASH,
                    "-c",
                    'source "$1"; tg2cloud_prepare_redeploy_config "$2" "$3"',
                    "--",
                    helper,
                    bash_path(candidate),
                    bash_path(missing),
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
            self.assertNotEqual(result.returncode, 0)

    def test_legacy_directory_and_stopped_container_only_warn(self) -> None:
        for edition, legacy_path in (
            ("clouddrive2", "/opt/tg115"),
            ("openlist", "/opt/tg115-openlist"),
        ):
            with self.subTest(edition=edition), tempfile.TemporaryDirectory() as temp:
                legacy_dir = Path(temp) / "legacy"
                legacy_dir.mkdir()
                script = (SOURCE / f"packaging/hooks/{edition}/remote_install.sh").read_text(
                    encoding="utf-8"
                )
                snippet = script.split(f"[[ ! -e {legacy_path} ]]", 1)[1].split(
                    'if [[ -d "$INSTALL_DIR"', 1
                )[0]
                snippet = f"[[ ! -e {bash_path(legacy_dir)} ]]" + snippet.replace(
                    legacy_path, bash_path(legacy_dir)
                )
                harness = (
                    'log() { printf "%s\\n" "$*"; }; '
                    'fail() { printf "%s\\n" "$*" >&2; exit 3; }; '
                    'docker() { [[ "$1 $2" == "container inspect" ]]; }; '
                    + snippet
                )
                result = subprocess.run(
                    [BASH, "-c", harness],
                    capture_output=True,
                    timeout=20,
                    check=False,
                    **(
                        {"creationflags": subprocess.CREATE_NO_WINDOW}
                        if os.name == "nt"
                        else {}
                    ),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("检测到旧目录".encode(), result.stdout)
                self.assertIn("检测到旧容器".encode(), result.stdout)

    def test_runtime_port_preflight_keeps_stopped_legacy_and_blocks_conflicts(self) -> None:
        for edition, port, legacy in (
            ("clouddrive2", 19798, "tg115-clouddrive2"),
            ("openlist", 5244, "tg115-openlist"),
        ):
            script = (SOURCE / f"packaging/hooks/{edition}/remote_install.sh").read_text(
                encoding="utf-8"
            )
            preflight = "for target_container in " + script.split(
                "for target_container in ", 1
            )[1].split("DOCKER_ROOT_DIR=", 1)[0]
            harness = (
                'INSTALL_DIR="/opt/tg2cloud-' + edition + '"; '
                'BOT_CONTAINER="tg2cloud-' + edition + '-bot"; '
                'OPENLIST_CONTAINER="tg2cloud-openlist"; '
                'log() { :; }; fail() { printf "%s\\n" "$*" >&2; exit 3; }; '
                'ss() { :; }; '
                'docker() { '
                'if [[ "$1 $2" == "container inspect" ]]; then '
                '[[ "${TG2CLOUD_TEST_TARGET_COLLISION:-}" == "$3" ]]; return; fi; '
                'if [[ "$1" == inspect ]]; then printf "%s\\n" /opt/other; return; fi; '
                'if [[ "$1" == ps ]]; then printf "%s\\n" "${TG2CLOUD_TEST_PORT_OWNER:-}"; return; fi; '
                'return 1; }; '
                + preflight
            )
            cases = (
                ("stopped", "", "", True),
                ("running_no_port", f"{legacy}|", "", True),
                ("running_port", f"{legacy}|127.0.0.1:{port}->{port}/tcp", "", False),
                ("foreign_port", f"other|127.0.0.1:{port}->{port}/tcp", "", False),
                ("target_collision", "", f"tg2cloud-{edition}-bot", False),
            )
            for scenario, port_owner, collision, allowed in cases:
                with self.subTest(edition=edition, scenario=scenario):
                    result = subprocess.run(
                        [BASH, "-c", harness],
                        env=os.environ
                        | {
                            "TG2CLOUD_TEST_PORT_OWNER": port_owner,
                            "TG2CLOUD_TEST_TARGET_COLLISION": collision,
                        },
                        capture_output=True,
                        timeout=20,
                        check=False,
                        **(
                            {"creationflags": subprocess.CREATE_NO_WINDOW}
                            if os.name == "nt"
                            else {}
                        ),
                    )
                    self.assertEqual(result.returncode == 0, allowed, result.stderr)

    def test_openlist_port_discovery_does_not_confuse_bot_with_gateway(self) -> None:
        script = (SOURCE / "packaging/hooks/openlist/remote_install.sh").read_text(
            encoding="utf-8"
        )
        preflight = "PORT_5244_OWNER=" + script.split("PORT_5244_OWNER=", 1)[1].split(
            "DOCKER_ROOT_DIR=", 1
        )[0]
        harness = (
            'OPENLIST_CONTAINER="tg2cloud-openlist"\n'
            'docker() { printf "%s\\n" "$TG2CLOUD_TEST_PS"; }\n'
            'ss() { :; }\n'
            'fail() { printf "%s\\n" "$*" >&2; exit 3; }\n'
            + preflight
        )
        cases = (
            ("gateway_and_bot", "tg2cloud-openlist|127.0.0.1:5244->5244/tcp\ntg2cloud-openlist-bot|", True),
            ("bot_without_port", "tg2cloud-openlist-bot|", True),
            ("bot_owns_port", "tg2cloud-openlist-bot|127.0.0.1:5244->5244/tcp", False),
            ("other_owns_port", "other|127.0.0.1:5244->5244/tcp", False),
        )
        for scenario, containers, allowed in cases:
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [BASH, "-c", harness],
                    env=os.environ | {"TG2CLOUD_TEST_PS": containers},
                    capture_output=True,
                    timeout=20,
                    check=False,
                    **(
                        {"creationflags": subprocess.CREATE_NO_WINDOW}
                        if os.name == "nt"
                        else {}
                    ),
                )
                self.assertEqual(result.returncode == 0, allowed, result.stderr)

    def run_openlist_admin_reset(
        self, command_output: str
    ) -> subprocess.CompletedProcess[bytes]:
        command = (
            'realpath() { printf "%s\\n" /opt/tg2cloud-openlist; }; '
            'cd() { :; }; '
            'docker() { printf "%s\\n" "$TG115_TEST_ADMIN_OUTPUT"; }; '
            'export INSTALL_DIR=/opt/tg2cloud-openlist; '
            'source "$1" reset-random I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD'
        )
        return subprocess.run(
            [
                BASH,
                "-c",
                command,
                "--",
                bash_path(SOURCE / "packaging/hooks/openlist/openlist_admin.sh"),
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
                self.assertIn(b"TG2CLOUD_OPENLIST_ADMIN_RESET=OK", result.stdout)
                self.assertIn(
                    b"TG2CLOUD_OPENLIST_ADMIN_PASSWORD=Reset_2345", result.stdout
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
                    bash_path(SOURCE / "packaging/hooks/openlist/preserve_webdav_config.sh"),
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
        self.assertEqual(result.stdout, b"TG2CLOUD_WEBDAV_CONFIG=PRESERVED\n")
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
                bash_path(SOURCE / "packaging/hooks/clouddrive2/backup_retention.sh"),
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
            shutil.copytree(payload("clouddrive2") / "app", root / "app")
            shutil.copyfile(
                SOURCE / "packaging/hooks/clouddrive2/backup_retention.sh",
                root / "backup_retention.sh",
            )
            env = os.environ | {
                "TG115_TEST_DIR": bash_path(root), "TG115_TEST_MODE": mode,
                "TG2CLOUD_TEST_PYTHON": bash_path(Path(sys.executable)),
                "TG115_TEST_SCRIPT": bash_path(
                    SOURCE / "packaging/hooks/clouddrive2/manage.sh"
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

    def test_manage_update_keeps_config_and_data_and_requires_success(self) -> None:
        for edition in ("clouddrive2", "openlist"):
            with self.subTest(edition=edition), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                old_config = (
                    "BOT_TOKEN_B64=token-value\nALLOWED_USER_ID=123\n"
                    "WEBDAV_PASSWORD_B64=password-value\nWEBDAV_TARGET_PATH_B64=custom\n"
                    "LOCAL_TEMP_BUDGET_GB=37\nMIN_FREE_DISK_GB=12\n"
                )
                (root / ".env").write_text(old_config, encoding="utf-8")
                shutil.copytree(payload(edition) / "app", root / "app")
                (root / "data").mkdir()
                (root / "data/tg115.db").write_bytes(b"database-stays")
                (root / "config/rclone").mkdir(parents=True)
                (root / "config/rclone/rclone.conf").write_bytes(b"rclone-stays")
                shutil.copyfile(
                    SOURCE / "packaging/hooks/clouddrive2/backup_retention.sh",
                    root / "backup_retention.sh",
                )
                for mode in ("ok", "invalid"):
                    with self.subTest(mode=mode):
                        calls_file = root / "calls"
                        if calls_file.exists():
                            calls_file.unlink()
                        result = subprocess.run(
                            [BASH, (SOURCE / "tests/manage_harness.sh").as_posix()],
                            env=os.environ
                            | {
                                "TG115_TEST_DIR": bash_path(root),
                                "TG2CLOUD_TEST_PYTHON": bash_path(Path(sys.executable)),
                                "TG115_TEST_MODE": mode,
                                "TG115_TEST_ACTION": "update",
                                "TG115_TEST_SCRIPT": bash_path(
                                    SOURCE / "packaging/hooks" / edition / "manage.sh"
                                ),
                                "TG115_TEST_CANDIDATE": bash_path(root / ".env"),
                            },
                            capture_output=True,
                            timeout=20,
                            check=False,
                            **(
                                {"creationflags": subprocess.CREATE_NO_WINDOW}
                                if os.name == "nt"
                                else {}
                            ),
                        )
                        calls = calls_file.read_text(encoding="utf-8")
                        self.assertEqual(result.returncode == 0, mode == "ok", result.stderr)
                        self.assertEqual(
                            b"TG2CLOUD_UPDATE=OK" in result.stdout, mode == "ok"
                        )
                        self.assertEqual((root / ".env").read_text(encoding="utf-8"), old_config)
                        self.assertEqual((root / "data/tg115.db").read_bytes(), b"database-stays")
                        self.assertEqual(
                            (root / "config/rclone/rclone.conf").read_bytes(),
                            b"rclone-stays",
                        )
                        self.assertIn(f"tg2cloud-{edition}-bot", calls)
                        if mode == "ok":
                            self.assertIn("--expected-code tg2cloud-code-v2:sha256:", calls)
                        self.assertNotIn("tg115-", calls)
                        self.assertNotIn("compose down", calls)


    def test_invalid_config_restores_old_file_without_restarting(self) -> None:
        code, config, calls = self.run_apply("invalid")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertNotIn("compose up", calls)

    def test_unhealthy_new_container_restores_previous_configuration(self) -> None:
        code, config, calls = self.run_apply("unhealthy")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertEqual(
            calls.count("compose up -d --no-deps tg2cloud-clouddrive2-bot"),
            2,
        )

    def test_interrupt_restores_previous_configuration(self) -> None:
        code, config, calls = self.run_apply("interrupt")
        self.assertNotEqual(code, 0)
        self.assertEqual(config, "old")
        self.assertNotIn("compose up", calls)

    def test_valid_config_is_applied_without_restarting_clouddrive(self) -> None:
        code, config, calls = self.run_apply("ok")
        self.assertEqual(code, 0)
        self.assertEqual(config, "new")
        self.assertNotIn("compose up -d clouddrive2", calls)
        self.assertIn("--expected-code tg2cloud-code-v2:sha256:", calls)

    def test_unsafe_install_path_is_rejected_before_commands(self) -> None:
        result = subprocess.run(
            [
                BASH,
                (SOURCE / "packaging/hooks/clouddrive2/manage.sh").as_posix(),
                "status",
            ],
            env=os.environ | {"INSTALL_DIR": "/opt/tg2cloud;false"},
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
    def test_linux_ci_runs_runtime_tests_without_desktop_dependencies(self) -> None:
        workflow = (SOURCE / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        linux_job = workflow.split("  linux-products:", 1)[1]
        self.assertIn(".github/scripts/check_python.py test", linux_job)
        self.assertNotIn("requirements-build.txt", linux_job)


    def test_backup_failure_is_fatal_before_program_replacement(self) -> None:
        script = (SOURCE / "packaging/hooks/clouddrive2/remote_install.sh").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            script.index('tar -tzf "$BACKUP"'),
            script.index('log "提交已预检的程序和配置"'),
        )
        self.assertIn('. || fail "配置备份失败', script)

    def test_upgrade_is_preflighted_and_has_database_rollback(self) -> None:
        script = (SOURCE / "packaging/hooks/clouddrive2/remote_install.sh").read_text(
            encoding="utf-8"
        )
        commit = script.index('log "提交已预检的程序和配置"')
        self.assertLess(script.index("-m app.deployment_check --validate-only"), commit)
        self.assertIn("-m app.backup_database", script)
        self.assertIn('install -m 600 "$DATABASE_BACKUP" "$ROLLBACK_DATABASE"', script)
        self.assertIn('validate_database_backup "$ROLLBACK_DATABASE"', script)
        self.assertIn('mv -f -- "$ROLLBACK_DATABASE" "$INSTALL_DIR/data/tg115.db"', script)
        self.assertIn("docker tag \"$OLD_IMAGE_ID\" \"$OLD_IMAGE_TAG\"", script)
        self.assertIn("已自动恢复升级前版本", script)
        self.assertIn("INT TERM HUP", script)
        self.assertIn('tg115_backup_inventory "$BACKUP_DIR"', script)
        self.assertNotIn('tg115_prune_backups "$BACKUP_DIR"', script)

    def test_docker_filesystem_is_rechecked_after_docker_start(self) -> None:
        script = (SOURCE / "packaging/hooks/clouddrive2/remote_install.sh").read_text(
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
                (SOURCE / "packaging/hooks/clouddrive2" / name).read_text(
                    encoding="utf-8"
                ),
            )


if __name__ == "__main__":
    unittest.main()
