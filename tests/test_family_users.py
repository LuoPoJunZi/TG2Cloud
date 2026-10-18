"""Family grants, private tasks and async-local notification routing."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_scenarios import make_service, make_settings

from tg2cloud.domain.actors import current_user, task_actor, user_scope
from tg2cloud.persistence import users
from tg2cloud.persistence.backup import backup_database
from tg2cloud.persistence.sqlite import TaskDB


class FamilyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data/tg115.db"
        self.settings = make_settings(Path(self.temp.name))
        self.db = TaskDB(self.path)
        self.addCleanup(self.db.close)
        self.admin = self.settings.allowed_user_id
        self.service = make_service(self.settings, self.db)
        self.service.snapshot = None
        self.service.client = SimpleNamespace(send_message=AsyncMock())

    def grant(self, action="add", member=123, **values):
        record = self.db.family_users(self.admin)
        return self.db.change_family_user(self.admin, dict(action=action, id=member,
                                                          revision=record["revision"], **values))

    def task(self, owner, message=1, state="queued"):
        task, _ = self.db.create_task(chat_id=owner, sender_id=owner, message_id=message,
                                      media_key=f"document:{message}", file_name=f"private-{owner}.mp4", file_size=10)
        self.db.update(task["id"], state=state)
        return self.db.get(task["id"])

    def test_grants_no_ddl_preserve_tasks_and_immutable_admin(self):
        task = self.task(self.admin)
        before = self.db._conn.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        self.assertFalse(self.service._authorized(123))
        self.grant(name="家人")
        self.assertTrue(self.service._authorized(123))
        self.grant("disable")
        self.assertFalse(self.service._authorized(123))
        self.grant("enable")
        self.assertTrue(self.service._authorized(123))
        self.grant("remove")
        self.assertEqual(self.db.get(task["id"]), task)
        self.assertEqual(before, self.db._conn.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall())
        self.assertEqual(len(self.db.family_users(self.admin)["events"]), 4)
        for action in ("add", "disable", "enable", "remove"):
            with self.assertRaises(ValueError):
                self.grant(action, self.admin)
        self.assertTrue(self.service._authorized(self.admin))

    def test_cas_two_connections_only_one_change_and_restart_persists(self):
        connections = [TaskDB(self.path), TaskDB(self.path)]
        try:
            def mutate(index):
                try:
                    connections[index].change_family_user(self.admin, {"action": "add", "id": 123 + index,
                                                                     "revision": "initial"})
                    return True
                except ValueError:
                    return False
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(sorted(executor.map(mutate, range(2))), [False, True])
            self.assertEqual(len(self.db.family_users(self.admin)["users"]), 1)
        finally:
            for connection in connections:
                connection.close()

    def test_invalid_registry_fails_closed_for_members_not_admin(self):
        self.grant()
        item = self.db.family_users(self.admin)
        item["admin_id"] += 1
        self.db._conn.execute("UPDATE service_meta SET value=? WHERE key=?", (json.dumps(item), users.KEY))
        self.assertFalse(self.service._authorized(123))
        self.assertTrue(self.service._authorized(self.admin))
        for value in (True, "123,456", "0", "-1", "1\n", "9" * 16):
            with self.assertRaises(ValueError):
                users.user_id(value)

    async def test_member_lists_search_buttons_and_operations_are_private(self):
        self.grant()
        own, foreign = self.task(123), self.task(self.admin)
        event = SimpleNamespace(sender_id=123, chat_id=123, is_private=True,
                                reply=AsyncMock(), answer=AsyncMock(), edit=AsyncMock())
        with user_scope(123):
            text, rows, _ = self.service._queue_page(1)
            self.assertEqual([row["id"] for row in rows], [own["id"]])
            self.assertNotIn(foreign["file_name"], text)
            from test_telethon_compat import callback_data
            self.assertNotIn(b"vps_resources", [callback_data(b) for r in self.service._user_home_buttons() for b in r])
            self.assertIn("❌ 0", self.service._format_status())
            for command in ("/task", "/cancel", "/retry", "/stream", "/watch", "/confirm", "/restart", "/recover"):
                await self.service._handle_command(event, f"{command} {foreign['id']}")
                self.assertEqual(event.reply.call_args.args[0], "没有找到这个任务。")
            for command in ("/pause", "/resume", "/doctor", "/orphans clean"):
                await self.service._handle_command(event, command)
                self.assertIn("仅限管理员", event.reply.call_args.args[0])
            for data in (b"control:pause", b"vps_resources", b"refresh:vps_resources", b"menu:doctor", b"menu:orphans"):
                event.data = data
                await self.service._on_callback(event)
                self.assertIn("仅限管理员", event.edit.call_args.args[0])
            for action in ("view", "retry", "stream", "cancel", "restart", "recover"):
                event.data = f"task:{action}:{foreign['id']}".encode()
                await self.service._on_callback(event)
                self.assertEqual(event.edit.call_args.args[0], "没有找到这个任务。")
        self.assertEqual(self.db.get(foreign["id"]), foreign)
        self.assertFalse(self.db.is_paused())

    async def test_retry_all_and_weekly_counts_filter_before_sql_limit(self):
        self.grant()
        for number in range(105):
            self.task(self.admin, message=number + 1, state="upload_failed_retained")
        task = self.task(123, state="download_failed")
        event = SimpleNamespace(reply=AsyncMock())
        with user_scope(123):
            self.assertEqual(self.db.weekly_failed_count(sender_id=123), 1)
            self.assertEqual(self.db.counts(sender_id=123), {"download_failed": 1})
            await self.service._command_retry(event, ["/retry", "all"])
        self.assertEqual(self.db.get(task["id"])["state"], "queued")
        self.assertEqual(self.db.counts(sender_id=self.admin)["upload_failed_retained"], 105)

    async def test_dedup_per_user_and_personal_notifications_no_context_leak(self):
        self.grant()
        first, second = self.task(123), self.task(self.admin)
        self.assertNotEqual(first["id"], second["id"])
        async def emit(owner):
            with user_scope(owner):
                await asyncio.sleep(0)
                await self.service._notify(f"owner-{owner}")
                self.assertEqual(current_user(self.admin), owner)
        await asyncio.gather(emit(123), emit(self.admin))
        self.assertEqual({call.args for call in self.service.client.send_message.call_args_list},
                         {(123, "owner-123"), (self.admin, f"owner-{self.admin}")})
        self.assertEqual(current_user(self.admin), self.admin)
        @task_actor
        async def worker(service, task_id):
            await service._notify("finished")
        await worker(self.service, first["id"])
        self.assertEqual(self.service.client.send_message.call_args.args, (123, "finished"))
        self.grant("disable")
        self.service.client.send_message.reset_mock()
        await worker(self.service, first["id"])
        self.service.client.send_message.assert_not_called()
        event = SimpleNamespace(sender_id=123, chat_id=123, answer=AsyncMock())
        await self.service._on_callback(event)
        self.assertTrue(event.answer.call_args.kwargs["alert"])

    async def test_recovery_confirmation_bound_to_actor(self):
        self.grant()
        task = self.task(123, state="cancelled")
        event = SimpleNamespace(reply=AsyncMock(), edit=AsyncMock())
        with user_scope(123):
            await self.service._offer_recovery(event, task["id"])
        plan = self.service._recovery_confirmations[task["id"]]
        with user_scope(self.admin):
            await self.service._confirm_recovery(event, task["id"], plan["token"])
        self.assertEqual(self.db.get(task["id"])["state"], "cancelled")
        with user_scope(123):
            await self.service._confirm_recovery(event, task["id"], plan["token"])
        self.assertEqual(self.db.get(task["id"])["state"], "queued")

    def test_consistent_backup_includes_grants_and_existing_history(self):
        self.grant()
        task = self.task(123, state="cancelled")
        destination = Path(self.temp.name) / "copy.db"
        backup_database(self.path, destination)
        restored = TaskDB(destination)
        try:
            self.assertEqual(restored.family_users(self.admin), self.db.family_users(self.admin))
            self.assertEqual(restored.get(task["id"]), task)
        finally:
            restored.close()

    async def test_family_media_ingestion_is_private_and_dedup_remains_user_scoped(self):
        self.grant()
        for sender in (self.admin, 123, 123):
            media = SimpleNamespace(id=1, grouped_id=None, document=SimpleNamespace(id=777), media=True,
                                    file=SimpleNamespace(name="movie.mp4", size=10, ext=".mp4", mime_type="video/mp4"))
            event = SimpleNamespace(sender_id=sender, chat_id=sender, is_private=True,
                                    message=media, raw_text="家庭电影", reply=AsyncMock())
            await self.service._on_message(event)
        tasks = self.db.list_recent()
        self.assertEqual(len(tasks), 2)
        self.assertEqual({t["sender_id"] for t in tasks}, {self.admin, 123})
        self.assertEqual({t["chat_id"] for t in tasks}, {self.admin, 123})

    async def test_revoked_member_watch_stops_without_editing_message(self):
        self.grant()
        task = self.task(123)
        message = SimpleNamespace(edit=AsyncMock())
        self.service._watch_messages = {task["id"]: message}
        self.service._stop = asyncio.Event()
        self.grant("disable")
        async def once(_seconds):
            self.service._stop.set()
        from unittest.mock import patch
        with patch("tg2cloud.telegram.handlers.asyncio.sleep", side_effect=once):
            await self.service._watch_loop()
        self.assertEqual(self.service._watch_messages, {})
        message.edit.assert_not_called()
