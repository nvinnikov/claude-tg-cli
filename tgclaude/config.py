import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_id: int
    chat_id: int
    default_cwd: Path
    approval_timeout_s: int
    db_path: Path


def load_config(path: Path) -> Config:
    """Читает config.toml. Относительные пути разрешаются рядом с конфигом."""
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    base = path.parent
    default_cwd = Path(raw["default_cwd"]).expanduser()
    if not default_cwd.is_dir():
        raise ValueError(f"default_cwd does not exist: {default_cwd}")

    db_path = Path(raw.get("db_path", "sessions.db")).expanduser()
    if not db_path.is_absolute():
        db_path = base / db_path

    return Config(
        bot_token=raw["bot_token"],
        allowed_user_id=raw["allowed_user_id"],
        chat_id=raw["chat_id"],
        default_cwd=default_cwd,
        approval_timeout_s=raw.get("approval_timeout_s", 300),
        db_path=db_path,
    )
