from collections.abc import AsyncIterator
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from tgclaude.rules import describe

# Инструменты только на чтение разрешаем статически — они не доходят до can_use_tool.
# Bash / Write / Edit сюда добавлять НЕЛЬЗЯ: это отключит контроль прав.
ALLOWED_TOOLS = ["Read", "Grep", "Glob"]


@dataclass(frozen=True)
class ToolEvent:
    description: str


@dataclass(frozen=True)
class TextEvent:
    text: str


@dataclass(frozen=True)
class DoneEvent:
    session_id: str
    result: str | None
    is_error: bool
    duration_ms: int


Event = ToolEvent | TextEvent | DoneEvent


def translate(message: object) -> list[Event]:
    """Переводит сообщение SDK в события для чата. Неизвестные типы игнорируются."""
    if isinstance(message, AssistantMessage):
        events: list[Event] = []
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                events.append(ToolEvent(description=describe(block.name, block.input)))
            elif isinstance(block, TextBlock) and block.text.strip():
                events.append(TextEvent(text=block.text))
        return events

    if isinstance(message, ResultMessage):
        return [
            DoneEvent(
                session_id=message.session_id,
                result=message.result,
                is_error=message.is_error,
                duration_ms=message.duration_ms,
            )
        ]

    return []


class Runner:
    """Одна сессия Claude Code. Живёт столько же, сколько topic в Telegram."""

    def __init__(self, cwd: str, session_id: str | None, can_use_tool) -> None:
        self._options = ClaudeAgentOptions(
            cwd=cwd,
            resume=session_id,
            can_use_tool=can_use_tool,
            allowed_tools=ALLOWED_TOOLS,
            permission_mode="default",
        )
        self._client: ClaudeSDKClient | None = None

    async def _ensure_client(self) -> ClaudeSDKClient:
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options)
            await self._client.connect()
        return self._client

    async def run(self, prompt: str) -> AsyncIterator[Event]:
        client = await self._ensure_client()
        try:
            await client.query(prompt)
            async for message in client.receive_response():
                for event in translate(message):
                    yield event
        except Exception:
            # После сбоя клиент остаётся нерабочим, и все следующие прогоны
            # падали бы с "Not connected". Сбрасываем — следующий вызов
            # подключится заново. Ловим Exception, а не BaseException, чтобы
            # не трогать клиент при отмене задачи или закрытии генератора.
            await self._drop_client()
            raise

    async def _drop_client(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass  # клиент уже мёртв — важно лишь снять кэш

    async def stop(self) -> None:
        """Только сигналит interrupt. Дренаж делает единственный потребитель — цикл run(),
        который получит терминальный ResultMessage и сам завершится. Второй потребитель
        receive_response() здесь привёл бы к гонке за один поток сообщений."""
        if self._client is not None:
            await self._client.interrupt()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
