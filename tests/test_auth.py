from types import SimpleNamespace

from tgclaude.bot import _is_authorized


def test_authorized_owner():
    assert _is_authorized(SimpleNamespace(id=42), 42) is True


def test_rejects_other_user():
    assert _is_authorized(SimpleNamespace(id=7), 42) is False


def test_rejects_none_user():
    # пост из привязанного канала / анонимный админ → from_user is None → отказ
    assert _is_authorized(None, 42) is False
