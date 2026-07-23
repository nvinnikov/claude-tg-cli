import pytest

from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from tgclaude.runner import DoneEvent, Runner, TextEvent, ToolEvent, translate


def test_translate_tool_use_block():
    msg = AssistantMessage(
        content=[ToolUseBlock(id="tu_1", name="Bash", input={"command": "git status"})],
        model="claude-opus-4-8",
    )

    assert translate(msg) == [ToolEvent(description="Bash: git status")]


def test_translate_text_block():
    msg = AssistantMessage(content=[TextBlock(text="готово")], model="claude-opus-4-8")

    assert translate(msg) == [TextEvent(text="готово")]


def test_translate_mixed_blocks_preserves_order():
    msg = AssistantMessage(
        content=[
            TextBlock(text="сейчас проверю"),
            ToolUseBlock(id="tu_1", name="Bash", input={"command": "ls"}),
        ],
        model="claude-opus-4-8",
    )

    assert translate(msg) == [
        TextEvent(text="сейчас проверю"),
        ToolEvent(description="Bash: ls"),
    ]


def test_translate_result_message():
    msg = ResultMessage(
        subtype="success",
        duration_ms=1234,
        duration_api_ms=1000,
        is_error=False,
        num_turns=2,
        session_id="sess-abc",
        result="итог",
    )

    assert translate(msg) == [
        DoneEvent(session_id="sess-abc", result="итог", is_error=False, duration_ms=1234)
    ]


def test_translate_error_result_message():
    msg = ResultMessage(
        subtype="error_during_execution",
        duration_ms=10,
        duration_api_ms=5,
        is_error=True,
        num_turns=1,
        session_id="sess-abc",
        result=None,
    )

    events = translate(msg)

    assert events[0].is_error is True
    assert events[0].result is None


def test_translate_ignores_unknown_message_types():
    class Whatever:
        pass

    assert translate(Whatever()) == []


def test_translate_ignores_empty_text():
    msg = AssistantMessage(content=[TextBlock(text="   ")], model="claude-opus-4-8")

    assert translate(msg) == []


async def test_stop_only_interrupts_without_draining():
    class FakeClient:
        def __init__(self) -> None:
            self.interrupted = False

        async def interrupt(self) -> None:
            self.interrupted = True

        def receive_response(self):
            raise AssertionError("stop() не должен читать receive_response()")

    runner = Runner(cwd="/tmp", session_id=None, can_use_tool=None)
    runner._client = FakeClient()

    await runner.stop()

    assert runner._client.interrupted is True


async def test_stop_is_noop_without_client():
    runner = Runner(cwd="/tmp", session_id=None, can_use_tool=None)

    await runner.stop()  # клиента ещё нет — не должно падать


async def test_run_drops_client_after_failure():
    """Сбой не должен навсегда ломать сессию: клиент сбрасывается,
    следующий прогон подключается заново (иначе — вечный 'Not connected')."""

    class FailingClient:
        def __init__(self) -> None:
            self.disconnected = False

        async def query(self, prompt: str, session_id: str = "default") -> None:
            raise RuntimeError("boom")

        def receive_response(self):  # pragma: no cover - до него не доходит
            raise AssertionError("не должно вызываться")

        async def disconnect(self) -> None:
            self.disconnected = True

    runner = Runner(cwd="/tmp", session_id=None, can_use_tool=None)
    client = FailingClient()
    runner._client = client

    with pytest.raises(RuntimeError):
        async for _ in runner.run("hi"):
            pass

    assert runner._client is None
    assert client.disconnected is True
