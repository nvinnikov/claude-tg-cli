from pathlib import Path

import pytest

from tgclaude.rules import Decision, describe, decide, load_rules

RULES_TOML = """
allow = ["^git (status|log)\\\\b", "^ls\\\\b"]
deny = ["rm\\\\s+-rf", "--context[= ]prod"]
"""


@pytest.fixture
def rules(tmp_path: Path):
    p = tmp_path / "rules.toml"
    p.write_text(RULES_TOML)
    return load_rules(p)


def test_read_only_tools_are_always_allowed(rules):
    assert decide("Read", {"file_path": "/etc/hosts"}, rules) is Decision.ALLOW
    assert decide("Grep", {"pattern": "x"}, rules) is Decision.ALLOW
    assert decide("Glob", {"pattern": "*.go"}, rules) is Decision.ALLOW


def test_whitelisted_bash_command_is_allowed(rules):
    assert decide("Bash", {"command": "git status"}, rules) is Decision.ALLOW


def test_unknown_bash_command_needs_confirmation(rules):
    assert decide("Bash", {"command": "curl https://example.com"}, rules) is Decision.ASK


def test_denylist_wins_over_allowlist(rules):
    # команда начинается с разрешённого ls, но содержит запрещённый фрагмент
    assert decide("Bash", {"command": "ls && rm -rf /tmp/x"}, rules) is Decision.DENY


def test_denylist_applies_to_prod_context(rules):
    assert decide("Bash", {"command": "kubectl --context prod delete pod x"}, rules) is Decision.DENY


def test_write_and_edit_require_confirmation(rules):
    assert decide("Write", {"file_path": "/tmp/a.txt"}, rules) is Decision.ASK
    assert decide("Edit", {"file_path": "/tmp/a.txt"}, rules) is Decision.ASK


def test_unknown_tool_requires_confirmation(rules):
    assert decide("SomeNewTool", {}, rules) is Decision.ASK


def test_bash_without_command_field_is_denied(rules):
    assert decide("Bash", {}, rules) is Decision.DENY


def test_describe_renders_bash_command(rules):
    assert describe("Bash", {"command": "git status"}) == "Bash: git status"


def test_describe_renders_file_tools(rules):
    assert describe("Write", {"file_path": "/tmp/a.txt"}) == "Write: /tmp/a.txt"


def test_describe_truncates_long_input(rules):
    long_cmd = "echo " + "x" * 300
    out = describe("Bash", {"command": long_cmd})
    assert len(out) <= 130
    assert out.endswith("…")
