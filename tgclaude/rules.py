import enum
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

READ_ONLY_TOOLS = frozenset({"Read", "Grep", "Glob", "NotebookRead", "TodoWrite"})
FILE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})
_MAX_DESCRIBE = 128


class Decision(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True)
class Rules:
    allow: tuple[re.Pattern, ...]
    deny: tuple[re.Pattern, ...]


def load_rules(path: Path) -> Rules:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return Rules(
        allow=tuple(re.compile(p) for p in raw.get("allow", [])),
        deny=tuple(re.compile(p) for p in raw.get("deny", [])),
    )


def describe(tool_name: str, input_data: dict) -> str:
    """Однострочное описание вызова инструмента для показа в чате."""
    if tool_name == "Bash":
        detail = input_data.get("command", "")
    elif tool_name in FILE_TOOLS:
        detail = input_data.get("file_path", "")
    else:
        detail = input_data.get("pattern") or input_data.get("file_path") or ""

    line = f"{tool_name}: {detail}".strip().rstrip(":")
    if len(line) > _MAX_DESCRIBE:
        line = line[: _MAX_DESCRIBE - 1] + "…"
    return line


def decide(tool_name: str, input_data: dict, rules: Rules) -> Decision:
    """Deny-лист → whitelist → запрос подтверждения."""
    if tool_name == "Bash":
        command = input_data.get("command")
        if not command:
            return Decision.DENY
        if any(p.search(command) for p in rules.deny):
            return Decision.DENY
        if any(p.search(command) for p in rules.allow):
            return Decision.ALLOW
        return Decision.ASK

    target = str(input_data.get("file_path", ""))
    if target and any(p.search(target) for p in rules.deny):
        return Decision.DENY

    if tool_name in READ_ONLY_TOOLS:
        return Decision.ALLOW

    return Decision.ASK
