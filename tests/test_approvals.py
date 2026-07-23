import asyncio
from pathlib import Path

import pytest

from tgclaude.approvals import ApprovalBroker, make_permission_callback
from tgclaude.rules import load_rules

RULES_TOML = """
allow = ["^git status\\\\b"]
deny = ["rm\\\\s+-rf"]
"""


@pytest.fixture
def rules(tmp_path: Path):
    p = tmp_path / "rules.toml"
    p.write_text(RULES_TOML)
    return load_rules(p)


async def test_request_returns_true_when_approved():
    asked: list[tuple[str, str]] = []

    async def ask(key: str, description: str) -> None:
        asked.append((key, description))

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    task = asyncio.create_task(broker.request("k1", "Bash: curl x"))
    await asyncio.sleep(0)

    assert asked == [("k1", "Bash: curl x")]
    broker.resolve("k1", True)

    assert await task is True


async def test_request_returns_false_when_denied():
    async def ask(key: str, description: str) -> None:
        pass

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    task = asyncio.create_task(broker.request("k1", "Bash: curl x"))
    await asyncio.sleep(0)
    broker.resolve("k1", False)

    assert await task is False


async def test_request_returns_false_on_timeout():
    async def ask(key: str, description: str) -> None:
        pass

    broker = ApprovalBroker(ask=ask, timeout_s=0)

    assert await broker.request("k1", "Bash: curl x") is False


async def test_resolve_of_unknown_key_is_noop():
    async def ask(key: str, description: str) -> None:
        pass

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    broker.resolve("nope", True)  # не должно бросать


async def test_pending_tracks_open_requests():
    async def ask(key: str, description: str) -> None:
        pass

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    task = asyncio.create_task(broker.request("k1", "x"))
    await asyncio.sleep(0)

    assert broker.pending() == ["k1"]

    broker.resolve("k1", True)
    await task

    assert broker.pending() == []


async def test_callback_allows_whitelisted_without_asking(rules):
    asked: list[str] = []

    async def ask(key: str, description: str) -> None:
        asked.append(key)

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    cb = make_permission_callback(rules, broker, on_denied=_noop)

    result = await cb("Bash", {"command": "git status"}, _ctx())

    assert result.behavior == "allow"
    assert asked == []


async def test_callback_denies_denylisted_and_notifies(rules):
    notified: list[str] = []

    async def on_denied(description: str) -> None:
        notified.append(description)

    async def ask(key: str, description: str) -> None:
        raise AssertionError("не должен спрашивать при deny")

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    cb = make_permission_callback(rules, broker, on_denied=on_denied)

    result = await cb("Bash", {"command": "rm -rf /tmp/x"}, _ctx())

    assert result.behavior == "deny"
    assert notified == ["Bash: rm -rf /tmp/x"]


async def test_callback_asks_for_unknown_command(rules):
    async def ask(key: str, description: str) -> None:
        asyncio.get_running_loop().call_soon(broker.resolve, key, True)

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    cb = make_permission_callback(rules, broker, on_denied=_noop)

    result = await cb("Bash", {"command": "curl https://x"}, _ctx())

    assert result.behavior == "allow"


async def test_callback_denies_when_user_rejects(rules):
    async def ask(key: str, description: str) -> None:
        asyncio.get_running_loop().call_soon(broker.resolve, key, False)

    broker = ApprovalBroker(ask=ask, timeout_s=5)
    cb = make_permission_callback(rules, broker, on_denied=_noop)

    result = await cb("Bash", {"command": "curl https://x"}, _ctx())

    assert result.behavior == "deny"


async def _noop(description: str) -> None:
    pass


def _ctx():
    from claude_agent_sdk.types import ToolPermissionContext

    return ToolPermissionContext(signal=None, suggestions=[], tool_use_id="tu_1")
