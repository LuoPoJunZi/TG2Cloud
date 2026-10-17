"""Existing schema v1 migration; caller retains its connection and RLock."""
import sqlite3

from tg2cloud.domain.states import FAILED_STATES

SCHEMA_VERSION = 1

def migrate(connection: sqlite3.Connection, columns: set[str]) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        for name, declaration in (
            ("remote_temp_path", "TEXT"),
            ("remote_final_path", "TEXT"),
            ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
            ("failure_kind", "TEXT"),
            ("verification_method", "TEXT"),
            ("verified_at", "REAL"),
            ("original_file_name", "TEXT"),
        ):
            if name not in columns:
                connection.execute(f"ALTER TABLE tasks ADD COLUMN {name} {declaration}")
        connection.execute(
            """UPDATE tasks SET remote_temp_path=remote_path
                WHERE remote_temp_path IS NULL AND remote_path LIKE '.uploading-%'"""
        )
        connection.execute(
            """UPDATE tasks SET remote_final_path=remote_path
                WHERE remote_final_path IS NULL AND remote_path IS NOT NULL
                AND remote_path NOT LIKE '.uploading-%'"""
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS service_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
                old_state TEXT, new_state TEXT NOT NULL, happened_at REAL NOT NULL)"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id, id)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(sender_id, id)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS task_recoveries (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
                happened_at REAL NOT NULL, operation TEXT NOT NULL, previous TEXT NOT NULL)"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS retained_objects (
                path TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id))"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_recoveries_task ON task_recoveries(task_id, id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_events_state_time ON task_events(new_state, happened_at, task_id)")
        # Preserve the timestamp of pre-event-schema failures before recovery
        # or progress updates can change updated_at. Never delete old tasks.
        for state in FAILED_STATES:
            connection.execute(
                """INSERT INTO task_events(task_id,old_state,new_state,happened_at)
                    SELECT t.id,NULL,t.state,t.updated_at FROM tasks t WHERE t.state=?
                    AND NOT EXISTS (SELECT 1 FROM task_events e WHERE e.task_id=t.id)""", (state,),
            )
        connection.execute(
            """CREATE TRIGGER IF NOT EXISTS task_state_event AFTER UPDATE OF state ON tasks
                WHEN OLD.state != NEW.state BEGIN
                    INSERT INTO task_events(task_id,old_state,new_state,happened_at)
                    VALUES(NEW.id,OLD.state,NEW.state,NEW.updated_at);
                END"""
        )
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
