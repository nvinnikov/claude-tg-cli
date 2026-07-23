import asyncio
import uuid
from collections.abc import Awaitable, Callable

from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from tgclaude.rules import Decision, Rules, decide, describe

AskFn = Callable[[str, str], Awaitable[None]]
NotifyFn = Callable[[str], Awaitable[None]]


class ApprovalBroker:
    """Ждёт решения пользователя по конкретному вызову инструмента."""

    def __init__(self, ask: AskFn, timeout_s: int) -> None:
        self._ask = ask
        self._timeout_s = timeout_s
        self._waiters: dict[str, asyncio.Future[bool]] = {}

    async def request(self, key: str, description: str) -> bool:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._waiters[key] = fut
        try:
            await self._ask(key, description)
            return await asyncio.wait_for(fut, timeout=self._timeout_s)
        except (TimeoutError, asyncio.TimeoutError):
            return False
        finally:
            self._waiters.pop(key, None)

    def resolve(self, key: str, approved: bool) -> None:
        fut = self._waiters.get(key)
        if fut is not None and not fut.done():
            fut.set_result(approved)

    def pending(self) -> list[str]:
        return list(self._waiters)


def make_permission_callback(rules: Rules, broker: ApprovalBroker, on_denied: NotifyFn):
    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        description = describe(tool_name, input_data)
        decision = decide(tool_name, input_data, rules)

        if decision is Decision.ALLOW:
            return PermissionResultAllow(updated_input=input_data)

        if decision is Decision.DENY:
            await on_denied(description)
            return PermissionResultDeny(message="Запрещено правилами", interrupt=False)

        key = context.tool_use_id or uuid.uuid4().hex
        if await broker.request(key, description):
            return PermissionResultAllow(updated_input=input_data)
        return PermissionResultDeny(message="Пользователь не подтвердил", interrupt=False)

    return can_use_tool
