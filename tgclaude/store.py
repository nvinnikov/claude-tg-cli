import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    thread_id       INTEGER PRIMARY KEY,
    cwd             TEXT    NOT NULL,
    session_id      TEXT,
    progress_msg_id INTEGER
)
"""


@dataclass
class SessionRow:
    thread_id: int
    cwd: str
    session_id: str | None = None
    progress_msg_id: int | None = None


class Store:
    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, thread_id: int) -> SessionRow | None:
        cur = self._conn.execute(
            "SELECT thread_id, cwd, session_id, progress_msg_id FROM sessions WHERE thread_id = ?",
            (thread_id,),
        )
        row = cur.fetchone()
        return SessionRow(**dict(row)) if row else None

    def ensure(self, thread_id: int, default_cwd: str) -> SessionRow:
        self._conn.execute(
            "INSERT OR IGNORE INTO sessions (thread_id, cwd) VALUES (?, ?)",
            (thread_id, default_cwd),
        )
        self._conn.commit()
        row = self.get(thread_id)
        assert row is not None
        return row

    def set_session_id(self, thread_id: int, session_id: str) -> None:
        self._update(thread_id, "session_id", session_id)

    def set_cwd(self, thread_id: int, cwd: str) -> None:
        self._update(thread_id, "cwd", cwd)

    def set_progress_msg_id(self, thread_id: int, msg_id: int | None) -> None:
        self._update(thread_id, "progress_msg_id", msg_id)

    def clear_session(self, thread_id: int) -> None:
        self._update(thread_id, "session_id", None)

    def all(self) -> list[SessionRow]:
        cur = self._conn.execute(
            "SELECT thread_id, cwd, session_id, progress_msg_id FROM sessions"
        )
        return [SessionRow(**dict(r)) for r in cur.fetchall()]

    def _update(self, thread_id: int, column: str, value: object) -> None:
        # column подставляется только из кода этого модуля, не из внешнего ввода
        self._conn.execute(
            f"UPDATE sessions SET {column} = ? WHERE thread_id = ?", (value, thread_id)
        )
        self._conn.commit()
