"""Optional personal login callbacks use the terminal, never logs or argv."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from tg2cloud.listening import account


class LoginInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_two_factor_is_hidden_and_values_are_not_printed(self):
        @contextmanager
        def lock(settings):
            yield Path("synthetic-personal")

        calls = []

        async def start(**kwargs):
            calls.extend(
                [kwargs["phone"](), kwargs["code_callback"](), kwargs["password"]()]
            )

        client = NS(
            start=AsyncMock(side_effect=start),
            get_me=AsyncMock(return_value=NS(id=42, bot=False)),
            disconnect=AsyncMock(),
        )
        with (
            patch.object(account.os, "isatty", return_value=True),
            patch.object(account.os, "umask", return_value=0o022),
            patch.object(account, "session_lock", lock),
            patch.object(account, "client", return_value=client),
            patch.object(account, "state", return_value={"account": None}),
            patch.object(account, "write_state") as saved,
            patch("builtins.input", side_effect=["+123456789", "12345"]) as visible,
            patch.object(
                account.getpass, "getpass", return_value="SYNTHETIC_PASSWORD"
            ) as hidden,
            patch("builtins.print") as output,
        ):
            await account.login(NS(), NS())
        self.assertEqual(calls, ["+123456789", "12345", "SYNTHETIC_PASSWORD"])
        self.assertEqual(
            [c.args[0] for c in visible.call_args_list],
            ["个人账号手机号: ", "Telegram 验证码: "],
        )
        hidden.assert_called_once_with("两步验证密码（隐藏输入）: ")
        self.assertFalse(saved.call_args.kwargs["enabled"])
        self.assertNotIn("SYNTHETIC_PASSWORD", str(output.call_args_list))
        self.assertNotIn("+123456789", str(output.call_args_list))

    async def test_unneeded_two_factor_callback_is_not_prompted(self):
        @contextmanager
        def lock(settings):
            yield Path("synthetic-personal")

        async def start(**kwargs):
            kwargs["phone"]()
            kwargs["code_callback"]()

        client = NS(
            start=AsyncMock(side_effect=start),
            get_me=AsyncMock(return_value=NS(id=42, bot=False)),
            disconnect=AsyncMock(),
        )
        with (
            patch.object(account.os, "isatty", return_value=True),
            patch.object(account.os, "umask", return_value=0o022),
            patch.object(account, "session_lock", lock),
            patch.object(account, "client", return_value=client),
            patch.object(account, "state", return_value={"account": None}),
            patch.object(account, "write_state"),
            patch("builtins.input", side_effect=["+123456789", "12345"]),
            patch.object(account.getpass, "getpass") as hidden,
            patch("builtins.print"),
        ):
            await account.login(NS(), NS())
        hidden.assert_not_called()
