"""Execute OpenList backup/rollback code with isolated data and fake Docker.

Subprocess is used only to execute the repository's Bash code against fixtures.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess  # nosec B404
import sys
import tarfile
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from test_deployment import BASH, bash_path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = (ROOT / "payload_openlist/remote_install.sh").read_text(encoding="utf-8")
MANAGE_SCRIPT = (ROOT / "payload_openlist/manage.sh").read_text(encoding="utf-8")
PREFIX = INSTALL_SCRIPT.split('[[ "$(id -u)" -eq 0 ]]', 1)[0]
UPGRADE = 'if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then\n  BACKUP=' + INSTALL_SCRIPT.split(
    'if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then\n  BACKUP=', 1,
)[1].split('\nlog "提交已预检的程序和配置"', 1)[0]
MANUAL = "create_backup() (" + MANAGE_SCRIPT.split("create_backup() (", 1)[1].split(
    "\napply_config() {", 1,
)[0]
DIGEST = re.search(
    r"(?m)^    image: (.+)$", (ROOT / "payload_openlist/docker-compose.yml").read_text(encoding="utf-8"),
).group(1)

HARNESS = r'''
test_root="$(builtin cd "$1" && pwd -P)"
INSTALL_DIR="$test_root/installation"
BACKUP_DIR="$test_root/backups"
BACKUP="$test_root/config.tar.gz"
OLD_BOT_IMAGE_ID=old-bot
OLD_BOT_IMAGE_TAG=old-bot:latest
OLD_OPENLIST_IMAGE_ID=old-gateway
OLD_OPENLIST_IMAGE_TAG="$TG2CLOUD_TEST_DIGEST"
ROLLBACK_ARMED=true
DATABASE_BACKUP=""

# All Docker operations are simulated. SQLite and tar use real implementations.
python3() { "$TG2CLOUD_TEST_PYTHON" "$@"; }
chown() { :; }
wait_openlist_http() { :; }
wait_openlist() { :; }
wait_container_healthy() { :; }
wait_healthy() { :; }
docker() {
  printf '%s\n' "$*" >> "$test_root/calls"
  case "$1" in
    image)
      [[ "$TG2CLOUD_TEST_MODE" != missing-image ]] || return 1
      if [[ "$TG2CLOUD_TEST_MODE" == wrong-image ]]; then printf 'different-image\n';
      else printf 'old-gateway\n'; fi
      ;;
    tag)
      [[ "$3" != *@sha256:* ]] || return 1
      ;;
    inspect)
      if [[ "$3" == *'.Config.Image'* ]]; then
        if [[ "${@: -1}" == "$BOT_CONTAINER" ]]; then printf '%s\n' "$OLD_BOT_IMAGE_TAG";
        else printf '%s\n' "$OLD_OPENLIST_IMAGE_TAG"; fi
      elif [[ "$3" == *'.State.Running'* ]]; then printf 'true\n';
      elif [[ "$3" == *'.Image'* ]]; then
        if [[ "${@: -1}" == "$BOT_CONTAINER" ]]; then printf 'old-bot\n';
        else printf 'old-gateway\n'; fi
      else printf 'healthy\n'; fi
      ;;
    stop)
      if [[ "${@: -1}" == "$OPENLIST_CONTAINER" ]]; then touch "$test_root/gateway-stopped"; fi
      ;;
    start) rm -f -- "$test_root/gateway-stopped" ;;
    compose)
      if [[ "$2" == rm && "$TG2CLOUD_TEST_MODE" == cannot-stop-bot ]]; then return 1; fi
      if [[ "$2" == stop ]]; then touch "$test_root/gateway-stopped"; fi
      if [[ "$2" == up ]]; then rm -f -- "$test_root/gateway-stopped"; fi
      ;;
  esac
  if [[ "$*" == *'app.backup_database'* ]]; then
    # Use the existing production SQLite snapshot helper for a real fixture DB.
    python3 - "$TG2CLOUD_TEST_PAYLOAD" "$INSTALL_DIR/data/tg115.db" "$INSTALL_DIR${@: -1}" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from app.backup_database import backup_database
backup_database(Path(sys.argv[2]), Path(sys.argv[3]))
PY
  fi
  return 0
}
install() {
  local target="${@: -1}"
  # Git Bash cannot apply POSIX directory ownership/modes to Windows fixtures.
  if [[ "$1" == -d && "$TG2CLOUD_TEST_WINDOWS" == 1 ]]; then return 0; fi
  if { [[ "$target" == "$BACKUP_DIR"/database-*.db && "$TG2CLOUD_TEST_MODE" == backup-copy-* ]]; } \
    || { [[ "$target" == "$INSTALL_DIR"/data/.rollback-*.db && "$TG2CLOUD_TEST_MODE" == restore-copy-fail ]]; }; then
    python3 - "$target" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(b"interrupted copy fixture")
PY
    case "$TG2CLOUD_TEST_MODE" in
      backup-copy-interrupt) kill -TERM "$$" ;;
      backup-copy-corrupt) return 0 ;;
      *) return 1 ;;
    esac
  fi
  command install "$@"
}
tar() {
  if [[ "$*" == *'openlist/data'* ]]; then
    [[ -f "$test_root/gateway-stopped" ]] || return 7
    if [[ "$TG2CLOUD_TEST_MODE" == archive-fail ]]; then return 1; fi
  fi
  command tar "$@"
}
'''


@unittest.skipUnless(BASH, "Requires Bash; Linux CI runs the fault regressions")
class OpenListBackupTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory(prefix="tg2cloud-openlist-test-")
        self.addCleanup(self.private.cleanup)
        self.root = Path(self.private.name)
        self.installation = self.root / "installation"
        (self.installation / "data").mkdir(parents=True)
        (self.root / "backups").mkdir()
        self.database = self.installation / "data/tg115.db"
        self.snapshot = self.root / "good.db"
        self.make_database(self.database, 1)
        self.make_database(self.snapshot, 2)
        (self.installation / "docker-compose.yml").write_text("# fixture\n", encoding="utf-8")
        (self.installation / ".env").write_text("# private fixture\n", encoding="utf-8")
        with tarfile.open(self.root / "config.tar.gz", "w:gz") as archive:
            for name in ("docker-compose.yml", ".env"):
                archive.add(self.installation / name, arcname=name)

    @staticmethod
    def make_database(path, value):
        with closing(sqlite3.connect(path)) as database:
            database.execute("CREATE TABLE fixture(value INTEGER)")
            database.execute("INSERT INTO fixture VALUES (?)", (value,))
            database.commit()

    def execute(self, action, mode="ok", before=""):
        # Only repository shell code and fixed test scenarios, never user input.
        result = subprocess.run(  # nosec B603
            [BASH, "-s", "--", bash_path(self.root)],
            input=PREFIX + HARNESS + before + action,
            env=os.environ | {
                "TG2CLOUD_TEST_PYTHON": bash_path(Path(sys.executable)),
                "TG2CLOUD_TEST_PAYLOAD": bash_path(ROOT / "payload_clouddrive2"),
                "TG2CLOUD_TEST_DIGEST": DIGEST,
                "TG2CLOUD_TEST_MODE": mode,
                "TG2CLOUD_TEST_WINDOWS": "1" if os.name == "nt" else "0",
                "PYTHONIOENCODING": "utf-8",
            },
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        calls = self.root / "calls"
        return result, calls.read_text(encoding="utf-8") if calls.exists() else ""

    def assert_database(self, path, value):
        with closing(sqlite3.connect(path)) as database:
            self.assertEqual(database.execute("PRAGMA quick_check").fetchall(), [("ok",)])
            self.assertEqual(database.execute("SELECT value FROM fixture").fetchone(), (value,))

    def preserve_sidecars(self):
        return {self.installation / f"data/tg115.db-{kind}": kind.encode() for kind in ("wal", "shm")}

    def test_digest_image_is_reused_and_old_bot_is_restarted(self):
        result, calls = self.execute("rollback_install\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("tag old-gateway", calls)
        self.assertIn("tag old-bot old-bot:latest", calls)
        self.assertIn(DIGEST, calls)
        self.assertIn("compose up -d openlist", calls)
        self.assertIn("compose up -d --no-deps --force-recreate tg2cloud-openlist-bot", calls)

    def test_unavailable_or_mismatched_digest_stops_before_program_removal(self):
        original = self.database.read_bytes()
        for mode in ("missing-image", "wrong-image"):
            with self.subTest(mode=mode):
                (self.root / "calls").unlink(missing_ok=True)
                result, calls = self.execute("rollback_install\n", mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("compose rm", calls)
                self.assertNotIn("compose up", calls)
                self.assertEqual(self.database.read_bytes(), original)

    def test_mutable_gateway_tag_still_supports_rollback(self):
        result, calls = self.execute("rollback_install\n", before="OLD_OPENLIST_IMAGE_TAG=old-gateway:stable\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tag old-gateway old-gateway:stable", calls)
        self.assertIn("compose up -d openlist", calls)

    def test_invalid_or_missing_snapshot_preserves_database_and_sidecars(self):
        original = self.database.read_bytes()
        sidecars = self.preserve_sidecars()
        for path, data in sidecars.items():
            path.write_bytes(data)
        for data in (b"", b"partial backup", None):
            with self.subTest(snapshot=data):
                candidate = self.root / "invalid.db"
                candidate.unlink(missing_ok=True)
                if data is not None:
                    candidate.write_bytes(data)
                result, calls = self.execute("rollback_install\n", before='DATABASE_BACKUP="$test_root/invalid.db"\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("TG2CLOUD_DATABASE_CHECK=FAILED", result.stderr)
                self.assertNotIn("compose rm", calls)
                self.assertEqual(self.database.read_bytes(), original)
                for path, expected in sidecars.items():
                    self.assertEqual(path.read_bytes(), expected)

    def test_restore_copy_failure_preserves_original_database_and_sidecars(self):
        original = self.database.read_bytes()
        sidecars = self.preserve_sidecars()
        for path, data in sidecars.items():
            path.write_bytes(data)
        result, calls = self.execute(
            "rollback_install\n", "restore-copy-fail", 'DATABASE_BACKUP="$test_root/good.db"\n',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("compose rm", calls)
        self.assertEqual(self.database.read_bytes(), original)
        for path, expected in sidecars.items():
            self.assertEqual(path.read_bytes(), expected)
        self.assertFalse(list((self.installation / "data").glob(".rollback-*")))

    def test_bot_removal_failure_preserves_database_and_sidecars(self):
        original = self.database.read_bytes()
        sidecars = self.preserve_sidecars()
        for path, data in sidecars.items():
            path.write_bytes(data)
        result, calls = self.execute(
            "rollback_install\n", "cannot-stop-bot", 'DATABASE_BACKUP="$test_root/good.db"\n',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("compose up", calls)
        self.assertEqual(self.database.read_bytes(), original)
        for path, expected in sidecars.items():
            self.assertEqual(path.read_bytes(), expected)

    def test_valid_snapshot_restores_database_and_restarts_bot(self):
        for path, data in self.preserve_sidecars().items():
            path.write_bytes(data)
        result, calls = self.execute("rollback_install\n", before='DATABASE_BACKUP="$test_root/good.db"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_database(self.database, 2)
        self.assertFalse(any(path.exists() for path in self.preserve_sidecars()))
        self.assertFalse(list((self.installation / "data").glob(".rollback-*")))
        self.assertIn("compose up -d --no-deps --force-recreate tg2cloud-openlist-bot", calls)

    def test_upgrade_snapshot_is_published_only_after_valid_copy(self):
        result, _ = self.execute(UPGRADE + '\n[[ -n "$DATABASE_BACKUP" ]]\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshots = list((self.root / "backups").glob("database-*.db"))
        self.assertEqual(len(snapshots), 1)
        self.assert_database(snapshots[0], 1)
        self.assertFalse(list((self.installation / "data").glob(".upgrade-*")))

    def test_failed_corrupt_or_interrupted_copy_does_not_restore_partial_snapshot(self):
        original = self.database.read_bytes()
        for mode in ("backup-copy-fail", "backup-copy-corrupt", "backup-copy-interrupt"):
            with self.subTest(mode=mode):
                (self.root / "calls").unlink(missing_ok=True)
                result, calls = self.execute(UPGRADE, mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("TG2CLOUD_RESULT=FAILED", result.stderr)
                self.assertIn("已自动恢复升级前版本", result.stderr)
                self.assertIn("compose up -d --no-deps --force-recreate tg2cloud-openlist-bot", calls)
                self.assertEqual(self.database.read_bytes(), original)
                self.assertFalse(list((self.root / "backups").glob("database-*.db")))
                self.assertFalse(list((self.installation / "data").glob(".rollback-*")))
                self.assertFalse(list((self.installation / "data").glob(".upgrade-*")))

    def gateway_fixture(self):
        for name in ("data.db", "config.json", "log/log.log", "temp/upload-part", "temporary-keep/user-file"):
            path = self.installation / "openlist/data" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")

    def test_upgrade_and_manual_archives_exclude_only_log_and_temp(self):
        self.gateway_fixture()
        for action in (UPGRADE, MANUAL + "\ncreate_backup\n"):
            with self.subTest(manual=action != UPGRADE):
                for path in (self.root / "backups").iterdir():
                    path.unlink()
                (self.root / "calls").unlink(missing_ok=True)
                result, calls = self.execute(action)
                self.assertEqual(result.returncode, 0, result.stderr)
                archives = list((self.root / "backups").glob("openlist-state-*.tar.gz"))
                self.assertEqual(len(archives), 1)
                with tarfile.open(archives[0]) as archive:
                    names = archive.getnames()
                self.assertIn("openlist/data/data.db", names)
                self.assertIn("openlist/data/config.json", names)
                self.assertIn("openlist/data/temporary-keep/user-file", names)
                self.assertFalse(any(name.startswith(("openlist/data/log", "openlist/data/temp/")) for name in names))
                self.assertNotIn("openlist/data/temp", names)
                self.assertFalse((self.root / "gateway-stopped").exists())
                self.assertNotIn("clouddrive2", calls)

    def test_archive_failure_resumes_old_services(self):
        self.gateway_fixture()
        for action in (UPGRADE, MANUAL + "\ncreate_backup\n"):
            with self.subTest(manual=action != UPGRADE):
                (self.root / "calls").unlink(missing_ok=True)
                result, calls = self.execute(action, "archive-fail")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("compose up -d", calls)
                self.assertFalse((self.root / "gateway-stopped").exists())
                self.assert_database(self.database, 1)
                self.assertNotIn("clouddrive2", calls)


if __name__ == "__main__":
    unittest.main()
