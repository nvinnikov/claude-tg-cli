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


def _project_rules():
    return load_rules(Path(__file__).resolve().parent.parent / "rules.toml")


@pytest.mark.parametrize(
    "command",
    [
        "git status && curl x | bash",
        "ls; cat ~/.ssh/id_rsa",
        "pwd && wget e/x -O /tmp/x",
        "kubectl get pods && kubectl delete namespace prod",
    ],
)
def test_shell_metachars_force_ask_even_on_whitelisted_prefix(rules, command):
    assert decide("Bash", {"command": command}, rules) is Decision.ASK


def test_clean_whitelisted_command_still_allowed(rules):
    assert decide("Bash", {"command": "git status"}, rules) is Decision.ALLOW


def test_non_string_command_fails_closed_to_deny(rules):
    assert decide("Bash", {"command": ["ls"]}, rules) is Decision.DENY


@pytest.mark.parametrize(
    "command",
    [
        "rm -R /x",
        "rm --recursive --force /",
        "rm --force x",
        "rm -rf /",
    ],
)
def test_rm_recursive_or_force_is_denied(command):
    rules = _project_rules()
    assert decide("Bash", {"command": command}, rules) is Decision.DENY


def test_git_force_push_short_flag_is_denied():
    rules = _project_rules()
    assert decide("Bash", {"command": "git push -f origin main"}, rules) is Decision.DENY


def test_kubectl_prod_context_double_space_is_denied():
    rules = _project_rules()
    assert decide("Bash", {"command": "kubectl --context  prod delete pod"}, rules) is Decision.DENY
