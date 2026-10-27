"""Host-only tests run without Telethon and must never launch a real Docker command."""

import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from tg2cloud.deployment.listening import main

ROOT = Path(__file__).resolve().parents[1]


class HostListeningTests(unittest.TestCase):
    def test_help_from_other_directory_without_site_packages(self):
        code = (
            "import sys;sys.path.insert(0,"
            + repr(str(ROOT / "src"))
            + ");from tg2cloud.cli.commands import main;main(['listen','--help'])"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", code],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--edition", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_verified_existing_container_is_only_touched_identity(self):
        for edition, redirected in ((e, r) for e in ("clouddrive2", "openlist") for r in (False, True)):
            with self.subTest(edition=edition, redirected=redirected), contextlib.ExitStack() as stack:
                stack.enter_context(
                    patch("tg2cloud.deployment.preflight.validate_host")
                )
                checked = stack.enter_context(
                    patch("tg2cloud.deployment.architecture.check_docker")
                )
                stack.enter_context(
                    patch("tg2cloud.deployment.architecture.check_environment")
                )
                stack.enter_context(
                    patch(
                        "tg2cloud.deployment.listening.shutil.which",
                        return_value="/usr/bin/docker",
                    )
                )
                stack.enter_context(
                    patch("tg2cloud.deployment.listening.os.isatty", side_effect=lambda fd, redirected=redirected: not redirected or fd == 77)
                )
                opened = mock_open()
                opened.return_value.fileno.return_value = 77
                opened.return_value.__exit__.side_effect = None
                opened.return_value.__exit__.return_value = False
                stack.enter_context(patch("builtins.open", opened))
                stack.enter_context(
                    patch(
                        "tg2cloud.deployment.host.edition_lock",
                        return_value=contextlib.nullcontext(),
                    )
                )
                stack.enter_context(
                    patch(
                        "tg2cloud.deployment.instances.docker_inventory",
                        return_value=set(),
                    )
                )
                discovery = stack.enter_context(
                    patch(
                        "tg2cloud.deployment.instances.discover",
                        return_value=SimpleNamespace(present=True, running=True),
                    )
                )
                runner = stack.enter_context(
                    patch(
                        "tg2cloud.deployment.listening.subprocess.run",
                        return_value=SimpleNamespace(returncode=0),
                    )
                )
                self.assertEqual(
                    main(
                        [
                            "login",
                            "--edition",
                            edition,
                            "--install-dir",
                            "/opt/custom-fixture",
                        ]
                    ),
                    0,
                )
                checked.assert_called_once()
                self.assertEqual(
                    discovery.call_args.kwargs["install_dir"], "/opt/custom-fixture"
                )
                args = runner.call_args.args[0]
                self.assertEqual(
                    args,
                    [
                        "/usr/bin/docker",
                        "exec",
                        "-it",
                        f"tg2cloud-{edition}-bot",
                        "python",
                        "-B",
                        "-m",
                        "tg2cloud.listening.account",
                        "login",
                    ],
                )
                self.assertNotIn("capture_output", runner.call_args.kwargs)
                if redirected:
                    opened.assert_called_once_with("/dev/tty", "r+b", buffering=0)
                    for stream in ("stdin", "stdout", "stderr"):
                        self.assertIs(runner.call_args.kwargs[stream], opened.return_value)
                    opened.return_value.__exit__.assert_called_once()
                else:
                    opened.assert_not_called()

    def test_invalid_or_partial_instance_never_executes_login(self):
        with (
            patch(
                "tg2cloud.deployment.preflight.validate_host",
                side_effect=ValueError("unsupported"),
            ),
            patch("tg2cloud.deployment.listening.subprocess.run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["login", "--edition", "clouddrive2"]), 1)
            run.assert_not_called()


class ExplicitStableReleaseTests(unittest.TestCase):
    def test_both_installers_pass_exact_stable_tag_without_writes_in_check_mode(self):
        from unittest.mock import Mock

        from tg2cloud.cli import vps
        from tg2cloud.deployment import architecture, instances, releases
        from tg2cloud.deployment.profiles import PRODUCTS
        from tg2cloud.deployment.proxy import lan
        for module in (vps, lan):
            for edition in PRODUCTS:
                with self.subTest(mode=module.__name__, edition=edition), contextlib.ExitStack() as stack:
                    product = PRODUCTS[edition]
                    instance = instances.Instance(product, Path(product.install_dir), False)
                    client = Mock(resolve=Mock(return_value=releases.Release("v1.4.9", "b" * 40)),
                                  download=Mock(return_value=ROOT))
                    stack.enter_context(patch.object(instances, "docker_inventory", return_value=set()))
                    stack.enter_context(patch.object(instances, "discover", return_value=instance))
                    stack.enter_context(patch.object(releases, "ReleaseClient", return_value=client))
                    stack.enter_context(patch.object(architecture, "check_docker"))
                    stack.enter_context(patch.object(module, "SafeLog", return_value=lambda _line: None))
                    terminal = stack.enter_context(patch.object(module.terminal, "Terminal"))
                    if module is vps:
                        stack.enter_context(patch.object(vps.preflight, "validate_host"))
                        stack.enter_context(patch.object(vps.install, "make_plan", return_value=Mock()))
                        stack.enter_context(patch.object(vps.terminal, "preview"))
                        execute = stack.enter_context(patch.object(vps.install, "execute_plan"))
                    else:
                        stack.enter_context(patch.object(lan, "validate_environment"))
                        stack.enter_context(patch.object(lan, "load_state", return_value=None))
                        stack.enter_context(patch.object(lan, "make_plan", return_value=Mock()))
                        stack.enter_context(patch.object(lan, "preview"))
                        execute = stack.enter_context(patch.object(lan, "execute"))
                    self.assertEqual(module.main(["--edition", edition, "--release", "v1.4.9", "--check"]), 0)
                    client.resolve.assert_called_once_with("v1.4.9")
                    terminal.assert_not_called()
                    execute.assert_not_called()

    def test_explicit_nonstable_release_remains_rejected_before_network(self):
        from tg2cloud.deployment.releases import ReleaseClient
        client = ReleaseClient()
        with patch.object(client, "json") as network:
            for tag in ("main", "v1.5.0-rc.1", "v1.4.9;echo bad", "v01.4.9"):
                with self.subTest(tag=tag), self.assertRaises(ValueError):
                    client.resolve(tag)
            network.assert_not_called()
