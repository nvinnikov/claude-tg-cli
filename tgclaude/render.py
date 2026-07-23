import html
import re

_MAX_STEPS_SHOWN = 12
_FENCE = re.compile(r"```[a-zA-Z0-9_-]*\n(.*?)```", re.DOTALL)
_INLINE = re.compile(r"`([^`\n]+)`")
_STATUS_ICON = {"ok": "✅", "stopped": "⛔ прервано,", "error": "❌ ошибка,"}


def _plural_steps(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "шаг"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "шага"
    return "шагов"


def progress_text(
    steps: list[str], *, finished: bool = False, elapsed_s: float = 0.0, status: str = "ok"
) -> str:
    if finished:
        icon = _STATUS_ICON.get(status, _STATUS_ICON["ok"])
        return f"{icon} {len(steps)} {_plural_steps(len(steps))}, {int(elapsed_s)}s"

    shown = steps[-_MAX_STEPS_SHOWN:]
    lines = ["⏳ Работаю…"] + [f"▸ {s}" for s in shown]
    return "\n".join(lines)


def to_html(text: str) -> str:
    """Markdown → подмножество HTML, которое понимает Telegram."""
    text = text.replace("\x00", "")
    placeholders: list[str] = []

    def stash(rendered: str) -> str:
        placeholders.append(rendered)
        return f"\x00{len(placeholders) - 1}\x00"

    text = _FENCE.sub(lambda m: stash(f"<pre>{html.escape(m.group(1).strip())}</pre>"), text)
    text = _INLINE.sub(lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = html.escape(text)

    for i, rendered in enumerate(placeholders):
        text = text.replace(f"\x00{i}\x00", rendered)
    return text


def chunks(text: str, limit: int = 3800) -> list[str]:
    """Режет текст под лимит Telegram, по возможности по границе строки."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut])
        rest = rest[cut:]
        if rest.startswith("\n"):
            rest = rest[1:]
    if rest:
        parts.append(rest)
    return parts
