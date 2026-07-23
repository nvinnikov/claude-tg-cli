import asyncio
import logging
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from tgclaude.approvals import ApprovalBroker, make_permission_callback
from tgclaude.config import load_config
from tgclaude.render import chunks, progress_text, to_html
from tgclaude.rules import load_rules
from tgclaude.runner import DoneEvent, Runner, TextEvent, ToolEvent
from tgclaude.sessions import SessionManager
from tgclaude.store import Store

log = logging.getLogger("tgclaude")
PROGRESS_EDIT_INTERVAL_S = 3.0


def _is_authorized(from_user, allowed_user_id: int) -> bool:
    """Пропускаем только владельца. from_user=None (канал/анонимный админ) → отказ (fail-closed)."""
    return from_user is not None and from_user.id == allowed_user_id


def _approval_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Разрешить", callback_data=f"ok:{key}"),
                InlineKeyboardButton(text="Запретить", callback_data=f"no:{key}"),
            ]
        ]
    )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    root = Path(__file__).resolve().parent.parent
    config = load_config(root / "config.toml")
    rules = load_rules(root / "rules.toml")

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    store = Store(config.db_path)
    brokers: dict[int, ApprovalBroker] = {}

    def make_runner_factory(thread_id: int):
        async def ask(key: str, description: str) -> None:
            await bot.send_message(
                config.chat_id,
                f"❓ Подтверди:\n<code>{to_html(description)}</code>",
                message_thread_id=thread_id,
                parse_mode="HTML",
                reply_markup=_approval_keyboard(key),
            )

        async def on_denied(description: str) -> None:
            await bot.send_message(
                config.chat_id,
                f"🚫 Заблокировано правилом:\n<code>{to_html(description)}</code>",
                message_thread_id=thread_id,
                parse_mode="HTML",
            )

        # Брокер создаём только один раз на thread — иначе повторный вызов
        # (например, из cmd_stop) пересобрал бы его посреди активного approval
        # и осиротил бы pending future: тап по кнопке резолвил бы уже мёртвый брокер.
        broker = brokers.get(thread_id)
        if broker is None:
            broker = ApprovalBroker(ask=ask, timeout_s=config.approval_timeout_s)
            brokers[thread_id] = broker
        callback = make_permission_callback(rules, broker, on_denied)

        def factory(cwd: str, session_id: str | None) -> Runner:
            return Runner(cwd=cwd, session_id=session_id, can_use_tool=callback)

        return factory

    class ThreadAwareManager(SessionManager):
        def get_or_create(self, thread_id: int):
            self._factory = make_runner_factory(thread_id)
            return super().get_or_create(thread_id)

    sessions = ThreadAwareManager(store=store, config=config, runner_factory=None)

    def thread_of(message: Message) -> int:
        return message.message_thread_id or 0

    @dp.message(lambda event: not _is_authorized(event.from_user, config.allowed_user_id))
    async def reject_strangers(message: Message) -> None:
        uid = message.from_user.id if message.from_user else None
        log.warning("dropped message from user_id=%s", uid)

    @dp.message(Command("new"))
    async def cmd_new(message: Message) -> None:
        await sessions.reset(thread_of(message))
        await message.reply("Сессия сброшена.")

    @dp.message(Command("pwd"))
    async def cmd_pwd(message: Message) -> None:
        row = store.ensure(thread_of(message), str(config.default_cwd))
        await message.reply(f"cwd: {row.cwd}\nsession: {row.session_id or '—'}")

    @dp.message(Command("cd"))
    async def cmd_cd(message: Message) -> None:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Использование: /cd <путь>")
            return
        try:
            new_cwd = await sessions.set_cwd(thread_of(message), parts[1])
        except ValueError as exc:
            await message.reply(str(exc))
            return
        await message.reply(f"cwd: {new_cwd}")

    @dp.message(Command("stop"))
    async def cmd_stop(message: Message) -> None:
        thread_id = thread_of(message)
        if not sessions.is_busy(thread_id):
            await message.reply("Нечего прерывать.")
            return
        sessions.mark_interrupted(thread_id)
        await sessions.get_or_create(thread_id).stop()
        await message.reply("Прерываю.")

    @dp.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        lines = [
            f"{r.thread_id}: {r.cwd} — {'занят' if sessions.is_busy(r.thread_id) else 'свободен'}"
            for r in store.all()
        ]
        await message.reply("\n".join(lines) or "Сессий нет.")

    @dp.callback_query(F.data.startswith(("ok:", "no:")))
    async def on_approval(query: CallbackQuery) -> None:
        if not _is_authorized(query.from_user, config.allowed_user_id):
            return
        if query.message is None:
            await query.answer()
            return
        verdict, _, key = query.data.partition(":")
        thread_id = query.message.message_thread_id or 0
        broker = brokers.get(thread_id)
        if broker is not None:
            broker.resolve(key, verdict == "ok")
        await query.answer("Разрешено" if verdict == "ok" else "Запрещено")
        await query.message.edit_reply_markup(reply_markup=None)

    @dp.message(F.text)
    async def on_prompt(message: Message) -> None:
        thread_id = thread_of(message)
        if sessions.is_busy(thread_id):
            await message.reply("Уже занят. /stop — прервать.")
            return

        runner = sessions.get_or_create(thread_id)
        sessions.mark_busy(thread_id, True)
        sessions.clear_interrupted(thread_id)
        started = time.monotonic()
        steps: list[str] = []
        texts: list[str] = []
        status = "ok"

        progress = await message.reply(progress_text(steps))
        last_edit = 0.0

        async def flush(force: bool = False) -> None:
            nonlocal last_edit
            now = time.monotonic()
            if not force and now - last_edit < PROGRESS_EDIT_INTERVAL_S:
                return
            last_edit = now
            try:
                await progress.edit_text(progress_text(steps))
            except Exception:  # редактирование тем же текстом даёт ошибку — она не важна
                pass

        try:
            async for event in runner.run(message.text):
                if isinstance(event, ToolEvent):
                    steps.append(event.description)
                    await flush()
                elif isinstance(event, TextEvent):
                    texts.append(event.text)
                elif isinstance(event, DoneEvent):
                    sessions.remember_session(thread_id, event.session_id)
                    if event.is_error:
                        status = "error"
                    if event.result:
                        texts.append(event.result)
        except Exception:
            log.exception("run failed in thread %s", thread_id)
            status = "error"
        finally:
            sessions.mark_busy(thread_id, False)

        if sessions.was_interrupted(thread_id):
            status = "stopped"

        elapsed = time.monotonic() - started
        await progress.edit_text(
            progress_text(steps, finished=True, elapsed_s=elapsed, status=status)
        )

        answer = texts[-1] if texts else "(пустой ответ)"
        for part in chunks(to_html(answer)):
            await message.answer(part, parse_mode="HTML")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
