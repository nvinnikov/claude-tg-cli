from pathlib import Path

from tgclaude.store import SessionRow, Store


def test_ensure_creates_row_with_default_cwd(tmp_path: Path):
    store = Store(tmp_path / "s.db")

    row = store.ensure(thread_id=7, default_cwd="/tmp")

    assert row == SessionRow(thread_id=7, cwd="/tmp", session_id=None, progress_msg_id=None)
    assert store.get(7) == row


def test_ensure_is_idempotent_and_keeps_existing_cwd(tmp_path: Path):
    store = Store(tmp_path / "s.db")
    store.ensure(thread_id=7, default_cwd="/tmp")
    store.set_cwd(7, "/var")

    row = store.ensure(thread_id=7, default_cwd="/tmp")

    assert row.cwd == "/var"


def test_get_returns_none_for_unknown_thread(tmp_path: Path):
    store = Store(tmp_path / "s.db")

    assert store.get(999) is None


def test_set_session_id_and_clear_session(tmp_path: Path):
    store = Store(tmp_path / "s.db")
    store.ensure(thread_id=7, default_cwd="/tmp")

    store.set_session_id(7, "sess-abc")
    assert store.get(7).session_id == "sess-abc"

    store.clear_session(7)
    assert store.get(7).session_id is None
    assert store.get(7).cwd == "/tmp"


def test_state_survives_reopen(tmp_path: Path):
    db = tmp_path / "s.db"
    store = Store(db)
    store.ensure(thread_id=7, default_cwd="/tmp")
    store.set_session_id(7, "sess-abc")

    reopened = Store(db)

    assert reopened.get(7).session_id == "sess-abc"


def test_all_returns_every_row(tmp_path: Path):
    store = Store(tmp_path / "s.db")
    store.ensure(thread_id=1, default_cwd="/a")
    store.ensure(thread_id=2, default_cwd="/b")

    assert {r.thread_id for r in store.all()} == {1, 2}
