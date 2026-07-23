from collections.abc import Callable
from pathlib import Path

from tgclaude.config import Config
from tgclaude.store import Store


class SessionManager:
    """Держит по одному Runner на topic и синхронизирует состояние с хранилищем."""

    def __init__(self, store: Store, config: Config, runner_factory: Callable) -> None:
        self.store = store
        self.config = config
        self._factory = runner_factory
        self._runners: dict[int, object] = {}
        self._busy: set[int] = set()
        self._interrupted: set[int] = set()

    def get_or_create(self, thread_id: int):
        if thread_id not in self._runners:
            row = self.store.ensure(thread_id, str(self.config.default_cwd))
            self._runners[thread_id] = self._factory(row.cwd, row.session_id)
        return self._runners[thread_id]

    def remember_session(self, thread_id: int, session_id: str) -> None:
        self.store.set_session_id(thread_id, session_id)

    async def reset(self, thread_id: int) -> None:
        runner = self._runners.pop(thread_id, None)
        if runner is not None:
            await runner.close()
        self.store.clear_session(thread_id)

    async def set_cwd(self, thread_id: int, path: str) -> str:
        target = Path(path).expanduser()
        if not target.is_dir():
            raise ValueError(f"каталог не найден: {target}")

        runner = self._runners.pop(thread_id, None)
        if runner is not None:
            await runner.close()

        self.store.ensure(thread_id, str(self.config.default_cwd))
        self.store.set_cwd(thread_id, str(target))
        # Сессии CLI привязаны к проектному каталогу: возобновить сессию из
        # старого cwd в новом нельзя (ProcessError). Смена каталога = новая сессия.
        self.store.clear_session(thread_id)
        return str(target)

    def is_busy(self, thread_id: int) -> bool:
        return thread_id in self._busy

    def mark_busy(self, thread_id: int, busy: bool) -> None:
        if busy:
            self._busy.add(thread_id)
        else:
            self._busy.discard(thread_id)

    def mark_interrupted(self, thread_id: int) -> None:
        self._interrupted.add(thread_id)

    def was_interrupted(self, thread_id: int) -> bool:
        return thread_id in self._interrupted

    def clear_interrupted(self, thread_id: int) -> None:
        self._interrupted.discard(thread_id)
