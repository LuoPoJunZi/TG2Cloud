"""Offline repository contracts; no build, deployment, or personal data."""

import ast
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_python", ROOT / ".github/scripts/check_python.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
repository_spec = importlib.util.spec_from_file_location("check_repository", ROOT / ".github/scripts/check_repository.py")
repository = importlib.util.module_from_spec(repository_spec)
repository_spec.loader.exec_module(repository)
lock_spec = importlib.util.spec_from_file_location("lock_dependencies", ROOT / ".github/scripts/lock_dependencies.py")
locks = importlib.util.module_from_spec(lock_spec)
lock_spec.loader.exec_module(locks)


class PythonCheckEntryTests(unittest.TestCase):
    def test_universal_locks_use_bot_python_not_generator_or_host_cli_runtime(self):
        with tempfile.TemporaryDirectory() as private:
            root = Path(private)
            (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10"\n', encoding="utf-8")
            (root / "packaging").mkdir()
            (root / "packaging/Dockerfile").write_text('FROM python:3.12-slim-trixie@sha256:' + "a" * 64 + "\n", encoding="utf-8")
            with patch.object(locks, "ROOT", root), patch.object(locks.sys, "argv", ["lock_dependencies.py"]), patch.object(locks.subprocess, "run") as run:
                self.assertEqual(locks.main(), 0)
            self.assertEqual(run.call_count, 2)
            for call in run.call_args_list:
                command = call.args[0]
                self.assertIn("--universal", command)
                self.assertIn("--generate-hashes", command)
                self.assertEqual(command[command.index("--python-version") + 1], "3.12")
                self.assertEqual(call.kwargs, {"cwd": root, "check": True, "shell": False})
            self.assertEqual(run.call_args_list[-1].args[0][-2:], ["--constraint", "requirements/bot.lock.txt"])

    def test_lock_generation_unknown_runtime_stops_before_resolution(self):
        with tempfile.TemporaryDirectory() as private:
            root = Path(private)
            (root / "packaging").mkdir()
            (root / "packaging/Dockerfile").write_text('FROM unknown:latest\n', encoding="utf-8")
            with patch.object(locks, "ROOT", root), patch.object(locks.sys, "argv", ["lock_dependencies.py"]), patch.object(locks.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "runtime version"):
                    locks.main()
                run.assert_not_called()

    def test_full_tests_use_existing_unittest_discovery(self):
        self.assertEqual(checks.commands("test", "all"), [[
            sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v",
        ]])

    def test_cli_checks_keep_separate_offline_test_patterns(self):
        commands = checks.commands("test", "cli")
        self.assertEqual([command[-2] for command in commands], list(checks.CLI_TESTS))
        self.assertNotIn("test*.py", [command[-2] for command in commands])
        self.assertNotIn("test_lan_gateway_docker.py", checks.CLI_TESTS)

    def test_full_lint_discovers_sources_instead_of_duplicating_ci_lists(self):
        self.assertEqual(checks.commands("lint", "all"), [[sys.executable, "-m", "ruff", "check", "."]])
        self.assertEqual(checks.commands("lint", "cli")[0][4:], list(checks.CLI_PATHS))

    def test_compile_scope_covers_formal_python_but_not_generated_trees(self):
        paths = checks.source_paths("all")
        for path in (".github/scripts", "src", "packaging/compat", "scripts", "tests"):
            self.assertIn(path, paths)
        for path in ("build", "dist", ".venv", "website", "legacy"):
            self.assertNotIn(path, paths)
        command = checks.commands("compile", "cli")[0]
        self.assertEqual(command[6:], list(checks.CLI_PATHS))
        self.assertEqual(command[1:3], ["-X", f"pycache_prefix={ROOT / 'build/check-pycache'}"])

    def test_all_checks_are_ordered_and_do_not_build_or_install(self):
        commands = checks.commands("all", "all")
        self.assertEqual(commands[0], [sys.executable, "-B", ".github/scripts/check_repository.py"])
        self.assertEqual([command[command.index("-m") + 1] for command in commands[1:]],
                         ["unittest", "ruff", "compileall"])
        self.assertNotIn("build.ps1", " ".join(part for command in commands for part in command))

    def test_repository_check_is_independent_of_python_scope_and_dependencies(self):
        self.assertEqual(checks.commands("repository", "all"), checks.commands("repository", "cli"))
        self.assertEqual(checks.commands("repository", "all"), [[
            sys.executable, "-B", ".github/scripts/check_repository.py",
        ]])
        self.assertIn(".github/scripts/check_repository.py", checks.CLI_PATHS)

    def test_runner_anchors_working_directory_and_stops_on_failure(self):
        with patch.dict(checks.os.environ, {"TG2CLOUD_TEST": "fixture"}, clear=True), patch.object(checks.subprocess, "run", return_value=Mock(returncode=7)) as run:
            self.assertEqual(checks.main(["all"]), 7)
            run.assert_called_once_with(checks.commands("repository", "all")[0], cwd=ROOT, check=False, shell=False,
                                        env={"TG2CLOUD_TEST": "fixture", "PYTHONPATH": str(ROOT / "src") + checks.os.pathsep})

    def test_runner_supports_successful_cli_check_sequence(self):
        with patch.object(checks.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertEqual(checks.main(["all", "--scope", "cli"]), 0)
            self.assertEqual([call.args[0] for call in run.call_args_list], checks.commands("all", "cli"))


class RepositoryContractTests(unittest.TestCase):
    def test_public_sources_are_script_only_without_root_duplicates(self):
        for name in ("installer.py", "installer_clouddrive2.py", "installer_openlist.py",
                     "operation_feedback.py", "build.ps1", "requirements-build.txt"):
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists())
        files = repository.public_files(ROOT)
        self.assertFalse(any(name.startswith("legacy/") for name in files))
        modules = {"deployer_products.py": "deployment/profiles.py", "domain_proxy.py": "deployment/proxy/manager.py",
                   "proxy_maintenance.py": "deployment/proxy/maintenance.py", "vps_resources.py": "deployment/resources.py"}
        for name, target in modules.items():
            self.assertFalse((ROOT / name).exists())
            self.assertIn("src/tg2cloud/" + target, files)
        code = "import sys; sys.path.insert(0, " + repr(str(ROOT / "src")) + "); from tg2cloud.cli import vps; from tg2cloud.deployment.proxy import lan; from tg2cloud.deployment import uninstall; assert not any(name.split('.')[0] in {'legacy', 'PySide6', 'paramiko', 'telethon', 'cryptg', 'psutil'} for name in sys.modules)"
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True,
                                text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_document_index_links_exist_and_stay_within_repository(self):
        index = ROOT / "docs/README.md"
        links = re.findall(r"\]\(([^)]+)\)", index.read_text(encoding="utf-8"))
        self.assertTrue(links)
        for link in links:
            with self.subTest(link=link):
                target = (index.parent / unquote(link)).resolve()
                self.assertTrue(target.is_relative_to(ROOT))
                self.assertTrue(target.is_file())

    def test_document_index_covers_existing_public_guides(self):
        index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
        for guide in (
            "README-小白使用说明.md", "填写信息清单.md", "VPS-INSTALL.md", "LAN-INSTALL.md",
            "UNINSTALL.md", "OPERATIONS.md", "MIGRATION_FROM_TG115.md", "第三方组件说明.md",
            "development/BRAND-GUIDE.md", "development/DOMAIN-HTTPS-ACCEPTANCE.md",
            "development/REPOSITORY.md",
        ):
            with self.subTest(guide=guide):
                self.assertIn(f"]({guide})", index)
        for readme in ("README.md", "README_EN.md"):
            self.assertIn('href="docs/README.md"', (ROOT / readme).read_text(encoding="utf-8"))

    def test_editor_rules_preserve_markdown_and_official_brand_assets(self):
        rules = (ROOT / ".editorconfig").read_text(encoding="utf-8")
        self.assertIn("root = true", rules)
        self.assertIn("charset = utf-8", rules)
        self.assertIn("[*.ps1]\nend_of_line = crlf", rules)
        self.assertIn("[*.md]", rules)
        self.assertIn("trim_trailing_whitespace = false", rules)
        self.assertIn("[*.{svg,png,ico}]", rules)
        self.assertIn("insert_final_newline = unset", rules)

    def test_ruff_keeps_original_implicit_defaults(self):
        config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        sections = re.findall(r"(?ms)^\[tool\.ruff\]\n(.*?)(?=^\[|\Z)", config)
        self.assertEqual(len(sections), 1)
        self.assertIn('target-version = "py310"', sections[0])
        self.assertIn("respect-gitignore = true", sections[0])
        self.assertIn('extend-exclude = ["website"]', sections[0])
        self.assertNotRegex(config, r"(?m)^\s*(?:select|ignore|extend-select|extend-ignore)\s*=")

    def test_ruff_has_no_parallel_root_configuration(self):
        for name in (".ruff.toml", "ruff.toml"):
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists())

    def test_ruff_workflow_filters_follow_shared_pyproject(self):
        for name in ("docs.yml", "vps-installer.yml"):
            with self.subTest(workflow=name):
                text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertEqual(text.count('      - "pyproject.toml"'), 2)
                self.assertNotIn('      - ".ruff.toml"', text)

    def test_branch_release_and_cli_workflows_share_check_entry(self):
        for workflow in ("tests.yml", "release.yml", "vps-installer.yml"):
            text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
            with self.subTest(workflow=workflow):
                for task in ("test", "lint", "compile"):
                    self.assertIn(f".github/scripts/check_python.py {task}", text)
                self.assertNotIn("ruff check installer.py", text)

    def test_certificate_fixtures_have_explicit_non_runtime_dependency(self):
        requirements = (ROOT / "requirements/dev.lock.txt").read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^cryptography==[0-9]+\.[0-9]+\.[0-9]+[ \\]*$")
        self.assertNotIn("cryptography", (ROOT / "requirements/bot.lock.txt").read_text(encoding="utf-8"))
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("-r requirements/dev.lock.txt", workflow.split("  linux-products:", 1)[1])

    def test_dependabot_openlist_scans_compose_not_a_missing_dockerfile(self):
        config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        updates = re.split(r"(?m)^  - package-ecosystem: *", config)[1:]
        openlist = [block for block in updates
                    if re.search(r"(?m)^    directory: /packaging/compose$", block)]
        self.assertEqual(len(openlist), 1)
        self.assertEqual(openlist[0].splitlines()[0], "docker-compose")
        self.assertIn("interval: monthly", openlist[0])
        self.assertIn("open-pull-requests-limit: 5", openlist[0])
        compose_files = sorted((ROOT / "packaging/compose").glob("*.yml"))
        self.assertEqual({path.name for path in compose_files},
                         {"docker-compose.clouddrive2.yml", "docker-compose.openlist.yml"})
        # Upstream DockerCompose::FileFetcher matches compose-prefixed names,
        # not arbitrary YAML: docker/lib/dependabot/docker_compose/file_fetcher.rb.
        for path in compose_files:
            self.assertRegex(path.name, r"^(docker-)?compose(-[\w]+)?(?:\.[\w-]+)?\.ya?ml$")

    def test_dependabot_shared_bot_image_keeps_docker_scanner_and_version_limits(self):
        config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        updates = re.split(r"(?m)^  - package-ecosystem: *", config)[1:]
        docker = [block for block in updates if block.splitlines()[0] == "docker"
                  and re.search(r"(?m)^    directory: /packaging$", block)]
        self.assertEqual(len(docker), 1)
        self.assertIn("    directory: /packaging\n", docker[0])
        self.assertTrue((ROOT / "packaging/Dockerfile").is_file())
        for rule in ("dependency-name: python", "version-update:semver-major", "version-update:semver-minor"):
            self.assertIn(rule, docker[0])

    def test_shellcheck_source_annotations_resolve_public_helpers(self):
        for script in sorted((ROOT / "packaging/hooks").rglob("*.sh")):
            for name in re.findall(r"(?m)^# shellcheck source=(\S+)$", script.read_text(encoding="utf-8")):
                with self.subTest(script=script.relative_to(ROOT).as_posix(), source=name):
                    self.assertTrue((ROOT / name).is_file(), "ShellCheck source annotation points to a missing helper")

    def test_consistency_checks_run_when_source_docs_or_brand_change(self):
        website = (ROOT / ".github/workflows/website-docs.yml").read_text(encoding="utf-8")
        for path in ("assets/brand/**", "docs/**", "README.md", "README_EN.md", "src/tg2cloud/version.py"):
            self.assertEqual(website.count(f'"{path}"'), 2, path)
        docs = (ROOT / ".github/workflows/docs.yml").read_text(encoding="utf-8")
        self.assertIn("-p test_repository.py", docs)

    def test_repository_ci_checks_every_change_without_build_or_write_permissions(self):
        workflow = (ROOT / ".github/workflows/repository.yml").read_text(encoding="utf-8")
        for text in ("  workflow_dispatch:", "  push:", "  pull_request:",
                     "  contents: read", "-B .github/scripts/check_repository.py", "-p test_repository.py"):
            self.assertIn(text, workflow)
        for text in ("paths:", "paths-ignore:", "build.ps1", "contents: write", "pip install", "git push"):
            self.assertNotIn(text, workflow)

    def test_release_checks_public_inputs_before_any_build(self):
        release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        prepare, downstream = release.split("  linux-validation:\n", 1)
        self.assertIn(".github/scripts/check_repository.py", prepare)
        self.assertIn("    needs: prepare", downstream)


