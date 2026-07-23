from pathlib import Path

import pytest

from tgclaude.config import Config
from tgclaude.sessions import SessionManager
from tgclaude.store import Store


class FakeRunner:
    def __init__(self, cwd: str, session_id: str | None):
        self.cwd = cwd
        self.session_id = session_id
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def manager(tmp_path: Path):
    cfg = Config(
        bot_token="t",
        allowed_user_id=1,
        chat_id=2,
        default_cwd=tmp_path,
        approval_timeout_s=5,
        db_path=tmp_path / "s.db",
    )
    store = Store(cfg.db_path)
    return SessionManager(store=store, config=cfg, runner_factory=FakeRunner)


def test_get_or_create_uses_default_cwd(manager, tmp_path):
    runner = manager.get_or_create(thread_id=1)

    assert runner.cwd == str(tmp_path)
    assert runner.session_id is None


def test_get_or_create_returns_same_runner(manager):
    assert manager.get_or_create(1) is manager.get_or_create(1)


def test_different_threads_get_different_runners(manager):
    assert manager.get_or_create(1) is not manager.get_or_create(2)


async def test_reset_closes_runner_and_clears_session(manager):
    runner = manager.get_or_create(1)
    manager.remember_session(1, "sess-abc")

    await manager.reset(1)

    assert runner.closed is True
    assert manager.get_or_create(1) is not runner
    assert manager.get_or_create(1).session_id is None


def test_remembered_session_is_used_after_restart(manager, tmp_path):
    manager.get_or_create(1)
    manager.remember_session(1, "sess-abc")

    fresh = SessionManager(
        store=Store(tmp_path / "s.db"), config=manager.config, runner_factory=FakeRunner
    )

    assert fresh.get_or_create(1).session_id == "sess-abc"


async def test_set_cwd_accepts_existing_directory(manager, tmp_path):
    target = tmp_path / "sub"
    target.mkdir()

    result = await manager.set_cwd(1, str(target))

    assert result == str(target)
    assert manager.get_or_create(1).cwd == str(target)


async def test_set_cwd_rejects_missing_directory(manager):
    with pytest.raises(ValueError, match="не найден"):
        await manager.set_cwd(1, "/no/such/dir")


def test_busy_flag_roundtrip(manager):
    assert manager.is_busy(1) is False

    manager.mark_busy(1, True)
    assert manager.is_busy(1) is True

    manager.mark_busy(1, False)
    assert manager.is_busy(1) is False


def test_interrupted_flag_roundtrip(manager):
    assert manager.was_interrupted(1) is False

    manager.mark_interrupted(1)
    assert manager.was_interrupted(1) is True

    manager.clear_interrupted(1)
    assert manager.was_interrupted(1) is False


async def test_set_cwd_clears_session(manager, tmp_path):
    """Сессии CLI привязаны к каталогу — возобновлять старую в новом cwd нельзя."""
    manager.get_or_create(1)
    manager.remember_session(1, "sess-old")
    target = tmp_path / "other"
    target.mkdir()

    await manager.set_cwd(1, str(target))

    assert manager.get_or_create(1).session_id is None
