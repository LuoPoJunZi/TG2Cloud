"""Async-local task ownership, never shared mutable Telegram request state."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_actor = ContextVar("tg2cloud_actor", default=None)


def current_user(admin_id: int) -> int:
    value = _actor.get()
    return admin_id if value is None else value


@contextmanager
def user_scope(user_id: int):
    token = _actor.set(user_id)
    try:
        yield
    finally:
        _actor.reset(token)


def user_event(handler):
    @wraps(handler)
    async def wrapped(self, event, *args, **kwargs):
        # The decorated handler still validates authorization and private chat.
        with user_scope(getattr(event, "sender_id", None)):
            return await handler(self, event, *args, **kwargs)
    return wrapped


def task_actor(handler):
    @wraps(handler)
    async def wrapped(self, task_id, *args, **kwargs):
        task = self.db.get(task_id)
        if task is None:
            return
        with user_scope(task["sender_id"]):
            return await handler(self, task_id, *args, **kwargs)
    return wrapped