class UserDocumentationTests(unittest.TestCase):
    """Repository guides stand alone and document real public operations."""

    GUIDES = (
        "README.md", "README_EN.md", "docs/README.md", "docs/BOT-USAGE.md",
        "docs/STORAGE.md", "docs/OPERATIONS.md", "docs/RECOVERY.md",
        "docs/VPS-INSTALL.md", "docs/LAN-INSTALL.md", "docs/填写信息清单.md",
        "docs/README-小白使用说明.md", "docs/development/REPOSITORY.md",
        "docs/development/SCRIPT-FIRST.md", "docs/development/LINUX-REFACTOR.md",
    )

    def test_readmes_and_index_offer_standalone_bot_and_storage_guides(self):
        for name in ("BOT-USAGE.md", "STORAGE.md"):
            self.assertIn(f"]({name})", (ROOT / "docs/README.md").read_text(encoding="utf-8"))
            for readme in ("README.md", "README_EN.md"):
                self.assertIn(f"](docs/{name})", (ROOT / readme).read_text(encoding="utf-8"))
        for name in ("VPS-INSTALL.md", "LAN-INSTALL.md", "RECOVERY.md"):
            text = (ROOT / "docs" / name).read_text(encoding="utf-8")
            for target in ("BOT-USAGE.md", "STORAGE.md"):
                self.assertIn(f"]({target})", text)

    def test_guide_links_and_local_heading_anchors_exist(self):
        for name in self.GUIDES:
            source = ROOT / name
            text = source.read_text(encoding="utf-8")
            for href in re.findall(r"\]\(([^)]+)\)", text):
                if re.match(r"(?:https?://|mailto:)", href):
                    continue
                relative, _, fragment = href.partition("#")
                target = (source.parent / unquote(relative)).resolve() if relative else source
                with self.subTest(source=name, link=href):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.is_file())
                    if fragment:
                        headings = re.findall(r"^#{1,6}\s+(.+)$", target.read_text(encoding="utf-8"), re.MULTILINE)
                        anchors = {re.sub(r"[^\w\s-]", "", heading.strip().lower()).replace(" ", "-")
                                   for heading in headings}
                        self.assertIn(unquote(fragment), anchors)

    def test_repository_navigation_does_not_depend_on_website_articles_or_source(self):
        for name in self.GUIDES:
            source = ROOT / name
            links = re.findall(r'\]\(([^)]+)\)|\bhref="([^"]+)"', source.read_text(encoding="utf-8"))
            for markdown, html in links:
                href = markdown or html
                with self.subTest(source=name, link=href):
                    if href.startswith("https://tg2cloud.pages.dev/"):
                        self.assertEqual(href, "https://tg2cloud.pages.dev/")
                    elif not re.match(r"(?:https?://|mailto:|#)", href):
                        target = (source.parent / unquote(href.split("#", 1)[0])).resolve()
                        self.assertFalse(target.is_relative_to(ROOT / "website"))

    def test_documented_bot_commands_are_handled_and_include_recovery(self):
        tree = ast.parse((ROOT / "src/tg2cloud/telegram/commands.py").read_text(encoding="utf-8"))
        supported = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name) or node.left.id != "command":
                continue
            for value in node.comparators:
                try:
                    literals = ast.literal_eval(value)
                except (ValueError, TypeError):
                    continue
                supported.update([literals] if isinstance(literals, str) else literals)
        text = (ROOT / "docs/BOT-USAGE.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"`(/[a-z]+)(?=[\s`])", text))
        self.assertTrue(documented)
        self.assertLessEqual(documented, supported)
        self.assertLessEqual({"/restart", "/recover", "/search", "/tasks", "/stream", "/orphans"}, documented)
        views = ast.parse((ROOT / "src/tg2cloud/telegram/views.py").read_text(encoding="utf-8"))
        menu = next(ast.literal_eval(node.value) for node in views.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "BOT_MENU_COMMANDS" for target in node.targets))
        for command, description in menu:
            self.assertRegex(text, rf"(?m)^/{command}\s+{re.escape(description)}$")

    def test_storage_guide_uses_actual_edition_addresses_without_importing_bot(self):
        tree = ast.parse((ROOT / "src/tg2cloud/deployment/profiles.py").read_text(encoding="utf-8"))
        text = (ROOT / "docs/STORAGE.md").read_text(encoding="utf-8")
        editions = set()
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            if not isinstance(node.value.func, ast.Name) or node.value.func.id != "ProductProfile":
                continue
            values = {item.arg: ast.literal_eval(item.value) for item in node.value.keywords
                      if item.arg in {"key", "webdav_url", "install_dir"}}
            editions.add(values["key"])
            for key in ("webdav_url", "install_dir"):
                self.assertIn("`" + values[key] + "`", text)
        self.assertEqual(editions, {"clouddrive2", "openlist"})

    def test_absolute_manage_examples_name_supported_subcommands(self):
        text = (ROOT / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        commands = {}
        for edition in ("clouddrive2", "openlist"):
            source = (ROOT / "packaging/hooks" / edition / "manage.sh").read_text(encoding="utf-8")
            labels = re.findall(r"^  ([a-z][a-z0-9-]*(?:\|[a-z][a-z0-9-]*)*)\)", source, re.MULTILINE)
            commands[edition] = {part for label in labels for part in label.split("|")}
        examples = re.findall(r"/opt/tg2cloud-(clouddrive2|openlist)/manage\.sh ([a-z-]+)", text)
        self.assertTrue(examples)
        for edition, command in examples:
            self.assertIn(command, commands[edition])
        for command in ("backup", "recent-logs", "restart-bot", "restart-openlist"):
            self.assertIn(command, commands["openlist"])
            self.assertNotIn(command, commands["clouddrive2"])
            self.assertIn("`" + command, text)
        self.assertIn("直接删除", text)
        self.assertIn("1～50", text)


class PublicFileTests(unittest.TestCase):
    def test_inventory_includes_tracked_and_unignored_candidates_without_path_quoting(self):
        result = Mock(stdout="README.md\0docs/中文 说明.md\0README.md\0")
        with patch.object(repository.shutil, "which", return_value="/tools/git"), patch.object(repository.subprocess, "run", return_value=result) as run, patch.object(Path, "exists", return_value=True):
            self.assertEqual(repository.public_files(ROOT), ["README.md", "docs/中文 说明.md"])
        run.assert_called_once_with(
            ["/tools/git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--"],
            capture_output=True, text=True, encoding="utf-8", check=True, shell=False,
        )

    def test_forbidden_outputs_private_files_and_internal_records(self):
        for name in (
            "dist/app.exe", "build/phase2-preview/view.png", "website/node_modules/tool/index.js",
            "app/__pycache__/bot.pyc", ".pytest_cache/README.md", ".ruff_cache/item",
            ".venv/Scripts/python.exe", "website/dist/index.html", "App.EXE", "old.spec",
            ".codex/PROJECT_MEMORY.md", "AGENTS.md", "website/AGENTS.md", "AGENTS_old.md",
            "docs/AUDIT.md", "docs/WORKLOG.md", "TG2Cloud-Codex-Kickoff-Prompt.md",
            "TG2Cloud-v1.0.0-RELEASE-CHECKLIST.md", "website/QA_REPORT.md",
            ".env", "payload_openlist/.env.production", "rclone.conf", "secret.pem", "id_ed25519",
            "tasks.db", "tasks.sqlite3", "tasks.sqlite-wal", "tasks.sqlite3-shm", "run.log",
            ".coverage.host.123", "coverage.xml", "draft.tmp", "draft.bak", "Thumbs.db",
            "../outside.md", "/outside.md", "C:/local.md", "docs\\local.md",
            "legacy/desktop/installer.py", "legacy/desktop/tests/test_core.py",
            "installer.py", "build.ps1", "requirements-build.txt",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(repository.forbidden_reason(name))

    def test_public_sources_resources_and_example_config_are_allowed(self):
        for name in (
            "src/tg2cloud/deployment/profiles.py", "install.sh", "tests/test_repository.py", ".github/workflows/release.yml",
            ".github/CONTRIBUTING.md", ".github/SECURITY.md", "assets/brand/tg2cloud.ico",
            "website/public/favicon.ico", "docs/填写信息清单.md", "docs/development/BRAND-GUIDE.md",
            "docs/development/DOMAIN-HTTPS-ACCEPTANCE.md", "LICENSE", "packaging/hooks/clouddrive2/.env.example",
        ):
            with self.subTest(name=name):
                self.assertIsNone(repository.forbidden_reason(name))

    def test_missing_git_fails_closed_without_echoing_exception_content(self):
        output = io.StringIO()
        with patch.object(repository, "public_files", side_effect=OSError("private diagnostic")), redirect_stderr(output):
            self.assertEqual(repository.main(), 1)
        self.assertIn("complete Git checkout", output.getvalue())
        self.assertNotIn("private diagnostic", output.getvalue())

    def test_missing_git_executable_never_starts_a_subprocess(self):
        with (patch.object(repository.shutil, "which", return_value=None),
              patch.object(repository.subprocess, "run") as run, self.assertRaises(FileNotFoundError)):
            repository.public_files(ROOT)
        run.assert_not_called()

    @unittest.skipUnless(shutil.which("git"), "Git is required for isolated inventory regression")
    def test_tracked_ignored_file_still_fails_but_local_ignored_files_do_not(self):
        # A separate temporary repository: never stage, commit or alter the real index.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".gitignore").write_text("build/\n.env\nAGENTS.md\n", encoding="utf-8")
            (root / "build").mkdir()
            (root / "build/preview.png").write_bytes(b"fixture")
            (root / "AGENTS.md").write_text("local fixture", encoding="utf-8")
            (root / ".env").write_text("EXAMPLE_ONLY=fixture\n", encoding="utf-8")
            (root / "new-guide.md").write_text("public fixture", encoding="utf-8")
            for arguments in (("init", "--quiet"), ("add", "--force", "--", ".env")):
                subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True, shell=False)
            files = repository.public_files(root)
            self.assertIn(".env", files)
            self.assertIn("new-guide.md", files)
            self.assertNotIn("build/preview.png", files)
            self.assertNotIn("AGENTS.md", files)
            self.assertIsNotNone(repository.forbidden_reason(".env"))


class RepositoryGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def put(self, name, text="fixture"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build_fixture(self):
        for name in repository.BUILD_FILES:
            self.put(name)
        self.put("src/tg2cloud/deployment/profiles.py", 'FILES = ("packaging/compose/docker-compose.clouddrive2.yml", "packaging/compose/docker-compose.openlist.yml")\n')
        self.put("packaging/compose/docker-compose.clouddrive2.yml")
        self.put("packaging/compose/docker-compose.openlist.yml")
        return list(repository.BUILD_FILES) + sorted(repository.payload_files(self.root))

    def test_payload_inspection_collects_both_editions_without_execution(self):
        self.put("src/tg2cloud/deployment/profiles.py", 'raise RuntimeError("must not execute")\n'
                 'FILES = ("packaging/compose/docker-compose.clouddrive2.yml", "packaging/compose/docker-compose.openlist.yml", "README.md")\n')
        self.assertEqual(repository.payload_files(self.root), {
            "packaging/compose/docker-compose.clouddrive2.yml", "packaging/compose/docker-compose.openlist.yml", "src/tg2cloud/deployment/profiles.py",
        })

    def test_build_contract_includes_all_public_regular_inputs(self):
        self.assertEqual(repository.check_build_inputs(self.root, self.build_fixture()), [])

    def test_missing_payload_and_excluded_brand_resource_are_reported(self):
        files = self.build_fixture()
        (self.root / "packaging/compose/docker-compose.openlist.yml").unlink()
        files.remove("assets/brand/tg2cloud.ico")
        errors = repository.check_build_inputs(self.root, files)
        self.assertTrue(any("packaging/compose/docker-compose.openlist.yml: required build input missing" in error for error in errors))
        self.assertTrue(any("assets/brand/tg2cloud.ico: required build input excluded" in error for error in errors))

    def test_directory_cannot_replace_build_file(self):
        files = self.build_fixture()
        path = self.root / "install.sh"
        path.unlink()
        path.mkdir()
        self.assertTrue(any("install.sh: required build input missing" in error
                            for error in repository.check_build_inputs(self.root, files)))

    def test_missing_edition_or_invalid_manifest_fails_without_echoing_code(self):
        files = self.build_fixture()
        for text in ('FILES = ("packaging/compose/docker-compose.clouddrive2.yml",)\n', 'invalid syntax PRIVATE_MARKER !\n'):
            with self.subTest(text=text):
                self.put("src/tg2cloud/deployment/profiles.py", text)
                errors = repository.check_build_inputs(self.root, files)
                self.assertIn("src/tg2cloud/deployment/profiles.py: cannot inspect both payload manifests", errors)
                self.assertNotIn("PRIVATE_MARKER", " ".join(errors))

    def test_document_index_resolves_chinese_spaces_and_encoded_paths(self):
        self.put("docs/中文 说明.md")
        self.put("docs/development/BUILD.md")
        self.put("README.md")
        self.put("docs/README.md", '[中文](<中文 说明.md>)\n[编码](%E4%B8%AD%E6%96%87%20%E8%AF%B4%E6%98%8E.md)\n'
                 '[开发](development/BUILD.md#section)\n[根目录](../README.md)\n'
                 '[网页](https://example.com/)\n[邮箱](mailto:docs@example.com)\n[本页](#section)\n')
        files = ["docs/README.md", "docs/中文 说明.md", "docs/development/BUILD.md", "README.md"]
        self.assertEqual(repository.check_document_index(self.root, files), [])

    def test_new_public_document_must_be_indexed_but_local_record_is_not_a_guide(self):
        self.put("docs/README.md", "# Index\n")
        self.put("docs/new-guide.md")
        self.put("docs/AUDIT.md")
        errors = repository.check_document_index(self.root, ["docs/README.md", "docs/new-guide.md", "docs/AUDIT.md"])
        self.assertEqual(errors, ["docs/new-guide.md: public document missing from docs/README.md"])

    def test_missing_or_non_public_link_reports_only_index_line(self):
        self.put("docs/README.md", '[missing](missing.md)\n[private](../.env)\n'
                 '[outside](../../PRIVATE_MARKER.md)\n[absolute](C:/PRIVATE_MARKER.md)\n')
        self.put(".env", "EXAMPLE_ONLY=fixture")
        errors = repository.check_document_index(self.root, ["docs/README.md", ".env"])
        self.assertEqual(len(errors), 4)
        self.assertTrue(all(error.startswith("docs/README.md:") for error in errors))
        self.assertNotIn("PRIVATE_MARKER", " ".join(errors))
        self.assertNotIn("EXAMPLE_ONLY", " ".join(errors))

    def test_missing_or_invalid_utf8_index_fails(self):
        self.assertEqual(repository.check_document_index(self.root, []), [
            "docs/README.md: missing repository-local document index",
        ])
        self.put("docs/README.md").write_bytes(b"\xff")
        self.assertEqual(repository.check_document_index(self.root, ["docs/README.md"]), [
            "docs/README.md: cannot read UTF-8 document index",
        ])

    def test_successful_main_is_read_only_and_explicit_about_limits(self):
        files = self.build_fixture()
        self.put("docs/README.md", "# Index\n")
        files.append("docs/README.md")
        output = io.StringIO()
        with patch.object(repository, "ROOT", self.root), patch.object(repository, "public_files", return_value=files), redirect_stdout(output):
            self.assertEqual(repository.main(), 0)
        self.assertIn("Repository check PASS", output.getvalue())
        self.assertIn("not a secret-content scan, EXE build or VPS acceptance", output.getvalue())
        self.assertEqual(repository.validate_repository(self.root, files), [])

    def test_real_repository_manifest_and_document_index(self):
        self.assertEqual(repository.validate_repository(ROOT, repository.public_files(ROOT)), [])


if __name__ == "__main__":
    unittest.main()
