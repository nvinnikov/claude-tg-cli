from pathlib import Path

import pytest

from tgclaude.config import Config, load_config


def test_load_config_reads_all_fields(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'bot_token = "abc"\n'
        "allowed_user_id = 42\n"
        "chat_id = -100500\n"
        f'default_cwd = "{tmp_path}"\n'
        "approval_timeout_s = 60\n"
        'db_path = "s.db"\n'
    )

    cfg = load_config(cfg_file)

    assert cfg == Config(
        bot_token="abc",
        allowed_user_id=42,
        chat_id=-100500,
        default_cwd=tmp_path,
        approval_timeout_s=60,
        db_path=tmp_path / "s.db",
    )


def test_db_path_is_resolved_next_to_config(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'bot_token = "abc"\n'
        "allowed_user_id = 1\n"
        "chat_id = 2\n"
        f'default_cwd = "{tmp_path}"\n'
        'db_path = "sessions.db"\n'
    )

    cfg = load_config(cfg_file)

    assert cfg.db_path == tmp_path / "sessions.db"
    assert cfg.approval_timeout_s == 300


def test_missing_required_field_raises(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('bot_token = "abc"\n')

    with pytest.raises(KeyError):
        load_config(cfg_file)


def test_nonexistent_default_cwd_raises(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'bot_token = "abc"\n'
        "allowed_user_id = 1\n"
        "chat_id = 2\n"
        'default_cwd = "/no/such/dir"\n'
    )

    with pytest.raises(ValueError, match="default_cwd"):
        load_config(cfg_file)
